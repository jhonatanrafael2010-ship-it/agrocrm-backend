# routes/messaging.py
"""
Endpoints de mensageria (WhatsApp e Telegram).
- /whatsapp/bindings (GET, POST)
- /whatsapp/webhook (GET, POST)
- /telegram/test-send (POST)
- /telegram/setup-link-codes (POST)
- /telegram/webhook (POST)
- /telegram/bindings (POST)
"""

import os
import re
import json
from flask import Blueprint, jsonify, request

from models import (
    db,
    Client,
    Consultant,
    WhatsAppContactBinding,
    WhatsAppInboundMessage,
    TelegramContactBinding,
    ChatbotConversationState,
    Visit,
)
from services.chatbot_service import ChatbotService, send_telegram_message

messaging_bp = Blueprint('messaging', __name__)


def _get_helpers():
    """Lazy import para evitar dependência circular."""
    from api_routes import (
        normalize_phone_number,
        normalize_lookup_text,
        resolve_telegram_consultant,
        resolve_audio_message_text,
        resolve_single_active_reference,
        resolve_pending_photo_for_message,
        find_telegram_binding,
        bind_telegram_consultant_by_code,
        clear_pending_telegram_photos,
        bot_phrase,
        handle_priority_stateful_actions,
        handle_agent_phase2_flow,
        is_field_data_save_request,
        handle_field_data_save_flow,
        is_field_data_query_request,
        handle_field_data_query_flow,
        is_days_planted_request,
        handle_days_planted_flow,
        handle_week_schedule_flow,
        handle_stale_clients_ranking_flow,
        handle_daily_routine_flow,
        handle_week_organization_flow,
        handle_month_visits_flow,
        handle_pdf_flow,
        handle_final_confirmation,
        normalize_culture_input,
        build_guided_state_payload,
        parse_yes_no,
        is_valid_fenologia,
        build_visit_summary_text,
        parse_human_date,
        get_local_today,
        parse_pending_reply,
        start_new_visit_direct_confirmation,
        extract_prefill_from_message_text,
        parse_date_flexible,
        get_current_chatbot_state,
        interpret_user_message_with_ai,
        try_extract_client_from_free_text,
        is_week_schedule_request,
        is_pdf_request,
        is_last_pdf_request,
        parse_summary_edit_command,
        build_name_confirmation_text,
        parse_chatbot_message,
        find_client_by_name,
        find_property_by_name,
        find_pending_visits,
        build_pending_visits_confirmation_text,
        extract_recommendation_fallback,
        normalize_products_from_parsed,
    )
    return {
        'normalize_phone_number': normalize_phone_number,
        'normalize_lookup_text': normalize_lookup_text,
        'resolve_telegram_consultant': resolve_telegram_consultant,
        'resolve_audio_message_text': resolve_audio_message_text,
        'resolve_single_active_reference': resolve_single_active_reference,
        'resolve_pending_photo_for_message': resolve_pending_photo_for_message,
        'find_telegram_binding': find_telegram_binding,
        'bind_telegram_consultant_by_code': bind_telegram_consultant_by_code,
        'clear_pending_telegram_photos': clear_pending_telegram_photos,
        'bot_phrase': bot_phrase,
        'handle_priority_stateful_actions': handle_priority_stateful_actions,
        'handle_agent_phase2_flow': handle_agent_phase2_flow,
        'is_field_data_save_request': is_field_data_save_request,
        'handle_field_data_save_flow': handle_field_data_save_flow,
        'is_field_data_query_request': is_field_data_query_request,
        'handle_field_data_query_flow': handle_field_data_query_flow,
        'is_days_planted_request': is_days_planted_request,
        'handle_days_planted_flow': handle_days_planted_flow,
        'handle_week_schedule_flow': handle_week_schedule_flow,
        'handle_stale_clients_ranking_flow': handle_stale_clients_ranking_flow,
        'handle_daily_routine_flow': handle_daily_routine_flow,
        'handle_week_organization_flow': handle_week_organization_flow,
        'handle_month_visits_flow': handle_month_visits_flow,
        'handle_pdf_flow': handle_pdf_flow,
        'handle_final_confirmation': handle_final_confirmation,
        'normalize_culture_input': normalize_culture_input,
        'build_guided_state_payload': build_guided_state_payload,
        'parse_yes_no': parse_yes_no,
        'is_valid_fenologia': is_valid_fenologia,
        'build_visit_summary_text': build_visit_summary_text,
        'parse_human_date': parse_human_date,
        'get_local_today': get_local_today,
        'parse_pending_reply': parse_pending_reply,
        'start_new_visit_direct_confirmation': start_new_visit_direct_confirmation,
        'extract_prefill_from_message_text': extract_prefill_from_message_text,
        'parse_date_flexible': parse_date_flexible,
        'get_current_chatbot_state': get_current_chatbot_state,
        'interpret_user_message_with_ai': interpret_user_message_with_ai,
        'try_extract_client_from_free_text': try_extract_client_from_free_text,
        'is_week_schedule_request': is_week_schedule_request,
        'is_pdf_request': is_pdf_request,
        'is_last_pdf_request': is_last_pdf_request,
        'parse_summary_edit_command': parse_summary_edit_command,
        'build_name_confirmation_text': build_name_confirmation_text,
        'parse_chatbot_message': parse_chatbot_message,
        'find_client_by_name': find_client_by_name,
        'find_property_by_name': find_property_by_name,
        'find_pending_visits': find_pending_visits,
        'build_pending_visits_confirmation_text': build_pending_visits_confirmation_text,
        'extract_recommendation_fallback': extract_recommendation_fallback,
        'normalize_products_from_parsed': normalize_products_from_parsed,
    }


# ================================================================
# WHATSAPP BINDINGS
# ================================================================

@messaging_bp.route('/whatsapp/bindings', methods=['GET'])
def list_whatsapp_bindings():
    rows = WhatsAppContactBinding.query.order_by(WhatsAppContactBinding.id.asc()).all()
    return jsonify([r.to_dict() for r in rows]), 200


@messaging_bp.route('/whatsapp/bindings', methods=['POST'])
def create_whatsapp_binding():
    h = _get_helpers()
    data = request.get_json() or {}

    phone_number = h['normalize_phone_number']((data.get("phone_number") or "").strip())
    consultant_id = data.get("consultant_id")
    display_name = (data.get("display_name") or "").strip() or None

    if not phone_number:
        return jsonify(message="phone_number is required"), 400

    if consultant_id is None:
        return jsonify(message="consultant_id is required"), 400

    try:
        consultant_id = int(consultant_id)
    except (TypeError, ValueError):
        return jsonify(message="consultant_id must be an integer"), 400

    consultant = Consultant.query.get(consultant_id)
    if not consultant:
        return jsonify(message="consultant not found"), 404

    existing = WhatsAppContactBinding.query.filter_by(phone_number=phone_number).first()
    if existing:
        return jsonify(message="phone_number already linked"), 409

    row = WhatsAppContactBinding(
        phone_number=phone_number,
        consultant_id=consultant_id,
        display_name=display_name,
        is_active=True,
    )

    db.session.add(row)
    db.session.commit()

    return jsonify(message="binding created", binding=row.to_dict()), 201


# ================================================================
# WHATSAPP WEBHOOK
# ================================================================

@messaging_bp.route('/whatsapp/webhook', methods=['GET'])
def whatsapp_webhook_verify():
    verify_token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    mode = request.args.get("hub.mode")

    expected_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "agrocrm_verify_token")

    if mode == "subscribe" and verify_token == expected_token:
        return challenge, 200

    return jsonify({"error": "verification failed"}), 403


@messaging_bp.route('/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook_receive():
    payload = request.get_json(silent=True) or {}

    try:
        entry_list = payload.get("entry", [])
        saved = 0

        for entry in entry_list:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                contacts = value.get("contacts", []) or []
                messages = value.get("messages", []) or []

                contact_name = None
                wa_from = None

                if contacts:
                    contact_name = contacts[0].get("profile", {}).get("name")
                    wa_from = contacts[0].get("wa_id")

                for msg in messages:
                    message_type = msg.get("type", "unknown")
                    wa_message_id = msg.get("id")
                    from_number = msg.get("from") or wa_from

                    text_content = None
                    media_id = None
                    mime_type = None

                    if message_type == "text":
                        text_content = (msg.get("text") or {}).get("body")

                    elif message_type == "image":
                        image_obj = msg.get("image") or {}
                        media_id = image_obj.get("id")
                        mime_type = image_obj.get("mime_type")

                    elif message_type == "audio":
                        audio_obj = msg.get("audio") or {}
                        media_id = audio_obj.get("id")
                        mime_type = audio_obj.get("mime_type")

                    existing = WhatsAppInboundMessage.query.filter_by(
                        wa_message_id=wa_message_id
                    ).first()

                    if existing:
                        continue

                    row = WhatsAppInboundMessage(
                        wa_message_id=wa_message_id,
                        phone_number=from_number or "",
                        contact_name=contact_name,
                        message_type=message_type,
                        text_content=text_content,
                        media_id=media_id,
                        mime_type=mime_type,
                        raw_payload=str(payload),
                        processing_status="received",
                    )
                    db.session.add(row)
                    saved += 1

        db.session.commit()
        return jsonify({"status": "ok", "saved": saved}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Erro no webhook WhatsApp: {e}")
        return jsonify({"error": str(e)}), 500


# ================================================================
# TELEGRAM TEST / SETUP
# ================================================================

@messaging_bp.route('/telegram/test-send', methods=['POST'])
def telegram_test_send():
    try:
        data = request.get_json(silent=True) or {}
        chat_id = str(data.get("chat_id") or "").strip()
        text = (data.get("text") or "Teste do AgroCRM no Telegram").strip()

        if not chat_id:
            return jsonify({
                "ok": False,
                "error": "chat_id is required"
            }), 400

        result = send_telegram_message(chat_id=chat_id, text=text)

        return jsonify({
            "ok": True,
            "send_result": result
        }), 200

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@messaging_bp.route('/telegram/setup-link-codes', methods=['POST'])
def setup_telegram_link_codes():
    try:
        mapping = {
            "Jhonatan": "JHONATAN123",
            "Felipe": "FELIPE123",
            "Everton": "EVERTON123",
            "Pedro": "PEDRO123",
            "Alexandre": "ALEXANDRE123",
        }

        consultants = Consultant.query.all()
        updated = []

        for consultant in consultants:
            code = mapping.get((consultant.name or "").strip())
            if not code:
                continue

            consultant.telegram_link_code = code
            updated.append({
                "id": consultant.id,
                "name": consultant.name,
                "telegram_link_code": consultant.telegram_link_code,
            })

        db.session.commit()

        return jsonify({
            "ok": True,
            "updated": updated,
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


# ================================================================
# TELEGRAM BINDINGS
# ================================================================

@messaging_bp.route('/telegram/bindings', methods=['POST'])
def create_telegram_binding():
    try:
        data = request.get_json(silent=True) or {}

        telegram_chat_id = str(data.get("telegram_chat_id") or "").strip()
        telegram_user_id = str(data.get("telegram_user_id") or "").strip()
        telegram_username = (data.get("telegram_username") or "").strip()
        display_name = (data.get("display_name") or "").strip()
        consultant_id = data.get("consultant_id")

        if not telegram_chat_id:
            return jsonify({
                "ok": False,
                "error": "telegram_chat_id is required"
            }), 400

        if not consultant_id:
            return jsonify({
                "ok": False,
                "error": "consultant_id is required"
            }), 400

        consultant = Consultant.query.get(consultant_id)
        if not consultant:
            return jsonify({
                "ok": False,
                "error": "consultant not found"
            }), 404

        existing = TelegramContactBinding.query.filter_by(
            telegram_chat_id=telegram_chat_id
        ).first()

        if existing:
            existing.telegram_user_id = telegram_user_id or existing.telegram_user_id
            existing.telegram_username = telegram_username or existing.telegram_username
            existing.display_name = display_name or existing.display_name
            existing.consultant_id = consultant_id
            existing.is_active = True
            db.session.commit()

            return jsonify({
                "ok": True,
                "message": "binding updated",
                "binding": existing.to_dict()
            }), 200

        binding = TelegramContactBinding(
            telegram_chat_id=telegram_chat_id,
            telegram_user_id=telegram_user_id or None,
            telegram_username=telegram_username or None,
            display_name=display_name or None,
            consultant_id=consultant_id,
            is_active=True
        )

        db.session.add(binding)
        db.session.commit()

        return jsonify({
            "ok": True,
            "message": "binding created",
            "binding": binding.to_dict()
        }), 201

    except Exception as e:
        print(f"Erro em /telegram/bindings: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# ================================================================
# TELEGRAM WEBHOOK (principal)
# ================================================================

@messaging_bp.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    """
    Webhook inicial do Telegram.
    Processa mensagens, comandos e fluxos de visita.
    """
    try:
        h = _get_helpers()
        payload = request.get_json(silent=True) or {}

        chatbot_service = ChatbotService()
        chat_message = chatbot_service.normalize_telegram_update(payload)

        if not chat_message:
            return jsonify({
                "ok": True,
                "message": "update sem mensagem utilizável"
            }), 200

        consultant = h['resolve_telegram_consultant'](chat_message)
        resolved_consultant_id = consultant.id if consultant else 1

        message_text = (chat_message.text or chat_message.caption or "").strip()
        message_text = h['resolve_audio_message_text'](
            chat_message=chat_message,
            payload=payload,
            current_text=message_text,
        )

        if message_text is None:
            return jsonify({
                "ok": False,
                "message": "falha no processamento do áudio"
            }), 200

        message_text = (message_text or "").strip()
        message_text_lower = message_text.lower()

        original_message = message_text
        safe_original_message = original_message

        from services.agent.conversation_memory import add_message as add_conv_message
        if message_text:
            add_conv_message(
                platform="telegram",
                chat_id=chat_message.chat_id,
                text=message_text,
                role="user",
            )

        single_reference = h['resolve_single_active_reference'](
            chat_message=chat_message,
            message_text=message_text,
        )
        if single_reference:
            message_text = single_reference
            message_text_lower = message_text.lower()

        photo_info = h['resolve_pending_photo_for_message'](
            chat_message=chat_message,
            payload=payload,
            current_text=message_text,
        )

        if photo_info == "__PHOTO_ONLY_WAITING_CONTEXT__":
            return jsonify({
                "ok": True,
                "message": "foto recebida e salva temporariamente"
            }), 200

        current_binding = h['find_telegram_binding'](chat_message)

        if message_text_lower == "/start":
            return _handle_start_command(chat_message, current_binding)

        if message_text_lower.startswith("/vincular "):
            return _handle_vincular_command(h, chat_message, message_text)

        if not message_text:
            send_telegram_message(
                chat_id=chat_message.chat_id,
                text="Recebi sua mensagem, mas ainda não consegui interpretar esse formato."
            )
            return jsonify({"ok": True, "message": "mensagem sem texto"}), 200

        if h['normalize_lookup_text'](message_text) in ("cancelar", "cancela", "cancel"):
            return _handle_cancel(h, chat_message)

        priority_state_response = h['handle_priority_stateful_actions'](
            chat_message=chat_message,
            consultant=consultant,
            message_text=message_text,
        )
        if priority_state_response:
            return priority_state_response

        agent_phase2_response = h['handle_agent_phase2_flow'](
            chat_message=chat_message,
            consultant=consultant,
            resolved_consultant_id=resolved_consultant_id,
            message_text=message_text,
        )
        if agent_phase2_response:
            return agent_phase2_response

        if h['is_field_data_save_request'](message_text):
            return h['handle_field_data_save_flow'](
                chat_message=chat_message,
                consultant=consultant,
                message_text=message_text,
            )

        if h['is_field_data_query_request'](message_text):
            return h['handle_field_data_query_flow'](
                chat_message=chat_message,
                consultant=consultant,
                message_text=message_text,
            )

        if h['is_days_planted_request'](message_text):
            return h['handle_days_planted_flow'](
                chat_message=chat_message,
                consultant=consultant,
                message_text=message_text,
            )

        week_schedule_response = h['handle_week_schedule_flow'](
            chat_message=chat_message,
            consultant=consultant,
            resolved_consultant_id=resolved_consultant_id,
            message_text=message_text,
        )
        if week_schedule_response:
            return week_schedule_response

        stale_clients_response = h['handle_stale_clients_ranking_flow'](
            chat_message=chat_message,
            consultant=consultant,
            message_text=message_text,
        )
        if stale_clients_response:
            return stale_clients_response

        daily_routine_response = h['handle_daily_routine_flow'](
            chat_message=chat_message,
            consultant=consultant,
            message_text=message_text,
        )
        if daily_routine_response:
            return daily_routine_response

        week_organization_response = h['handle_week_organization_flow'](
            chat_message=chat_message,
            consultant=consultant,
            message_text=message_text,
        )
        if week_organization_response:
            return week_organization_response

        month_visits_response = h['handle_month_visits_flow'](
            chat_message=chat_message,
            consultant=consultant,
            message_text=message_text,
        )
        if month_visits_response:
            return month_visits_response

        pdf_flow_response = h['handle_pdf_flow'](
            chat_message=chat_message,
            consultant=consultant,
            message_text=message_text,
        )
        if pdf_flow_response:
            return pdf_flow_response

        final_confirmation_response = h['handle_final_confirmation'](
            chat_message=chat_message,
            message_text=message_text,
            photo_info=photo_info,
        )
        if final_confirmation_response:
            return final_confirmation_response

        state = ChatbotConversationState.query.filter_by(
            platform="telegram",
            chat_id=chat_message.chat_id
        ).first()

        if state and state.status in (
            "awaiting_culture",
            "awaiting_planting_confirmation",
            "awaiting_avulsa_confirmation",
            "awaiting_fenologia",
            "awaiting_date",
            "awaiting_observations",
        ):
            return _handle_guided_flow_states(
                h=h,
                state=state,
                chat_message=chat_message,
                message_text=message_text,
                resolved_consultant_id=resolved_consultant_id,
            )

        is_numeric_like_reply = bool(re.fullmatch(r"[\d,\s;]+", message_text.strip()))
        if is_numeric_like_reply:
            client_confirm_response = _handle_client_confirmation_reply(
                h=h,
                chat_message=chat_message,
                message_text=message_text,
                original_message=original_message,
                consultant=consultant,
                resolved_consultant_id=resolved_consultant_id,
            )
            if client_confirm_response:
                return client_confirm_response

        parsed_reply = h['parse_pending_reply'](message_text)

        if parsed_reply and parsed_reply["mode"] in ("update_existing", "close_only", "create_new"):
            pending_reply_response = _handle_pending_visit_reply(
                h=h,
                chat_message=chat_message,
                message_text=message_text,
                parsed_reply=parsed_reply,
                resolved_consultant_id=resolved_consultant_id,
            )
            if pending_reply_response:
                return pending_reply_response

        current_state_row = h['get_current_chatbot_state']("telegram", chat_message.chat_id)
        current_state = current_state_row.status if current_state_row else ""

        ai_result = h['interpret_user_message_with_ai'](
            message_text=message_text,
            current_state=current_state
        ) or {}

        if ai_result and ai_result.get("confidence") in ("high", "medium"):
            message_text = _apply_ai_interpretation(h, ai_result, message_text)

        free_client_guess = h['try_extract_client_from_free_text'](message_text)

        if free_client_guess and not any([
            h['is_week_schedule_request'](message_text),
            h['is_pdf_request'](message_text),
            h['is_last_pdf_request'](message_text),
            h['parse_pending_reply'](message_text),
            h['parse_summary_edit_command'](message_text),
        ]):
            return _handle_free_client_guess(
                h=h,
                chat_message=chat_message,
                free_client_guess=free_client_guess,
                original_message=original_message,
                consultant=consultant,
                resolved_consultant_id=resolved_consultant_id,
            )

        normalized_help = h['normalize_lookup_text'](message_text)

        if normalized_help in {"ajuda", "menu", "o que voce faz", "o que você faz", "comandos"}:
            return _handle_help(chat_message)

        return _handle_default_visit_flow(
            h=h,
            chatbot_service=chatbot_service,
            chat_message=chat_message,
            message_text=message_text,
            safe_original_message=safe_original_message,
            consultant=consultant,
            resolved_consultant_id=resolved_consultant_id,
        )

    except Exception as e:
        print(f"Erro em /telegram/webhook: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# ================================================================
# HELPER FUNCTIONS FOR TELEGRAM WEBHOOK
# ================================================================

def _handle_start_command(chat_message, current_binding):
    """Trata comando /start."""
    if current_binding:
        send_result = send_telegram_message(
            chat_id=chat_message.chat_id,
            text=f"Olá, {current_binding.consultant.name}! Seu Telegram já está vinculado ao AgroCRM ✅"
        )
        return jsonify({
            "ok": True,
            "message": "telegram já vinculado",
            "binding": current_binding.to_dict(),
            "send_result": send_result,
        }), 200

    send_result = send_telegram_message(
        chat_id=chat_message.chat_id,
        text=(
            "Olá! Seu Telegram ainda não está vinculado ao AgroCRM.\n\n"
            "Envie o comando:\n"
            "/vincular SEU_CODIGO\n\n"
            "Exemplo:\n"
            "/vincular JHONAT-AB12"
        )
    )
    return jsonify({
        "ok": True,
        "message": "aguardando vínculo",
        "send_result": send_result,
    }), 200


def _handle_vincular_command(h, chat_message, message_text):
    """Trata comando /vincular."""
    code = message_text[10:].strip()

    binding, error = h['bind_telegram_consultant_by_code'](chat_message, code)

    if error:
        send_result = send_telegram_message(
            chat_id=chat_message.chat_id,
            text="Código inválido. Verifique o código recebido e tente novamente."
        )
        return jsonify({
            "ok": False,
            "message": error,
            "send_result": send_result,
        }), 400

    send_result = send_telegram_message(
        chat_id=chat_message.chat_id,
        text=f"Telegram vinculado com sucesso ✅\nConsultor: {binding.consultant.name}"
    )
    return jsonify({
        "ok": True,
        "message": "vínculo realizado com sucesso",
        "binding": binding.to_dict(),
        "send_result": send_result,
    }), 200


def _handle_cancel(h, chat_message):
    """Trata comando de cancelamento."""
    state = ChatbotConversationState.query.filter_by(
        platform="telegram",
        chat_id=chat_message.chat_id
    ).first()

    if state:
        state.status = "cancelled"
        db.session.commit()

    h['clear_pending_telegram_photos'](chat_message.chat_id)

    send_result = send_telegram_message(
        chat_id=chat_message.chat_id,
        text=h['bot_phrase']("operation_cancelled", "Operação cancelada com sucesso.")
    )

    return jsonify({
        "ok": True,
        "message": "operação cancelada",
        "send_result": send_result,
    }), 200


def _handle_help(chat_message):
    """Envia menu de ajuda."""
    help_text = (
        "🤖 Posso te ajudar com:\n\n"
        "1. Agenda semanal\n"
        "- Ex.: agenda da semana\n"
        "- Ex.: lança a 3\n"
        "- Ex.: conclui a 2\n\n"
        "2. Rotina do dia\n"
        "- Ex.: meu dia\n"
        "- Ex.: agenda de hoje\n"
        "- Ex.: prioridades de hoje\n\n"
        "3. Clientes mais atrasados\n"
        "- Ex.: clientes mais atrasados\n"
        "- Ex.: visitas do mês atrasadas\n\n"
        "4. PDFs\n"
        "- Ex.: pdf\n"
        "- Ex.: pdf da ultima visita\n"
        "- Ex.: pdf do Evaristo\n\n"
        "5. Lançar visita em linguagem natural\n"
        "- Ex.: cliente Marcelo Alonso soja v4 hoje aplicar fungicida\n"
        "- Ex.: a terceira\n"
        "- Ex.: essa\n\n"
        "6. Organização da semana\n"
        "- Ex.: organiza minha semana\n"
        "- Ex.: organize a minha semana\n"
        "- Ex.: monta minha semana\n"
        "- Ex.: planeja minha semana\n"
    )

    send_telegram_message(chat_id=chat_message.chat_id, text=help_text)

    return jsonify({"ok": True, "message": "ajuda enviada"}), 200


def _handle_guided_flow_states(h, state, chat_message, message_text, resolved_consultant_id):
    """Trata estados do fluxo guiado (cultura, plantio, fenologia, etc)."""
    stored_data = json.loads(state.visit_preview_json or "{}")
    action = stored_data.get("action")
    final_visit_payload = stored_data.get("final_visit_payload") or {}
    selected_pending_visit = stored_data.get("selected_pending_visit")
    close_only = stored_data.get("close_only", False)

    if state.status == "awaiting_culture":
        culture_input = h['normalize_culture_input'](message_text)

        if not culture_input:
            send_telegram_message(
                chat_id=chat_message.chat_id,
                text="🌱 Cultura inválida.\nEnvie algo como: Milho, Soja ou Algodão."
            )
            return jsonify({"ok": True, "message": "cultura inválida"}), 200

        final_visit_payload["culture"] = culture_input

        state.visit_preview_json = json.dumps(
            h['build_guided_state_payload'](
                action=action,
                final_visit_payload=final_visit_payload,
                selected_pending_visit=selected_pending_visit,
                close_only=close_only,
            ),
            ensure_ascii=False
        )
        state.status = "awaiting_planting_confirmation"
        db.session.commit()

        send_telegram_message(
            chat_id=chat_message.chat_id,
            text="🌱 É visita de plantio?\nResponda com SIM ou NÃO."
        )

        return jsonify({"ok": True, "message": "cultura recebida"}), 200

    if state.status == "awaiting_planting_confirmation":
        yes_no = h['parse_yes_no'](message_text)

        if yes_no is None:
            send_telegram_message(
                chat_id=chat_message.chat_id,
                text="🌱 Resposta inválida.\nResponda apenas com SIM ou NÃO."
            )
            return jsonify({"ok": True, "message": "resposta inválida"}), 200

        if yes_no is True:
            final_visit_payload["fenologia_real"] = "Plantio"

            state.visit_preview_json = json.dumps(
                h['build_guided_state_payload'](
                    action=action,
                    final_visit_payload=final_visit_payload,
                    selected_pending_visit=selected_pending_visit,
                    close_only=close_only,
                ),
                ensure_ascii=False
            )
            state.status = "awaiting_date"
            db.session.commit()

            send_telegram_message(
                chat_id=chat_message.chat_id,
                text="📅 Informe a data da visita.\nExemplos: hoje, amanhã, 15, 24/02/2026"
            )

            return jsonify({"ok": True, "message": "plantio confirmado"}), 200

        state.visit_preview_json = json.dumps(
            h['build_guided_state_payload'](
                action=action,
                final_visit_payload=final_visit_payload,
                selected_pending_visit=selected_pending_visit,
                close_only=close_only,
            ),
            ensure_ascii=False
        )
        state.status = "awaiting_avulsa_confirmation"
        db.session.commit()

        send_telegram_message(
            chat_id=chat_message.chat_id,
            text="📌 É uma visita avulsa?\nResponda com SIM ou NÃO."
        )

        return jsonify({"ok": True, "message": "aguardando avulsa"}), 200

    if state.status == "awaiting_avulsa_confirmation":
        yes_no = h['parse_yes_no'](message_text)

        if yes_no is None:
            send_telegram_message(
                chat_id=chat_message.chat_id,
                text="📌 Resposta inválida.\nResponda apenas com SIM ou NÃO."
            )
            return jsonify({"ok": True, "message": "resposta inválida"}), 200

        if yes_no is True:
            forced_payload = {
                **(final_visit_payload or {}),
                "linked_pending_visit_id": None,
            }

            state.visit_preview_json = json.dumps(
                h['build_guided_state_payload'](
                    action="create_new_visit",
                    final_visit_payload=forced_payload,
                    selected_pending_visit=None,
                    close_only=False,
                ),
                ensure_ascii=False
            )
            state.status = "awaiting_fenologia"
            db.session.commit()

            send_telegram_message(
                chat_id=chat_message.chat_id,
                text="🌿 Perfeito. Como é visita avulsa, vou criar uma NOVA visita.\nAgora me informe a fenologia observada.\nExemplo: V4, V5, VE, VT, R1"
            )

            return jsonify({"ok": True, "message": "avulsa confirmada"}), 200

        send_telegram_message(
            chat_id=chat_message.chat_id,
            text=(
                "No momento consigo seguir com dois tipos de nova visita:\n"
                "- visita de plantio\n"
                "- visita avulsa\n\n"
                "Se quiser, me envie novamente os dados da visita."
            )
        )

        state.status = "cancelled"
        db.session.commit()

        return jsonify({"ok": True, "message": "fluxo encerrado"}), 200

    if state.status == "awaiting_fenologia":
        if not h['is_valid_fenologia'](message_text.strip()):
            send_telegram_message(
                chat_id=chat_message.chat_id,
                text="🌿 Fenologia inválida.\nEnvie algo como: V4, V5, R1, Plantio, Emergência"
            )
            return jsonify({"ok": True, "message": "fenologia inválida"}), 200

        fenologia_map = {
            "emergencia": "Emergência",
            "plantio": "Plantio",
            "floracao": "Floração",
            "maturacao": "Maturação",
            "enchimento": "Enchimento de grãos",
            "colheita": "Colheita",
            "dessecacao": "Dessecação",
        }
        normalized_fen = h['normalize_lookup_text'](message_text.strip())
        fenologia_input = fenologia_map.get(normalized_fen, message_text.strip().upper())
        final_visit_payload["fenologia_real"] = fenologia_input

        has_date = bool(final_visit_payload.get("date"))
        has_obs = bool((final_visit_payload.get("recommendation") or "").strip())

        if not has_date:
            next_status = "awaiting_date"
            next_message = "📅 Informe a data da visita.\nExemplo: 24/02/2026"
        elif not has_obs:
            next_status = "awaiting_observations"
            next_message = "💬 Informe as observações da visita."
        else:
            summary_text = h['build_visit_summary_text'](
                action=action,
                final_visit_payload=final_visit_payload,
                selected_pending_visit=selected_pending_visit,
                close_only=close_only
            )
            state.visit_preview_json = json.dumps(
                h['build_guided_state_payload'](
                    action=action,
                    final_visit_payload=final_visit_payload,
                    selected_pending_visit=selected_pending_visit,
                    close_only=close_only,
                ),
                ensure_ascii=False
            )
            state.confirmation_text = summary_text
            state.status = "awaiting_final_confirmation"
            db.session.commit()

            send_telegram_message(chat_id=chat_message.chat_id, text=summary_text)
            return jsonify({"ok": True, "message": "resumo final"}), 200

        state.visit_preview_json = json.dumps(
            h['build_guided_state_payload'](
                action=action,
                final_visit_payload=final_visit_payload,
                selected_pending_visit=selected_pending_visit,
                close_only=close_only,
            ),
            ensure_ascii=False
        )
        state.status = next_status
        db.session.commit()

        send_telegram_message(chat_id=chat_message.chat_id, text=next_message)
        return jsonify({"ok": True, "message": "fenologia recebida"}), 200

    if state.status == "awaiting_date":
        parsed_date_obj = h['parse_human_date'](
            message_text.strip(),
            base_date=h['get_local_today']()
        )
        if not parsed_date_obj:
            send_telegram_message(
                chat_id=chat_message.chat_id,
                text="Data inválida. Envie: hoje, amanhã, ontem, 2 dias atrás, 15, 24/02/2026 ou 2026-02-24."
            )
            return jsonify({"ok": True, "message": "data inválida"}), 200

        final_visit_payload["date"] = parsed_date_obj.isoformat()

        state.visit_preview_json = json.dumps(
            h['build_guided_state_payload'](
                action=action,
                final_visit_payload=final_visit_payload,
                selected_pending_visit=selected_pending_visit,
                close_only=close_only,
            ),
            ensure_ascii=False
        )
        has_obs = bool((final_visit_payload.get("recommendation") or "").strip())

        if has_obs:
            summary_text = h['build_visit_summary_text'](
                action=action,
                final_visit_payload=final_visit_payload,
                selected_pending_visit=selected_pending_visit,
                close_only=close_only
            )
            state.confirmation_text = summary_text
            state.status = "awaiting_final_confirmation"
            db.session.commit()

            send_telegram_message(chat_id=chat_message.chat_id, text=summary_text)
            return jsonify({"ok": True, "message": "resumo final"}), 200

        state.status = "awaiting_observations"
        db.session.commit()

        send_telegram_message(
            chat_id=chat_message.chat_id,
            text="💬 Informe as observações da visita."
        )

        return jsonify({"ok": True, "message": "data recebida"}), 200

    if state.status == "awaiting_observations":
        observations_input = message_text.strip()

        if observations_input == "":
            send_telegram_message(
                chat_id=chat_message.chat_id,
                text="💬 Envie algo nas observações, mesmo que seja apenas ."
            )
            return jsonify({"ok": True, "message": "observação vazia"}), 200

        final_visit_payload["recommendation"] = observations_input

        summary_text = h['build_visit_summary_text'](
            action=action,
            final_visit_payload=final_visit_payload,
            selected_pending_visit=selected_pending_visit,
            close_only=close_only
        )

        state.visit_preview_json = json.dumps(
            h['build_guided_state_payload'](
                action=action,
                final_visit_payload=final_visit_payload,
                selected_pending_visit=selected_pending_visit,
                close_only=close_only,
            ),
            ensure_ascii=False
        )
        state.confirmation_text = summary_text
        state.status = "awaiting_final_confirmation"
        db.session.commit()

        send_telegram_message(chat_id=chat_message.chat_id, text=summary_text)

        return jsonify({"ok": True, "message": "observações recebidas"}), 200

    return None


def _handle_client_confirmation_reply(h, chat_message, message_text, original_message, consultant, resolved_consultant_id):
    """Trata resposta numérica para confirmação de cliente."""
    state = ChatbotConversationState.query.filter_by(
        platform="telegram",
        chat_id=chat_message.chat_id,
        status="awaiting_client_confirmation"
    ).first()

    if not state:
        return None

    client_candidates = json.loads(state.pending_visit_suggestions_json or "[]")

    try:
        idx = int(message_text.strip()) - 1
    except ValueError:
        return None

    if idx < 0 or idx >= len(client_candidates):
        send_telegram_message(
            chat_id=chat_message.chat_id,
            text="Opção inválida. Responda com o número correto do cliente."
        )
        return jsonify({"ok": True, "message": "opção inválida"}), 200

    selected_client = client_candidates[idx]
    selected_client_id = selected_client.get("id")

    matched_client = Client.query.get(selected_client_id)
    if not matched_client:
        send_telegram_message(
            chat_id=chat_message.chat_id,
            text="Não consegui localizar o cliente escolhido."
        )
        return jsonify({"ok": True, "message": "cliente não encontrado"}), 200

    safe_original_message = (state.last_message or original_message or message_text or "").strip()
    parsed = h['parse_chatbot_message'](safe_original_message) or {}

    parsed_recommendation = h['extract_recommendation_fallback'](safe_original_message)
    if not parsed_recommendation:
        parsed_recommendation = (parsed.get("recommendation") or "").strip()

    parsed_products = h['normalize_products_from_parsed'](parsed.get("products") or [])

    matched_property, property_candidates, property_needs_confirmation = h['find_property_by_name'](
        parsed.get("property_name"),
        matched_client.id if matched_client else None
    )

    pending_visits, same_culture_found = [], False

    if matched_client:
        pending_visits, same_culture_found = h['find_pending_visits'](
            client_id=matched_client.id,
            property_id=matched_property.id if matched_property else None,
            culture=parsed.get("culture"),
            consultant_id=consultant.id if consultant else None,
            limit=5
        )

    suggestions = [
        {
            "id": v.id,
            "date": v.date.isoformat() if v.date else None,
            "status": v.status,
            "culture": v.culture,
            "variety": v.variety,
            "fenologia_real": v.fenologia_real,
            "recommendation": (v.recommendation or "").strip(),
            "client_id": v.client_id,
            "property_id": v.property_id,
            "plot_id": v.plot_id,
            "property_name": v.property.name if getattr(v, "property", None) else "",
            "plot_name": v.plot.name if getattr(v, "plot", None) else "",
            "display_text": v.to_dict().get("display_text"),
        }
        for v in pending_visits
    ]

    visit_preview = {
        "client_id": matched_client.id,
        "property_id": matched_property.id if matched_property else None,
        "plot_id": None,
        "consultant_id": resolved_consultant_id,
        "date": parsed.get("date"),
        "status": parsed.get("status", "planned"),
        "culture": parsed.get("culture") or "",
        "variety": "",
        "fenologia_real": parsed.get("fenologia_real"),
        "recommendation": parsed_recommendation,
        "products": parsed_products,
        "latitude": None,
        "longitude": None,
        "generate_schedule": False,
        "source": parsed.get("source", "chatbot"),
    }

    if not suggestions:
        return h['start_new_visit_direct_confirmation'](
            state=state,
            chat_message=chat_message,
            visit_preview=visit_preview,
            matched_client=matched_client,
            matched_property=matched_property,
        )

    confirmation_text = h['build_pending_visits_confirmation_text'](
        client_name=matched_client.name,
        requested_culture=parsed.get("culture"),
        suggestions=suggestions,
        same_culture_found=same_culture_found
    )

    state.pending_visit_suggestions_json = json.dumps(suggestions, ensure_ascii=False)
    state.visit_preview_json = json.dumps(visit_preview, ensure_ascii=False)
    state.confirmation_text = confirmation_text
    state.status = "awaiting_confirmation"

    db.session.commit()

    send_result = send_telegram_message(chat_id=chat_message.chat_id, text=confirmation_text)

    return jsonify({
        "ok": True,
        "message": "cliente confirmado",
        "matched_client": matched_client.to_dict(),
        "send_result": send_result,
    }), 200


def _handle_pending_visit_reply(h, chat_message, message_text, parsed_reply, resolved_consultant_id):
    """Trata resposta para seleção de visita pendente."""
    state = ChatbotConversationState.query.filter_by(
        platform="telegram",
        chat_id=chat_message.chat_id,
        status="awaiting_confirmation"
    ).first()

    if not state:
        return None

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
            h['build_guided_state_payload'](
                action="create_new_visit",
                final_visit_payload=final_visit_payload,
                selected_pending_visit=None,
                close_only=False,
            ),
            ensure_ascii=False
        )
        state.status = "awaiting_culture"
        db.session.commit()

        send_telegram_message(
            chat_id=chat_message.chat_id,
            text="🌱 Informe a cultura da visita.\nExemplo: Milho, Soja, Algodão"
        )

        return jsonify({"ok": True, "message": "aguardando cultura", "action": "create_new_visit"}), 200

    idx = parsed_reply.get("index", -1)

    if idx < 0 or idx >= len(pending_visit_suggestions):
        send_telegram_message(
            chat_id=chat_message.chat_id,
            text="Número inválido da lista. Revise as opções e tente novamente."
        )
        return jsonify({"ok": True, "message": "índice inválido"}), 200

    selected_pending_visit = pending_visit_suggestions[idx]
    action = "use_existing_pending_visit"
    close_only = (mode == "close_only")

    final_visit_payload = {
        **visit_preview,
        "client_id": selected_pending_visit.get("client_id") or visit_preview.get("client_id"),
        "property_id": selected_pending_visit.get("property_id") or visit_preview.get("property_id"),
        "plot_id": selected_pending_visit.get("plot_id") or visit_preview.get("plot_id"),
        "consultant_id": resolved_consultant_id or visit_preview.get("consultant_id"),
        "linked_pending_visit_id": selected_pending_visit.get("id"),
        "status": "done",
        "culture": visit_preview.get("culture") or selected_pending_visit.get("culture") or "",
        "variety": selected_pending_visit.get("variety") or visit_preview.get("variety") or "",
        "fenologia_real": visit_preview.get("fenologia_real"),
        "date": visit_preview.get("date"),
        "recommendation": visit_preview.get("recommendation") or "",
        "products": visit_preview.get("products") or [],
        "latitude": visit_preview.get("latitude"),
        "longitude": visit_preview.get("longitude"),
        "source": "chatbot",
    }

    if close_only:
        summary_text = h['build_visit_summary_text'](
            action=action,
            final_visit_payload=final_visit_payload,
            selected_pending_visit=selected_pending_visit,
            close_only=True
        )

        state.visit_preview_json = json.dumps(
            h['build_guided_state_payload'](
                action=action,
                final_visit_payload=final_visit_payload,
                selected_pending_visit=selected_pending_visit,
                close_only=True,
            ),
            ensure_ascii=False
        )
        state.confirmation_text = summary_text
        state.status = "awaiting_final_confirmation"
        db.session.commit()

        send_telegram_message(chat_id=chat_message.chat_id, text=summary_text)
        return jsonify({"ok": True, "message": "resumo enviado"}), 200

    original_message = (state.last_message or "").strip()
    robust_prefill = h['extract_prefill_from_message_text'](original_message)
    original_parsed = h['parse_chatbot_message'](original_message) or {}
    fallback_products = h['normalize_products_from_parsed'](original_parsed.get("products") or [])

    if not (final_visit_payload.get("fenologia_real") or "").strip():
        final_visit_payload["fenologia_real"] = (
            (robust_prefill.get("fenologia_real") or "").strip()
            or (original_parsed.get("fenologia_real") or "").strip()
            or None
        )

    if not final_visit_payload.get("date"):
        parsed_fallback_date = robust_prefill.get("date") or original_parsed.get("date")
        if parsed_fallback_date:
            parsed_fallback_date = h['parse_date_flexible'](parsed_fallback_date) or parsed_fallback_date
        final_visit_payload["date"] = parsed_fallback_date

    if not (final_visit_payload.get("recommendation") or "").strip():
        final_visit_payload["recommendation"] = (
            (robust_prefill.get("recommendation") or "").strip()
            or (original_parsed.get("recommendation") or "").strip()
            or (selected_pending_visit.get("recommendation") or "").strip()
            or ""
        )

    if not final_visit_payload.get("products"):
        final_visit_payload["products"] = robust_prefill.get("products") or fallback_products or []

    has_prefilled_fenologia = bool((final_visit_payload.get("fenologia_real") or "").strip())
    has_prefilled_date = bool(final_visit_payload.get("date"))
    has_prefilled_observation = bool((final_visit_payload.get("recommendation") or "").strip())

    if has_prefilled_fenologia and has_prefilled_date and has_prefilled_observation:
        summary_text = h['build_visit_summary_text'](
            action=action,
            final_visit_payload=final_visit_payload,
            selected_pending_visit=selected_pending_visit,
            close_only=False
        )

        state.visit_preview_json = json.dumps(
            h['build_guided_state_payload'](
                action=action,
                final_visit_payload=final_visit_payload,
                selected_pending_visit=selected_pending_visit,
                close_only=False,
            ),
            ensure_ascii=False
        )
        state.confirmation_text = summary_text
        state.status = "awaiting_final_confirmation"
        db.session.commit()

        send_telegram_message(chat_id=chat_message.chat_id, text=summary_text)
        return jsonify({"ok": True, "message": "resumo final enviado"}), 200

    composite_fenologia = (parsed_reply or {}).get("fenologia")
    if composite_fenologia and not has_prefilled_fenologia:
        final_visit_payload["fenologia_real"] = composite_fenologia
        has_prefilled_fenologia = True

    if not has_prefilled_fenologia:
        next_status = "awaiting_fenologia"
        next_message = "🌿 Informe a fenologia observada.\nExemplo: V4, V5, R1"
    elif not has_prefilled_date:
        next_status = "awaiting_date"
        next_message = "📅 Informe a data da visita.\nExemplo: hoje, ontem ou 24/02/2026"
    else:
        next_status = "awaiting_observations"
        next_message = "💬 Informe as observações da visita."

    state.visit_preview_json = json.dumps(
        h['build_guided_state_payload'](
            action=action,
            final_visit_payload=final_visit_payload,
            selected_pending_visit=selected_pending_visit,
            close_only=False,
        ),
        ensure_ascii=False
    )
    state.status = next_status
    db.session.commit()

    send_telegram_message(chat_id=chat_message.chat_id, text=next_message)

    return jsonify({"ok": True, "message": "fluxo guiado", "next_status": next_status}), 200


def _apply_ai_interpretation(h, ai_result, message_text):
    """Aplica interpretação da IA para transformar a mensagem."""
    ai_intent = ai_result.get("intent")

    intent_map = {
        "week_schedule_request": "agenda da semana",
        "pdf_last_visit": "pdf da última visita",
        "pdf_recent_visits": "gerar pdf",
        "confirm": "CONFIRMAR",
        "cancel": "CANCELAR",
        "today_schedule_request": "agenda de hoje",
        "daily_routine_request": "rotina do dia",
    }

    if ai_intent in intent_map:
        return intent_map[ai_intent]

    if ai_intent == "edit_summary":
        field = ai_result.get("field")
        value = (ai_result.get("value") or "").strip()

        if field and value:
            field_map = {
                "fenologia_real": "ALTERAR FENOLOGIA",
                "date": "ALTERAR DATA",
                "recommendation": "ALTERAR OBSERVACAO",
                "culture": "ALTERAR CULTURA",
                "variety": "ALTERAR VARIEDADE",
            }

            prefix = field_map.get(field)
            if prefix:
                return f"{prefix} {value}"

    elif ai_intent == "launch_week_visit":
        visit_index = ai_result.get("visit_index")
        if visit_index:
            return f"LANCAR VISITA {visit_index}"

    elif ai_intent == "complete_week_visit":
        visit_index = ai_result.get("visit_index")
        if visit_index:
            return f"CONCLUIR VISITA {visit_index}"

    elif ai_intent == "create_visit_like_message":
        parsed_visit = ai_result.get("parsed_visit") or {}

        ai_parts = []
        for key, prefix in [
            ("client_name", "cliente"),
            ("property_name", "fazenda"),
            ("plot_name", "talhao"),
        ]:
            if parsed_visit.get(key):
                ai_parts.append(f"{prefix} {parsed_visit[key]}")

        for key in ["culture", "fenologia_real", "date", "recommendation"]:
            if parsed_visit.get(key):
                ai_parts.append(str(parsed_visit[key]))

        if ai_parts:
            return " ".join(ai_parts)

    elif ai_intent == "pdf_by_client_reference":
        parsed_visit = ai_result.get("parsed_visit") or {}
        client_name = (parsed_visit.get("client_name") or "").strip()
        if client_name:
            return f"pdf do cliente {client_name}"

    elif ai_intent == "contextual_visit_reference":
        visit_index = ai_result.get("visit_index")
        if visit_index:
            return str(visit_index)

    return message_text


def _handle_free_client_guess(h, chat_message, free_client_guess, original_message, consultant, resolved_consultant_id):
    """Trata caso onde cliente foi identificado por texto livre."""
    guessed_client = free_client_guess["client"]

    pending_visits, same_culture_found = h['find_pending_visits'](
        client_id=guessed_client.id,
        property_id=None,
        culture=None,
        consultant_id=consultant.id if consultant else None,
        limit=5
    )

    suggestions = [
        {
            "id": v.id,
            "date": v.date.isoformat() if v.date else None,
            "status": v.status,
            "culture": v.culture,
            "variety": v.variety,
            "fenologia_real": v.fenologia_real,
            "recommendation": (v.recommendation or "").strip(),
            "client_id": v.client_id,
            "property_id": v.property_id,
            "plot_id": v.plot_id,
            "property_name": v.property.name if getattr(v, "property", None) else "",
            "plot_name": v.plot.name if getattr(v, "plot", None) else "",
            "display_text": v.to_dict().get("display_text"),
        }
        for v in pending_visits
    ]

    state = ChatbotConversationState.query.filter_by(
        platform="telegram",
        chat_id=chat_message.chat_id
    ).first()

    if not state:
        state = ChatbotConversationState(platform="telegram", chat_id=chat_message.chat_id)
        db.session.add(state)

    state.last_message = original_message

    prefill = h['extract_prefill_from_message_text'](original_message)

    visit_preview = {
        "client_id": guessed_client.id,
        "property_id": None,
        "plot_id": None,
        "consultant_id": resolved_consultant_id,
        "date": prefill.get("date"),
        "status": "planned",
        "culture": prefill.get("culture") or "",
        "variety": "",
        "fenologia_real": prefill.get("fenologia_real"),
        "recommendation": prefill.get("recommendation") or "",
        "products": prefill.get("products") or [],
        "latitude": None,
        "longitude": None,
        "generate_schedule": False,
        "source": "chatbot",
    }

    if not suggestions:
        return h['start_new_visit_direct_confirmation'](
            state=state,
            chat_message=chat_message,
            visit_preview=visit_preview,
            matched_client=guessed_client,
            matched_property=None,
        )

    confirmation_text = h['build_pending_visits_confirmation_text'](
        client_name=guessed_client.name,
        requested_culture=None,
        suggestions=suggestions,
        same_culture_found=same_culture_found
    )

    state.pending_visit_suggestions_json = json.dumps(suggestions, ensure_ascii=False)
    state.visit_preview_json = json.dumps(visit_preview, ensure_ascii=False)
    state.confirmation_text = confirmation_text
    state.status = "awaiting_confirmation"
    db.session.commit()

    send_result = send_telegram_message(chat_id=chat_message.chat_id, text=confirmation_text)

    return jsonify({
        "ok": True,
        "message": "cliente identificado",
        "matched_client": guessed_client.to_dict(),
        "send_result": send_result,
    }), 200


def _handle_default_visit_flow(h, chatbot_service, chat_message, message_text, safe_original_message, consultant, resolved_consultant_id):
    """Fluxo padrão de parsing e sugestão de visitas."""
    parsed = h['parse_chatbot_message'](message_text)

    matched_client, client_candidates, client_needs_confirmation = h['find_client_by_name'](
        parsed.get("client_name")
    )

    matched_property, property_candidates, property_needs_confirmation = h['find_property_by_name'](
        parsed.get("property_name"),
        matched_client.id if matched_client else None
    )

    if client_needs_confirmation:
        confirmation_text = h['build_name_confirmation_text']("cliente", client_candidates)

        state = ChatbotConversationState.query.filter_by(
            platform="telegram",
            chat_id=chat_message.chat_id
        ).first()

        if not state:
            state = ChatbotConversationState(platform="telegram", chat_id=chat_message.chat_id)
            db.session.add(state)

        state.last_message = safe_original_message
        state.pending_visit_suggestions_json = json.dumps(
            [{"id": c.id, "name": c.name} for c in client_candidates[:3]],
            ensure_ascii=False
        )
        state.visit_preview_json = json.dumps({}, ensure_ascii=False)
        state.confirmation_text = confirmation_text
        state.status = "awaiting_client_confirmation"

        db.session.commit()

        send_result = send_telegram_message(chat_id=chat_message.chat_id, text=confirmation_text)

        return jsonify({
            "ok": True,
            "confirmation_text": confirmation_text,
            "send_result": send_result,
        }), 200

    pending_visits, same_culture_found = [], False

    if matched_client:
        pending_visits, same_culture_found = h['find_pending_visits'](
            client_id=matched_client.id,
            property_id=matched_property.id if matched_property else None,
            culture=parsed.get("culture"),
            consultant_id=consultant.id if consultant else None,
            limit=5
        )

    suggestions = [
        {
            "id": v.id,
            "date": v.date.isoformat() if v.date else None,
            "status": v.status,
            "culture": v.culture,
            "variety": v.variety,
            "fenologia_real": v.fenologia_real,
            "recommendation": (v.recommendation or "").strip(),
            "client_id": v.client_id,
            "property_id": v.property_id,
            "plot_id": v.plot_id,
            "property_name": v.property.name if getattr(v, "property", None) else "",
            "plot_name": v.plot.name if getattr(v, "plot", None) else "",
            "display_text": v.to_dict().get("display_text"),
        }
        for v in pending_visits
    ]

    parsed_recommendation = h['extract_recommendation_fallback'](safe_original_message)
    if not parsed_recommendation:
        parsed_recommendation = (parsed.get("recommendation") or "").strip()

    parsed_products = h['normalize_products_from_parsed'](parsed.get("products") or [])

    if matched_client:
        confirmation_text = h['build_pending_visits_confirmation_text'](
            client_name=matched_client.name,
            requested_culture=parsed.get("culture"),
            suggestions=suggestions,
            same_culture_found=same_culture_found
        )
    else:
        confirmation_text = (
            "Não consegui localizar o cliente informado.\n\n"
            "Tente enviar no formato:\n"
            "cliente NOME_CLIENTE fazenda NOME_FAZENDA cultura estágio observação"
        )

    visit_preview = {
        "client_id": matched_client.id if matched_client else None,
        "property_id": matched_property.id if matched_property else None,
        "plot_id": None,
        "consultant_id": resolved_consultant_id,
        "date": parsed.get("date"),
        "status": parsed.get("status", "planned"),
        "culture": parsed.get("culture") or "",
        "variety": "",
        "fenologia_real": parsed.get("fenologia_real"),
        "recommendation": parsed_recommendation,
        "products": parsed_products,
        "latitude": None,
        "longitude": None,
        "generate_schedule": False,
        "source": parsed.get("source", "chatbot"),
    }

    state = ChatbotConversationState.query.filter_by(
        platform="telegram",
        chat_id=chat_message.chat_id
    ).first()

    if not state:
        state = ChatbotConversationState(platform="telegram", chat_id=chat_message.chat_id)
        db.session.add(state)

    state.last_message = safe_original_message
    state.pending_visit_suggestions_json = json.dumps(suggestions, ensure_ascii=False)
    state.visit_preview_json = json.dumps(visit_preview, ensure_ascii=False)
    state.confirmation_text = confirmation_text
    state.status = "awaiting_confirmation"

    db.session.commit()

    send_result = send_telegram_message(chat_id=chat_message.chat_id, text=confirmation_text)

    return jsonify({
        "ok": True,
        "telegram_summary": chatbot_service.build_internal_summary(chat_message),
        "parsed_message": parsed,
        "matched_client": matched_client.to_dict() if matched_client else None,
        "matched_property": matched_property.to_dict() if matched_property else None,
        "pending_visit_suggestions": suggestions,
        "same_culture_found": same_culture_found,
        "confirmation_text": confirmation_text,
        "send_result": send_result,
    }), 200
