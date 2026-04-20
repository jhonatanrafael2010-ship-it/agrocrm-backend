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
  futura melhora ou piora a qualidade do agente.

VERSAO DESTE ARQUIVO:
  v2 - adicionado registro das entidades RESOLVIDAS (Passo 2):
       - client_id, client_score
       - property_id, property_score
       - plot_id, plot_score
       Alem das entidades textuais originais.

COMPATIBILIDADE:
  Tabela agent_decision_log NAO muda. Os novos campos entram
  dentro do entities_json existente, como um sub-dicionario
  "resolved". Nao precisa rodar migration.
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


def _extract_resolved_summary(entities: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extrai um resumo COMPACTO das entidades resolvidas pelo
    EntityResolver (Passo 2). Esse resumo fica salvo no log para
    permitir auditar se o resolver esta acertando.

    Formato de saida (apenas com o que interessa para auditoria):
    {
        "client":   {"id": 47, "name": "Marcelo Alonso", "score": 0.92, "raw": "Marcelo"},
        "property": {"id": None, "score": 0.0, "raw": ""},
        "plot":     {...}
    }

    Nunca lanca excecao. Em caso de erro, devolve dict vazio.
    """
    if not entities or not isinstance(entities, dict):
        return {}

    result: Dict[str, Any] = {}

    try:
        for key in ("client", "property", "plot"):
            item = entities.get(key)
            if not item or not isinstance(item, dict):
                continue
            result[key] = {
                "id": item.get("id"),
                "name": item.get("name"),
                "score": item.get("score"),
                "raw": item.get("raw_name"),
            }
    except Exception:
        # se qualquer chave der problema, retornamos vazio
        return {}

    return result


def _build_entities_payload_for_log(entities: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Monta o payload final que vai para o campo entities_json.
    Mantem tudo que o EntityExtractor devolveu (como antes) e
    adiciona um resumo compacto das entidades resolvidas.

    Se nao houver entities, devolve None.
    """
    if not entities:
        return None

    try:
        payload = {}

        # Campos textuais originais do EntityExtractor.
        # Copiamos apenas os que sao serializaveis e relevantes.
        # NAO inclui raw_message (pode ser longo; ja vai em raw_message separado).
        safe_keys = [
            "client_name",
            "property_name",
            "plot_name",
            "culture",
            "fenologia_real",
            "date",
            "recommendation",
            "products",
            "visit_index",
            "pdf_client_name",
        ]
        for key in safe_keys:
            if key in entities:
                payload[key] = entities.get(key)

        # Resumo compacto das entidades RESOLVIDAS (Passo 2).
        resolved = _extract_resolved_summary(entities)
        if resolved:
            payload["resolved"] = resolved

        return payload
    except Exception:
        # ultima rede: em caso de qualquer falha, serializa o dict bruto
        return entities


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
    """
    try:
        # importacao tardia para nao criar ciclo de import
        from models import db, AgentDecisionLog

        entities_payload = _build_entities_payload_for_log(entities)

        row = AgentDecisionLog(
            platform=_truncate(platform or "telegram", 20),
            chat_id=_truncate(chat_id, 64),
            consultant_id=consultant_id if isinstance(consultant_id, int) else None,
            raw_message=_truncate(raw_message, 2000),
            current_state=_truncate(current_state, 80),
            intent=_truncate(intent, 80),
            intent_confidence=_truncate(intent_confidence, 20),
            intent_matched_by=_truncate(intent_matched_by, 40),
            entities_json=_safe_dumps(entities_payload),
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
            "entities": {...},    # agora ja vem enriquecido pelo EntityResolver
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
