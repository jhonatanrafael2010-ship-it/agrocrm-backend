# routes/mobile.py
"""
Endpoints mobile (chat, PDF proxy, transcricao).
- /mobile/chat (POST)
- /mobile/pdf-proxy (GET)
- /mobile/transcribe (POST)
"""

import base64
import gc
import io
import json
import os
import re
import uuid
from typing import Optional

from flask import Blueprint, jsonify, request, make_response
from werkzeug.utils import secure_filename
import requests

from models import (
    db,
    Visit,
    Client,
    Consultant,
    ChatbotConversationState,
    Photo,
)
from utils.r2_client import get_r2_client

mobile_bp = Blueprint('mobile', __name__)


# ============================================================
# HELPERS - Lazy imports para evitar dependencia circular
# ============================================================

def _get_helpers():
    """Lazy import para evitar dependencia circular."""
    from api_routes import (
        parse_chatbot_message,
        find_client_by_name,
        find_property_by_name,
        normalize_products_from_parsed,
        parse_human_date,
        parse_date_flexible,
        parse_pending_reply,
        build_guided_state_payload,
        build_visit_summary_text,
        build_final_visit_payload,
        apply_payload_to_existing_visit,
        create_visit_from_payload,
        auto_close_previous_cycle_visits,
        normalize_lookup_text,
        normalize_culture_input,
        parse_visit_purpose,
        parse_visit_purpose_with_ai,
        is_valid_fenologia,
        parse_fenologia_with_ai,
        parse_pdf_client_reference,
        find_last_completed_visit_for_client_reference,
        find_last_completed_visits_for_consultant,
        build_pdf_visit_selection_text,
        parse_pdf_selection,
        extract_recommendation_fallback,
        extract_prefill_from_message_text,
        _format_recommendation,
        build_consultant_days_planted_portfolio,
        build_consultant_days_planted_text,
        find_stale_clients_ranking,
        build_stale_clients_ranking_text,
        build_month_visits_text,
        build_weekly_report_text,
        build_visit_pdf_file,
        convert_audio_bytes_to_wav,
        transcribe_audio_bytes,
        AGENT_SERVICE,
    )
    return {
        'parse_chatbot_message': parse_chatbot_message,
        'find_client_by_name': find_client_by_name,
        'find_property_by_name': find_property_by_name,
        'normalize_products_from_parsed': normalize_products_from_parsed,
        'parse_human_date': parse_human_date,
        'parse_date_flexible': parse_date_flexible,
        'parse_pending_reply': parse_pending_reply,
        'build_guided_state_payload': build_guided_state_payload,
        'build_visit_summary_text': build_visit_summary_text,
        'build_final_visit_payload': build_final_visit_payload,
        'apply_payload_to_existing_visit': apply_payload_to_existing_visit,
        'create_visit_from_payload': create_visit_from_payload,
        'auto_close_previous_cycle_visits': auto_close_previous_cycle_visits,
        'normalize_lookup_text': normalize_lookup_text,
        'normalize_culture_input': normalize_culture_input,
        'parse_visit_purpose': parse_visit_purpose,
        'parse_visit_purpose_with_ai': parse_visit_purpose_with_ai,
        'is_valid_fenologia': is_valid_fenologia,
        'parse_fenologia_with_ai': parse_fenologia_with_ai,
        'parse_pdf_client_reference': parse_pdf_client_reference,
        'find_last_completed_visit_for_client_reference': find_last_completed_visit_for_client_reference,
        'find_last_completed_visits_for_consultant': find_last_completed_visits_for_consultant,
        'build_pdf_visit_selection_text': build_pdf_visit_selection_text,
        'parse_pdf_selection': parse_pdf_selection,
        'extract_recommendation_fallback': extract_recommendation_fallback,
        'extract_prefill_from_message_text': extract_prefill_from_message_text,
        '_format_recommendation': _format_recommendation,
        'build_consultant_days_planted_portfolio': build_consultant_days_planted_portfolio,
        'build_consultant_days_planted_text': build_consultant_days_planted_text,
        'find_stale_clients_ranking': find_stale_clients_ranking,
        'build_stale_clients_ranking_text': build_stale_clients_ranking_text,
        'build_month_visits_text': build_month_visits_text,
        'build_weekly_report_text': build_weekly_report_text,
        'build_visit_pdf_file': build_visit_pdf_file,
        'convert_audio_bytes_to_wav': convert_audio_bytes_to_wav,
        'transcribe_audio_bytes': transcribe_audio_bytes,
        'AGENT_SERVICE': AGENT_SERVICE,
    }


# ============================================================
# STATE HELPERS
# ============================================================

def _mob_get_state(session_id: str):
    return ChatbotConversationState.query.filter_by(
        platform="mobile", chat_id=session_id
    ).first()


def _mob_ensure_state(session_id: str):
    st = _mob_get_state(session_id)
    if not st:
        st = ChatbotConversationState(platform="mobile", chat_id=session_id)
        db.session.add(st)
    return st


def _mob_cancel_current_flow(session_id: str) -> str:
    state = _mob_get_state(session_id)
    if state:
        old_status = state.status
        db.session.delete(state)
        db.session.commit()
        if old_status and old_status not in ("idle", "none", ""):
            return "Operacao cancelada. Pode comecar um novo comando."
    return "Pronto. Pode enviar um novo comando."


# ============================================================
# PDF HELPERS
# ============================================================

def _visit_pdf_label(visit) -> str:
    parts = []
    if visit.client:
        parts.append(visit.client.name)
    culture_variety = " ".join(filter(None, [visit.culture or "", visit.variety or ""])).strip()
    if culture_variety:
        parts.append(culture_variety)
    if visit.property:
        parts.append(visit.property.name)
    if visit.plot:
        parts.append(visit.plot.name)
    return " - ".join(parts) if parts else f"Visita {visit.id}"


def _upload_pdf_to_r2(pdf_bytes: bytes, filename: str):
    try:
        bucket = os.environ.get("R2_BUCKET")
        public_base = (os.environ.get("R2_PUBLIC_BASE_URL") or "").rstrip("/")
        if not bucket or not public_base:
            return None
        r2 = get_r2_client()
        safe_name = secure_filename(filename or "visita.pdf")
        key = f"mobile_pdf/{uuid.uuid4().hex}_{safe_name}"
        r2.upload_fileobj(
            Fileobj=io.BytesIO(pdf_bytes),
            Bucket=bucket,
            Key=key,
            ExtraArgs={"ContentType": "application/pdf"},
        )
        return f"{public_base}/{key}"
    except Exception as e:
        print(f"Erro ao enviar PDF para R2: {e}")
        return None


def _upload_base64_to_r2(data_url: str, filename: str):
    try:
        bucket = os.environ.get("R2_BUCKET")
        public_base = (os.environ.get("R2_PUBLIC_BASE_URL") or "").rstrip("/")
        if not bucket or not public_base:
            return None
        b64data = data_url.split(",", 1)[1] if "," in data_url else data_url
        img_bytes = base64.b64decode(b64data)
        r2 = get_r2_client()
        safe_name = secure_filename(filename or "foto.jpg")
        key = f"mobile_chat/{uuid.uuid4().hex}_{safe_name}"
        r2.upload_fileobj(
            Fileobj=io.BytesIO(img_bytes),
            Bucket=bucket,
            Key=key,
            ExtraArgs={"ContentType": "image/jpeg"},
        )
        return f"{public_base}/{key}"
    except Exception as e:
        print(f"Erro ao enviar foto para R2: {e}")
        return None


# ============================================================
# MOBILE ENDPOINTS
# ============================================================

@mobile_bp.route("/mobile/pdf-proxy", methods=["GET"])
def mobile_pdf_proxy():
    """Proxy para PDFs no R2 - contorna CORS no WebView."""
    target_url = request.args.get("url", "").strip()
    public_base = (os.environ.get("R2_PUBLIC_BASE_URL") or "").rstrip("/")
    if not target_url or not public_base or not target_url.startswith(public_base + "/"):
        return jsonify({"error": "URL invalida ou nao autorizada"}), 403
    try:
        r = requests.get(target_url, timeout=30)
        r.raise_for_status()
        filename = target_url.split("/")[-1].split("?")[0] or "visita.pdf"
        resp = make_response(r.content)
        resp.headers["Content-Type"] = "application/pdf"
        resp.headers["Content-Disposition"] = f"inline; filename={filename}"
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@mobile_bp.route("/mobile/chat", methods=["POST"])
def mobile_chat():
    data = request.get_json(force=True) or {}
    session_id = (data.get("session_id") or request.headers.get("X-Session-Id", "")).strip()
    message_text = (data.get("message") or "").strip()
    consultant_id_raw = data.get("consultant_id") or request.headers.get("X-Consultant-Id")
    photos = data.get("photos") or []

    if not session_id:
        return jsonify({"ok": False, "error": "session_id obrigatorio"}), 400

    consultant = None
    resolved_consultant_id = None
    if consultant_id_raw:
        try:
            cid = int(consultant_id_raw)
            consultant = Consultant.query.get(cid)
            if consultant:
                resolved_consultant_id = cid
        except (ValueError, TypeError):
            pass

    state = _mob_get_state(session_id)
    status = state.status if state else None

    if status == "awaiting_final_confirmation":
        resp = _mob_final_confirmation(session_id, state, message_text, resolved_consultant_id, photos)
    elif status == "awaiting_confirmation":
        resp = _mob_awaiting_confirmation(session_id, state, message_text, resolved_consultant_id)
    elif status == "awaiting_client_confirmation":
        resp = _mob_client_confirmation(session_id, state, message_text, consultant, resolved_consultant_id)
    elif status in ("awaiting_fenologia", "awaiting_date", "awaiting_observations", "awaiting_culture", "awaiting_purpose"):
        resp = _mob_guided_field(session_id, state, message_text, status)
    elif status == "awaiting_visit_details":
        resp = _mob_visit_details_with_stored_photos(session_id, state, message_text, photos, consultant, resolved_consultant_id)
    elif status == "awaiting_pdf_selection":
        resp = _mob_pdf_selection(session_id, state, message_text)
    else:
        resp = _mob_new_message(session_id, message_text, photos, consultant, resolved_consultant_id)

    if isinstance(resp, dict):
        result = {"ok": True, "response": resp.get("text", "")}
        if resp.get("pdf_items"):
            result["pdf_items"] = resp["pdf_items"]
        if resp.get("image_url"):
            result["image_url"] = resp["image_url"]
        if resp.get("source"):
            result["source"] = resp["source"]
        return jsonify(result), 200
    return jsonify({"ok": True, "response": resp}), 200


@mobile_bp.route("/mobile/transcribe", methods=["POST"])
def mobile_transcribe():
    h = _get_helpers()
    data = request.get_json(force=True) or {}
    audio_b64 = (data.get("audio_base64") or "").strip()
    audio_format = (data.get("format") or "webm").strip().lstrip(".")

    if not audio_b64:
        return jsonify({"ok": False, "error": "audio_base64 obrigatorio"}), 400

    try:
        b64clean = audio_b64.split(",", 1)[1] if "," in audio_b64 else audio_b64
        audio_bytes = base64.b64decode(b64clean)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Base64 invalido: {e}"}), 400

    wav_bytes, err = h['convert_audio_bytes_to_wav'](audio_bytes, input_suffix=f".{audio_format}")
    if err or not wav_bytes:
        return jsonify({"ok": False, "error": f"Conversao de audio falhou: {err}"}), 500

    text, err = h['transcribe_audio_bytes'](wav_bytes, filename="audio.wav")
    if err or not text:
        return jsonify({"ok": False, "error": f"Transcricao falhou: {err}"}), 500

    return jsonify({"ok": True, "text": text}), 200


# ============================================================
# CHAT FLOW HANDLERS
# ============================================================

def _mob_new_message(session_id, message_text, photos, consultant, resolved_consultant_id):
    h = _get_helpers()

    is_photo_only = (not message_text or message_text == "(foto)") and bool(photos)
    if is_photo_only:
        photo_urls = []
        for p in photos:
            url = _upload_base64_to_r2(p.get("dataUrl", ""), p.get("filename", "foto.jpg"))
            if url:
                photo_urls.append(url)
        state = _mob_ensure_state(session_id)
        state.visit_preview_json = json.dumps({"pending_photos": photo_urls}, ensure_ascii=False)
        state.status = "awaiting_visit_details"
        db.session.commit()
        n = len(photo_urls)
        s = "s" if n != 1 else ""
        return (
            f"{n} foto{s} recebida{s}!\n"
            "Agora informe os detalhes da visita:\n"
            "Exemplo: cliente Joao Silva soja R5 ontem"
        )

    from services.agent.conversation_memory import (
        add_message as add_conv_message,
        get_conversation_context,
    )

    if message_text:
        add_conv_message(
            platform="mobile",
            chat_id=session_id,
            text=message_text,
            role="user",
        )

    conv_context = get_conversation_context("mobile", session_id)

    context = {
        "platform": "mobile",
        "chat_id": session_id,
        "consultant_id": resolved_consultant_id,
        "consultant_name": consultant.name if consultant else None,
        "current_state": "",
        "message_text": message_text,
        "recent_messages": conv_context.recent_messages,
        "last_intent": conv_context.last_intent,
        "last_entities": conv_context.last_entities,
        "last_visit_id": conv_context.last_visit_id,
        "last_client_name": conv_context.last_client_name,
        "last_culture": conv_context.last_culture,
    }

    agent_result = h['AGENT_SERVICE'].process(message_text=message_text, context=context)
    execution = agent_result.get("execution") or {}
    action = execution.get("action")
    entities = execution.get("entities") or {}

    if not action or execution.get("should_fallback", True):
        return (
            "Nao entendi. Exemplos:\n"
            "- cliente Joao Silva soja R5 ontem observacao...\n"
            "- agenda da semana\n"
            "- meu dia"
        )

    if action == "START_GUIDED_VISIT_FROM_FREE_TEXT":
        return _mob_start_visit_flow(session_id, message_text, entities, consultant, resolved_consultant_id, photos)

    if action == "ROUTE_TO_WEEK_SCHEDULE":
        return _mob_week_schedule_text(consultant, resolved_consultant_id)

    if action == "ROUTE_TO_DAILY_ROUTINE":
        return _mob_daily_routine_text(consultant, resolved_consultant_id)

    if action == "ROUTE_TO_PDF":
        return _mob_pdf_flow(message_text, consultant, resolved_consultant_id, session_id)

    if action == "ROUTE_TO_PLANTING_DAYS":
        return _mob_planting_days_text(consultant)

    if action == "ROUTE_TO_STALE_CLIENTS":
        return _mob_stale_clients_text(consultant)

    if action == "ROUTE_TO_MONTH_VISITS":
        return _mob_month_visits_text(consultant, resolved_consultant_id)

    if action == "ROUTE_TO_PEST_DIAGNOSIS":
        return _mob_pest_diagnosis(message_text)

    if action == "ADD_TO_EXISTING_VISIT":
        decision = agent_result.get("decision") or {}
        visit_id = decision.get("visit_id")
        return _mob_add_to_existing_visit(session_id, message_text, visit_id)

    if action == "ROUTE_TO_WEEKLY_REPORT":
        return _mob_weekly_report_text(consultant)

    if action == "ROUTE_TO_CANCEL":
        return _mob_cancel_current_flow(session_id)

    if action == "ROUTE_TO_CONFIRM":
        return "Nao ha nada pendente para confirmar. Envie uma visita ou comando."

    return "Acao reconhecida mas ainda nao suportada no app. Use: 'cliente Nome cultura fenologia data observacoes'."


def _mob_visit_details_with_stored_photos(session_id, state, message_text, photos, consultant, resolved_consultant_id):
    try:
        preview_data = json.loads(state.visit_preview_json or "{}")
    except Exception:
        preview_data = {}
    stored_photo_urls = preview_data.get("pending_photos") or []
    stored_photos = [{"url": u, "filename": u.split("/")[-1]} for u in stored_photo_urls]
    combined_photos = stored_photos + list(photos or [])
    db.session.delete(state)
    db.session.commit()
    return _mob_new_message(session_id, message_text, combined_photos, consultant, resolved_consultant_id)


def _mob_pdf_flow(message_text: str, consultant, resolved_consultant_id, session_id: str):
    h = _get_helpers()

    if not consultant:
        return "Nenhum consultor selecionado. Volte e escolha seu nome."

    client_ref = h['parse_pdf_client_reference'](message_text)
    if client_ref:
        visit = h['find_last_completed_visit_for_client_reference'](
            consultant_id=consultant.id,
            client_name=client_ref,
        )
        if not visit:
            return f"Nao encontrei visita concluida para {client_ref}."
        try:
            buffer, filename = h['build_visit_pdf_file'](visit.id)
            url = _upload_pdf_to_r2(buffer.getvalue(), filename)
            if not url:
                return "PDF gerado, mas falhou ao salvar. Verifique a configuracao do R2."
            return {
                "text": "PDF pronto!",
                "pdf_items": [{"url": url, "label": _visit_pdf_label(visit), "filename": filename}],
            }
        except Exception as e:
            return f"Erro ao gerar PDF: {str(e)}"

    recent = h['find_last_completed_visits_for_consultant'](consultant.id, limit=10)
    if not recent:
        return "Nao encontrei nenhuma visita concluida para gerar PDF."

    state = _mob_ensure_state(session_id)
    state.pending_visit_suggestions_json = json.dumps(
        [{"id": v.id} for v in recent], ensure_ascii=False
    )
    state.status = "awaiting_pdf_selection"
    db.session.commit()
    return h['build_pdf_visit_selection_text'](recent)


def _mob_pdf_selection(session_id: str, state, message_text: str):
    h = _get_helpers()

    if message_text.strip().upper() == "CANCELAR":
        state.status = ""
        db.session.commit()
        return "Cancelado."

    selected_indexes = h['parse_pdf_selection'](message_text)
    if not selected_indexes:
        return "Opcao invalida. Responda com um numero ou varios, como 1,3 ou 1 3 5.\nDigite CANCELAR para sair."

    if len(selected_indexes) > 3:
        return "Selecione no maximo 3 PDFs por vez para evitar sobrecarga. Ex: 1,2,3"

    pdf_candidates = json.loads(state.pending_visit_suggestions_json or "[]")
    invalid = [i for i in selected_indexes if i < 0 or i >= len(pdf_candidates)]
    if invalid:
        return "Uma ou mais opcoes sao invalidas. Revise os numeros e tente novamente."

    items = []
    for idx in selected_indexes:
        visit_id = pdf_candidates[idx]["id"]
        try:
            visit = Visit.query.get(visit_id)
            buffer, filename = h['build_visit_pdf_file'](visit_id)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            del buffer
            url = _upload_pdf_to_r2(pdf_bytes, filename)
            del pdf_bytes
            gc.collect()
            if url:
                items.append({"url": url, "label": _visit_pdf_label(visit), "filename": filename})
        except Exception:
            pass

    state.status = ""
    db.session.commit()

    if not items:
        return "Erro ao gerar os PDFs. Tente novamente."

    n = len(items)
    text = "PDF pronto!" if n == 1 else f"{n} PDFs prontos!"
    return {"text": text, "pdf_items": items}


def _mob_start_visit_flow(session_id, original_message, entities, consultant, resolved_consultant_id, photos):
    h = _get_helpers()

    client_name = (entities.get("client_name") or "").strip()
    culture = (entities.get("culture") or "").strip()
    variety = (entities.get("variety") or "").strip()
    visit_purpose = (entities.get("visit_purpose") or "").strip()
    fenologia_real = (entities.get("fenologia_real") or "").strip()
    recommendation = (entities.get("recommendation") or "").strip()
    date_value = entities.get("date")
    products = h['normalize_products_from_parsed'](entities.get("products") or [])
    property_name = (entities.get("property_name") or "").strip()

    if not visit_purpose and fenologia_real:
        fen_upper = fenologia_real.upper()
        if re.match(r"R\d+$", fen_upper):
            visit_purpose = "Reprodutivo"
        elif re.match(r"V\d+$", fen_upper) or fen_upper in ("VE", "VC", "VT"):
            visit_purpose = "Vegetativo"
        elif "emergencia" in fenologia_real.lower() or "emergência" in fenologia_real.lower():
            visit_purpose = "Emergencia"

    if not client_name:
        return "Informe o nome do cliente. Exemplo: 'cliente Joao Silva soja R5 hoje'"

    matched_client, client_candidates, needs_confirmation = h['find_client_by_name'](client_name)

    if needs_confirmation and client_candidates:
        state = _mob_ensure_state(session_id)
        state.last_message = original_message
        state.pending_visit_suggestions_json = json.dumps(
            [{"id": c.id, "name": c.name} for c in client_candidates[:3]], ensure_ascii=False
        )
        state.visit_preview_json = json.dumps({}, ensure_ascii=False)
        state.status = "awaiting_client_confirmation"
        db.session.commit()

        lines = ["Encontrei mais de um cliente com esse nome. Qual deles?\n"]
        for i, c in enumerate(client_candidates[:3], 1):
            lines.append(f"{i}. {c.name}")
        return "\n".join(lines)

    if not matched_client:
        return f"Cliente '{client_name}' nao encontrado. Verifique o nome e tente novamente."

    matched_property = None
    if property_name:
        matched_property, _, _ = h['find_property_by_name'](property_name, matched_client.id)

    resolved_date = None
    if date_value:
        d = h['parse_human_date'](date_value)
        resolved_date = d.isoformat() if d else h['parse_date_flexible'](date_value)

    parsed_recommendation = h['extract_recommendation_fallback'](original_message) or recommendation

    photo_urls = []
    for p in (photos or []):
        url = _upload_base64_to_r2(p.get("dataUrl", ""), p.get("filename", "foto.jpg"))
        if url:
            photo_urls.append(url)

    visit_preview = {
        "client_id": matched_client.id,
        "property_id": matched_property.id if matched_property else None,
        "plot_id": None,
        "consultant_id": resolved_consultant_id,
        "date": resolved_date,
        "status": "planned",
        "culture": culture,
        "variety": variety,
        "visit_purpose": visit_purpose,
        "fenologia_real": fenologia_real or None,
        "recommendation": parsed_recommendation,
        "products": products,
        "latitude": None,
        "longitude": None,
        "generate_schedule": False,
        "source": "mobile",
        "photos": photo_urls,
    }

    state = _mob_ensure_state(session_id)
    state.last_message = original_message

    has_culture = bool(culture)
    has_purpose = bool(visit_purpose)
    has_date = bool(resolved_date)

    if not has_culture:
        guided_payload = h['build_guided_state_payload'](
            action="create_new_visit",
            final_visit_payload=visit_preview,
            selected_pending_visit=None,
            close_only=False,
        )
        state.pending_visit_suggestions_json = json.dumps([], ensure_ascii=False)
        state.visit_preview_json = json.dumps(guided_payload, ensure_ascii=False)
        state.status = "awaiting_culture"
        db.session.commit()
        return "Informe a cultura da visita.\nExemplos: Soja, Milho, Algodao"

    if not has_purpose:
        guided_payload = h['build_guided_state_payload'](
            action="create_new_visit",
            final_visit_payload=visit_preview,
            selected_pending_visit=None,
            close_only=False,
        )
        state.pending_visit_suggestions_json = json.dumps([], ensure_ascii=False)
        state.visit_preview_json = json.dumps(guided_payload, ensure_ascii=False)
        state.status = "awaiting_purpose"
        db.session.commit()
        return (
            "Qual o objetivo da visita?\n\n"
            "1. Plantio\n"
            "2. Emergencia\n"
            "3. Vegetativo\n"
            "4. Reprodutivo\n"
            "5. Colheita\n\n"
            "Responda com o numero ou nome."
        )

    if visit_purpose in ("Vegetativo", "Reprodutivo") and not fenologia_real:
        guided_payload = h['build_guided_state_payload'](
            action="create_new_visit",
            final_visit_payload=visit_preview,
            selected_pending_visit=None,
            close_only=False,
        )
        state.pending_visit_suggestions_json = json.dumps([], ensure_ascii=False)
        state.visit_preview_json = json.dumps(guided_payload, ensure_ascii=False)
        state.status = "awaiting_fenologia"
        db.session.commit()
        if visit_purpose == "Vegetativo":
            return "Informe a fenologia vegetativa.\nExemplo: VE, V1, V4, V8, VT"
        else:
            return "Informe a fenologia reprodutiva.\nExemplo: R1, R3, R5, R7"

    if not has_date:
        guided_payload = h['build_guided_state_payload'](
            action="create_new_visit",
            final_visit_payload=visit_preview,
            selected_pending_visit=None,
            close_only=False,
        )
        state.pending_visit_suggestions_json = json.dumps([], ensure_ascii=False)
        state.visit_preview_json = json.dumps(guided_payload, ensure_ascii=False)
        state.status = "awaiting_date"
        db.session.commit()
        return "Informe a data da visita.\nExemplo: hoje, ontem, 07/05/2026"

    guided_payload = h['build_guided_state_payload'](
        action="create_new_visit",
        final_visit_payload=visit_preview,
        selected_pending_visit=None,
        close_only=False,
    )
    summary_text = h['build_visit_summary_text'](
        action="create_new_visit",
        final_visit_payload=visit_preview,
        selected_pending_visit=None,
        close_only=False,
    )

    state.pending_visit_suggestions_json = json.dumps([], ensure_ascii=False)
    state.visit_preview_json = json.dumps(guided_payload, ensure_ascii=False)
    state.confirmation_text = summary_text
    state.status = "awaiting_final_confirmation"
    db.session.commit()

    return summary_text


def _mob_awaiting_confirmation(session_id, state, message_text, resolved_consultant_id):
    h = _get_helpers()

    parsed_reply = h['parse_pending_reply'](message_text)

    if not parsed_reply:
        return state.confirmation_text or "Responda com o numero da visita ou NOVA VISITA."

    pending_visit_suggestions = json.loads(state.pending_visit_suggestions_json or "[]")
    visit_preview = json.loads(state.visit_preview_json or "{}")
    mode = parsed_reply["mode"]

    if mode == "create_new":
        final_visit_payload = {
            **visit_preview,
            "culture": "",
            "fenologia_real": None,
            "date": None,
            "recommendation": "",
        }
        state.visit_preview_json = json.dumps(
            h['build_guided_state_payload']("create_new_visit", final_visit_payload, None, False),
            ensure_ascii=False,
        )
        state.status = "awaiting_culture"
        db.session.commit()
        return "Informe a cultura da visita.\nExemplo: Milho, Soja, Algodao"

    if mode == "cancel_final":
        db.session.delete(state)
        db.session.commit()
        return "Operacao cancelada."

    if mode == "confirm_final":
        return state.confirmation_text or "Responda com o numero da visita ou NOVA VISITA."

    idx = parsed_reply.get("index") if parsed_reply.get("index") is not None else -1
    if idx < 0 or idx >= len(pending_visit_suggestions):
        return "Numero invalido. Revise as opcoes e tente novamente."

    selected = pending_visit_suggestions[idx]
    action = "use_existing_pending_visit"
    close_only = (mode == "close_only")

    final_visit_payload = {
        **visit_preview,
        "client_id": selected.get("client_id") or visit_preview.get("client_id"),
        "property_id": selected.get("property_id") or visit_preview.get("property_id"),
        "plot_id": selected.get("plot_id") or visit_preview.get("plot_id"),
        "consultant_id": resolved_consultant_id or visit_preview.get("consultant_id"),
        "linked_pending_visit_id": selected.get("id"),
        "status": "done",
        "culture": visit_preview.get("culture") or selected.get("culture") or "",
        "variety": selected.get("variety") or visit_preview.get("variety") or "",
        "fenologia_real": visit_preview.get("fenologia_real"),
        "date": visit_preview.get("date"),
        "recommendation": visit_preview.get("recommendation") or "",
        "products": visit_preview.get("products") or [],
        "latitude": visit_preview.get("latitude"),
        "longitude": visit_preview.get("longitude"),
        "source": "mobile",
    }

    original_message = (state.last_message or "").strip()
    robust_prefill = h['extract_prefill_from_message_text'](original_message)
    original_parsed = h['parse_chatbot_message'](original_message) or {}

    composite_fenologia = (parsed_reply or {}).get("fenologia")
    if composite_fenologia:
        final_visit_payload["fenologia_real"] = composite_fenologia

    if not (final_visit_payload.get("fenologia_real") or "").strip():
        final_visit_payload["fenologia_real"] = (
            (robust_prefill.get("fenologia_real") or "").strip()
            or (original_parsed.get("fenologia_real") or "").strip()
            or None
        )

    if not final_visit_payload.get("date"):
        fallback_date = robust_prefill.get("date") or original_parsed.get("date")
        if fallback_date:
            d = h['parse_human_date'](fallback_date)
            fallback_date = d.isoformat() if d else h['parse_date_flexible'](fallback_date)
        final_visit_payload["date"] = fallback_date

    if not (final_visit_payload.get("recommendation") or "").strip():
        final_visit_payload["recommendation"] = (
            (robust_prefill.get("recommendation") or "").strip()
            or (original_parsed.get("recommendation") or "").strip()
            or (selected.get("recommendation") or "").strip()
            or ""
        )

    has_fenologia = bool((final_visit_payload.get("fenologia_real") or "").strip())
    has_date = bool(final_visit_payload.get("date"))
    has_obs = bool((final_visit_payload.get("recommendation") or "").strip())

    if close_only or (has_fenologia and has_date and has_obs):
        summary_text = h['build_visit_summary_text'](action, final_visit_payload, selected, close_only)
        state.visit_preview_json = json.dumps(
            h['build_guided_state_payload'](action, final_visit_payload, selected, close_only),
            ensure_ascii=False,
        )
        state.confirmation_text = summary_text
        state.status = "awaiting_final_confirmation"
        db.session.commit()
        return summary_text

    if not has_fenologia:
        next_status, next_msg = "awaiting_fenologia", "Informe a fenologia observada.\nExemplo: V4, V5, R1"
    elif not has_date:
        next_status, next_msg = "awaiting_date", "Informe a data da visita.\nExemplo: hoje, ontem ou 24/02/2026"
    else:
        next_status, next_msg = "awaiting_observations", "Informe as observacoes da visita."

    state.visit_preview_json = json.dumps(
        h['build_guided_state_payload'](action, final_visit_payload, selected, close_only),
        ensure_ascii=False,
    )
    state.status = next_status
    db.session.commit()
    return next_msg


def _mob_client_confirmation(session_id, state, message_text, consultant, resolved_consultant_id):
    h = _get_helpers()

    text = message_text.strip()
    candidates = json.loads(state.pending_visit_suggestions_json or "[]")
    original_message = (state.last_message or "").strip()

    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(candidates):
            chosen = candidates[idx]
            matched_client = Client.query.get(chosen["id"])
            if matched_client:
                db.session.delete(state)
                db.session.commit()
                return _mob_start_visit_flow(
                    session_id, original_message,
                    {"client_name": matched_client.name, **_extract_entities_from_text(original_message, h)},
                    consultant, resolved_consultant_id, [],
                )
    return (
        "Numero invalido. Escolha:\n"
        + "\n".join(f"{i+1}. {c['name']}" for i, c in enumerate(candidates))
    )


def _extract_entities_from_text(text, h):
    parsed = h['parse_chatbot_message'](text) or {}
    return {
        "culture": parsed.get("culture") or "",
        "fenologia_real": parsed.get("fenologia_real") or "",
        "date": parsed.get("date"),
        "recommendation": parsed.get("recommendation") or "",
        "products": parsed.get("products") or [],
        "property_name": parsed.get("property_name") or "",
    }


def _mob_guided_field(session_id, state, message_text, current_status):
    h = _get_helpers()

    normalized = h['normalize_lookup_text'](message_text)
    if normalized in ("cancelar", "cancela", "cancel", "sair", "voltar"):
        db.session.delete(state)
        db.session.commit()
        return "Operacao cancelada."

    try:
        preview_data = json.loads(state.visit_preview_json or "{}")
    except Exception:
        preview_data = {}

    final_visit_payload = preview_data.get("final_visit_payload") or {}
    selected_pending_visit = preview_data.get("selected_pending_visit") or {}
    action = preview_data.get("action") or "create_new_visit"
    close_only = bool(preview_data.get("close_only"))
    next_status = None
    next_msg = ""

    if current_status == "awaiting_culture":
        culture = h['normalize_culture_input'](message_text.strip())
        if not culture:
            return "Cultura nao reconhecida.\nExemplos: Soja, Milho, Algodao"
        final_visit_payload["culture"] = culture
        next_status = "awaiting_purpose"
        next_msg = (
            "Qual o objetivo da visita?\n\n"
            "1. Plantio\n"
            "2. Emergencia\n"
            "3. Vegetativo\n"
            "4. Reprodutivo\n"
            "5. Colheita\n\n"
            "Responda com o numero ou nome."
        )

    elif current_status == "awaiting_purpose":
        purpose = h['parse_visit_purpose'](message_text.strip())
        if not purpose:
            purpose = h['parse_visit_purpose_with_ai'](message_text.strip())

        if not purpose:
            return (
                "Objetivo nao reconhecido.\n\n"
                "Escolha:\n"
                "1. Plantio\n"
                "2. Emergencia\n"
                "3. Vegetativo\n"
                "4. Reprodutivo\n"
                "5. Colheita"
            )

        final_visit_payload["visit_purpose"] = purpose

        if purpose in ("Vegetativo", "Reprodutivo"):
            if purpose == "Vegetativo":
                next_msg = "Informe a fenologia vegetativa.\nExemplo: VE, V1, V4, V8, VT"
            else:
                next_msg = "Informe a fenologia reprodutiva.\nExemplo: R1, R3, R5, R7"
            next_status = "awaiting_fenologia"
        else:
            next_status = "awaiting_date"
            next_msg = "Informe a data da visita.\nExemplo: hoje, ontem, 24/02/2026"

    elif current_status == "awaiting_fenologia":
        purpose = final_visit_payload.get("visit_purpose") or ""

        fenologia = message_text.strip().upper()
        if not h['is_valid_fenologia'](fenologia):
            fenologia = h['parse_fenologia_with_ai'](message_text.strip(), purpose)

        if not fenologia:
            if purpose == "Vegetativo":
                return "Fenologia invalida.\nExemplo: VE, V1, V4, V8, VT"
            else:
                return "Fenologia invalida.\nExemplo: R1, R3, R5, R7"

        final_visit_payload["fenologia_real"] = fenologia
        next_status = "awaiting_date"
        next_msg = "Informe a data da visita.\nExemplo: hoje, ontem, 24/02/2026"

    elif current_status == "awaiting_date":
        d = h['parse_human_date'](message_text.strip())
        if d:
            final_visit_payload["date"] = d.isoformat()
        else:
            iso = h['parse_date_flexible'](message_text.strip())
            if not iso:
                return "Data nao reconhecida.\nExemplo: hoje, ontem, 24/02/2026"
            final_visit_payload["date"] = iso
        next_status = "awaiting_observations"
        next_msg = "Informe as observacoes da visita.\nOu digite 'pular' para continuar sem observacoes."

    elif current_status == "awaiting_observations":
        if normalized not in ("pular", "skip", "-", "nenhuma", "nenhum"):
            final_visit_payload["recommendation"] = h['_format_recommendation'](message_text.strip()) or message_text.strip()
        summary_text = h['build_visit_summary_text'](action, final_visit_payload, selected_pending_visit or None, close_only)
        state.visit_preview_json = json.dumps(
            h['build_guided_state_payload'](action, final_visit_payload, selected_pending_visit or None, close_only),
            ensure_ascii=False,
        )
        state.confirmation_text = summary_text
        state.status = "awaiting_final_confirmation"
        db.session.commit()
        return summary_text

    state.visit_preview_json = json.dumps(
        h['build_guided_state_payload'](action, final_visit_payload, selected_pending_visit or None, close_only),
        ensure_ascii=False,
    )
    state.status = next_status
    db.session.commit()
    return next_msg


def _mob_handle_alter_command(state, message_text: str, h) -> Optional[str]:
    if not message_text:
        return None

    normalized = h['normalize_lookup_text'](message_text)

    alter_patterns = [
        (r"^alterar\s+data\s+(.+)$", "date"),
        (r"^data\s+(.+)$", "date"),
        (r"^alterar\s+fenologia\s+(.+)$", "fenologia"),
        (r"^fenologia\s+(.+)$", "fenologia"),
        (r"^alterar\s+observacao\s+(.+)$", "observation"),
        (r"^alterar\s+observacoes\s+(.+)$", "observation"),
        (r"^observacao\s+(.+)$", "observation"),
        (r"^observacoes\s+(.+)$", "observation"),
        (r"^alterar\s+objetivo\s+(.+)$", "purpose"),
        (r"^objetivo\s+(.+)$", "purpose"),
        (r"^alterar\s+cultura\s+(.+)$", "culture"),
        (r"^cultura\s+(.+)$", "culture"),
    ]

    field_to_alter = None
    new_value = None

    for pattern, field in alter_patterns:
        match = re.match(pattern, normalized)
        if match:
            field_to_alter = field
            original_match = re.match(pattern, message_text.strip(), flags=re.IGNORECASE)
            if original_match:
                new_value = original_match.group(1).strip()
            else:
                new_value = match.group(1).strip()
            break

    if not field_to_alter or not new_value:
        return None

    try:
        preview_data = json.loads(state.visit_preview_json or "{}")
    except Exception:
        preview_data = {}

    final_visit_payload = preview_data.get("final_visit_payload") or {}
    action = preview_data.get("action") or "create_new_visit"
    selected_pending_visit = preview_data.get("selected_pending_visit")
    close_only = preview_data.get("close_only", False)

    if field_to_alter == "date":
        parsed_date = h['parse_human_date'](new_value)
        if not parsed_date:
            parsed_date_str = h['parse_date_flexible'](new_value)
            if parsed_date_str:
                final_visit_payload["date"] = parsed_date_str
            else:
                return "Data nao reconhecida. Exemplo: hoje, ontem, 07/05/2026"
        else:
            final_visit_payload["date"] = parsed_date.isoformat()

    elif field_to_alter == "fenologia":
        fenologia = new_value.upper()
        if not h['is_valid_fenologia'](fenologia):
            fenologia = h['parse_fenologia_with_ai'](new_value, final_visit_payload.get("visit_purpose") or "")
        if not fenologia:
            return "Fenologia invalida. Exemplo: V4, R2, VT"
        final_visit_payload["fenologia_real"] = fenologia

    elif field_to_alter == "observation":
        final_visit_payload["recommendation"] = h['_format_recommendation'](new_value) or new_value

    elif field_to_alter == "purpose":
        purpose = h['parse_visit_purpose'](new_value)
        if not purpose:
            purpose = h['parse_visit_purpose_with_ai'](new_value)
        if not purpose:
            return "Objetivo invalido. Escolha: Plantio, Emergencia, Vegetativo, Reprodutivo, Colheita"
        final_visit_payload["visit_purpose"] = purpose

    elif field_to_alter == "culture":
        culture = h['normalize_culture_input'](new_value)
        if not culture:
            return "Cultura nao reconhecida. Exemplos: Soja, Milho, Algodao"
        final_visit_payload["culture"] = culture

    summary_text = h['build_visit_summary_text'](action, final_visit_payload, selected_pending_visit, close_only)

    state.visit_preview_json = json.dumps(
        h['build_guided_state_payload'](action, final_visit_payload, selected_pending_visit, close_only),
        ensure_ascii=False,
    )
    state.confirmation_text = summary_text
    db.session.commit()

    return f"Alterado!\n\n{summary_text}"


def _mob_final_confirmation(session_id, state, message_text, resolved_consultant_id, photos):
    h = _get_helpers()

    alter_result = _mob_handle_alter_command(state, message_text, h)
    if alter_result:
        return alter_result

    reply = h['parse_pending_reply'](message_text)

    if not reply:
        return (
            "Nao entendi. Responda com:\n"
            "CONFIRMAR\n"
            "CANCELAR\n"
            "ALTERAR DATA ontem\n"
            "ALTERAR FENOLOGIA V8"
        )

    if reply["mode"] == "cancel_final":
        db.session.delete(state)
        db.session.commit()
        return "Operacao cancelada."

    if reply["mode"] != "confirm_final":
        return (
            "Responda com:\n"
            "CONFIRMAR\n"
            "CANCELAR\n"
            "ALTERAR DATA/FENOLOGIA/OBSERVACAO"
        )

    try:
        preview_data = json.loads(state.visit_preview_json or "{}")
    except Exception:
        preview_data = {}

    action = preview_data.get("action") or "create_new_visit"
    base_preview = preview_data.get("final_visit_payload") or {}
    selected_pending_visit = preview_data.get("selected_pending_visit") or {}
    close_only = bool(preview_data.get("close_only"))

    final_visit_payload = h['build_final_visit_payload'](
        base_preview=base_preview,
        selected_pending_visit=selected_pending_visit,
        resolved_consultant_id=base_preview.get("consultant_id") or resolved_consultant_id or 1,
        close_only=close_only,
    )

    try:
        visit = None

        if action == "use_existing_pending_visit":
            visit_id = (
                final_visit_payload.get("linked_pending_visit_id")
                or selected_pending_visit.get("id")
            )
            if not visit_id:
                raise ValueError("ID da visita pendente nao encontrado")
            visit = Visit.query.get(visit_id)
            if not visit:
                raise ValueError(f"Visita {visit_id} nao encontrada")
            visit = h['apply_payload_to_existing_visit'](visit=visit, final_visit_payload=final_visit_payload, close_only=close_only)
        elif action == "create_new_visit":
            visit = h['create_visit_from_payload'](final_visit_payload)
        else:
            raise ValueError(f"Acao invalida: {action}")

        auto_closed_ids = h['auto_close_previous_cycle_visits'](visit)

        stored_photo_urls = base_preview.get("photos") or []
        stored_photo_infos = [{"url": u} for u in stored_photo_urls]
        all_photos = stored_photo_infos + list(photos or [])
        attached_count = 0
        if all_photos and visit:
            for photo_info in all_photos:
                raw = photo_info.get("url") or photo_info.get("filename") or photo_info.get("dataUrl") or ""
                if not raw:
                    continue
                if raw.startswith("data:"):
                    photo_url = _upload_base64_to_r2(raw, photo_info.get("filename") or "foto.jpg")
                    if not photo_url:
                        continue
                else:
                    photo_url = raw
                p = Photo(visit_id=visit.id, url=photo_url)
                db.session.add(p)
                attached_count += 1
            if attached_count:
                db.session.commit()

        db.session.delete(state)
        db.session.commit()

        from services.agent.conversation_memory import update_last_message_with_result
        update_last_message_with_result(
            platform="mobile",
            chat_id=session_id,
            intent="CREATE_VISIT_LIKE_MESSAGE",
            visit_id=visit.id,
        )

        lines = []
        if action == "use_existing_pending_visit":
            lines.append(f"Visita {visit.id} atualizada e concluida com sucesso.")
        else:
            lines.append(f"Nova visita criada com sucesso. ID {visit.id}.")

        if auto_closed_ids:
            lines.append(f"Fechei automaticamente {len(auto_closed_ids)} visita(s) anterior(es) do mesmo ciclo.")

        if attached_count:
            lines.append(f"{attached_count} foto(s) vinculada(s).")

        return "\n".join(lines)

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao confirmar visita mobile: {e}")
        return f"Erro ao salvar visita: {str(e)}"


# ============================================================
# SCHEDULE/ROUTINE HELPERS
# ============================================================

def _mob_week_schedule_text(consultant, resolved_consultant_id) -> str:
    from datetime import date as _d, timedelta as _td
    today = _d.today()
    start = today - _td(days=today.weekday())
    end = start + _td(days=6)
    visits = Visit.query.filter(
        Visit.date >= start,
        Visit.date <= end,
        Visit.consultant_id == resolved_consultant_id,
    ).order_by(Visit.date).limit(20).all() if resolved_consultant_id else []

    if not visits:
        return "Nenhuma visita encontrada para esta semana."

    lines = [f"Agenda da semana ({start.strftime('%d/%m')} - {end.strftime('%d/%m')}):\n"]
    for v in visits:
        date_str = v.date.strftime("%d/%m") if v.date else "-"
        client_name = v.client.name if getattr(v, "client", None) else "-"
        lines.append(f"- {date_str} - {client_name} ({v.culture or '?'})")
    return "\n".join(lines)


def _mob_daily_routine_text(consultant, resolved_consultant_id) -> str:
    from datetime import date as _d
    today = _d.today()
    visits = Visit.query.filter(
        Visit.date == today,
        Visit.consultant_id == resolved_consultant_id,
    ).order_by(Visit.id).limit(10).all() if resolved_consultant_id else []

    if not visits:
        return f"Nenhuma visita agendada para hoje ({today.strftime('%d/%m/%Y')})."

    lines = [f"Sua rotina de hoje ({today.strftime('%d/%m/%Y')}):\n"]
    for i, v in enumerate(visits, 1):
        client_name = v.client.name if getattr(v, "client", None) else "-"
        lines.append(f"{i}. {client_name} - {v.culture or '?'} ({v.status})")
    return "\n".join(lines)


def _mob_planting_days_text(consultant) -> str:
    h = _get_helpers()
    if not consultant:
        return "Voce precisa estar vinculado a um consultor para ver os dias de plantado."
    items = h['build_consultant_days_planted_portfolio'](consultant.id)
    return h['build_consultant_days_planted_text'](consultant.name, items)


def _mob_stale_clients_text(consultant) -> str:
    h = _get_helpers()
    if not consultant:
        return "Voce precisa estar vinculado a um consultor para ver os clientes atrasados."
    ranking = h['find_stale_clients_ranking'](consultant_id=consultant.id, limit=15)
    return h['build_stale_clients_ranking_text'](consultant.name, ranking)


def _mob_month_visits_text(consultant, resolved_consultant_id) -> str:
    h = _get_helpers()
    if not consultant:
        return "Voce precisa estar vinculado a um consultor para ver as visitas do mes."
    from datetime import date as _d
    today = _d.today()
    visits = Visit.query.filter(
        db.extract("month", Visit.date) == today.month,
        db.extract("year", Visit.date) == today.year,
        Visit.consultant_id == resolved_consultant_id,
    ).order_by(Visit.date).all() if resolved_consultant_id else []
    visit_dicts = [v.to_dict() for v in visits]
    return h['build_month_visits_text'](consultant.name, visit_dicts)


def _mob_weekly_report_text(consultant) -> str:
    h = _get_helpers()
    if not consultant:
        return "Voce precisa estar vinculado a um consultor para ver o relatorio semanal."
    return h['build_weekly_report_text'](consultant.id, consultant.name)


# ============================================================
# PEST DIAGNOSIS
# ============================================================

def _mob_pest_diagnosis(message_text: str) -> dict:
    from services.diseases_database import search_disease

    crop = None
    msg_lower = message_text.lower()
    if "soja" in msg_lower:
        crop = "soja"
    elif "milho" in msg_lower:
        crop = "milho"
    elif "algodao" in msg_lower or "algodão" in msg_lower:
        crop = "algodao"

    local_result = search_disease(message_text, crop)

    if local_result.get("found"):
        disease = local_result.get("disease", {})
        response_text = _format_disease_response_mobile(disease)
        return {
            "text": response_text,
            "image_url": disease.get("image_url"),
            "source": "local_database",
            "disease_name": disease.get("name"),
        }

    from services.agent.skill_loader import interpret_with_skill

    ai_result = interpret_with_skill(
        message_text=message_text,
        skill_name="diagnostico_praga",
    )

    if ai_result and ai_result.get("diagnosis", {}).get("name"):
        diagnosis = ai_result.get("diagnosis", {})
        response_text = _format_ai_diagnosis_mobile(diagnosis, ai_result.get("confidence", "low"))
        return {
            "text": response_text,
            "image_url": None,
            "source": "ai_fallback",
            "disease_name": diagnosis.get("name"),
        }

    suggestions = local_result.get("suggestions", [])
    if suggestions:
        response_text = (
            "Nao encontrei essa praga/doenca especifica.\n\n"
            f"Voce quis dizer:\n- " + "\n- ".join(suggestions)
        )
    else:
        response_text = (
            "Nao consegui identificar a praga ou doenca.\n\n"
            "Tente especificar melhor, por exemplo:\n"
            "- ferrugem asiatica\n"
            "- mancha de bipolaris no milho\n"
            "- lagarta do cartucho"
        )

    return {"text": response_text, "image_url": None, "source": "not_found"}


def _format_disease_response_mobile(disease: dict) -> str:
    lines = []

    pest_type = disease.get("type", "")
    type_label = "Praga" if pest_type == "praga" else "Doenca" if pest_type == "doenca" else "Info"

    lines.append(f"[{type_label}] {disease.get('name')}")
    if disease.get("scientific_name"):
        lines.append(f"({disease.get('scientific_name')})")

    crop = disease.get("crop")
    if crop:
        lines.append(f"Cultura: {crop.capitalize()}")
    lines.append("")

    symptoms = disease.get("symptoms")
    if symptoms:
        lines.append(f"Sintomas:\n{symptoms}")
        lines.append("")

    conditions = disease.get("favorable_conditions")
    if conditions:
        lines.append(f"Condicoes favoraveis:\n{conditions}")
        lines.append("")

    threshold = disease.get("control_threshold")
    if threshold:
        lines.append(f"Nivel de controle:\n{threshold}")
        lines.append("")

    products = disease.get("products") or []
    if products:
        lines.append("Produtos recomendados:")
        for prod in products[:5]:
            name = prod.get("name", "")
            dose = prod.get("dose", "")
            if name:
                lines.append(f"- {name}" + (f" ({dose})" if dose else ""))
        lines.append("")

    tips = disease.get("management_tips")
    if tips:
        lines.append(f"Dica: {tips}")

    return "\n".join(lines).strip()


def _format_ai_diagnosis_mobile(diagnosis: dict, confidence: str) -> str:
    lines = []

    pest_type = diagnosis.get("type", "")
    type_label = "Praga" if pest_type == "praga" else "Doenca" if pest_type == "doenca" else "Info"

    lines.append(f"[{type_label}] {diagnosis.get('name')}")

    crop = diagnosis.get("crop")
    if crop:
        lines.append(f"Cultura: {crop.capitalize()}")

    if confidence == "low":
        lines.append("(Confianca baixa - verifique os sintomas)")
    lines.append("")

    symptoms = diagnosis.get("symptoms")
    if symptoms:
        lines.append(f"Sintomas:\n{symptoms}")
        lines.append("")

    conditions = diagnosis.get("favorable_conditions")
    if conditions:
        lines.append(f"Condicoes favoraveis:\n{conditions}")
        lines.append("")

    threshold = diagnosis.get("control_threshold")
    if threshold:
        lines.append(f"Nivel de controle:\n{threshold}")
        lines.append("")

    products = diagnosis.get("recommended_products") or []
    if products:
        lines.append("Produtos recomendados:")
        for prod in products[:5]:
            name = prod.get("name", "")
            dose = prod.get("dose", "")
            if name:
                lines.append(f"- {name}" + (f" ({dose})" if dose else ""))
        lines.append("")

    tips = diagnosis.get("management_tips")
    if tips:
        lines.append(f"Dica: {tips}")

    return "\n".join(lines).strip()


def _mob_add_to_existing_visit(session_id: str, message_text: str, visit_id: int) -> str:
    h = _get_helpers()

    if not visit_id:
        return (
            "Nao encontrei uma visita recente para adicionar essa informacao.\n"
            "Por favor, crie uma visita primeiro."
        )

    visit = Visit.query.get(visit_id)
    if not visit:
        return "A visita referenciada nao foi encontrada. Pode ter sido excluida."

    contextual_triggers = [
        "adiciona que", "adicionar que", "acrescenta que", "acrescentar que",
        "inclui que", "incluir que", "tambem", "também", "mais uma coisa",
        "outra coisa", "esqueci de falar", "faltou", "alem disso", "além disso",
        "complementando", "complemento", "adiciona", "adicionar", "acrescenta",
        "acrescentar", "inclui", "incluir",
    ]
    new_observation = message_text.strip()
    normalized_msg = h['normalize_lookup_text'](new_observation)
    for trigger in contextual_triggers:
        if normalized_msg.startswith(trigger):
            new_observation = new_observation[len(trigger):].strip()
            break

    if not new_observation:
        return "Nao consegui identificar o que voce quer adicionar. Pode reformular?"

    current_recommendation = (visit.recommendation or "").strip()
    if current_recommendation:
        visit.recommendation = f"{current_recommendation}\n\n- {new_observation}"
    else:
        visit.recommendation = new_observation

    db.session.commit()

    client_name = ""
    if visit.client_id:
        client = Client.query.get(visit.client_id)
        if client:
            client_name = f" do {client.name}"

    return f"Adicionado a visita{client_name}:\n+ {new_observation}"
