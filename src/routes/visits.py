# routes/visits.py
"""
CRUD de visitas e relacionados.
- /visits (GET, POST)
- /visits/<id> (GET, PUT, DELETE)
- /visits/<id>/photos (GET, POST, DELETE)
- /visits/<id>/pdf (GET)
- /visits/<id>/products (POST)
- /visits/<id>/link-planting (PATCH)
- /visits/bulk (POST)
- /phenology/schedule (GET)
- /photos/<id> (PUT, DELETE)
- /products/<id> (PUT, DELETE)
- /view/visit/<id> (GET)
- /orphan-visits (GET)
- /fix-orphan-visits (POST)
- /clients/<id>/plantings (GET)
"""

import os
import uuid
from datetime import datetime, timedelta, date as _date

from flask import Blueprint, jsonify, request, send_file, render_template_string
from flask_cors import cross_origin
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from models import (
    db,
    Visit,
    Photo,
    Client,
    Property,
    Plot,
    Planting,
    Consultant,
    VisitProduct,
    PhenologyStage,
)
from utils.r2_client import get_r2_client
from utils.auth_helper import apply_consultant_filter, get_consultant_id_filter

visits_bp = Blueprint('visits', __name__)


# ============================================================
# HELPERS
# ============================================================

def _get_helpers():
    """Lazy import para evitar dependência circular."""
    from api_routes import (
        build_visit_pdf_file,
        parse_optional_float,
        auto_create_planting_if_needed,
    )
    return {
        'build_visit_pdf_file': build_visit_pdf_file,
        'parse_optional_float': parse_optional_float,
        'auto_create_planting_if_needed': auto_create_planting_if_needed,
    }


def resolve_photo_url(u: str) -> str:
    """Resolve URL pública da foto (R2 / legado)."""
    if not u:
        return ""
    if u.startswith("http://") or u.startswith("https://"):
        return u
    if u.startswith("/uploads/"):
        backend_url = (os.environ.get("RENDER_EXTERNAL_URL") or "https://agrocrm-backend.onrender.com").rstrip("/")
        return f"{backend_url}{u}"
    return u


UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(os.path.dirname(__file__), "..", "uploads"))


# ============================================================
# VISITS CRUD
# ============================================================

def _get_group_key(v):
    """Gera chave de agrupamento para uma visita."""
    if v.planting_id:
        return f"plant-{v.planting_id}"
    return f"{v.client_id}-{v.property_id}-{v.plot_id}-{v.variety or ''}"


def _build_visit_dict(v, clients_map, consultants_map):
    """Constroi dict de uma visita com dados relacionados."""
    client = clients_map.get(v.client_id)
    consultant = consultants_map.get(v.consultant_id) if v.consultant_id else None

    photos = []
    for p in v.photos:
        photos.append({
            "id": p.id,
            "url": resolve_photo_url(p.url),
            "caption": p.caption or ""
        })

    culture = v.culture or (v.planting.culture if v.planting else "—")
    variety = v.variety or (v.planting.variety if v.planting else "—")

    d = v.to_dict()
    d["fenologia_real"] = v.fenologia_real or ""
    d["products"] = [p.to_dict() for p in v.products]
    d["client_name"] = client.name if client else f"Cliente {v.client_id}"
    d["consultant_name"] = consultant.name if consultant else "—"
    d["culture"] = culture
    d["variety"] = variety
    d["photos"] = photos
    return d


@visits_bp.route('/visits', methods=['GET'])
def get_visits():
    """
    Rota unificada com suporte a paginacao por GRUPOS:
    - ?month=current -> modo iOS (visitas so do mes)
    - ?scope=all -> retorna todas as visitas, paginadas por grupo
    - ?page=N&limit=M -> pagina N grupos de tamanho M (default 20 grupos)
    - sem params -> filtros normais
    """
    try:
        month = request.args.get("month")
        scope = request.args.get("scope")
        page = request.args.get("page", type=int)
        limit = request.args.get("limit", default=20, type=int)
        today = _date.today()

        use_pagination = page is not None
        if use_pagination:
            page = max(1, page)
            limit = min(max(1, limit), 50)

        if month == "current":
            q = (
                Visit.query
                .options(joinedload(Visit.photos), joinedload(Visit.products))
                .filter(db.extract('month', Visit.date) == today.month)
                .filter(db.extract('year', Visit.date) == today.year)
                .order_by(Visit.date.asc())
            )
            # Aplica filtro por consultor se autenticado
            q = apply_consultant_filter(q, Visit.consultant_id)
            visits = q.all()

            client_ids = {v.client_id for v in visits if v.client_id}
            consultant_ids = {v.consultant_id for v in visits if v.consultant_id}
            clients_map = {c.id: c for c in Client.query.filter(Client.id.in_(client_ids)).all()} if client_ids else {}
            consultants_map = {c.id: c for c in Consultant.query.filter(Consultant.id.in_(consultant_ids)).all()} if consultant_ids else {}

            result = [_build_visit_dict(v, clients_map, consultants_map) for v in visits]
            return jsonify(result), 200

        elif scope == "all":
            _window_start = today - timedelta(days=365)
            q = (
                Visit.query
                .options(joinedload(Visit.photos), joinedload(Visit.products))
                .filter(db.or_(Visit.date.is_(None), Visit.date >= _window_start))
            )

            client_id_filter = request.args.get('client_id', type=int)
            property_id = request.args.get('property_id', type=int)
            plot_id = request.args.get('plot_id', type=int)
            consultant_id = request.args.get('consultant_id', type=int)
            culture = request.args.get('culture')
            variety = request.args.get('variety')
            date_start = request.args.get('date_start')
            date_end = request.args.get('date_end')

            if client_id_filter:
                q = q.filter(Visit.client_id == client_id_filter)
            if property_id:
                q = q.filter(Visit.property_id == property_id)
            if plot_id:
                q = q.filter(Visit.plot_id == plot_id)
            if consultant_id:
                q = q.filter(Visit.consultant_id == consultant_id)
            if culture:
                q = q.filter(Visit.culture == culture)
            if variety:
                q = q.filter(Visit.variety == variety)
            if date_start:
                q = q.filter(Visit.date >= date_start)
            if date_end:
                q = q.filter(Visit.date <= date_end)

            # Aplica filtro por consultor se autenticado
            q = apply_consultant_filter(q, Visit.consultant_id)

            all_visits = q.all()

            groups = {}
            for v in all_visits:
                key = _get_group_key(v)
                if key not in groups:
                    groups[key] = []
                groups[key].append(v)

            for key in groups:
                groups[key].sort(key=lambda x: x.date or _date.min)

            def group_latest_date(key):
                visits_in_group = groups[key]
                dates = [v.date for v in visits_in_group if v.date]
                return max(dates) if dates else _date.min

            sorted_group_keys = sorted(groups.keys(), key=group_latest_date, reverse=True)

            total_groups = len(sorted_group_keys)

            if use_pagination:
                pages = (total_groups + limit - 1) // limit if total_groups > 0 else 1
                offset = (page - 1) * limit
                selected_keys = sorted_group_keys[offset:offset + limit]
            else:
                pages = 1
                selected_keys = sorted_group_keys

            selected_visits = []
            for key in selected_keys:
                selected_visits.extend(groups[key])

            client_ids = {v.client_id for v in selected_visits if v.client_id}
            consultant_ids = {v.consultant_id for v in selected_visits if v.consultant_id}
            clients_map = {c.id: c for c in Client.query.filter(Client.id.in_(client_ids)).all()} if client_ids else {}
            consultants_map = {c.id: c for c in Consultant.query.filter(Consultant.id.in_(consultant_ids)).all()} if consultant_ids else {}

            result = [_build_visit_dict(v, clients_map, consultants_map) for v in selected_visits]

            total_visits = sum(len(groups[k]) for k in selected_keys)

            if use_pagination:
                return jsonify({
                    "items": result,
                    "total": len(all_visits),
                    "total_groups": total_groups,
                    "page": page,
                    "pages": pages,
                    "limit": limit,
                    "has_next": page < pages,
                    "has_prev": page > 1,
                    "groups_in_page": len(selected_keys),
                    "visits_in_page": total_visits
                }), 200
            else:
                return jsonify(result), 200

        else:
            client_id_filter = request.args.get('client_id', type=int)
            property_id = request.args.get('property_id', type=int)
            plot_id = request.args.get('plot_id', type=int)
            consultant_id = request.args.get('consultant_id', type=int)

            q = Visit.query.options(joinedload(Visit.photos), joinedload(Visit.products))
            if client_id_filter:
                q = q.filter_by(client_id=client_id_filter)
            if property_id:
                q = q.filter_by(property_id=property_id)
            if plot_id:
                q = q.filter_by(plot_id=plot_id)
            if consultant_id:
                q = q.filter_by(consultant_id=consultant_id)

            # Aplica filtro por consultor se autenticado
            q = apply_consultant_filter(q, Visit.consultant_id)

            q = q.order_by(Visit.date.desc().nullslast())

            visits = q.all()

            client_ids = {v.client_id for v in visits if v.client_id}
            consultant_ids = {v.consultant_id for v in visits if v.consultant_id}
            clients_map = {c.id: c for c in Client.query.filter(Client.id.in_(client_ids)).all()} if client_ids else {}
            consultants_map = {c.id: c for c in Consultant.query.filter(Consultant.id.in_(consultant_ids)).all()} if consultant_ids else {}

            result = [_build_visit_dict(v, clients_map, consultants_map) for v in visits]
            return jsonify(result), 200

    except Exception as e:
        print(f"Erro ao listar visitas: {e}")
        import traceback
        traceback.print_exc()
        return jsonify(error=str(e)), 500


@visits_bp.route('/visits', methods=['POST', 'OPTIONS'])
@cross_origin(origins=["https://agrocrm-frontend.onrender.com", "https://localhost", "capacitor://localhost", "http://localhost"])
def create_visit():
    """Cria uma nova visita."""
    h = _get_helpers()
    data = request.get_json(silent=True) or {}

    client_id = data.get('client_id')
    property_id = data.get('property_id')
    plot_id = data.get('plot_id')
    consultant_id = data.get('consultant_id')
    status = (data.get('status') or 'planned').strip().lower()
    gen_schedule = bool(data.get('generate_schedule'))
    culture = (data.get('culture') or '').strip() or None
    variety = (data.get('variety') or '').strip() or None
    date_str = data.get('date')
    recommendation = (data.get('recommendation') or '').strip()
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    fenologia_real = data.get("fenologia_real")

    if not client_id:
        return jsonify(message="client_id e obrigatorio"), 400
    if not Client.query.get(client_id):
        return jsonify(message="cliente nao encontrado"), 404
    if property_id and not Property.query.get(property_id):
        return jsonify(message="propriedade nao encontrada"), 404
    if plot_id and not Plot.query.get(plot_id):
        return jsonify(message="talhao nao encontrado"), 404
    if consultant_id not in (None, "", 0, "0"):
        try:
            consultant_id = int(consultant_id)
        except (TypeError, ValueError):
            return jsonify(message="consultant_id invalido"), 400
        if not Consultant.query.get(consultant_id):
            return jsonify(message="consultor nao encontrado"), 404
    else:
        consultant_id = None

    try:
        visit_date = _date.fromisoformat(date_str)
    except Exception:
        return jsonify(message="data invalida, esperado formato YYYY-MM-DD"), 400

    p = None
    if gen_schedule:
        if not culture or not variety:
            return jsonify(message="culture e variety sao obrigatorios quando gerar cronograma"), 400

        p = Planting(
            plot_id=plot_id if plot_id else None,
            culture=culture,
            variety=variety,
            planting_date=visit_date
        )
        db.session.add(p)
        db.session.flush()

        v0 = Visit(
            client_id=client_id,
            property_id=property_id or None,
            plot_id=plot_id or None,
            planting_id=p.id if p else None,
            consultant_id=consultant_id,
            date=visit_date,
            recommendation="Plantio",
            status=status,
            culture=culture,
            variety=variety,
            latitude=latitude,
            longitude=longitude
        )
        db.session.add(v0)

        stages = PhenologyStage.query.filter_by(culture=culture).order_by(PhenologyStage.days.asc()).all()
        if culture.lower() == "soja":
            stages = [s for s in stages if "maturacao fisiologica" not in s.name.lower()]

        for st in stages:
            if st.days == 0 or "plantio" in st.name.lower():
                continue
            fut_date = visit_date + timedelta(days=int(st.days))
            vv = Visit(
                client_id=client_id,
                property_id=property_id,
                plot_id=plot_id,
                planting_id=p.id if p else None,
                consultant_id=consultant_id or v0.consultant_id,
                date=fut_date,
                recommendation=st.name.strip().capitalize(),
                status='planned',
                culture=culture,
                variety=variety,
                latitude=latitude,
                longitude=longitude
            )
            db.session.add(vv)

        db.session.commit()
        return jsonify(message="visita criada com cronograma", visit=v0.to_dict()), 201

    v = Visit(
        client_id=client_id,
        property_id=property_id or None,
        plot_id=plot_id or None,
        consultant_id=consultant_id,
        date=visit_date,
        checklist=data.get('checklist'),
        diagnosis=data.get('diagnosis'),
        recommendation=recommendation,
        status=status,
        culture=culture,
        variety=variety,
        latitude=latitude,
        longitude=longitude,
        fenologia_real=fenologia_real
    )

    if not v.culture and v.plot_id:
        planting = Planting.query.filter_by(plot_id=v.plot_id).order_by(Planting.id.desc()).first()
        if planting:
            v.culture = planting.culture
            v.variety = planting.variety

    db.session.add(v)
    db.session.commit()

    products = data.get("products", [])
    for prod in products:
        vp = VisitProduct(
            visit_id=v.id,
            product_name=prod.get("product_name", ""),
            dose=prod.get("dose", ""),
            unit=prod.get("unit", ""),
            application_date=(
                datetime.strptime(prod["application_date"], "%Y-%m-%d").date()
                if prod.get("application_date")
                else None
            ),
        )
        db.session.add(vp)

    db.session.commit()
    return jsonify(message="visita criada", visit=v.to_dict()), 201


@visits_bp.route('/visits/<int:visit_id>', methods=['GET'])
def get_visit(visit_id):
    v = Visit.query.get_or_404(visit_id)

    photos = []
    try:
        for p in (v.photos or []):
            photos.append({
                "id": p.id,
                "url": resolve_photo_url(p.url),
                "caption": p.caption or ""
            })
    except Exception:
        photos = []

    return jsonify({
        "id": v.id,
        "client_id": v.client_id,
        "property_id": v.property_id,
        "plot_id": v.plot_id,
        "consultant_id": v.consultant_id,
        "date": v.date.isoformat() if getattr(v, "date", None) else None,
        "recommendation": v.recommendation or "",
        "status": v.status or "planned",
        "fenologia_real": getattr(v, "fenologia_real", None),
        "latitude": getattr(v, "latitude", None),
        "longitude": getattr(v, "longitude", None),
        "products": [p.to_dict() for p in (getattr(v, "products", []) or [])],
        "photos": photos
    }), 200


@visits_bp.route('/visits/<int:visit_id>', methods=['PUT', 'OPTIONS'])
@cross_origin(origins=["https://agrocrm-frontend.onrender.com", "https://localhost", "capacitor://localhost", "http://localhost"])
def update_visit(visit_id: int):
    h = _get_helpers()
    v = Visit.query.get(visit_id)
    if not v:
        return jsonify(message='visit not found'), 404

    data = request.get_json(silent=True) or {}
    print("PAYLOAD RECEBIDO NO PUT:", data)

    for tf in ('checklist', 'diagnosis', 'fenologia_real'):
        if tf in data:
            setattr(v, tf, data[tf])

    if "recommendation" in data:
        rec = data.get("recommendation")
        if rec not in (None, "", " "):
            v.recommendation = rec.strip()

    if 'client_id' in data:
        cid = data.get('client_id')
        if cid not in (None, "", 0):
            if not Client.query.get(cid):
                return jsonify(message='client not found'), 404
            v.client_id = cid

    if 'property_id' in data:
        pid = data.get('property_id')
        if pid in (None, "", 0):
            v.property_id = None
        else:
            if not Property.query.get(pid):
                return jsonify(message='property not found'), 404
            v.property_id = pid

    if 'plot_id' in data:
        plid = data.get('plot_id')
        if plid in (None, "", 0):
            v.plot_id = None
        else:
            if not Plot.query.get(plid):
                return jsonify(message='plot not found'), 404
            v.plot_id = plid

    if 'planting_id' in data:
        planting_id = data.get('planting_id')
        if planting_id in (None, "", 0):
            v.planting_id = None
            print(f"Visita {visit_id}: planting_id removido (desvinculada)")
        else:
            planting = Planting.query.get(planting_id)
            if not planting:
                return jsonify(message='planting not found'), 404
            v.planting_id = planting_id
            if planting.plot_id and not v.plot_id:
                v.plot_id = planting.plot_id
            if planting.culture and not v.culture:
                v.culture = planting.culture
            if planting.variety and not v.variety:
                v.variety = planting.variety
            if planting.plot_id and not v.property_id:
                plot_obj = Plot.query.get(planting.plot_id)
                if plot_obj:
                    v.property_id = plot_obj.property_id
            print(f"Visita {visit_id}: vinculada ao planting_id={planting_id}")

    if 'consultant_id' in data:
        cid = data.get('consultant_id')
        if cid in (None, "", 0):
            v.consultant_id = None
        else:
            try:
                cid = int(cid)
            except (TypeError, ValueError):
                return jsonify(message='invalid consultant_id'), 400

            consultant = Consultant.query.get(cid)
            if not consultant:
                return jsonify(message='consultant not found'), 404

            if not getattr(v, "planting_id", None):
                candidate_planting = None
                if getattr(v, "plot_id", None):
                    candidate_planting = (
                        Planting.query
                        .filter_by(plot_id=v.plot_id)
                        .order_by(Planting.planting_date.desc().nullslast(), Planting.id.desc())
                        .first()
                    )
                if not candidate_planting:
                    q = Planting.query
                    if getattr(v, "culture", None):
                        q = q.filter(Planting.culture == v.culture)
                    if getattr(v, "variety", None):
                        q = q.filter(Planting.variety == v.variety)
                    candidate_planting = (
                        q.order_by(Planting.planting_date.desc().nullslast(), Planting.id.desc())
                        .first()
                    )
                if candidate_planting:
                    v.planting_id = candidate_planting.id
                    if not getattr(v, "plot_id", None):
                        v.plot_id = candidate_planting.plot_id
                    if candidate_planting.plot_id and not getattr(v, "property_id", None):
                        plot_obj = Plot.query.get(candidate_planting.plot_id)
                        if plot_obj:
                            v.property_id = getattr(plot_obj, "property_id", None)
                    if not getattr(v, "culture", None):
                        v.culture = candidate_planting.culture
                    if not getattr(v, "variety", None):
                        v.variety = candidate_planting.variety

            v.consultant_id = cid

            if v.planting_id:
                sibling_visits = (
                    Visit.query
                    .filter(Visit.planting_id == v.planting_id)
                    .filter(Visit.id != v.id)
                    .filter(Visit.status != "done")
                    .all()
                )
                for sib in sibling_visits:
                    sib.consultant_id = cid
                    db.session.add(sib)

    if 'culture' in data:
        culture = (data.get('culture') or "").strip()
        v.culture = culture or None

    if 'variety' in data:
        variety = (data.get('variety') or "").strip()
        v.variety = variety or None

    if "preserve_date" in data and data.get("preserve_date"):
        data["date"] = v.date.isoformat() if v.date else None

    if 'date' in data:
        if not data['date']:
            v.date = None
        else:
            try:
                v.date = _date.fromisoformat(data['date'])
            except Exception:
                return jsonify(message='invalid date, expected YYYY-MM-DD'), 400

    if 'status' in data and data['status']:
        v.status = data['status'].strip().lower()

    if 'latitude' in data:
        v.latitude = h['parse_optional_float'](data.get('latitude'))

    if 'longitude' in data:
        v.longitude = h['parse_optional_float'](data.get('longitude'))

    if "products" in data:
        VisitProduct.query.filter_by(visit_id=visit_id).delete()
        for prod in data["products"]:
            vp = VisitProduct(
                visit_id=visit_id,
                product_name=prod.get("product_name", ""),
                dose=prod.get("dose", ""),
                unit=prod.get("unit", ""),
                application_date=(
                    datetime.strptime(prod["application_date"], "%Y-%m-%d")
                    if prod.get("application_date") else None
                ),
            )
            db.session.add(vp)

    db.session.commit()
    return jsonify(message='visit updated', visit=v.to_dict() | {"status": v.status}), 200


@visits_bp.route('/visits/<int:visit_id>', methods=['DELETE'])
def delete_visit(visit_id):
    """Exclui uma visita."""
    try:
        visit = Visit.query.get(visit_id)
        if not visit:
            print(f"Visita {visit_id} nao encontrada.")
            return jsonify({'error': 'Visita nao encontrada'}), 404

        print(f"Solicitada exclusao da visita {visit_id}: {visit.recommendation}")

        def is_plantio_like(v):
            rec_local = (v.recommendation or "").strip().lower()
            fen_local = (v.fenologia_real or "").strip().lower()
            return (
                rec_local == "plantio"
                or rec_local.startswith("plantio ")
                or "plantio -" in rec_local
                or fen_local == "plantio"
            )

        if visit.planting_id and is_plantio_like(visit):
            planting = Planting.query.get(visit.planting_id)

            if planting:
                first_cycle_visit = (
                    Visit.query
                    .filter(Visit.planting_id == planting.id)
                    .order_by(Visit.date.asc().nullslast(), Visit.id.asc())
                    .first()
                )

                is_root_plantio_visit = (
                    first_cycle_visit is not None
                    and first_cycle_visit.id == visit.id
                    and is_plantio_like(first_cycle_visit)
                )

                if is_root_plantio_visit:
                    print(f"Exclusao em cascata do plantio {planting.id}")

                    linked_visits = (
                        Visit.query
                        .filter(Visit.planting_id == planting.id)
                        .order_by(Visit.date.asc().nullslast(), Visit.id.asc())
                        .all()
                    )

                    for lv in linked_visits:
                        print(f"   -> Removendo visita vinculada {lv.id} ({lv.recommendation})")
                        db.session.delete(lv)

                    print(f"   -> Removendo plantio {planting.id}")
                    db.session.delete(planting)

                    db.session.commit()
                    print("Plantio e visitas vinculadas excluidos com sucesso.")
                    return jsonify({'message': 'Plantio e visitas vinculadas excluidos com sucesso'}), 200

                print(
                    f"Visita {visit.id} parece plantio, mas nao e a visita raiz do ciclo. "
                    "Excluindo apenas a visita isolada."
                )

        print(f"Excluindo visita isolada {visit_id}")
        db.session.delete(visit)
        db.session.commit()

        print(f"Visita {visit_id} excluida com sucesso.")
        return jsonify({'message': 'Visita excluida com sucesso'}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Erro interno ao excluir visita {visit_id}: {e}")
        return jsonify({'error': f'Erro interno ao excluir visita: {str(e)}'}), 500


@visits_bp.route('/visits/bulk', methods=['POST'])
def create_visits_bulk():
    data = request.get_json(silent=True) or {}
    items = data.get('items', [])
    created = []

    for it in items:
        client_id = it.get('client_id')
        property_id = it.get('property_id')
        plot_id = it.get('plot_id')
        consultant_id = it.get('consultant_id')
        status = (it.get('status') or 'planned').strip().lower()

        if not (client_id and property_id and plot_id and it.get('date')):
            continue
        if not Client.query.get(client_id):
            continue
        if not Property.query.get(property_id):
            continue
        if not Plot.query.get(plot_id):
            continue
        if consultant_id:
            try:
                consultant_id = int(consultant_id)
            except (TypeError, ValueError):
                continue
            if not Consultant.query.get(consultant_id):
                continue

        try:
            visit_date = _date.fromisoformat(it['date'])
        except Exception:
            continue

        v = Visit(
            client_id=client_id,
            property_id=property_id,
            plot_id=plot_id,
            consultant_id=consultant_id,
            date=visit_date,
            checklist=None,
            diagnosis=None,
            recommendation=it.get('recommendation'),
            status=status
        )
        db.session.add(v)
        created.append(v)

    db.session.commit()
    return jsonify([v.to_dict() | {"status": v.status} for v in created]), 201


@visits_bp.route('/visits/<int:visit_id>/pdf', methods=['GET'])
@cross_origin(origins=["https://agrocrm-frontend.onrender.com", "https://localhost", "capacitor://localhost", "http://localhost"])
def export_visit_pdf(visit_id):
    h = _get_helpers()
    buffer, filename = h['build_visit_pdf_file'](visit_id)
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )


# ============================================================
# PHOTOS
# ============================================================

@visits_bp.route('/visits/<int:visit_id>/photos', methods=['POST', 'OPTIONS'])
@cross_origin(origins=["https://agrocrm-frontend.onrender.com", "https://localhost", "capacitor://localhost", "http://localhost"])
def upload_photos(visit_id):
    """Upload de multiplas fotos com legendas - agora no Cloudflare R2."""
    visit = Visit.query.get_or_404(visit_id)

    files = request.files.getlist('photos')
    captions = request.form.getlist('captions')

    if not files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    bucket = os.environ.get("R2_BUCKET")
    public_base = (os.environ.get("R2_PUBLIC_BASE_URL") or "").rstrip("/")

    if not bucket or not public_base:
        return jsonify({"error": "R2 nao configurado: faltam variaveis de ambiente"}), 500

    r2 = get_r2_client()
    saved = []

    for i, file in enumerate(files):
        unique = uuid.uuid4().hex
        original = secure_filename(file.filename or "foto.jpg")
        if "." not in original:
            original = f"{original}.jpg"

        key = f"visits/{visit_id}/{unique}_{original}"

        r2.upload_fileobj(
            Fileobj=file,
            Bucket=bucket,
            Key=key,
            ExtraArgs={"ContentType": file.mimetype or "image/jpeg"},
        )

        caption = captions[i] if i < len(captions) else ""
        url = f"{public_base}/{key}"

        photo = Photo(visit_id=visit_id, url=url, caption=caption)
        db.session.add(photo)
        db.session.flush()

        saved.append({"id": photo.id, "url": url, "caption": caption or ""})

    db.session.commit()

    return jsonify({
        "message": f"{len(saved)} foto(s) salvas.",
        "photos": saved
    }), 201


@visits_bp.route('/visits/<int:visit_id>/photos', methods=['GET'])
def list_photos(visit_id):
    visit = Visit.query.get_or_404(visit_id)

    photos = []
    for p in (visit.photos or []):
        photos.append({
            "id": p.id,
            "url": resolve_photo_url(p.url),
            "caption": p.caption or ""
        })

    return jsonify(photos), 200


@visits_bp.route('/visits/<int:visit_id>/photos', methods=['DELETE'])
def delete_all_photos_of_visit(visit_id):
    """Exclui todas as fotos associadas a uma visita."""
    try:
        visit = Visit.query.get_or_404(visit_id)
        count = 0
        for photo in visit.photos:
            from urllib.parse import urlparse
            parsed = urlparse(photo.url)
            filename = os.path.basename(parsed.path)
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            db.session.delete(photo)
            count += 1

        db.session.commit()
        return jsonify({"message": f"{count} foto(s) excluidas com sucesso"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao excluir fotos da visita: {e}")
        return jsonify({"error": str(e)}), 500


@visits_bp.route('/photos/<int:photo_id>', methods=['PUT', 'OPTIONS'])
@cross_origin(origins=["https://agrocrm-frontend.onrender.com", "https://localhost", "capacitor://localhost", "http://localhost"])
def update_photo_caption(photo_id):
    """Atualiza a legenda de uma foto especifica."""
    try:
        data = request.get_json() or {}
        caption = data.get("caption", "").strip()

        photo = Photo.query.get(photo_id)
        if not photo:
            return jsonify({"error": "Foto nao encontrada"}), 404

        photo.caption = caption
        db.session.commit()

        print(f"Legenda atualizada -> Foto {photo_id}: {caption}")
        return jsonify({"success": True, "caption": caption}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar legenda da foto {photo_id}: {e}")
        return jsonify({"error": str(e)}), 500


@visits_bp.route('/photos/<int:photo_id>', methods=['DELETE', 'OPTIONS'])
@cross_origin(origins=["https://agrocrm-frontend.onrender.com", "https://localhost", "capacitor://localhost", "http://localhost"])
def delete_single_photo(photo_id):
    """Exclui uma foto especifica do banco e do disco."""
    photo = Photo.query.get_or_404(photo_id)
    try:
        from urllib.parse import urlparse
        parsed = urlparse(photo.url)
        filename = os.path.basename(parsed.path)
        file_path = os.path.join(UPLOAD_DIR, filename)

        if os.path.exists(file_path):
            os.remove(file_path)

        db.session.delete(photo)
        db.session.commit()
        return jsonify({"message": "Foto excluida com sucesso"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao excluir foto: {e}")
        return jsonify({"error": f"Erro ao excluir foto: {e}"}), 500


# ============================================================
# PRODUCTS
# ============================================================

@visits_bp.route("/visits/<int:visit_id>/products", methods=["POST"])
def add_visit_product(visit_id):
    data = request.get_json()

    product = VisitProduct(
        visit_id=visit_id,
        product_name=data.get("product_name", "").strip(),
        dose=data.get("dose", "").strip(),
        unit=data.get("unit", "").strip(),
        application_date=datetime.strptime(data.get("application_date"), "%Y-%m-%d") if data.get("application_date") else None,
    )

    db.session.add(product)
    db.session.commit()

    return jsonify({"success": True, "product": product.to_dict()}), 201


@visits_bp.route("/products/<int:product_id>", methods=["PUT"])
def update_visit_product(product_id):
    data = request.get_json()
    product = VisitProduct.query.get_or_404(product_id)

    product.product_name = data.get("product_name", product.product_name)
    product.dose = data.get("dose", product.dose)
    product.unit = data.get("unit", product.unit)
    product.application_date = (
        datetime.strptime(data["application_date"], "%Y-%m-%d")
        if data.get("application_date")
        else product.application_date
    )

    db.session.commit()
    return jsonify({"success": True, "product": product.to_dict()})


@visits_bp.route("/products/<int:product_id>", methods=["DELETE"])
def delete_visit_product(product_id):
    product = VisitProduct.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    return jsonify({"success": True})


# ============================================================
# PHENOLOGY SCHEDULE
# ============================================================

@visits_bp.route('/phenology/schedule', methods=['GET'])
def get_phenology_schedule():
    """Retorna o cronograma fenologico real do banco de dados."""
    from sqlalchemy import text

    culture = request.args.get("culture")
    planting_date = request.args.get("planting_date")

    if not culture or not planting_date:
        return jsonify({"error": "culture and planting_date required"}), 400

    try:
        planting_dt = datetime.fromisoformat(planting_date).date()
    except ValueError:
        return jsonify({"error": "invalid planting_date format"}), 400

    stages = db.session.execute(
        text("SELECT code, name, days FROM phenology_stage WHERE culture = :culture ORDER BY days"),
        {"culture": culture}
    ).fetchall()

    if not stages:
        print(f"Nenhum estagio encontrado para {culture}.")
        return jsonify([]), 200

    events = []
    for s in stages:
        date = planting_dt + timedelta(days=s.days)
        events.append({
            "stage": s.name,
            "code": s.code,
            "suggested_date": date.isoformat(),
        })

    print(f"{len(events)} estagios retornados para {culture}.")
    return jsonify(events), 200


# ============================================================
# VIEW VISIT (PUBLIC PAGE)
# ============================================================

@visits_bp.route("/view/visit/<int:visit_id>", methods=["GET"])
def public_visit_view(visit_id):
    """Pagina publica de visualizacao de visita (NutriCRM Viewer)."""
    visit = Visit.query.get_or_404(visit_id)
    client = Client.query.get(visit.client_id)
    prop = Property.query.get(visit.property_id)
    plot = Plot.query.get(visit.plot_id)
    consultant = Consultant.query.get(visit.consultant_id) if hasattr(visit, "consultant_id") else None

    lat = getattr(plot, "latitude", None)
    lon = getattr(plot, "longitude", None)

    photos = []
    for p in (visit.photos or []):
        photos.append({
            "id": p.id,
            "url": resolve_photo_url(p.url),
            "caption": p.caption or ""
        })

    html_template = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Visita #{{ visit.id }} - NutriCRM</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet" />
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            body { background-color:#f9fafb; font-family:'Inter', sans-serif; padding-bottom:60px; }
            header { background:#1B5E20; color:white; padding:16px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; }
            header img { height:46px; object-fit:contain; }
            .info-card { background:white; border-radius:10px; box-shadow:0 2px 10px rgba(0,0,0,0.05); padding:20px; margin-top:20px; }
            .photos img { width:100%; border-radius:8px; cursor:pointer; transition:transform 0.2s; }
            .photos img:hover { transform:scale(1.02); }
            #map { height:300px; border-radius:10px; margin-top:15px; }
            footer { margin-top:40px; text-align:center; color:#888; }
            .download-btn { background:#2E7D32; color:white; padding:10px 18px; border-radius:6px; text-decoration:none; transition:opacity .2s; }
            .download-btn:hover { opacity:.85; }
            .lightbox { display:none; position:fixed; z-index:9999; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); justify-content:center; align-items:center; }
            .lightbox img { max-width:90%; max-height:90%; }
        </style>
    </head>
    <body>
        <header>
            <img src="/static/nutricrm_logo.png" alt="NutriCRM Logo" />
            <h4>Relatorio Tecnico - Visita #{{ visit.id }}</h4>
            <a class="download-btn" href="/api/visits/{{ visit.id }}/pdf" target="_blank">Baixar PDF</a>
        </header>

        <main class="container">
            <div class="info-card">
                <h4>Informacoes Gerais</h4>
                <table class="table table-borderless mt-3">
                    <tr><th>Cliente:</th><td>{{ client.name if client else '-' }}</td></tr>
                    <tr><th>Fazenda:</th><td>{{ prop.name if prop else '-' }}</td></tr>
                    <tr><th>Talhao:</th><td>{{ plot.name if plot else '-' }}</td></tr>
                    <tr><th>Consultor:</th><td>{{ consultant.name if consultant else '-' }}</td></tr>
                    <tr><th>Data:</th><td>{{ visit.date.strftime('%d/%m/%Y') if visit.date else '-' }}</td></tr>
                    <tr><th>Status:</th><td>{{ visit.status }}</td></tr>
                </table>
                {% if lat and lon %}
                <div id="map"></div>
                {% endif %}
            </div>

            {% if visit.diagnosis %}
            <div class="info-card">
                <h4>Diagnostico</h4>
                <p>{{ visit.diagnosis }}</p>
            </div>
            {% endif %}

            {% if visit.recommendation %}
            <div class="info-card">
                <h4>Recomendacoes Tecnicas</h4>
                <p>{{ visit.recommendation }}</p>
            </div>
            {% endif %}

            {% if photos %}
            <div class="info-card photos">
                <h4>Fotos da Visita</h4>
                <div class="row mt-3">
                    {% for p in photos %}
                    <div class="col-md-6 mb-3">
                        <img src="{{ p.url }}" onclick="openLightbox('{{ p.url }}')" />
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
        </main>

        <div id="lightbox" class="lightbox" onclick="closeLightbox()">
            <img id="lightbox-img" src="">
        </div>

        <footer>
            <small>NutriCRM - Relatorio tecnico automatizado</small>
        </footer>

        <script>
            function openLightbox(src) {
                document.getElementById('lightbox-img').src = src;
                document.getElementById('lightbox').style.display = 'flex';
            }
            function closeLightbox() {
                document.getElementById('lightbox').style.display = 'none';
            }

            {% if lat and lon %}
            const map = L.map('map').setView([{{ lat }}, {{ lon }}], 15);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: 'OpenStreetMap contributors'
            }).addTo(map);
            L.marker([{{ lat }}, {{ lon }}]).addTo(map)
                .bindPopup("{{ plot.name if plot else 'Talhao' }}")
                .openPopup();
            {% endif %}
        </script>
    </body>
    </html>
    """

    return render_template_string(
        html_template,
        visit=visit,
        client=client,
        prop=prop,
        plot=plot,
        consultant=consultant,
        photos=photos,
        lat=lat,
        lon=lon
    )


# ============================================================
# ORPHAN VISITS
# ============================================================

@visits_bp.route("/orphan-visits", methods=["GET"])
def list_orphan_visits():
    """Lista visitas sem planting_id para vinculacao manual."""
    client_id = request.args.get("client_id", type=int)
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    query = Visit.query.filter(Visit.planting_id.is_(None))

    if client_id:
        query = query.filter(Visit.client_id == client_id)

    total = query.count()

    visits = (
        query.order_by(Visit.date.desc().nullslast(), Visit.id.desc())
             .offset(offset)
             .limit(limit)
             .all()
    )

    result = []
    for v in visits:
        client = Client.query.get(v.client_id) if v.client_id else None
        property_ = Property.query.get(v.property_id) if v.property_id else None
        plot = Plot.query.get(v.plot_id) if v.plot_id else None

        result.append({
            "id": v.id,
            "date": v.date.isoformat() if v.date else None,
            "client_id": v.client_id,
            "client_name": client.name if client else None,
            "property_id": v.property_id,
            "property_name": property_.name if property_ else None,
            "plot_id": v.plot_id,
            "plot_name": plot.name if plot else None,
            "culture": v.culture,
            "variety": v.variety,
            "fenologia_real": v.fenologia_real,
            "visit_purpose": v.visit_purpose,
            "recommendation": v.recommendation,
            "status": v.status,
        })

    return jsonify({
        "ok": True,
        "total": total,
        "visits": result,
    }), 200


@visits_bp.route("/fix-orphan-visits", methods=["POST"])
def fix_orphan_visits():
    """Corrige visitas sem planting_id."""
    h = _get_helpers()

    visits_without_planting = Visit.query.filter(
        Visit.planting_id.is_(None),
        Visit.culture.isnot(None),
        Visit.culture != "",
        Visit.plot_id.isnot(None),
    ).all()

    fixed = []
    skipped = []

    for visit in visits_without_planting:
        payload = {
            "plot_id": visit.plot_id,
            "culture": visit.culture,
            "variety": visit.variety,
            "visit_purpose": visit.visit_purpose,
            "fenologia_real": visit.fenologia_real,
        }

        planting_id = h['auto_create_planting_if_needed'](payload, visit.date)

        if planting_id:
            visit.planting_id = planting_id
            db.session.add(visit)
            fixed.append({
                "visit_id": visit.id,
                "client_id": visit.client_id,
                "planting_id": planting_id,
                "culture": visit.culture,
                "date": visit.date.isoformat() if visit.date else None,
            })
        else:
            skipped.append({
                "visit_id": visit.id,
                "client_id": visit.client_id,
                "reason": "Sem plot_id ou culture suficiente",
            })

    db.session.commit()

    return jsonify({
        "ok": True,
        "fixed_count": len(fixed),
        "skipped_count": len(skipped),
        "fixed": fixed,
        "skipped": skipped,
    }), 200


@visits_bp.route("/visits/<int:visit_id>/link-planting", methods=["PATCH"])
def link_visit_to_planting(visit_id):
    """Vincula manualmente uma visita a um planting especifico."""
    visit = Visit.query.get(visit_id)
    if not visit:
        return jsonify({"ok": False, "error": "Visita nao encontrada"}), 404

    data = request.get_json() or {}
    planting_id = data.get("planting_id")

    if not planting_id:
        return jsonify({"ok": False, "error": "planting_id e obrigatorio"}), 400

    planting = Planting.query.get(planting_id)
    if not planting:
        return jsonify({"ok": False, "error": "Planting nao encontrado"}), 404

    visit.planting_id = planting_id

    if planting.plot_id and not visit.plot_id:
        visit.plot_id = planting.plot_id

    if planting.culture and not visit.culture:
        visit.culture = planting.culture

    if planting.variety and not visit.variety:
        visit.variety = planting.variety

    if planting.plot_id and not visit.property_id:
        plot = Plot.query.get(planting.plot_id)
        if plot:
            visit.property_id = plot.property_id

    db.session.commit()

    return jsonify({
        "ok": True,
        "visit_id": visit.id,
        "planting_id": planting_id,
        "message": "Visita vinculada com sucesso",
    }), 200


@visits_bp.route("/clients/<int:client_id>/plantings", methods=["GET"])
def list_client_plantings(client_id):
    """Lista plantings de um cliente para selecao na vinculacao manual."""
    client = Client.query.get(client_id)
    if not client:
        return jsonify({"ok": False, "error": "Cliente nao encontrado"}), 404

    plantings = (
        Planting.query
        .join(Plot, Plot.id == Planting.plot_id)
        .join(Property, Property.id == Plot.property_id)
        .filter(Property.client_id == client_id)
        .order_by(Planting.planting_date.desc().nullslast(), Planting.id.desc())
        .all()
    )

    result = []
    for p in plantings:
        plot = Plot.query.get(p.plot_id) if p.plot_id else None
        property_ = Property.query.get(plot.property_id) if plot else None

        visits_count = Visit.query.filter_by(planting_id=p.id).count()

        result.append({
            "id": p.id,
            "culture": p.culture,
            "variety": p.variety,
            "planting_date": p.planting_date.isoformat() if p.planting_date else None,
            "plot_id": p.plot_id,
            "plot_name": plot.name if plot else None,
            "property_id": property_.id if property_ else None,
            "property_name": property_.name if property_ else None,
            "visits_count": visits_count,
        })

    return jsonify({
        "ok": True,
        "client_id": client_id,
        "client_name": client.name,
        "plantings": result,
    }), 200
