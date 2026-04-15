from typing import Any, Dict


class ActionExecutor:
    """
    Nesta fase o executor não salva nada sozinho.
    Ele apenas devolve um envelope estruturado para o routes.py.
    O routes.py continua chamando as funções reais já existentes.
    """

    def execute(
        self,
        decision: Dict[str, Any],
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        context = context or {}
        return {
            "ok": True,
            "action": decision.get("action"),
            "intent": decision.get("intent"),
            "confidence": decision.get("confidence"),
            "entities": decision.get("entities") or {},
            "should_fallback": bool(decision.get("should_fallback", True)),
            "reason": decision.get("reason") or "",
        }
