# routes/chatbot.py
"""
Endpoints do chatbot (preview/suggest/resolve/commit).
- /chatbot/preview-visit (POST)
- /chatbot/suggest-pending-visits (POST)
- /chatbot/resolve-confirmation (POST)
- /chatbot/commit-visit (POST)
"""

from datetime import date as _date
from flask import Blueprint, jsonify, request

from models import db, Visit

chatbot_bp = Blueprint('chatbot', __name__)


# Importa helpers do módulo principal (serão movidos para helpers.py no futuro)
def _get_helpers():
    """Lazy import para evitar dependência circular."""
    from api_routes import (
        parse_chatbot_message,
        find_client_by_name,
        find_property_by_name,
        find_pending_visits,
        normalize_products_from_parsed,
        build_pending_visits_confirmation_text,
    )
    return {
        'parse_chatbot_message': parse_chatbot_message,
        'find_client_by_name': find_client_by_name,
        'find_property_by_name': find_property_by_name,
        'find_pending_visits': find_pending_visits,
        'normalize_products_from_parsed': normalize_products_from_parsed,
        'build_pending_visits_confirmation_text': build_pending_visits_confirmation_text,
    }


def _extract_recommendation_fallback(message: str) -> str:
    """Extrai recomendação quando o parser principal não encontra."""
    if not message:
        return ""
    lines = message.strip().split("\n")
    if len(lines) >= 4:
        return "\n".join(lines[3:]).strip()
    return ""


@chatbot_bp.route('/chatbot/preview-visit', methods=['POST'])
def chatbot_preview_visit():
    """
    Recebe uma mensagem simples e devolve uma prévia
    do payload que no futuro será enviado para /api/visits.
    Ainda não salva nada no banco.
    """
    try:
        h = _get_helpers()
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        consultant_id = data.get("consultant_id", 1)

        if not message:
            return jsonify({
                "ok": False,
                "error": "message is required"
            }), 400

        parsed = h['parse_chatbot_message'](message)

        matched_client, client_candidates, client_needs_confirmation = h['find_client_by_name'](
            parsed.get("client_name")
        )

        matched_property, property_candidates, property_needs_confirmation = h['find_property_by_name'](
            parsed.get("property_name"),
            matched_client.id if matched_client else None
        )

        visit_payload = {
            "client_id": matched_client.id if matched_client else None,
            "property_id": matched_property.id if matched_property else None,
            "plot_id": None,
            "consultant_id": consultant_id,
            "date": parsed.get("date"),
            "status": parsed.get("status", "planned"),
            "culture": parsed.get("culture") or "",
            "variety": "",
            "fenologia_real": parsed.get("fenologia_real"),
            "recommendation": parsed.get("recommendation") or "",
            "products": [],
            "latitude": None,
            "longitude": None,
            "generate_schedule": False,
            "source": parsed.get("source", "chatbot"),
        }

        return jsonify({
            "ok": True,
            "parsed_message": parsed,
            "matched_entities": {
                "client": matched_client.to_dict() if matched_client else None,
                "property": matched_property.to_dict() if matched_property else None,
            },
            "visit_preview": visit_payload
        }), 200

    except Exception as e:
        print(f"Erro em /chatbot/preview-visit: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@chatbot_bp.route('/chatbot/suggest-pending-visits', methods=['POST'])
def chatbot_suggest_pending_visits():
    """
    Recebe uma mensagem do chatbot, resolve cliente/propriedade
    e sugere visitas pendentes compatíveis para confirmação.
    Ainda não salva nada.
    """
    try:
        h = _get_helpers()
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        consultant_id = data.get("consultant_id", 1)

        if not message:
            return jsonify({
                "ok": False,
                "error": "message is required"
            }), 400

        parsed = h['parse_chatbot_message'](message)

        matched_client, client_candidates, client_needs_confirmation = h['find_client_by_name'](
            parsed.get("client_name")
        )

        matched_property, property_candidates, property_needs_confirmation = h['find_property_by_name'](
            parsed.get("property_name"),
            matched_client.id if matched_client else None
        )

        pending_visits = []
        same_culture_found = False

        if matched_client:
            pending_visits, same_culture_found = h['find_pending_visits'](
                client_id=matched_client.id,
                property_id=matched_property.id if matched_property else None,
                culture=parsed.get("culture"),
                consultant_id=consultant_id,
                limit=5
            )

        parsed_recommendation = (parsed.get("recommendation") or "").strip()
        if not parsed_recommendation:
            parsed_recommendation = _extract_recommendation_fallback(message)

        visit_preview = {
            "client_id": matched_client.id if matched_client else None,
            "property_id": matched_property.id if matched_property else None,
            "plot_id": None,
            "consultant_id": consultant_id,
            "date": parsed.get("date"),
            "status": parsed.get("status", "planned"),
            "culture": (parsed.get("culture") or "").strip(),
            "variety": "",
            "fenologia_real": (parsed.get("fenologia_real") or "").strip() or None,
            "recommendation": parsed_recommendation,
            "products": h['normalize_products_from_parsed'](parsed.get("products") or []),
            "latitude": None,
            "longitude": None,
            "generate_schedule": False,
            "source": parsed.get("source", "chatbot"),
        }

        suggestions = []
        for visit in pending_visits:
            suggestions.append({
                "id": visit.id,
                "date": visit.date.isoformat() if visit.date else None,
                "status": visit.status,
                "culture": visit.culture,
                "variety": visit.variety,
                "fenologia_real": visit.fenologia_real,
                "recommendation": (visit.recommendation or "").strip(),
                "client_id": visit.client_id,
                "property_id": visit.property_id,
                "plot_id": visit.plot_id,
                "property_name": visit.property.name if getattr(visit, "property", None) else "",
                "plot_name": visit.plot.name if getattr(visit, "plot", None) else "",
                "display_text": visit.to_dict().get("display_text"),
            })

        confirmation_text = h['build_pending_visits_confirmation_text'](
            client_name=matched_client.name if matched_client else parsed.get("client_name"),
            requested_culture=parsed.get("culture"),
            suggestions=suggestions,
            same_culture_found=same_culture_found
        )

        return jsonify({
            "ok": True,
            "parsed_message": parsed,
            "matched_entities": {
                "client": matched_client.to_dict() if matched_client else None,
                "property": matched_property.to_dict() if matched_property else None,
            },
            "visit_preview": visit_preview,
            "pending_visit_suggestions": suggestions,
            "needs_confirmation": True if suggestions else False,
            "same_culture_found": same_culture_found,
            "requested_culture": parsed.get("culture"),
            "confirmation_text": confirmation_text,
        }), 200

    except Exception as e:
        print(f"Erro em /chatbot/suggest-pending-visits: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@chatbot_bp.route('/chatbot/resolve-confirmation', methods=['POST'])
def chatbot_resolve_confirmation():
    """
    Recebe a resposta do usuário após a sugestão de visitas pendentes.
    Ainda não salva nada no banco.
    Apenas decide se:
    - usa uma visita pendente existente
    - ou cria uma nova visita
    """
    try:
        data = request.get_json(silent=True) or {}

        user_reply = (data.get("user_reply") or "").strip().upper()
        pending_visit_suggestions = data.get("pending_visit_suggestions") or []
        visit_preview = data.get("visit_preview") or {}

        if not user_reply:
            return jsonify({
                "ok": False,
                "error": "user_reply is required"
            }), 400

        if user_reply == "NOVA":
            return jsonify({
                "ok": True,
                "action": "create_new_visit",
                "selected_pending_visit": None,
                "final_visit_payload": visit_preview,
                "message": "Usuário optou por criar uma nova visita."
            }), 200

        if user_reply.isdigit():
            idx = int(user_reply) - 1

            if idx < 0 or idx >= len(pending_visit_suggestions):
                return jsonify({
                    "ok": False,
                    "error": "opção inválida"
                }), 400

            selected = pending_visit_suggestions[idx]

            merged_payload = {
                **visit_preview,
                "client_id": selected.get("client_id") or visit_preview.get("client_id"),
                "property_id": selected.get("property_id") or visit_preview.get("property_id"),
                "plot_id": selected.get("plot_id") or visit_preview.get("plot_id"),
                "linked_pending_visit_id": selected.get("id"),
            }

            return jsonify({
                "ok": True,
                "action": "use_existing_pending_visit",
                "selected_pending_visit": selected,
                "final_visit_payload": merged_payload,
                "message": f"Usuário escolheu a visita pendente #{user_reply}."
            }), 200

        return jsonify({
            "ok": False,
            "error": "resposta inválida. Use um número ou NOVA"
        }), 400

    except Exception as e:
        print(f"Erro em /chatbot/resolve-confirmation: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@chatbot_bp.route('/chatbot/commit-visit', methods=['POST'])
def chatbot_commit_visit():
    """
    Efetiva a visita no banco.
    - Se action == use_existing_pending_visit: atualiza a visita pendente escolhida e marca como done
    - Se action == create_new_visit: cria nova visita e marca como done
    """
    try:
        data = request.get_json(silent=True) or {}

        action = data.get("action")
        final_visit_payload = data.get("final_visit_payload") or {}
        selected_pending_visit = data.get("selected_pending_visit")

        if not action:
            return jsonify({
                "ok": False,
                "error": "action is required"
            }), 400

        if not final_visit_payload:
            return jsonify({
                "ok": False,
                "error": "final_visit_payload is required"
            }), 400

        final_visit_payload["status"] = "done"

        # 1) Atualizar visita pendente existente
        if action == "use_existing_pending_visit":
            pending_visit_id = final_visit_payload.get("linked_pending_visit_id")

            if not pending_visit_id:
                return jsonify({
                    "ok": False,
                    "error": "linked_pending_visit_id is required for use_existing_pending_visit"
                }), 400

            visit = Visit.query.get(pending_visit_id)
            if not visit:
                return jsonify({
                    "ok": False,
                    "error": "pending visit not found"
                }), 404

            if final_visit_payload.get("date"):
                visit.date = _date.fromisoformat(final_visit_payload["date"])

            visit.status = "done"
            visit.culture = final_visit_payload.get("culture") or visit.culture
            visit.variety = final_visit_payload.get("variety") or visit.variety
            visit.fenologia_real = final_visit_payload.get("fenologia_real")
            visit.recommendation = final_visit_payload.get("recommendation") or visit.recommendation
            visit.consultant_id = final_visit_payload.get("consultant_id") or visit.consultant_id
            visit.latitude = final_visit_payload.get("latitude")
            visit.longitude = final_visit_payload.get("longitude")

            if hasattr(visit, "source"):
                visit.source = final_visit_payload.get("source", "chatbot")

            db.session.commit()

            return jsonify({
                "ok": True,
                "action": action,
                "message": "Visita pendente atualizada com sucesso.",
                "visit": visit.to_dict()
            }), 200

        # 2) Criar nova visita
        if action == "create_new_visit":
            if not final_visit_payload.get("client_id"):
                return jsonify({
                    "ok": False,
                    "error": "client_id is required to create a new visit"
                }), 400

            visit_date = None
            if final_visit_payload.get("date"):
                visit_date = _date.fromisoformat(final_visit_payload["date"])

            new_visit = Visit(
                client_id=final_visit_payload.get("client_id"),
                property_id=final_visit_payload.get("property_id"),
                plot_id=final_visit_payload.get("plot_id"),
                consultant_id=final_visit_payload.get("consultant_id"),
                date=visit_date,
                recommendation=final_visit_payload.get("recommendation") or "",
                status="done",
                culture=final_visit_payload.get("culture") or "",
                variety=final_visit_payload.get("variety") or "",
                fenologia_real=final_visit_payload.get("fenologia_real"),
                latitude=final_visit_payload.get("latitude"),
                longitude=final_visit_payload.get("longitude"),
            )

            if hasattr(new_visit, "source"):
                new_visit.source = final_visit_payload.get("source", "chatbot")

            db.session.add(new_visit)
            db.session.commit()

            return jsonify({
                "ok": True,
                "action": action,
                "message": "Nova visita criada com sucesso.",
                "visit": new_visit.to_dict()
            }), 201

        return jsonify({
            "ok": False,
            "error": "invalid action"
        }), 400

    except Exception as e:
        db.session.rollback()
        print(f"Erro em /chatbot/commit-visit: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500
