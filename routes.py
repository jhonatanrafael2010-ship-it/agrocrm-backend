import os
import datetime
from flask import Blueprint, jsonify, request
from sqlalchemy import text
import jwt
from models import db, User, Client, Property, Plot, Visit, Planting, Opportunity

bp = Blueprint('api', __name__, url_prefix='/api')

# ============================================================
# 🌾 CULTURAS, VARIEDADES, CONSULTOR
# ============================================================

@bp.route('/cultures', methods=['GET'])
def list_cultures():
    CULTURES = [
        {"id": 1, "name": "Milho"},
        {"id": 2, "name": "Soja"},
        {"id": 3, "name": "Algodão"},
    ]
    return jsonify(CULTURES), 200


@bp.route('/varieties', methods=['GET'])
def list_varieties():
    VARIETIES = [
        {"id": 1, "culture": "Soja", "name": "AS 3800 12X"},
        {"id": 2, "culture": "Soja", "name": "AS 3840 12X"},
        {"id": 3, "culture": "Soja", "name": "AS 3790 12X"},
        {"id": 4, "culture": "Soja", "name": "AS 3815 12X"},
        {"id": 5, "culture": "Soja", "name": "AS 3707 12X"},
        {"id": 6, "culture": "Soja", "name": "AS 3700 XTD"},
        {"id": 7, "culture": "Soja", "name": "AS 3640 12X"},
        {"id": 8, "culture": "Soja", "name": "AS 3715 12X"},
        {"id": 9, "culture": "Milho", "name": "AS 1820 PRO4"},
        {"id": 10, "culture": "Milho", "name": "AS 1868 PRO4"},
        {"id": 11, "culture": "Milho", "name": "AS 1877 PRO4"},
        {"id": 12, "culture": "Algodão", "name": "TMG 41"}
    ]
    return jsonify(VARIETIES), 200


# ============================================================
# 👨‍🌾 CONSULTANTS — lista fixa (IDs estáveis 1..5)
# ============================================================
CONSULTANTS = [
    {"id": 1, "name": "Jhonatan"},
    {"id": 2, "name": "Felipe"},
    {"id": 3, "name": "Everton"},
    {"id": 4, "name": "Pedro"},
    {"id": 5, "name": "Alexandre"},
]

CONSULTANT_IDS = {c["id"] for c in CONSULTANTS}

@bp.route('/consultants', methods=['GET'])
def list_consultants():
    return jsonify(CONSULTANTS), 200


# ============================================================
# 🌱 VISITS ENDPOINTS
# ============================================================

@bp.route('/visits', methods=['GET'])
def get_visits():
    """Retorna visitas com nomes de cliente, consultor e fotos associadas"""
    try:
        client_id = request.args.get('client_id', type=int)
        property_id = request.args.get('property_id', type=int)
        plot_id = request.args.get('plot_id', type=int)
        consultant_id = request.args.get('consultant_id', type=int)
        status = request.args.get('status', type=str)

        q = Visit.query
        if client_id:
            q = q.filter_by(client_id=client_id)
        if property_id:
            q = q.filter_by(property_id=property_id)
        if plot_id:
            q = q.filter_by(plot_id=plot_id)
        if consultant_id:
            q = q.filter_by(consultant_id=consultant_id)
        if status:
            q = q.filter_by(status=status)

        items = q.order_by(Visit.date.asc().nullslast()).all()
        result = []

        for v in items:
            client = Client.query.get(v.client_id)
            consultant_name = next(
                (c["name"] for c in CONSULTANTS if c["id"] == v.consultant_id),
                None
            )

            result.append({
                **v.to_dict(),
                "client_name": client.name if client else f"Cliente {v.client_id}",
                "consultant_name": consultant_name or "—",
                "status": v.status,
                # ✅ inclui as fotos associadas
                "photos": [{"id": p.id, "url": p.url} for p in v.photos]
            })

        return jsonify(result), 200

    except Exception as e:
        print(f"⚠️ Erro ao listar visitas: {e}")
        return jsonify(error=str(e)), 500





@bp.route('/visits', methods=['POST'])
def create_visit():
    data = request.get_json(silent=True) or {}
    client_id = data.get('client_id')
    property_id = data.get('property_id')
    plot_id = data.get('plot_id')
    consultant_id = data.get('consultant_id')
    status = (data.get('status') or 'planned').strip().lower()
    gen_schedule = bool(data.get('generate_schedule'))
    culture = data.get('culture')
    variety = data.get('variety')
    date_str = data.get('date')

    if not client_id:
        return jsonify(message='client_id is required'), 400


    if not Client.query.get(client_id): return jsonify(message='client not found'), 404
    if not Property.query.get(property_id): return jsonify(message='property not found'), 404
    if not Plot.query.get(plot_id): return jsonify(message='plot not found'), 404
    if consultant_id and int(consultant_id) not in CONSULTANT_IDS:
        return jsonify(message='consultant not found'), 404

    from datetime import date as _d, timedelta
    try:
        visit_date = _d.fromisoformat(date_str)
    except Exception:
        return jsonify(message='invalid date, expected YYYY-MM-DD'), 400

    # ✅ sem cronograma
    if not gen_schedule:
        v = Visit(
            client_id=client_id,
            property_id=property_id,
            plot_id=plot_id,
            consultant_id=consultant_id,
            date=visit_date,
            checklist=data.get('checklist'),
            diagnosis=data.get('diagnosis'),
            recommendation=(data.get('recommendation') or '').strip(),
            status=status
        )
        db.session.add(v)
        db.session.commit()
        return jsonify(message='visit created', visit=v.to_dict()), 201

    # ✅ com cronograma
    if not (culture and variety):
        return jsonify(message='culture and variety required'), 400

    p = Planting(plot_id=plot_id, culture=culture, variety=variety, planting_date=visit_date)
    db.session.add(p)
    db.session.flush()

    v0 = Visit(
        client_id=client_id,
        property_id=property_id,
        plot_id=plot_id,
        planting_id=p.id,
        consultant_id=consultant_id,
        date=visit_date,
        recommendation='Plantio',
        status=status
    )
    db.session.add(v0)

    from models import PhenologyStage
    # 🌱 Gera visitas automáticas conforme estágios fenológicos
    if gen_schedule and culture:  # ✅ usa o nome correto da variável
        stages = PhenologyStage.query.filter_by(culture=culture).order_by(PhenologyStage.days.asc()).all()

        # 🔎 Remove redundâncias apenas para soja (onde havia o problema)
        if culture.strip().lower() == "soja":
            stages = [s for s in stages if "maturação fisiológica" not in s.name.lower()]


        for st in stages:
            # Pula o estágio "Plantio" (já criado manualmente)
            if st.days == 0 or "plantio" in st.name.lower():
                continue

            fut_date = visit_date + timedelta(days=int(st.days))
            vv = Visit(
                client_id=client_id,
                property_id=property_id,
                plot_id=plot_id,
                planting_id=p.id,
                consultant_id=consultant_id,
                date=fut_date,
                recommendation=st.name,
                status='planned'
            )
            db.session.add(vv)

    db.session.commit()
    return jsonify(message='visit created with schedule', visit=v0.to_dict()), 201





@bp.route('/visits/bulk', methods=['POST'])
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

        if not Client.query.get(client_id): continue
        if not Property.query.get(property_id): continue
        if not Plot.query.get(plot_id): continue
        if consultant_id and int(consultant_id) not in CONSULTANT_IDS: continue

        try:
            from datetime import date as _d
            visit_date = _d.fromisoformat(it['date'])
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


@bp.route('/visits/<int:vid>', methods=['PUT'])
def update_visit(vid: int):
    v = Visit.query.get(vid)
    if not v:
        return jsonify(message='visit not found'), 404

    data = request.get_json(silent=True) or {}

    for tf in ('checklist','diagnosis','recommendation'):
        if tf in data:
            setattr(v, tf, data[tf])

    if 'client_id' in data and data['client_id']:
        if not Client.query.get(data['client_id']): return jsonify(message='client not found'), 404
        v.client_id = data['client_id']
    if 'property_id' in data and data['property_id']:
        if not Property.query.get(data['property_id']): return jsonify(message='property not found'), 404
        v.property_id = data['property_id']
    if 'plot_id' in data and data['plot_id']:
        if not Plot.query.get(data['plot_id']): return jsonify(message='plot not found'), 404
        v.plot_id = data['plot_id']

    if 'consultant_id' in data:
        cid = data['consultant_id']
        if cid and int(cid) not in CONSULTANT_IDS:
            return jsonify(message='consultant not found'), 404
        v.consultant_id = cid

    if 'date' in data:
        if not data['date']:
            v.date = None
        else:
            try:
                from datetime import date as _d
                v.date = _d.fromisoformat(data['date'])
            except Exception:
                return jsonify(message='invalid date, expected YYYY-MM-DD'), 400

    if 'status' in data and data['status']:
        v.status = data['status'].strip().lower()

    db.session.commit()
    return jsonify(message='visit updated', visit=v.to_dict() | {"status": v.status}), 200



@bp.route('/visits/<int:visit_id>', methods=['DELETE'])
def delete_visit(visit_id):
    """
    Exclui uma visita. Se for a visita de plantio, remove também o plantio e
    TODAS as visitas geradas automaticamente (mesmo que planting_id esteja nulo).
    """
    try:
        visit = Visit.query.get(visit_id)
        if not visit:
            print(f"⚠️ Visita {visit_id} não encontrada.")
            return jsonify({'error': 'Visita não encontrada'}), 404

        print(f"🗑 Solicitada exclusão da visita {visit_id}: {visit.recommendation}")

        is_plantio = False
        if visit.recommendation:
            is_plantio = 'plantio' in visit.recommendation.lower()

        # =========================================================
        # 🌱 Caso seja visita de plantio, excluir todas relacionadas
        # =========================================================
        if is_plantio and visit.planting_id:
            planting = Planting.query.get(visit.planting_id)
            if planting:
                print(f"🌾 Excluindo plantio {planting.id} e visitas associadas...")

                # Busca TODAS as visitas ligadas a este plantio (apenas pelo planting_id)
                related = Visit.query.filter(Visit.planting_id == planting.id).all()

                print(f"🔍 {len(related)} visitas associadas encontradas:")
                for v in related:
                    print(f"   → Removendo visita {v.id} ({v.recommendation})")
                    db.session.delete(v)


                print(f"🔍 {len(related)} visitas associadas encontradas:")
                for v in related:
                    print(f"   → Removendo visita {v.id} ({v.recommendation})")
                    db.session.delete(v)

                # Remove também o registro do plantio
                db.session.delete(planting)
                db.session.commit()
                print(f"✅ Plantio {planting.id} e todas as visitas associadas foram removidos.")
                return jsonify({'message': 'Plantio e visitas associadas excluídos'}), 200
            else:
                print(f"⚠️ Nenhum plantio encontrado para planting_id={visit.planting_id}")

        # =========================================================
        # 🧾 Caso contrário, excluir apenas a visita isolada
        # =========================================================
        print(f"🧾 Excluindo visita isolada {visit_id}")
        db.session.delete(visit)
        db.session.commit()
        print(f"✅ Visita {visit_id} excluída com sucesso.")
        return jsonify({'message': 'Visita excluída com sucesso'}), 200

    except Exception as e:
        print(f"❌ Erro interno ao excluir visita {visit_id}: {e}")
        db.session.rollback()
        return jsonify({'error': f'Erro interno ao excluir visita: {str(e)}'}), 500


import os
from werkzeug.utils import secure_filename

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@bp.route('/visits/<int:visit_id>/photos', methods=['POST'])
def upload_photos(visit_id):
    visit = Visit.query.get(visit_id)
    if not visit:
        return jsonify(message="Visit not found"), 404

    if 'photos' not in request.files:
        return jsonify(message="No photos received"), 400

    files = request.files.getlist('photos')
    saved_photos = []

    for f in files:
        filename = secure_filename(f.filename)
        path = os.path.join(UPLOAD_DIR, filename)
        f.save(path)
        # cria URL acessível (Render usa pasta /uploads se servida via static)
        public_url = f"/uploads/{filename}"

        photo = Photo(visit_id=visit_id, url=public_url)
        db.session.add(photo)
        saved_photos.append(public_url)

    db.session.commit()
    return jsonify(message="Photos uploaded", urls=saved_photos), 201



@bp.route('/photos/<int:photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    """Exclui uma foto específica do banco e do disco"""
    try:
        photo = Photo.query.get(photo_id)
        if not photo:
            return jsonify(message="Foto não encontrada"), 404

        # Exclui o arquivo físico
        if os.path.exists(photo.url.replace('/uploads/', 'uploads/')):
            os.remove(photo.url.replace('/uploads/', 'uploads/'))

        db.session.delete(photo)
        db.session.commit()

        return jsonify(message="Foto excluída com sucesso"), 200

    except Exception as e:
        print(f"⚠️ Erro ao excluir foto: {e}")
        return jsonify(error=str(e)), 500




@bp.route('/phenology/schedule', methods=['GET'])
def get_phenology_schedule():
    """
    Retorna o cronograma fenológico para uma cultura e data de plantio.
    Exemplo de uso:
    /api/phenology/schedule?culture=Milho&planting_date=2025-10-12
    """
    culture = request.args.get('culture')
    planting_date = request.args.get('planting_date')

    if not culture or not planting_date:
        return jsonify(message="culture and planting_date required"), 400

    try:
        from datetime import datetime, timedelta
        planting_date = datetime.fromisoformat(planting_date).date()
    except Exception:
        return jsonify(message="invalid planting_date, expected YYYY-MM-DD"), 400

    stages = PhenologyStage.query.filter_by(culture=culture).order_by(PhenologyStage.days_after_planting).all()
    if not stages:
        return jsonify([]), 200

    events = []
    for st in stages:
        date = planting_date + timedelta(days=st.days_after_planting)
        events.append({
            "stage": st.name,
            "code": st.code,
            "suggested_date": date.isoformat(),
            "color": "#60a5fa",  # azul para visitas planejadas
        })

    return jsonify(events), 200

# ============================================================
# 🔧 TESTES E UTILITÁRIOS
# ============================================================

@bp.route('/ping')
def ping():
    return jsonify({"status": "ok"}), 200


@bp.route('/status')
def status():
    return jsonify({
        "ok": True,
        "clients": Client.query.count(),
        "properties": Property.query.count(),
        "plots": Plot.query.count(),
        "visits": Visit.query.count(),
    }), 200



@bp.route('/hello', methods=['GET'])
def hello():
    return jsonify(message="Hello from Flask!")


@bp.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([{'id': u.id, 'email': u.email} for u in users])


# ---- Clients CRUD -------------------------------------------------
from models import Client


@bp.route('/clients', methods=['GET'])
def get_clients():
    """Return list of clients."""
    clients = Client.query.order_by(Client.id.desc()).all()
    return jsonify([c.to_dict() for c in clients]), 200


@bp.route('/clients/<int:client_id>', methods=['GET'])
def get_client(client_id: int):
    client = Client.query.get(client_id)
    if not client:
        return jsonify(message='client not found'), 404
    return jsonify(client.to_dict()), 200


@bp.route('/clients', methods=['POST'])
def create_client():
    data = request.get_json() or {}
    name = data.get('name')
    if not name:
        return jsonify(message='name is required'), 400

    client = Client(
        name=name,
        document=data.get('document'),
        segment=data.get('segment'),
        vendor=data.get('vendor'),
    )
    db.session.add(client)
    db.session.commit()
    return jsonify(message='client created', client=client.to_dict()), 201


@bp.route('/clients/<int:client_id>', methods=['PUT'])
def update_client(client_id: int):
    client = Client.query.get(client_id)
    if not client:
        return jsonify(message='client not found'), 404
    data = request.get_json() or {}
    # Update allowed fields if present
    for field in ('name', 'document', 'segment', 'vendor'):
        if field in data:
            setattr(client, field, data.get(field))
    db.session.commit()
    return jsonify(message='client updated', client=client.to_dict()), 200


@bp.route('/clients/<int:client_id>', methods=['DELETE'])
def delete_client(client_id: int):
    client = Client.query.get(client_id)
    if not client:
        return jsonify(message='client not found'), 404
    db.session.delete(client)
    db.session.commit()
    return jsonify(message='client deleted'), 200


# ---- Properties CRUD -------------------------------------------------
from models import Property


@bp.route('/properties', methods=['GET'])
def get_properties():
    """List properties. Optional query param: client_id to filter by client."""
    client_id = request.args.get('client_id', type=int)
    q = Property.query
    if client_id:
        q = q.filter_by(client_id=client_id)
    props = q.order_by(Property.id.desc()).all()
    return jsonify([p.to_dict() for p in props]), 200


@bp.route('/properties/<int:prop_id>', methods=['GET'])
def get_property(prop_id: int):
    p = Property.query.get(prop_id)
    if not p:
        return jsonify(message='property not found'), 404
    return jsonify(p.to_dict()), 200


@bp.route('/properties', methods=['POST'])
def create_property():
    data = request.get_json() or {}
    client_id = data.get('client_id')
    name = data.get('name')
    if not client_id or not name:
        return jsonify(message='client_id and name are required'), 400
    # ensure client exists
    client = Client.query.get(client_id)
    if not client:
        return jsonify(message='client not found'), 404

    prop = Property(
        client_id=client_id,
        name=name,
        city_state=data.get('city_state'),
        area_ha=(float(data.get('area_ha')) if data.get('area_ha') is not None else None),
    )
    db.session.add(prop)
    db.session.commit()
    return jsonify(message='property created', property=prop.to_dict()), 201


@bp.route('/properties/<int:prop_id>', methods=['PUT'])
def update_property(prop_id: int):
    p = Property.query.get(prop_id)
    if not p:
        return jsonify(message='property not found'), 404
    data = request.get_json() or {}
    for field in ('name', 'city_state', 'area_ha', 'client_id'):
        if field in data:
            # convert area_ha to float when provided
            if field == 'area_ha':
                setattr(p, field, float(data.get(field)) if data.get(field) is not None else None)
            else:
                setattr(p, field, data.get(field))

    # If client_id was changed, ensure the client exists
    if 'client_id' in data and data.get('client_id') is not None:
        if not Client.query.get(data.get('client_id')):
            return jsonify(message='client not found'), 404

    db.session.commit()
    return jsonify(message='property updated', property=p.to_dict()), 200


@bp.route('/properties/<int:prop_id>', methods=['DELETE'])
def delete_property(prop_id: int):
    p = Property.query.get(prop_id)
    if not p:
        return jsonify(message='property not found'), 404
    db.session.delete(p)
    db.session.commit()
    return jsonify(message='property deleted'), 200


# ---- Plots (Talhões) CRUD -------------------------------------------
from models import Plot


@bp.route('/plots', methods=['GET'])
def get_plots():
    try:
        property_id = request.args.get('property_id', type=int)
        client_id = request.args.get('client_id', type=int)
        q = Plot.query
        if property_id:
            q = q.filter_by(property_id=property_id)
        if client_id:
            q = q.join(Property).filter(Property.client_id == client_id)
        plots = q.order_by(Plot.id.desc()).all()
        return jsonify([pl.to_dict() for pl in plots]), 200
    except Exception as e:
        print(f"❌ Erro em /plots: {e}")
        return jsonify(error=str(e)), 500



@bp.route('/plots/<int:plot_id>', methods=['GET'])
def get_plot(plot_id: int):
    pl = Plot.query.get(plot_id)
    if not pl:
        return jsonify(message='plot not found'), 404
    return jsonify(pl.to_dict()), 200


@bp.route('/plots', methods=['POST'])
def create_plot():
    data = request.get_json() or {}
    property_id = data.get('property_id')
    name = data.get('name')
    if not property_id or not name:
        return jsonify(message='property_id and name are required'), 400
    prop = Property.query.get(property_id)
    if not prop:
        return jsonify(message='property not found'), 404

    irrigated = data.get('irrigated')
    # normalize irrigated to boolean or None
    if irrigated is not None:
        if isinstance(irrigated, str):
            irrigated = irrigated.lower() in ('1', 'true', 'yes', 'sim')
        else:
            irrigated = bool(irrigated)

    pl = Plot(
        property_id=property_id,
        name=name,
        area_ha=(float(data.get('area_ha')) if data.get('area_ha') is not None else None),
        irrigated=irrigated,
    )
    db.session.add(pl)
    db.session.commit()
    return jsonify(message='plot created', plot=pl.to_dict()), 201


@bp.route('/plots/<int:plot_id>', methods=['PUT'])
def update_plot(plot_id: int):
    pl = Plot.query.get(plot_id)
    if not pl:
        return jsonify(message='plot not found'), 404
    data = request.get_json() or {}
    for field in ('name', 'area_ha', 'irrigated', 'property_id'):
        if field in data:
            if field == 'area_ha':
                setattr(pl, field, float(data.get(field)) if data.get(field) is not None else None)
            elif field == 'irrigated':
                v = data.get(field)
                if isinstance(v, str):
                    v = v.lower() in ('1', 'true', 'yes', 'sim')
                else:
                    v = bool(v)
                setattr(pl, field, v)
            else:
                setattr(pl, field, data.get(field))

    if 'property_id' in data and data.get('property_id') is not None:
        if not Property.query.get(data.get('property_id')):
            return jsonify(message='property not found'), 404

    db.session.commit()
    return jsonify(message='plot updated', plot=pl.to_dict()), 200


@bp.route('/plots/<int:plot_id>', methods=['DELETE'])
def delete_plot(plot_id: int):
    pl = Plot.query.get(plot_id)
    if not pl:
        return jsonify(message='plot not found'), 404
    db.session.delete(pl)
    db.session.commit()
    return jsonify(message='plot deleted'), 200


# ---- Plantings (Plantios) CRUD --------------------------------------
from models import Planting
from datetime import datetime


@bp.route('/plantings', methods=['GET'])
def get_plantings():
    """List plantings. Optional filters: plot_id, property_id, client_id"""
    plot_id = request.args.get('plot_id', type=int)
    property_id = request.args.get('property_id', type=int)
    client_id = request.args.get('client_id', type=int)

    q = Planting.query
    if plot_id:
        q = q.filter_by(plot_id=plot_id)
    if property_id:
        q = q.join(Plot).filter(Plot.property_id == property_id)
    if client_id:
        q = q.join(Plot).join(Property).filter(Property.client_id == client_id)

    items = q.order_by(Planting.id.desc()).all()
    return jsonify([it.to_dict() for it in items]), 200


@bp.route('/plantings/<int:pid>', methods=['GET'])
def get_planting(pid: int):
    p = Planting.query.get(pid)
    if not p:
        return jsonify(message='planting not found'), 404
    return jsonify(p.to_dict()), 200


@bp.route('/plantings', methods=['POST'])
def create_planting():
    data = request.get_json() or {}
    plot_id = data.get('plot_id')
    if not plot_id:
        return jsonify(message='plot_id is required'), 400

    plot = Plot.query.get(plot_id)
    if not plot:
        return jsonify(message='plot not found'), 404

    # cultura e variedade podem vir do select do frontend
    culture = data.get('culture')  # esperado: "Milho", "Soja", "Algodão" (case-insensitive ok)
    variety = data.get('variety')

    planting_date = None
    if data.get('planting_date'):
        try:
            planting_date = datetime.fromisoformat(data.get('planting_date')).date()
        except Exception:
            return jsonify(message='invalid planting_date, expected YYYY-MM-DD'), 400

    p = Planting(
        plot_id=plot_id,
        culture=culture,
        variety=variety,
        planting_date=planting_date,
    )
    db.session.add(p)
    db.session.flush()  # para ter p.id

    # === Gerar Visitas automáticas pela fenologia ===
    # Só se tivermos planting_date e culture mapeada
    if planting_date and culture:
        key = culture.strip().lower()
        stages = PHENOLOGY_TABLES.get(key)
        if stages:
            # precisamos de client_id e property_id a partir do plot
            prop = Property.query.get(plot.property_id) if plot.property_id else None
            client = Client.query.get(prop.client_id) if (prop and prop.client_id) else None

            for st in stages:
                try:
                    visit_date = planting_date + datetime.timedelta(days=int(st['days']))
                except Exception:
                    continue  # ignora entrada inválida

                v = Visit(
                    client_id=(client.id if client else None),
                    property_id=(prop.id if prop else None),
                    plot_id=plot.id,
                    planting_id=p.id,
                    consultant_id=None,          # opcional — pode preencher depois
                    date=visit_date,
                    checklist=None,
                    diagnosis=None,
                    recommendation=f"{st['name']} ({st['code']}) — {culture}",
                )
                db.session.add(v)

    db.session.commit()
    return jsonify(message='planting created', planting=p.to_dict()), 201



@bp.route('/plantings/<int:pid>', methods=['PUT'])
def update_planting(pid: int):
    p = Planting.query.get(pid)
    if not p:
        return jsonify(message='planting not found'), 404
    data = request.get_json() or {}

    if 'plot_id' in data and data.get('plot_id') is not None:
        if not Plot.query.get(data.get('plot_id')):
            return jsonify(message='plot not found'), 404
        p.plot_id = data.get('plot_id')

    if 'culture' in data:
        p.culture = data.get('culture')
    if 'variety' in data:
        p.variety = data.get('variety')
    if 'planting_date' in data:
        if data.get('planting_date') in (None, ''):
            p.planting_date = None
        else:
            try:
                p.planting_date = datetime.fromisoformat(data.get('planting_date')).date()
            except Exception:
                return jsonify(message='invalid planting_date, expected YYYY-MM-DD'), 400

    db.session.commit()
    return jsonify(message='planting updated', planting=p.to_dict()), 200


@bp.route('/plantings/<int:pid>', methods=['DELETE'])
def delete_planting(pid: int):
    p = Planting.query.get(pid)
    if not p:
        return jsonify(message='planting not found'), 404
    db.session.delete(p)
    db.session.commit()
    return jsonify(message='planting deleted'), 200


# ---- Visits (Visitas) CRUD ------------------------------------------
from models import Visit
from datetime import date

# ---- Opportunities CRUD --------------------------------------------
from models import Opportunity


@bp.route('/opportunities', methods=['GET'])
def get_opportunities():
    """List opportunities. Optional filter: client_id"""
    client_id = request.args.get('client_id', type=int)
    q = Opportunity.query
    if client_id:
        q = q.filter_by(client_id=client_id)
    items = q.order_by(Opportunity.id.desc()).all()
    return jsonify([it.to_dict() for it in items]), 200


@bp.route('/opportunities/<int:oid>', methods=['GET'])
def get_opportunity(oid: int):
    o = Opportunity.query.get(oid)
    if not o:
        return jsonify(message='opportunity not found'), 404
    return jsonify(o.to_dict()), 200


@bp.route('/opportunities', methods=['POST'])
def create_opportunity():
    data = request.get_json() or {}
    client_id = data.get('client_id')
    if not client_id:
        return jsonify(message='client_id is required'), 400
    if not Client.query.get(client_id):
        return jsonify(message='client not found'), 404

    title = data.get('title')
    estimated_value = data.get('estimated_value')
    stage = data.get('stage') or 'prospecção'

    try:
        estimated_value = float(estimated_value) if estimated_value is not None else None
    except Exception:
        return jsonify(message='estimated_value must be a number'), 400

    o = Opportunity(
        client_id=client_id,
        title=title,
        estimated_value=estimated_value,
        stage=stage,
    )
    db.session.add(o)
    db.session.commit()
    return jsonify(message='opportunity created', opportunity=o.to_dict()), 201


@bp.route('/opportunities/<int:oid>', methods=['PUT'])
def update_opportunity(oid: int):
    o = Opportunity.query.get(oid)
    if not o:
        return jsonify(message='opportunity not found'), 404
    data = request.get_json() or {}
    if 'client_id' in data and data.get('client_id') is not None:
        if not Client.query.get(data.get('client_id')):
            return jsonify(message='client not found'), 404
        o.client_id = data.get('client_id')
    if 'title' in data:
        o.title = data.get('title')
    if 'estimated_value' in data:
        try:
            o.estimated_value = float(data.get('estimated_value')) if data.get('estimated_value') is not None else None
        except Exception:
            return jsonify(message='estimated_value must be a number'), 400
    if 'stage' in data:
        o.stage = data.get('stage') or 'prospecção'

    db.session.commit()
    return jsonify(message='opportunity updated', opportunity=o.to_dict()), 200


@bp.route('/opportunities/<int:oid>', methods=['DELETE'])
def delete_opportunity(oid: int):
    o = Opportunity.query.get(oid)
    if not o:
        return jsonify(message='opportunity not found'), 404
    db.session.delete(o)
    db.session.commit()
    return jsonify(message='opportunity deleted'), 200


@bp.route('/db-test', methods=['GET'])
def db_test():
    """Simple endpoint to test DB connectivity and return user count."""
    try:
        # run a trivial select to verify connection
        result = None
        with db.engine.connect() as conn:
            row = conn.execute(text('SELECT 1')).fetchone()
            result = row[0] if row is not None else None

        # also give a user count
        user_count = User.query.count()
        return jsonify(status='ok', ping=result, users=user_count), 200
    except Exception as e:
        return jsonify(status='error', error=str(e)), 500


@bp.route('/users', methods=['POST'])
def create_user():
    """Create a new user. Expects JSON: {email, password}"""
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify(message='email and password are required'), 400

    if User.query.filter_by(email=email).first():
        return jsonify(message='user with that email already exists'), 409

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(message='user created', id=user.id, email=user.email), 201


@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify(message='email and password are required'), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify(message='invalid credentials'), 401

    # create JWT
    secret = os.environ.get('JWT_SECRET', 'dev-secret')
    payload = {
        'sub': user.id,
        'email': user.email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    token = jwt.encode(payload, secret, algorithm='HS256')
    return jsonify(message='ok', token=token), 200


def _get_current_user_from_token(req):
    auth = req.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None, 'missing token'
    token = auth.split(' ', 1)[1]
    secret = os.environ.get('JWT_SECRET', 'dev-secret')
    try:
        payload = jwt.decode(token, secret, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None, 'token expired'
    except jwt.InvalidTokenError:
        return None, 'invalid token'

    user = User.query.get(payload.get('sub'))
    if not user:
        return None, 'user not found'
    return user, None


@bp.route('/me', methods=['GET'])
def me():
    user, err = _get_current_user_from_token(request)
    if err:
        return jsonify(message=err), 401
    return jsonify(id=user.id, email=user.email), 200
