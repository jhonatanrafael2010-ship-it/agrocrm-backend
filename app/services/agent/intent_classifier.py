import re
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

        return result