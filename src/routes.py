import os
import datetime
from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import text
import jwt
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Flowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing, String, Rect
from reportlab.graphics.barcode import qr
from reportlab.pdfgen.canvas import Canvas
from models import db, User, Client, Property, Plot, Visit, Planting, Opportunity, Photo, PhenologyStage




bp = Blueprint('api', __name__, url_prefix='/api')

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/opt/render/project/src/uploads")

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

import os
from flask import current_app, request, jsonify

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

        backend_url = os.environ.get("RENDER_EXTERNAL_URL") or "https://agrocrm-backend.onrender.com"

        for v in items:
            client = Client.query.get(v.client_id)
            consultant_name = next(
                (c["name"] for c in CONSULTANTS if c["id"] == v.consultant_id),
                None
            )

            # ✅ Monta URLs completas das fotos
            backend_url = os.environ.get("RENDER_EXTERNAL_URL") or "http://localhost:5000"
            photos = []
            for p in v.photos:
                # Garante nome limpo
                file_name = os.path.basename(p.url)
                photos.append({
                    "id": p.id,
                    "url": f"{backend_url}/uploads/{file_name}"
                })

            # 🔍 tenta pegar cultura e variedade do Planting, mas se não tiver, usa diretamente da visita (caso venha preenchido)
            culture = None
            variety = None
            if v.planting:
                culture = v.planting.culture
                variety = v.planting.variety
            else:
                culture = getattr(v, "culture", None)
                variety = getattr(v, "variety", None)

            result.append({
                **v.to_dict(),
                "client_name": client.name if client else f"Cliente {v.client_id}",
                "consultant_name": consultant_name or "—",
                "status": v.status,
                "culture": culture or "—",
                "variety": variety or "—",
                "photos": photos,
            })



        return jsonify(result), 200

    except Exception as e:
        print(f"⚠️ Erro ao listar visitas: {e}")
        return jsonify(error=str(e)), 500



@bp.route('/visits', methods=['POST'])
def create_visit():
    """
    Cria uma nova visita.
    Se 'generate_schedule' for True, gera automaticamente o cronograma fenológico
    com base na cultura e na data de plantio.
    """
    from datetime import date as _d, timedelta
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

    # ========================
    # ✅ VALIDAÇÕES BÁSICAS
    # ========================
    if not client_id:
        return jsonify(message="client_id é obrigatório"), 400
    if not Client.query.get(client_id):
        return jsonify(message="cliente não encontrado"), 404
    if property_id and not Property.query.get(property_id):
        return jsonify(message="propriedade não encontrada"), 404
    if plot_id and not Plot.query.get(plot_id):
        return jsonify(message="talhão não encontrado"), 404
    if consultant_id and int(consultant_id) not in {c["id"] for c in CONSULTANTS}:
        return jsonify(message="consultor não encontrado"), 404

    try:
        visit_date = _d.fromisoformat(date_str)
    except Exception:
        return jsonify(message="data inválida, esperado formato YYYY-MM-DD"), 400

    # ======================================================
    # 🌾 GERAÇÃO AUTOMÁTICA DO CRONOGRAMA FENOLÓGICO
    # ======================================================
    from models import PhenologyStage

    p = None
    if gen_schedule:
        if not culture or not variety:
            return jsonify(message="culture e variety são obrigatórios quando gerar cronograma"), 400

        # Cria o registro de plantio, se houver talhão
        if plot_id:
            p = Planting(plot_id=plot_id, culture=culture, variety=variety, planting_date=visit_date)
            db.session.add(p)
            db.session.flush()

        # Visita inicial (plantio)
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

        # Gera visitas futuras conforme fenologia
        stages = PhenologyStage.query.filter_by(culture=culture).order_by(PhenologyStage.days.asc()).all()
        if culture.lower() == "soja":
            stages = [s for s in stages if "maturação fisiológica" not in s.name.lower()]

        for st in stages:
            if st.days == 0 or "plantio" in st.name.lower():
                continue

            fut_date = visit_date + timedelta(days=int(st.days))
            vv = Visit(
                client_id=client_id,
                property_id=property_id or None,
                plot_id=plot_id or None,
                planting_id=p.id if p else None,
                consultant_id=consultant_id,
                date=fut_date,
                recommendation=st.name,
                status='planned',
                culture=culture,
                variety=variety,
                latitude=latitude,
                longitude=longitude
            )
            db.session.add(vv)

        db.session.commit()
        return jsonify(message="visita criada com cronograma", visit=v0.to_dict()), 201

    # ======================================================
    # 🌱 VISITA NORMAL (SEM CRONOGRAMA)
    # ======================================================
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
        longitude=longitude
    )

    # 🌿 Preenche cultura e variedade a partir do plantio, se não vierem do frontend
    if not v.culture and v.plot_id:
        planting = Planting.query.filter_by(plot_id=v.plot_id).order_by(Planting.id.desc()).first()
        if planting:
            v.culture = planting.culture
            v.variety = planting.variety

    db.session.add(v)
    db.session.commit()
    return jsonify(message="visita criada", visit=v.to_dict()), 201




@bp.route('/visits/<int:visit_id>/pdf', methods=['GET'])
def export_visit_pdf(visit_id):
    """
    Gera o PDF técnico da visita:
    - Layout profissional com moldura e sombra nas fotos
    - 2 fotos por linha, legendas abaixo
    - Nome automático: Cliente - Variedade - Visita.pdf
    """
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.graphics.shapes import Drawing, Rect

    visit = Visit.query.get_or_404(visit_id)
    client = Client.query.get(visit.client_id)
    property_ = Property.query.get(visit.property_id) if visit.property_id else None
    plot = Plot.query.get(visit.plot_id) if visit.plot_id else None

    # 🧑‍🌾 Nome do consultor
    consultant_name = None
    if visit.consultant_id:
        match = next((c["name"] for c in CONSULTANTS if c["id"] == visit.consultant_id), None)
        consultant_name = match or f"Consultor {visit.consultant_id}"

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=40, leftMargin=40, topMargin=60, bottomMargin=40)

    # 🎨 Estilos
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Label", fontSize=11, leading=14, textColor=colors.HexColor("#2E7D32"), spaceAfter=6))
    styles.add(ParagraphStyle(name="NormalSmall", fontSize=10, leading=13))
    styles.add(ParagraphStyle(name="PhotoCaption", fontSize=9, textColor=colors.gray, alignment=1, spaceAfter=8))

    story = []

    # ✅ Logo da NutriCRM (mantém proporção original)
    try:
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        logo_path = os.path.join(static_dir, "nutricrm_logo.png")
        if os.path.exists(logo_path):
            logo = Image(logo_path, width=140, height=40)
            logo.hAlign = 'CENTER'
            story.append(logo)
            story.append(Spacer(1, 12))
        else:
            print(f"⚠️ Logo não encontrada: {logo_path}")
    except Exception as e:
        print(f"⚠️ Erro ao carregar logo: {e}")

    # Função utilitária
    def safe(v): return v if v else "-"

    # 🧾 Dados principais
    data_table = [
        ["Cliente:", safe(client.name if client else None)],
        ["Propriedade:", safe(property_.name if property_ else None)],
        ["Talhão:", safe(plot.name if plot else None)],
        ["Cultura:", safe(visit.culture)],
        ["Variedade:", safe(visit.variety)],
        ["Consultor:", safe(consultant_name)],
        ["Data da Visita:", safe(visit.date.strftime("%d/%m/%Y") if visit.date else None)],
        ["Status:", safe(visit.status.capitalize() if visit.status else None)],
    ]
    table = Table(data_table, colWidths=[120, 350])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F5E9")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1B5E20")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOX", (0, 0), (-1, -1), 0.25, colors.gray),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
    ]))
    story.append(table)
    story.append(Spacer(1, 18))

    # 🧠 "Visita"
    story.append(Paragraph("<b>Visita:</b>", styles["Label"]))
    story.append(Paragraph(visit.recommendation or "-", styles["NormalSmall"]))
    story.append(Spacer(1, 12))

    # 📍 GPS
    if visit.latitude and visit.longitude:
        coords_text = f"{visit.latitude:.5f}, {visit.longitude:.5f}"
        story.append(Paragraph("<b>Localização GPS:</b>", styles["Label"]))
        story.append(Paragraph(coords_text, styles["NormalSmall"]))
        story.append(Spacer(1, 12))

    # 🖼️ Fotos da visita — 2 por linha, com moldura e legenda
    if hasattr(visit, "photos") and visit.photos:
        story.append(Paragraph("<b>Fotos da Visita:</b>", styles["Label"]))
        photos = [p for p in visit.photos if p.url]
        row = []

        uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
        for i, photo in enumerate(photos, 1):
            file_name = os.path.basename(photo.url)
            photo_path = os.path.join(uploads_dir, file_name)

            if os.path.exists(photo_path):
                try:
                    img = Image(photo_path, width=250, height=180)
                    img.hAlign = "CENTER"

                    # Moldura e sombra leve
                    frame = Drawing(250, 180)
                    frame.add(Rect(3, -3, 250, 180, fillColor=colors.Color(0, 0, 0, alpha=0.15), strokeWidth=0))
                    frame.add(Rect(0, 0, 250, 180, strokeColor=colors.grey, strokeWidth=0.5, fillColor=None))
                    frame.add(img, name="photo")

                    # Adiciona legenda se houver
                    cell = [frame]
                    if photo.caption:
                        cell.append(Paragraph(photo.caption, styles["PhotoCaption"]))

                    row.append(cell)
                except Exception as e:
                    row.append([Paragraph(f"[Erro ao carregar imagem: {e}]", styles["NormalSmall"])])

            if len(row) == 2 or i == len(photos):
                t = Table([row], colWidths=[260, 260])
                t.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]))
                story.append(t)
                story.append(Spacer(1, 10))
                row = []
    else:
        story.append(Paragraph("<i>Sem fotos anexadas</i>", styles["NormalSmall"]))

    # ✍️ Rodapé
    story.append(Spacer(1, 24))
    story.append(Paragraph("<b>NutriCRM - CRM Inteligente para o Agronegócio</b>", styles["Label"]))
    story.append(Paragraph("Relatório técnico gerado automaticamente via sistema NutriCRM.", styles["NormalSmall"]))

    # 📄 Gera o PDF
    doc.build(story)
    buffer.seek(0)

    filename = f"{safe(client.name)} - {safe(visit.variety)} - {safe(visit.recommendation)}.pdf"

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )





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

    # ✅ Atualiza status da visita (feito via botão “Concluir”)
    if 'status' in data and data['status']:
        v.status = data['status'].strip().lower()

    print("🧠 Atualizando visita", vid, "com dados:", data)
    db.session.commit()
    return jsonify(message='visit updated', visit=v.to_dict() | {"status": v.status}), 200



@bp.route('/visits/<int:visit_id>', methods=['DELETE'])
def delete_visit(visit_id):
    """
    Exclui uma visita. Se for a visita de plantio, remove também o plantio e TODAS
    as visitas geradas automaticamente (fenológicas) do mesmo talhão.
    """
    try:
        visit = Visit.query.get(visit_id)
        if not visit:
            print(f"⚠️ Visita {visit_id} não encontrada.")
            return jsonify({'error': 'Visita não encontrada'}), 404

        print(f"🗑 Solicitada exclusão da visita {visit_id}: {visit.recommendation}")

        # Detecta se é uma visita de plantio
        is_plantio = bool(visit.recommendation and 'plantio' in visit.recommendation.lower())

        if is_plantio:
            # 1️⃣ Identifica o plantio associado
            planting = None
            if visit.planting_id:
                planting = Planting.query.get(visit.planting_id)

            # 2️⃣ Busca TODAS as visitas fenológicas do mesmo talhão após a data do plantio
            future_visits = Visit.query.filter(
                Visit.plot_id == visit.plot_id,
                Visit.date > visit.date
            ).all()

            for fv in future_visits:
                print(f"   → Removendo visita futura {fv.id} ({fv.recommendation})")
                db.session.delete(fv)

            # 3️⃣ Remove também o próprio plantio, se existir
            if planting:
                print(f"🌾 Removendo plantio {planting.id} vinculado.")
                db.session.delete(planting)

            # 4️⃣ Por fim, remove a visita de plantio
            db.session.delete(visit)
            db.session.commit()
            print(f"✅ Plantio e visitas futuras excluídos com sucesso.")
            return jsonify({'message': 'Plantio e visitas futuras excluídos com sucesso'}), 200

        # Caso comum (visita isolada)
        print(f"🧾 Excluindo visita isolada {visit_id}")
        db.session.delete(visit)
        db.session.commit()
        print(f"✅ Visita {visit_id} excluída com sucesso.")
        return jsonify({'message': 'Visita excluída com sucesso'}), 200

    except Exception as e:
        print(f"❌ Erro interno ao excluir visita {visit_id}: {e}")
        db.session.rollback()
        return jsonify({'error': f'Erro interno ao excluir visita: {str(e)}'}), 500




from werkzeug.utils import secure_filename
import os

# ==============================
# 📸 FOTOS — upload, legenda, exclusão (REVISADO)
# ==============================

@bp.route('/visits/<int:visit_id>/photos', methods=['POST'])
def upload_photos(visit_id):
    """Upload de múltiplas fotos com legendas (captions)."""
    visit = Visit.query.get_or_404(visit_id)
    files = request.files.getlist('photos')
    captions = request.form.getlist('captions')  # lista paralela de legendas

    if not files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    saved = []
    for i, file in enumerate(files):
        filename = secure_filename(file.filename)
        save_path = os.path.join(UPLOAD_DIR, filename)
        file.save(save_path)

        # Captura legenda correspondente
        caption = captions[i] if i < len(captions) else None
        photo = Photo(visit_id=visit_id, url=f"/uploads/{filename}", caption=caption)
        db.session.add(photo)
        db.session.flush()  # garante que o ID exista

        saved.append({
            "id": photo.id,
            "url": f"/uploads/{filename}",
            "caption": caption or ""
        })

    db.session.commit()
    return jsonify({"message": f"{len(saved)} foto(s) salvas.", "photos": saved}), 201


@bp.route('/visits/<int:visit_id>/photos', methods=['GET'])
def list_photos(visit_id):
    """Lista todas as fotos de uma visita (com legendas incluídas)."""
    visit = Visit.query.get_or_404(visit_id)
    backend_url = os.environ.get("RENDER_EXTERNAL_URL") or "http://localhost:5000"
    photos = []

    for p in visit.photos:
        file_name = os.path.basename(p.url)
        full_url = f"{backend_url}/uploads/{file_name}"
        photos.append({
            "id": p.id,
            "url": full_url,
            "caption": getattr(p, "caption", "")
        })

    return jsonify(photos), 200


@bp.route('/photos/<int:photo_id>', methods=['PUT'])
def update_photo(photo_id):
    """Atualiza a legenda (caption) de uma foto existente."""
    try:
        data = request.get_json()
        photo = Photo.query.get_or_404(photo_id)

        if 'caption' in data:
            photo.caption = data['caption']

        db.session.commit()
        return jsonify({'success': True, 'caption': photo.caption}), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao atualizar legenda da foto {photo_id}: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/photos/<int:photo_id>', methods=['DELETE'])
def delete_single_photo(photo_id):
    """Exclui uma foto específica do banco e do disco."""
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
        return jsonify({"message": "Foto excluída com sucesso"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Erro ao excluir foto: {e}")
        return jsonify({"error": f"Erro ao excluir foto: {e}"}), 500


@bp.route('/visits/<int:visit_id>/photos', methods=['DELETE'])
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
        return jsonify({"message": f"{count} foto(s) excluídas com sucesso"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Erro ao excluir fotos da visita: {e}")
        return jsonify({"error": str(e)}), 500




from flask import render_template_string

@bp.route("/view/visit/<int:visit_id>", methods=["GET"])
def public_visit_view(visit_id):
    """🌿 Página pública de visualização de visita (NutriCRM Viewer)"""
    from models import Visit, Client, Property, Plot, Consultant
    visit = Visit.query.get_or_404(visit_id)
    client = Client.query.get(visit.client_id)
    prop = Property.query.get(visit.property_id)
    plot = Plot.query.get(visit.plot_id)
    consultant = Consultant.query.get(visit.consultant_id) if hasattr(visit, "consultant_id") else None

    lat = getattr(plot, "latitude", None)
    lon = getattr(plot, "longitude", None)

    photos = []
    for p in visit.photos:
        file_name = os.path.basename(p.url)
        photos.append({"url": f"/uploads/{file_name}"})

    html_template = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Visita #{{ visit.id }} — NutriCRM</title>
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
            <h4>Relatório Técnico — Visita #{{ visit.id }}</h4>
            <a class="download-btn" href="/api/visits/{{ visit.id }}/pdf" target="_blank">📄 Baixar PDF</a>
        </header>

        <main class="container">
            <div class="info-card">
                <h4>Informações Gerais</h4>
                <table class="table table-borderless mt-3">
                    <tr><th>Cliente:</th><td>{{ client.name if client else '-' }}</td></tr>
                    <tr><th>Fazenda:</th><td>{{ prop.name if prop else '-' }}</td></tr>
                    <tr><th>Talhão:</th><td>{{ plot.name if plot else '-' }}</td></tr>
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
                <h4>Diagnóstico</h4>
                <p>{{ visit.diagnosis }}</p>
            </div>
            {% endif %}

            {% if visit.recommendation %}
            <div class="info-card">
                <h4>Recomendações Técnicas</h4>
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
            <small>NutriCRM © 2025 — Relatório técnico automatizado</small>
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
                attribution: '© OpenStreetMap contributors'
            }).addTo(map);
            L.marker([{{ lat }}, {{ lon }}]).addTo(map)
                .bindPopup("{{ plot.name if plot else 'Talhão' }}")
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
    for field in ('name', 'area_ha', 'irrigated', 'property_id', 'latitude', 'longitude'):
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
