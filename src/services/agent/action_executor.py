from typing import Any, Dict


class ActionExecutor:
    """
    Executor de ações do agente.

    STATUS ATUAL (v1):
        Este executor NÃO executa ações diretamente. Ele apenas
        devolve um envelope estruturado para o routes.py, que
        contém a lógica real de execução (~11k linhas).

    TODO FUTURO (v2):
        Migrar a lógica de execução do routes.py para cá,
        transformando o ActionExecutor no ponto único de
        execução. Isso permitirá:
        - Testes unitários isolados
        - Reutilização entre plataformas (Telegram, WhatsApp, App)
        - Código mais organizado e manutenível

    COMPATIBILIDADE:
        O envelope retornado é consumido pelo routes.py que
        decide qual função chamar baseado em decision['action'].
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
