"""
================================================================
AgentDecisionLogger
================================================================

Registra cada decisao do agente para permitir medir se o bot
esta acertando. Este servico e 100% isolado:

- Se der qualquer erro, ele SILENCIA e nao quebra o fluxo do bot.
- Ele nunca re-lanca excecao.
- Ele nunca muda o comportamento do agente.
- Ele so ESCREVE logs estruturados.

Por que isso importa:
  Sem observabilidade, nao da para saber se uma mudanca
  futura melhora ou piora a qualidade do agente. Este e o
  trilho que vai sustentar todas as proximas otimizacoes.
================================================================
"""

import json
import traceback
from typing import Any, Dict, Optional


def _safe_dumps(value: Any) -> Optional[str]:
    """
    Converte qualquer coisa para JSON string. Se nao conseguir,
    devolve None e nao quebra.
    """
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        try:
            return json.dumps(str(value), ensure_ascii=False)
        except Exception:
            return None


def _truncate(text: Optional[str], limit: int) -> Optional[str]:
    if text is None:
        return None
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit]


def log_agent_decision(
    *,
    platform: str = "telegram",
    chat_id: Optional[str] = None,
    consultant_id: Optional[int] = None,
    raw_message: Optional[str] = None,
    current_state: Optional[str] = None,
    intent: Optional[str] = None,
    intent_confidence: Optional[str] = None,
    intent_matched_by: Optional[str] = None,
    entities: Optional[Dict[str, Any]] = None,
    decision_action: Optional[str] = None,
    decision_reason: Optional[str] = None,
    executed: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Grava uma linha em AgentDecisionLog.
    NUNCA lanca excecao. Em caso de erro, imprime warning e segue.

    Parametros:
        platform           - "telegram", "whatsapp" etc.
        chat_id            - id do chat do Telegram
        consultant_id      - id do consultor vinculado (pode ser None)
        raw_message        - texto original do usuario (truncado)
        current_state      - estado conversacional no momento da mensagem
        intent             - intent decidida (ex: LIST_WEEK, UNKNOWN)
        intent_confidence  - "high", "medium" ou "low"
        intent_matched_by  - "keyword", "ai_fallback", "state", ...
        entities           - dict com entidades extraidas
        decision_action    - action decidida (ex: ROUTE_TO_WEEK_SCHEDULE)
        decision_reason    - razao textual da decisao
        executed           - True se o agente de fato executou a acao
        extra              - qualquer outro contexto extra (dict)
    """
    try:
        # importacao tardia para nao criar ciclo de import
        from models import db, AgentDecisionLog

        row = AgentDecisionLog(
            platform=_truncate(platform or "telegram", 20),
            chat_id=_truncate(chat_id, 64),
            consultant_id=consultant_id if isinstance(consultant_id, int) else None,
            raw_message=_truncate(raw_message, 2000),
            current_state=_truncate(current_state, 80),
            intent=_truncate(intent, 80),
            intent_confidence=_truncate(intent_confidence, 20),
            intent_matched_by=_truncate(intent_matched_by, 40),
            entities_json=_safe_dumps(entities),
            decision_action=_truncate(decision_action, 80),
            decision_reason=_truncate(decision_reason, 300),
            executed=bool(executed),
            extra_json=_safe_dumps(extra),
        )

        db.session.add(row)
        db.session.commit()

    except Exception as e:
        # Nunca quebra o fluxo do bot por causa do logger.
        print(f"[AgentDecisionLogger] warning - falha ao gravar log: {e}")
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        traceback.print_exc()


def log_from_agent_result(
    *,
    agent_result: Dict[str, Any],
    platform: str = "telegram",
    chat_id: Optional[str] = None,
    consultant_id: Optional[int] = None,
    raw_message: Optional[str] = None,
    current_state: Optional[str] = None,
    executed: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Atalho: recebe o dicionario completo devolvido por
    AgentService.process(...) e extrai os campos certos
    antes de gravar o log.

    O formato esperado de agent_result e:
        {
            "intent_result": {...},
            "entities": {...},
            "decision": {...},
            "execution": {...},
        }
    """
    try:
        agent_result = agent_result or {}
        intent_result = agent_result.get("intent_result") or {}
        entities = agent_result.get("entities") or {}
        decision = agent_result.get("decision") or {}

        log_agent_decision(
            platform=platform,
            chat_id=chat_id,
            consultant_id=consultant_id,
            raw_message=raw_message,
            current_state=current_state,
            intent=intent_result.get("intent"),
            intent_confidence=intent_result.get("confidence"),
            intent_matched_by=intent_result.get("matched_by"),
            entities=entities,
            decision_action=decision.get("action"),
            decision_reason=decision.get("reason"),
            executed=executed,
            extra=extra,
        )
    except Exception as e:
        print(f"[AgentDecisionLogger] warning - falha no log_from_agent_result: {e}")
