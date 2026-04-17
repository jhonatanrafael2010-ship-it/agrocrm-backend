"""
================================================================
Agent Metrics Routes
================================================================

Blueprint SEPARADO do routes.py principal, seguindo o padrao
strangler fig: toda rota NOVA nasce em arquivo proprio.

Expõe endpoints READ-ONLY para consultar o AgentDecisionLog
e medir a qualidade do bot ao longo do tempo.

Endpoints:
  GET /api/agent/metrics/summary
    -> resumo geral (totais por intent, confidence, action)

  GET /api/agent/metrics/recent?limit=50
    -> ultimas N decisoes do agente (default 50, max 500)

  GET /api/agent/metrics/unknown?limit=50
    -> ultimas mensagens que cairam em UNKNOWN
       (util para saber o que o bot nao entendeu)

Estes endpoints sao apenas de LEITURA. Nao mexem em dado.
================================================================
"""

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from models import db, AgentDecisionLog


agent_metrics_bp = Blueprint(
    "agent_metrics",
    __name__,
    url_prefix="/api/agent/metrics",
)


def _row_to_dict(row: AgentDecisionLog) -> dict:
    if not row:
        return {}
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "platform": row.platform,
        "chat_id": row.chat_id,
        "consultant_id": row.consultant_id,
        "raw_message": row.raw_message,
        "current_state": row.current_state,
        "intent": row.intent,
        "intent_confidence": row.intent_confidence,
        "intent_matched_by": row.intent_matched_by,
        "decision_action": row.decision_action,
        "decision_reason": row.decision_reason,
        "executed": bool(row.executed) if row.executed is not None else False,
    }


@agent_metrics_bp.route("/summary", methods=["GET"])
def metrics_summary():
    """
    Retorna totais agregados:
      - total de decisoes registradas
      - contagem por intent
      - contagem por confidence
      - contagem por action
      - quantas foram de fato executadas
    """
    try:
        total = db.session.query(func.count(AgentDecisionLog.id)).scalar() or 0

        executed_total = (
            db.session.query(func.count(AgentDecisionLog.id))
            .filter(AgentDecisionLog.executed.is_(True))
            .scalar()
            or 0
        )

        by_intent = (
            db.session.query(AgentDecisionLog.intent, func.count(AgentDecisionLog.id))
            .group_by(AgentDecisionLog.intent)
            .all()
        )

        by_confidence = (
            db.session.query(AgentDecisionLog.intent_confidence, func.count(AgentDecisionLog.id))
            .group_by(AgentDecisionLog.intent_confidence)
            .all()
        )

        by_action = (
            db.session.query(AgentDecisionLog.decision_action, func.count(AgentDecisionLog.id))
            .group_by(AgentDecisionLog.decision_action)
            .all()
        )

        by_matched_by = (
            db.session.query(AgentDecisionLog.intent_matched_by, func.count(AgentDecisionLog.id))
            .group_by(AgentDecisionLog.intent_matched_by)
            .all()
        )

        return jsonify({
            "ok": True,
            "total": total,
            "executed_total": executed_total,
            "execution_rate_pct": round((executed_total / total) * 100, 1) if total else 0.0,
            "by_intent": [{"intent": k or "NULL", "count": v} for k, v in by_intent],
            "by_confidence": [{"confidence": k or "NULL", "count": v} for k, v in by_confidence],
            "by_action": [{"action": k or "NULL", "count": v} for k, v in by_action],
            "by_matched_by": [{"matched_by": k or "NULL", "count": v} for k, v in by_matched_by],
        }), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@agent_metrics_bp.route("/recent", methods=["GET"])
def metrics_recent():
    """
    Retorna as ultimas N decisoes registradas.
    Default 50, limite maximo 500.
    """
    try:
        limit = request.args.get("limit", default=50, type=int)
        limit = max(1, min(limit, 500))

        rows = (
            AgentDecisionLog.query
            .order_by(AgentDecisionLog.id.desc())
            .limit(limit)
            .all()
        )

        return jsonify({
            "ok": True,
            "count": len(rows),
            "items": [_row_to_dict(r) for r in rows],
        }), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@agent_metrics_bp.route("/unknown", methods=["GET"])
def metrics_unknown():
    """
    Retorna as ultimas mensagens que cairam em UNKNOWN.
    E o endpoint mais util para descobrir o que o bot nao esta
    entendendo e precisa de ajuste na heuristica ou no prompt da IA.
    """
    try:
        limit = request.args.get("limit", default=50, type=int)
        limit = max(1, min(limit, 500))

        rows = (
            AgentDecisionLog.query
            .filter(AgentDecisionLog.intent == "UNKNOWN")
            .order_by(AgentDecisionLog.id.desc())
            .limit(limit)
            .all()
        )

        return jsonify({
            "ok": True,
            "count": len(rows),
            "items": [_row_to_dict(r) for r in rows],
        }), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
