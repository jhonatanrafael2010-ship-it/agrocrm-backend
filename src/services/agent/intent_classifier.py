import re
import json
import os
import unicodedata
from typing import Any, Dict


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ================================================================
# Fallback com IA: usado APENAS quando a heuristica nao tiver
# certeza. Nao substitui a heuristica, apenas complementa.
# Mapeia o intent textual da IA para os nomes internos do agente.
# ================================================================

AI_INTENT_MAP = {
    "week_schedule_request": "LIST_WEEK",
    "today_schedule_request": "DAILY_ROUTINE",
    "daily_routine_request": "DAILY_ROUTINE",
    "pdf_last_visit": "GENERATE_PDF",
    "pdf_recent_visits": "GENERATE_PDF",
    "pdf_by_client_reference": "GENERATE_PDF",
    "create_visit_like_message": "CREATE_VISIT_LIKE_MESSAGE",
    "launch_week_visit": "STATEFUL_REPLY",
    "complete_week_visit": "STATEFUL_REPLY",
    "contextual_visit_reference": "STATEFUL_REPLY",
    "edit_summary": "STATEFUL_REPLY",
    "confirm": "CONFIRM",
    "cancel": "CANCEL",
    "unknown": "UNKNOWN",
}


def classify_with_ai_fallback(message_text: str, current_state: str = ""):
    """
    So chama a OpenAI se existir chave configurada.
    Retorna um dict no MESMO formato da heuristica, ou None.
    Se der qualquer erro, retorna None e o fluxo segue sem IA.
    """
    if not message_text:
        return None

    if not os.getenv("OPENAI_API_KEY"):
        return None

    try:
        from openai import OpenAI
        client = OpenAI()

        system_prompt = (
            "Voce e um interpretador de intencoes de um bot agricola. "
            "Responda SOMENTE com JSON valido, sem markdown, sem comentarios. "
            "Campos: intent (string), confidence (high|medium|low). "
            "Intents permitidos: week_schedule_request, today_schedule_request, "
            "daily_routine_request, pdf_last_visit, pdf_recent_visits, "
            "pdf_by_client_reference, create_visit_like_message, launch_week_visit, "
            "complete_week_visit, contextual_visit_reference, edit_summary, "
            "confirm, cancel, unknown. "
            "Seja tolerante a erros de digitacao, falta de acento e portugues informal."
        )

        user_prompt = (
            f"Estado atual do chatbot: {current_state or 'none'}\n"
            f"Mensagem do usuario: {message_text}"
        )

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        output_text = (response.output_text or "").strip()
        if not output_text:
            return None

        try:
            data = json.loads(output_text)
        except Exception:
            match = re.search(r"\{.*\}", output_text, flags=re.DOTALL)
            if not match:
                return None
            try:
                data = json.loads(match.group(0))
            except Exception:
                return None

        ai_intent = (data.get("intent") or "").strip()
        ai_confidence = (data.get("confidence") or "low").strip().lower()

        mapped_intent = AI_INTENT_MAP.get(ai_intent, "UNKNOWN")

        if mapped_intent == "UNKNOWN":
            return None

        return {
            "intent": mapped_intent,
            "confidence": ai_confidence if ai_confidence in ("high", "medium", "low") else "medium",
            "matched_by": "ai_fallback",
            "ai_intent_raw": ai_intent,
        }

    except Exception as e:
        print(f"[IntentClassifier.ai_fallback] erro: {e}")
        return None


class IntentClassifier:
    def classify(self, text: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        normalized = normalize_text(text)
        context = context or {}
        current_state = (context.get("current_state") or "").strip()

        result = {
            "intent": "UNKNOWN",
            "confidence": "low",
            "matched_by": "none",
        }

        if not normalized:
            return result

        if current_state:
            result.update({"intent": "STATEFUL_REPLY", "confidence": "high", "matched_by": "state"})
            return result

        if normalized in {"cancelar", "cancela", "cancel"}:
            result.update({"intent": "CANCEL", "confidence": "high", "matched_by": "exact"})
            return result

        if normalized in {"confirmar", "confirma", "confirmo", "ok", "certo", "isso", "fechou"}:
            result.update({"intent": "CONFIRM", "confidence": "medium", "matched_by": "exact"})
            return result

        explicit_field_data_save_patterns = [
            r"^salva(?:r)?\s+dados?\s+de\s+campo\b",
            r"^anota(?:r)?\s+(?:no|nos)\s+dados?\s+de\s+campo\b",
            r"^perfil\s+comercial\s+do\s+cliente\b",
            r"^perfil\s+tecnico\s+do\s+cliente\b",
            r"^perfil\s+técnico\s+do\s+cliente\b",
            r"^perfil\s+do\s+produtor\b",
        ]
        if any(re.search(pattern, normalized) for pattern in explicit_field_data_save_patterns):
            result.update({"intent": "FIELD_DATA_SAVE", "confidence": "high", "matched_by": "explicit"})
            return result

        explicit_field_data_query_triggers = [
            "me mostra o perfil comercial",
            "me mostra o perfil tecnico",
            "me mostra o perfil técnico",
            "me mostra o perfil do produtor",
            "o que foi anotado sobre",
            "me resume os dados de campo",
            "me mostra os dados de campo",
            "consultar dado de campo",
            "consultar dados de campo",
        ]
        if any(t in normalized for t in explicit_field_data_query_triggers):
            result.update({"intent": "FIELD_DATA_QUERY", "confidence": "high", "matched_by": "explicit"})
            return result

        week_triggers = [
            "agenda da semana",
            "visitas da semana",
            "visitas pendentes da semana",
            "me passa agenda",
            "me passe agenda",
            "quais visitas tenho essa semana",
            "minha agenda da semana",
        ]
        if any(t in normalized for t in week_triggers):
            result.update({"intent": "LIST_WEEK", "confidence": "high", "matched_by": "keyword"})
            return result

        stale_triggers = [
            "clientes mais atrasados",
            "clientes atrasados",
            "clientes sem visita",
            "ranking de clientes atrasados",
            "visitas atrasadas",
        ]
        if any(t in normalized for t in stale_triggers):
            result.update({"intent": "LIST_LATE", "confidence": "high", "matched_by": "keyword"})
            return result

        daily_triggers = [
            "agenda de hoje",
            "visitas de hoje",
            "o que tenho hoje",
            "rotina do dia",
            "prioridades de hoje",
            "resumo do dia",
            "o que falta hoje",
        ]
        if any(t in normalized for t in daily_triggers):
            result.update({"intent": "DAILY_ROUTINE", "confidence": "high", "matched_by": "keyword"})
            return result

        organize_week_triggers = [
            "organiza minha semana",
            "organizar minha semana",
            "organize minha semana",
            "monta minha semana",
            "planeja minha semana",
            "me ajuda a organizar minha semana",
        ]
        if any(t in normalized for t in organize_week_triggers):
            result.update({"intent": "ORGANIZE_WEEK", "confidence": "high", "matched_by": "keyword"})
            return result

        if "pdf" in normalized:
            result.update({"intent": "GENERATE_PDF", "confidence": "medium", "matched_by": "keyword"})
            return result

        month_triggers = [
            "visitas do mes",
            "visitas do mês",
            "minhas visitas do mes",
            "minhas visitas do mês",
        ]
        if any(t in normalized for t in month_triggers):
            result.update({"intent": "LIST_MONTH", "confidence": "high", "matched_by": "keyword"})
            return result

        visit_signals = [
            "cliente",
            "produtor",
            "fazenda",
            "propriedade",
            "talhao",
            "talhão",
            "milho",
            "soja",
            "algodao",
            "algodão",
            "hoje",
            "ontem",
            "amanha",
            "amanhã",
        ]
        fenology_match = re.search(r"\b(v\d{1,2}|r\d{1,2}|ve|vc|vt)\b", normalized)

        hit_count = sum(1 for signal in visit_signals if signal in normalized)
        if fenology_match or hit_count >= 2:
            result.update({
                "intent": "CREATE_VISIT_LIKE_MESSAGE",
                "confidence": "medium",
                "matched_by": "heuristic",
            })
            return result

        # ============================================================
        # FALLBACK COM IA
        # So chega aqui se a heuristica nao reconheceu nada.
        # Se a IA tambem nao souber, retorna UNKNOWN normalmente.
        # ============================================================
        ai_result = classify_with_ai_fallback(
            message_text=text,
            current_state=current_state,
        )
        if ai_result:
            return ai_result

        return result