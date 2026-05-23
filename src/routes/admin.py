# routes/admin.py
"""
Endpoints administrativos e cron jobs.
- /admin/diseases (GET)
- /admin/diseases/<slug>/image (POST)
- /admin/diseases/upload-batch (POST)
- /admin/generate-seed (GET)
- /admin/seed-stats (GET)
- /cron/daily-reminders (POST)
- /cron/test-reminder/<id> (POST)
- /insights/<id> (GET)
- /reports/monthly.xlsx (GET)
"""

import os
import base64
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_cors import cross_origin

from models import (
    db,
    Client,
    Property,
    Plot,
    Culture,
    Variety,
    Consultant,
    TelegramContactBinding,
)
from services.chatbot_service import send_telegram_message

admin_bp = Blueprint('admin', __name__)


# ================================================================
# REPORTS
# ================================================================

@admin_bp.route("/reports/monthly.xlsx", methods=["GET"])
def report_monthly_xlsx():
    from services.excel_report_service import generate_monthly_xlsx
    return generate_monthly_xlsx(request)


# ================================================================
# DASHBOARD INSIGHTS - Dados agregados para o dashboard
# ================================================================

@admin_bp.route("/dashboard/insights", methods=["GET"])
@cross_origin(origins=["https://agrocrm-frontend.onrender.com", "https://localhost", "capacitor://localhost", "http://localhost"])
def get_dashboard_insights():
    """
    Retorna insights agregados para o dashboard principal.
    - Clientes sem visita há 30+ dias
    - Próximas visitas da semana
    - Visitas por mês (últimos 6 meses)
    - Plantios por estágio fenológico
    """
    from datetime import date, timedelta
    from sqlalchemy import func, extract
    from models import Visit, Planting

    today = date.today()

    # 1) Clientes sem visita há 30+ dias
    threshold_30 = today - timedelta(days=30)
    subq_last_visit = db.session.query(
        Visit.client_id,
        func.max(Visit.date).label("last_visit")
    ).filter(
        Visit.status == "done",
        Visit.client_id.isnot(None),
    ).group_by(Visit.client_id).subquery()

    stale_clients_30 = db.session.query(
        Client.id,
        Client.name,
        subq_last_visit.c.last_visit
    ).join(
        subq_last_visit, Client.id == subq_last_visit.c.client_id
    ).filter(
        subq_last_visit.c.last_visit < threshold_30
    ).order_by(
        subq_last_visit.c.last_visit.asc()
    ).limit(10).all()

    stale_clients = []
    for cid, cname, last_visit in stale_clients_30:
        days = (today - last_visit).days if last_visit else 999
        stale_clients.append({
            "id": cid,
            "name": cname,
            "last_visit": last_visit.isoformat() if last_visit else None,
            "days_since": days,
        })

    # 2) Sugestões de visitas baseadas em fenologia e tempo
    # Dias estimados entre estágios fenológicos (soja/milho)
    STAGE_INTERVALS = {
        "VE": 7, "V1": 7, "V2": 7, "V3": 7, "V4": 7, "V5": 7, "V6": 7,
        "V7": 7, "V8": 7, "V9": 7, "V10": 7, "V11": 7, "V12": 7,
        "R1": 10, "R2": 10, "R3": 12, "R4": 12, "R5": 14,
        "R5.1": 7, "R5.2": 7, "R5.3": 7, "R5.4": 7, "R5.5": 7,
        "R6": 14, "R7": 14, "R8": 21,
    }
    STAGE_NEXT = {
        "VE": "V1", "V1": "V2", "V2": "V3", "V3": "V4", "V4": "V5", "V5": "V6",
        "V6": "V7", "V7": "V8", "V8": "V9", "V9": "V10", "V10": "V11", "V11": "V12",
        "V12": "R1", "R1": "R2", "R2": "R3", "R3": "R4", "R4": "R5",
        "R5": "R5.1", "R5.1": "R5.2", "R5.2": "R5.3", "R5.3": "R5.4", "R5.4": "R5.5",
        "R5.5": "R6", "R6": "R7", "R7": "R8",
    }

    # Busca última visita por cliente com fenologia registrada (últimos 60 dias)
    sixty_days_ago = today - timedelta(days=60)
    subq_latest = db.session.query(
        Visit.client_id,
        func.max(Visit.date).label("last_date")
    ).filter(
        Visit.date >= sixty_days_ago,
        Visit.fenologia_real.isnot(None),
        Visit.fenologia_real != "",
        Visit.client_id.isnot(None),
    ).group_by(Visit.client_id).subquery()

    latest_visits = db.session.query(Visit).join(
        subq_latest,
        db.and_(
            Visit.client_id == subq_latest.c.client_id,
            Visit.date == subq_latest.c.last_date
        )
    ).all()

    suggestions = []
    for v in latest_visits:
        stage = (v.fenologia_real or "").strip().upper()
        if not stage or stage not in STAGE_INTERVALS:
            continue

        days_since = (today - v.date).days if v.date else 0
        interval = STAGE_INTERVALS.get(stage, 14)
        next_stage = STAGE_NEXT.get(stage, "—")

        # Se já passou do intervalo esperado, sugerir visita
        days_until = interval - days_since
        if days_until <= 7:  # Sugerir se falta 7 dias ou menos (ou já passou)
            client = Client.query.get(v.client_id) if v.client_id else None
            priority = "high" if days_until <= 0 else "medium"
            suggestions.append({
                "client_id": v.client_id,
                "client_name": client.name if client else "—",
                "culture": v.culture or "",
                "current_stage": stage,
                "next_stage": next_stage,
                "days_since_visit": days_since,
                "days_until_next": max(0, days_until),
                "priority": priority,
                "reason": "phenology",
            })

    # Ordenar por prioridade (dias_until_next ascending)
    suggestions.sort(key=lambda x: x["days_until_next"])

    # Adicionar clientes sem visita há muito tempo que não estão nas sugestões de fenologia
    suggested_client_ids = {s["client_id"] for s in suggestions}
    for sc in stale_clients[:5]:
        if sc["id"] not in suggested_client_ids and len(suggestions) < 10:
            suggestions.append({
                "client_id": sc["id"],
                "client_name": sc["name"],
                "culture": "",
                "current_stage": "",
                "next_stage": "",
                "days_since_visit": sc["days_since"],
                "days_until_next": 0,
                "priority": "high" if sc["days_since"] > 30 else "medium",
                "reason": "stale",
            })

    suggestions = suggestions[:10]

    # 3) Visitas por mês (últimos 6 meses)
    six_months_ago = today - timedelta(days=180)
    visits_by_month_raw = db.session.query(
        extract('year', Visit.date).label('year'),
        extract('month', Visit.date).label('month'),
        func.count(Visit.id).label('count')
    ).filter(
        Visit.date >= six_months_ago,
        Visit.status == "done",
    ).group_by(
        extract('year', Visit.date),
        extract('month', Visit.date)
    ).order_by(
        extract('year', Visit.date),
        extract('month', Visit.date)
    ).all()

    visits_by_month = []
    for year, month, count in visits_by_month_raw:
        visits_by_month.append({
            "year": int(year),
            "month": int(month),
            "label": f"{int(month):02d}/{int(year)}",
            "count": count,
        })

    # 4) Visitas recentes por estágio fenológico (últimos 30 dias)
    thirty_days_ago = today - timedelta(days=30)
    visits_by_stage_raw = db.session.query(
        Visit.fenologia_real,
        func.count(Visit.id).label('count')
    ).filter(
        Visit.date >= thirty_days_ago,
        Visit.fenologia_real.isnot(None),
        Visit.fenologia_real != "",
    ).group_by(
        Visit.fenologia_real
    ).all()

    phenology_stages = []
    for stage, count in visits_by_stage_raw:
        phenology_stages.append({
            "stage": stage,
            "count": count,
        })

    # Ordenar por estágios fenológicos comuns (V1-Vn, R1-R8)
    stage_order = {
        "VE": 0, "V1": 1, "V2": 2, "V3": 3, "V4": 4, "V5": 5, "V6": 6,
        "V7": 7, "V8": 8, "V9": 9, "V10": 10, "V11": 11, "V12": 12,
        "R1": 20, "R2": 21, "R3": 22, "R4": 23, "R5": 24, "R5.1": 25,
        "R5.2": 26, "R5.3": 27, "R5.4": 28, "R5.5": 29, "R6": 30, "R7": 31, "R8": 32,
    }
    phenology_stages.sort(key=lambda x: stage_order.get(x["stage"], 99))

    return jsonify({
        "ok": True,
        "date": today.isoformat(),
        "stale_clients": stale_clients,
        "stale_clients_count": len(stale_clients),
        "visit_suggestions": suggestions,
        "visit_suggestions_count": len(suggestions),
        "visits_by_month": visits_by_month,
        "phenology_stages": phenology_stages,
    }), 200


# ================================================================
# PROACTIVE INSIGHTS - Lembretes e alertas proativos
# ================================================================

@admin_bp.route("/insights/<int:consultant_id>", methods=["GET"])
@cross_origin(origins=["https://agrocrm-frontend.onrender.com", "https://localhost", "capacitor://localhost", "http://localhost"])
def get_consultant_insights_endpoint(consultant_id: int):
    """
    Retorna insights proativos para um consultor.
    Usado pelo app/site para exibir alertas e lembretes.
    """
    from services.proactive_insights import get_consultant_insights

    consultant = Consultant.query.get(consultant_id)
    if not consultant:
        return jsonify({"ok": False, "error": "Consultor não encontrado"}), 404

    insights = get_consultant_insights(consultant_id)

    return jsonify({
        "ok": True,
        "insights": insights,
    }), 200


# ================================================================
# CRON JOBS
# ================================================================

@admin_bp.route("/cron/daily-reminders", methods=["POST"])
def cron_daily_reminders():
    """
    Endpoint para envio de lembretes diários via Telegram.
    Deve ser chamado por um cron externo (ex: cron-job.org) às 7h.

    Segurança: aceita apenas requests com header X-Cron-Secret válido.
    """
    from services.proactive_insights import (
        get_all_consultants_for_daily_reminder,
        build_daily_reminder_text,
    )

    cron_secret = os.getenv("CRON_SECRET")
    request_secret = request.headers.get("X-Cron-Secret")

    if cron_secret and request_secret != cron_secret:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    consultants = get_all_consultants_for_daily_reminder()
    sent_count = 0
    errors = []

    for c in consultants:
        try:
            text = build_daily_reminder_text(c["consultant_id"], c["consultant_name"])

            if text:
                result = send_telegram_message(
                    chat_id=c["telegram_chat_id"],
                    text=text,
                )
                if result.get("ok"):
                    sent_count += 1
                else:
                    errors.append({
                        "consultant_id": c["consultant_id"],
                        "error": result.get("error", "unknown"),
                    })
        except Exception as e:
            errors.append({
                "consultant_id": c["consultant_id"],
                "error": str(e),
            })

    return jsonify({
        "ok": True,
        "sent": sent_count,
        "total_consultants": len(consultants),
        "errors": errors if errors else None,
    }), 200


@admin_bp.route("/cron/test-reminder/<int:consultant_id>", methods=["POST"])
def cron_test_reminder(consultant_id: int):
    """
    Testa o envio de lembrete para um consultor específico.
    Útil para debug e demonstração.
    """
    from services.proactive_insights import build_daily_reminder_text

    consultant = Consultant.query.get(consultant_id)
    if not consultant:
        return jsonify({"ok": False, "error": "Consultor não encontrado"}), 404

    binding = TelegramContactBinding.query.filter_by(
        consultant_id=consultant_id,
        is_active=True,
    ).first()

    text = build_daily_reminder_text(consultant_id, consultant.name)

    if not text:
        return jsonify({
            "ok": True,
            "message": "Nenhum lembrete relevante para enviar",
            "would_send": False,
        }), 200

    if not binding:
        return jsonify({
            "ok": True,
            "message": "Consultor sem Telegram vinculado",
            "would_send": True,
            "preview": text,
        }), 200

    result = send_telegram_message(
        chat_id=binding.telegram_chat_id,
        text=text,
    )

    return jsonify({
        "ok": result.get("ok", False),
        "message": "Lembrete enviado" if result.get("ok") else "Erro ao enviar",
        "preview": text,
        "telegram_result": result,
    }), 200


# ================================================================
# ADMIN - Gerenciamento de imagens de doenças
# ================================================================

@admin_bp.route("/admin/diseases", methods=["GET"])
def admin_list_diseases():
    """Lista todas as doenças cadastradas e status das imagens."""
    from services.diseases_database import DISEASES_DATABASE, get_r2_base_url

    base_url = get_r2_base_url()
    diseases = []

    for d in DISEASES_DATABASE:
        slug = d.get("slug", "")
        image_url = f"{base_url}/diseases/{slug}.jpg" if base_url else None
        diseases.append({
            "slug": slug,
            "name": d.get("name"),
            "crop": d.get("crop"),
            "type": d.get("type"),
            "image_url": image_url,
            "has_image_url": bool(image_url),
        })

    return jsonify({
        "ok": True,
        "count": len(diseases),
        "r2_base_url": base_url,
        "diseases": diseases,
    }), 200


@admin_bp.route("/admin/diseases/<slug>/image", methods=["POST"])
def admin_upload_disease_image(slug: str):
    """
    Faz upload de imagem para uma doença específica.

    Body (JSON):
        - image_url: URL pública para baixar a imagem
        - image_base64: Imagem em base64 (alternativa)
    """
    from services.diseases_database import DISEASES_DATABASE
    import requests as req

    disease = next((d for d in DISEASES_DATABASE if d.get("slug") == slug), None)
    if not disease:
        return jsonify({"ok": False, "error": f"Doença '{slug}' não encontrada"}), 404

    data = request.get_json(force=True) or {}
    image_url = data.get("image_url", "").strip()
    image_base64 = data.get("image_base64", "").strip()

    if not image_url and not image_base64:
        return jsonify({"ok": False, "error": "Forneça image_url ou image_base64"}), 400

    bucket = os.environ.get("R2_BUCKET")
    public_base = (os.environ.get("R2_PUBLIC_BASE_URL") or "").rstrip("/")

    if not bucket or not public_base:
        return jsonify({"ok": False, "error": "R2 não configurado"}), 500

    try:
        from utils.r2_client import get_r2_client

        if image_url:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "image/*,*/*;q=0.8",
            }
            resp = req.get(image_url, headers=headers, timeout=30, allow_redirects=True)
            resp.raise_for_status()
            image_bytes = resp.content
            content_type = resp.headers.get("Content-Type", "image/jpeg")
        else:
            if "," in image_base64:
                image_base64 = image_base64.split(",", 1)[1]
            image_bytes = base64.b64decode(image_base64)
            content_type = "image/jpeg"

        client = get_r2_client()
        key = f"diseases/{slug}.jpg"

        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=image_bytes,
            ContentType=content_type,
        )

        final_url = f"{public_base}/{key}"

        return jsonify({
            "ok": True,
            "message": f"Imagem enviada para {disease.get('name')}",
            "slug": slug,
            "image_url": final_url,
        }), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@admin_bp.route("/admin/diseases/upload-batch", methods=["POST"])
def admin_upload_disease_images_batch():
    """
    Upload em lote de imagens de doenças.

    Body (JSON):
        - images: [{"slug": "ferrugem-asiatica", "url": "https://..."}]
    """
    import requests as req
    from services.diseases_database import DISEASES_DATABASE
    from utils.r2_client import get_r2_client

    data = request.get_json(force=True) or {}
    images = data.get("images", [])

    if not images:
        return jsonify({"ok": False, "error": "Forneça lista de images"}), 400

    bucket = os.environ.get("R2_BUCKET")
    public_base = (os.environ.get("R2_PUBLIC_BASE_URL") or "").rstrip("/")

    if not bucket or not public_base:
        return jsonify({"ok": False, "error": "R2 não configurado"}), 500

    client = get_r2_client()
    results = []

    for item in images:
        slug = item.get("slug", "").strip()
        url = item.get("url", "").strip()

        if not slug or not url:
            results.append({"slug": slug, "ok": False, "error": "slug ou url faltando"})
            continue

        disease = next((d for d in DISEASES_DATABASE if d.get("slug") == slug), None)
        if not disease:
            results.append({"slug": slug, "ok": False, "error": "slug não encontrado"})
            continue

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            }
            resp = req.get(url, headers=headers, timeout=30, allow_redirects=True)
            resp.raise_for_status()

            key = f"diseases/{slug}.jpg"
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=resp.content,
                ContentType=resp.headers.get("Content-Type", "image/jpeg"),
            )

            results.append({
                "slug": slug,
                "ok": True,
                "image_url": f"{public_base}/{key}",
            })

        except Exception as e:
            results.append({"slug": slug, "ok": False, "error": str(e)})

    success_count = sum(1 for r in results if r.get("ok"))

    return jsonify({
        "ok": True,
        "total": len(images),
        "success": success_count,
        "failed": len(images) - success_count,
        "results": results,
    }), 200


# ================================================================
# ADMIN - SEED DATA GENERATOR
# ================================================================

@admin_bp.route("/admin/generate-seed", methods=["GET"])
def admin_generate_seed():
    """
    Gera seed.json com dados atuais do banco para embutir no APK.
    O arquivo gerado deve ser copiado para frontend/public/seed/data.json
    """
    try:
        consultants = [
            {"id": c.id, "name": c.name}
            for c in Consultant.query.order_by(Consultant.id).all()
        ]

        clients = [
            {"id": c.id, "name": c.name}
            for c in Client.query.order_by(Client.name).all()
        ]

        properties = [
            {"id": p.id, "name": p.name, "client_id": p.client_id}
            for p in Property.query.order_by(Property.name).all()
        ]

        plots = [
            {"id": p.id, "name": p.name, "property_id": p.property_id}
            for p in Plot.query.order_by(Plot.name).all()
        ]

        cultures = [
            {"id": c.id, "name": c.name}
            for c in Culture.query.order_by(Culture.name).all()
        ]

        varieties = [
            {"id": v.id, "name": v.name, "culture_id": v.culture_id, "culture_name": v.culture.name if v.culture else None}
            for v in Variety.query.order_by(Variety.name).all()
        ]

        seed_data = {
            "version": datetime.now().strftime("%Y%m%d_%H%M"),
            "generated_at": datetime.now().isoformat(),
            "consultants": consultants,
            "clients": clients,
            "properties": properties,
            "plots": plots,
            "cultures": cultures,
            "varieties": varieties,
            "_stats": {
                "consultants": len(consultants),
                "clients": len(clients),
                "properties": len(properties),
                "plots": len(plots),
                "cultures": len(cultures),
                "varieties": len(varieties),
            }
        }

        return jsonify(seed_data), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@admin_bp.route("/admin/seed-stats", methods=["GET"])
def admin_seed_stats():
    """Retorna estatísticas do que seria incluído no seed."""
    try:
        return jsonify({
            "ok": True,
            "consultants": Consultant.query.count(),
            "clients": Client.query.count(),
            "properties": Property.query.count(),
            "plots": Plot.query.count(),
            "cultures": Culture.query.count(),
            "varieties": Variety.query.count(),
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
