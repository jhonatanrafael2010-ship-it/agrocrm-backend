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
from models import db, User, Client, Property, Plot, Visit, Planting, Opportunity, Photo



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

            result.append({
                **v.to_dict(),
                "client_name": client.name if client else f"Cliente {v.client_id}",
                "consultant_name": consultant_name or "—",
                "status": v.status,
                "photos": photos,   # 👈 garante que fotos vão no JSON
            })


        return jsonify(result), 200

    except Exception as e:
        print(f"⚠️ Erro ao listar visitas: {e}")
        return jsonify(error=str(e)), 500



@bp.route('/visits', methods=['POST'])
def create_visit():
    from datetime import date as _d, datetime, timedelta
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    import os

    data = request.get_json(silent=True) or {}
    client_id = data.get('client_id')
    property_id = data.get('property_id') or None
    plot_id = data.get('plot_id') or None
    consultant_id = data.get('consultant_id')
    status = (data.get('status') or 'planned').strip().lower()
    gen_schedule = bool(data.get('generate_schedule'))
    culture = data.get('culture')
    variety = data.get('variety')
    date_str = data.get('date')
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    # Validação mínima
    if not client_id:
        return jsonify(message='client_id is required'), 400
    if not Client.query.get(client_id):
        return jsonify(message='client not found'), 404
    if property_id and not Property.query.get(property_id):
        return jsonify(message='property not found'), 404
    if plot_id and not Plot.query.get(plot_id):
        return jsonify(message='plot not found'), 404

    try:
        visit_date = _d.fromisoformat(date_str)
    except Exception:
        visit_date = _d.today()

    # 🌱 Cria a visita base
    v = Visit(
        client_id=client_id,
        property_id=property_id,
        plot_id=plot_id,
        consultant_id=consultant_id,
        date=visit_date,
        checklist=data.get('checklist'),
        diagnosis=data.get('diagnosis'),
        recommendation=(data.get('recommendation') or '').strip(),
        status=status,
        latitude=latitude,
        longitude=longitude
    )
    db.session.add(v)
    db.session.commit()

    # 🌾 Gera cronograma fenológico se configurado
    if gen_schedule and culture:
        from models import PhenologyStage
        stages = PhenologyStage.query.filter_by(culture=culture).order_by(PhenologyStage.days.asc()).all()
        if culture.strip().lower() == "soja":
            stages = [s for s in stages if "maturação fisiológica" not in s.name.lower()]

        for st in stages:
            if st.days == 0 or "plantio" in st.name.lower():
                continue
            fut_date = visit_date + timedelta(days=int(st.days))
            vv = Visit(
                client_id=client_id,
                property_id=property_id,
                plot_id=plot_id,
                consultant_id=consultant_id,
                date=fut_date,
                recommendation=st.name,
                status='planned'
            )
            db.session.add(vv)
        db.session.commit()

    # 🧾 GERA PDF AUTOMÁTICO (NutriCRM Premium)
    try:
        os.makedirs('static/reports', exist_ok=True)
        pdf_path = f'static/reports/visita_{v.id}.pdf'
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        logo_path = os.path.join('static', 'nutricrm_logo.png')
        if os.path.exists(logo_path):
            elements.append(Image(logo_path, width=5*cm, height=5*cm))
        elements.append(Spacer(1, 0.5*cm))

        elements.append(Paragraph("<b>Relatório de Visita Técnica</b>", styles['Title']))
        elements.append(Spacer(1, 0.3*cm))

        data_table = [
            ["Cliente", str(v.client_id)],
            ["Propriedade", str(property_id or "—")],
            ["Talhão", str(plot_id or "—")],
            ["Data da Visita", str(visit_date)],
            ["Cultura", str(culture or "—")],
            ["Variedade", str(variety or "—")],
            ["Consultor", str(consultant_id or "—")],
            ["Status", str(status)],
            ["Latitude", str(latitude or "—")],
            ["Longitude", str(longitude or "—")],
        ]
        table = Table(data_table, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#a7d38d")),
            ('BOX', (0,0), (-1,-1), 1, colors.black),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 10)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph("<b>Recomendações:</b>", styles['Heading3']))
        elements.append(Paragraph(v.recommendation or "—", styles['BodyText']))
        elements.append(Spacer(1, 0.3*cm))
        elements.append(Paragraph("<b>Diagnóstico:</b>", styles['Heading3']))
        elements.append(Paragraph(v.diagnosis or "—", styles['BodyText']))
        doc.build(elements)

    except Exception as e:
        print(f"⚠️ Erro ao gerar PDF: {e}")

    return jsonify(message='✅ Visita criada com sucesso!', visit=v.to_dict()), 201



@bp.route('/visits/<int:visit_id>/pdf', methods=['GET'])
def get_visit_pdf(visit_id):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    import os

    visit = Visit.query.get_or_404(visit_id)

    # Caminho para salvar o PDF
    os.makedirs('static/reports', exist_ok=True)
    pdf_path = f'static/reports/visita_{visit.id}.pdf'

    # Se já existir, apenas devolve o arquivo
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True)

    # 🔹 Gera o PDF se não existir ainda
    try:
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        logo_path = os.path.join('static', 'nutricrm_logo.png')
        if os.path.exists(logo_path):
            elements.append(Image(logo_path, width=5*cm, height=5*cm))
        elements.append(Spacer(1, 0.5*cm))

        elements.append(Paragraph("<b>Relatório de Visita Técnica</b>", styles['Title']))
        elements.append(Spacer(1, 0.3*cm))

        client_name = visit.client.name if visit.client else "—"
        prop_name = visit.property.name if visit.property else "—"
        plot_name = visit.plot.name if visit.plot else "—"
        consultant_name = visit.consultant.name if visit.consultant else "—"

        data_table = [
            ["Cliente", client_name],
            ["Propriedade", prop_name],
            ["Talhão", plot_name],
            ["Data da Visita", str(visit.date)],
            ["Cultura", str(getattr(visit, 'culture', '—'))],
            ["Variedade", str(getattr(visit, 'variety', '—'))],
            ["Consultor", consultant_name],
            ["Status", visit.status or "—"],
            ["Latitude", str(visit.latitude or "—")],
            ["Longitude", str(visit.longitude or "—")],
        ]
        table = Table(data_table, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#a7d38d")),
            ('BOX', (0,0), (-1,-1), 1, colors.black),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 10)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 0.5*cm))

        elements.append(Paragraph("<b>Recomendações:</b>", styles['Heading3']))
        elements.append(Paragraph(visit.recommendation or "—", styles['BodyText']))
        elements.append(Spacer(1, 0.3*cm))
        elements.append(Paragraph("<b>Diagnóstico:</b>", styles['Heading3']))
        elements.append(Paragraph(visit.diagnosis or "—", styles['BodyText']))

        doc.build(elements)
        return send_file(pdf_path, as_attachment=True)

    except Exception as e:
        print(f"❌ Erro ao gerar PDF: {e}")
        return jsonify(error=str(e)), 500



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


from werkzeug.utils import secure_filename
import os

@bp.route('/visits/<int:visit_id>/photos', methods=['POST'])
def upload_photos(visit_id):
    try:
        visit = Visit.query.get_or_404(visit_id)
        files = request.files.getlist('photos')

        if not files:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400

        upload_dir = UPLOAD_DIR
        os.makedirs(upload_dir, exist_ok=True)

        saved_photos = []

        for file in files:
            filename = secure_filename(file.filename)
            # garante nome único no Render
            unique_name = f"{visit_id}_{os.urandom(8).hex()}_{filename}"
            file_path = os.path.join(upload_dir, unique_name)
            file.save(file_path)

            # monta URL pública correta (Render ou local)
            backend_url = (os.environ.get("RENDER_EXTERNAL_URL") or "https://agrocrm-backend.onrender.com").rstrip("/")
            url = f"{backend_url}/uploads/{unique_name}"

            photo = Photo(visit_id=visit_id, url=url)
            db.session.add(photo)
            saved_photos.append(photo)


        db.session.commit()
        print(f"✅ {len(saved_photos)} fotos salvas para visita {visit_id}")
        return jsonify({"success": True, "count": len(saved_photos)}), 201

    except Exception as e:
        import traceback
        print("❌ Erro ao salvar fotos:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bp.route("/visits/<int:visit_id>/pdf", methods=["GET"])
def export_visit_pdf(visit_id):
    """📄 Gera PDF NutriCRM Premium com QR Code e assinatura"""
    from models import Visit, Client, Property, Plot, Consultant

    visit = Visit.query.get_or_404(visit_id)
    client = Client.query.get(visit.client_id)
    prop = Property.query.get(visit.property_id)
    plot = Plot.query.get(visit.plot_id)
    consultant = Consultant.query.get(visit.consultant_id) if hasattr(visit, "consultant_id") else None

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=40, rightMargin=40, topMargin=60, bottomMargin=40
    )

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontName = "Helvetica"
    normal.fontSize = 10
    green = colors.HexColor("#26b96a")

    content = []

    # ============================================================
    # 🟢 Cabeçalho verde com logo e data
    # ============================================================
    logo_path = os.path.join("static", "nutricrm_logo.png")
    header_date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    header = Table(
        [[
            Image(logo_path, width=110, height=40) if os.path.exists(logo_path) else Paragraph("<b>NutriCRM</b>", normal),
            Paragraph(f"<b>Emitido em:</b> {header_date}", normal)
        ]],
        colWidths=[350, 150],
    )
    header.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    content.append(header)
    content.append(Spacer(1, 6))
    content.append(Paragraph("<b>Relatório Técnico de Visita</b>", ParagraphStyle("h1", textColor=green, fontSize=18)))
    content.append(Spacer(1, 10))

    # ============================================================
    # 🧾 Bloco de informações
    # ============================================================
    info_data = [
        ["Cliente:", client.name if client else "-"],
        ["Fazenda:", prop.name if prop else "-"],
        ["Talhão:", plot.name if plot else "-"],
        ["Consultor:", consultant.name if consultant else "-"],
        ["Data da Visita:", visit.date.strftime("%d/%m/%Y") if visit.date else "-"],
        ["Cultura:", getattr(visit, "culture", "-")],
        ["Variedade:", getattr(visit, "variety", "-")],
        ["Status:", (visit.status or "").capitalize()],
    ]
    info_table = Table(info_data, colWidths=[120, 380])
    info_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, green),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, 0), green),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ]))
    content.append(info_table)
    content.append(Spacer(1, 15))

    # ============================================================
    # 💬 Diagnóstico e Recomendação
    # ============================================================
    if visit.diagnosis:
        content.append(Paragraph("<b>Diagnóstico:</b>", styles["Heading3"]))
        content.append(Paragraph(visit.diagnosis.replace("\n", "<br/>"), normal))
        content.append(Spacer(1, 8))

    if visit.recommendation:
        content.append(Paragraph("<b>Recomendações Técnicas:</b>", styles["Heading3"]))
        content.append(Paragraph(visit.recommendation.replace("\n", "<br/>"), normal))
        content.append(Spacer(1, 12))

    
    # ============================================================
    # 🗺️ Mapa do Talhão (se houver coordenadas)
    # ============================================================
    if plot and plot.latitude and plot.longitude:
        import requests
        try:
            # Static map API (OpenStreetMap tile)
            map_url = f"https://static-maps.yandex.ru/1.x/?ll={plot.longitude},{plot.latitude}&z=15&size=450,250&l=map&pt={plot.longitude},{plot.latitude},pm2gnl"
            img_data = requests.get(map_url, timeout=10).content
            map_img_path = os.path.join("uploads", f"map_{visit_id}.png")
            with open(map_img_path, "wb") as f:
                f.write(img_data)
            content.append(Spacer(1, 12))
            content.append(Paragraph("<b>Localização do Talhão:</b>", styles["Heading3"]))
            content.append(Image(map_img_path, width=450, height=250))
            content.append(Spacer(1, 10))
        except Exception as e:
            print(f"⚠️ Falha ao gerar mapa: {e}")


    # ============================================================
    # 🖼️ Fotos da visita
    # ============================================================
    photos = getattr(visit, "photos", [])
    if photos:
        content.append(Paragraph("<b>Fotos da Visita:</b>", styles["Heading3"]))
        grid = []
        row = []
        for i, ph in enumerate(photos, start=1):
            img_path = os.path.join("uploads", os.path.basename(ph.url))
            if os.path.exists(img_path):
                row.append(Image(img_path, width=200, height=150))
                if i % 2 == 0:
                    grid.append(row)
                    row = []
        if row:
            grid.append(row)
        for r in grid:
            content.append(Table([r], hAlign="CENTER"))
        content.append(Spacer(1, 20))

    
    # ============================================================
    # 🗺️ Mapa e Coordenadas da Visita
    # ============================================================
    if visit.latitude and visit.longitude:
        import requests
        try:
            # Gera imagem estática do mapa com marcador verde
            map_url = f"https://static-maps.yandex.ru/1.x/?ll={visit.longitude},{visit.latitude}&z=15&size=450,250&l=map&pt={visit.longitude},{visit.latitude},pm2gnl"
            img_data = requests.get(map_url, timeout=10).content

            # salva temporariamente
            map_img_path = os.path.join("uploads", f"map_visit_{visit_id}.png")
            with open(map_img_path, "wb") as f:
                f.write(img_data)

            # adiciona ao PDF
            content.append(Spacer(1, 12))
            content.append(Paragraph("<b>Localização da Visita:</b>", styles["Heading3"]))
            content.append(Image(map_img_path, width=450, height=250))
            content.append(Spacer(1, 6))

            # ✅ Adiciona coordenadas em texto
            coord_text = f"<font size=10 color='gray'>Latitude: {visit.latitude:.5f} / Longitude: {visit.longitude:.5f}</font>"
            content.append(Paragraph(coord_text, styles["Normal"]))
            content.append(Spacer(1, 12))
        except Exception as e:
            print(f"⚠️ Falha ao gerar mapa: {e}")


    # ============================================================
    # ✍️ Assinatura técnica e QR Code
    # ============================================================
    qr_url = f"https://nutricrm.app/visits/{visit_id}"
    qr_code = qr.QrCodeWidget(qr_url)
    bounds = qr_code.getBounds()
    w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
    d = Drawing(60, 60, transform=[60.0 / w, 0, 0, 60.0 / h, 0, 0])
    d.add(qr_code)

    ass_path = os.path.join("static", "assinatura_consultor.png")
    ass_img = Image(ass_path, width=140, height=50) if os.path.exists(ass_path) else Paragraph(" ", normal)

    footer = Table([
        [Paragraph("<b>Assinatura do Consultor:</b>", normal), Paragraph("<b>Ver visita online:</b>", normal)],
        [ass_img, d],
    ], colWidths=[400, 100])
    footer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
    ]))
    content.append(footer)
    content.append(Spacer(1, 10))

    # ============================================================
    # 🌿 Rodapé institucional
    # ============================================================
    content.append(Paragraph(
        "<i>NutriCRM © 2025 — Relatório técnico automatizado</i>",
        ParagraphStyle("footer", fontSize=8, textColor=colors.grey, alignment=1),
    ))

    # ============================================================
    # 💧 Marca d’água NutriCRM
    # ============================================================
    def draw_watermark(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 40)
        canvas.setFillColorRGB(0.15, 0.75, 0.4, alpha=0.08)
        canvas.drawCentredString(300, 400, "NutriCRM")
        canvas.restoreState()

    doc.build(content, onFirstPage=draw_watermark, onLaterPages=draw_watermark)
    buffer.seek(0)

    filename = f"visita_{visit_id}_nutricrm.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")

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

    # Pega coordenadas se existirem no banco
    lat = getattr(plot, "latitude", None)
    lon = getattr(plot, "longitude", None)

    photos = []
    for p in visit.photos:
        photos.append({"url": f"/uploads/{os.path.basename(p.url)}"})

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
            body { background-color:#f9fafb; font-family:'Helvetica'; padding-bottom:60px; }
            header { background:#26b96a; color:white; padding:20px; display:flex; justify-content:space-between; align-items:center; }
            header img { height:50px; }
            .info-card { background:white; border-radius:10px; box-shadow:0 2px 10px rgba(0,0,0,0.05); padding:20px; margin-top:20px; }
            .photos img { width:100%; border-radius:8px; cursor:pointer; transition:transform 0.2s; }
            .photos img:hover { transform:scale(1.02); }
            #map { height:300px; border-radius:10px; margin-top:15px; }
            footer { margin-top:40px; text-align:center; color:#888; }
            .download-btn { background:#26b96a; color:white; padding:10px 18px; border-radius:6px; text-decoration:none; }
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



@bp.route('/photos/<int:photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    """Exclui uma foto específica do banco e do disco"""
    try:
        photo = Photo.query.get(photo_id)
        if not photo:
            return jsonify(message="Foto não encontrada"), 404

        # Extrai nome do arquivo com segurança
        from urllib.parse import urlparse
        parsed = urlparse(photo.url)
        filename = os.path.basename(parsed.path)
        file_path = os.path.join(UPLOAD_DIR, filename)

        # Remove arquivo físico se existir
        if os.path.exists(file_path):
            os.remove(file_path)

        # Remove do banco
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
