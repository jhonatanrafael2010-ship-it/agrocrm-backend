from typing import Any, Dict


class DecisionEngine:
    def decide(
        self,
        intent_result: Dict[str, Any],
        entities: Dict[str, Any],
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        context = context or {}
        intent = intent_result.get("intent") or "UNKNOWN"
        confidence = intent_result.get("confidence") or "low"

        decision = {
            "action": "NO_ACTION",
            "intent": intent,
            "confidence": confidence,
            "entities": entities,
            "should_fallback": True,
            "reason": "unmatched",
        }

        if intent == "STATEFUL_REPLY":
            decision.update({
                "action": "ROUTE_TO_STATEFUL_FLOW",
                "should_fallback": False,
                "reason": "stateful reply must keep current flow",
            })
            return decision

        if intent == "CREATE_VISIT_LIKE_MESSAGE":
            minimum_data = 0
            for field in ["client_name", "culture", "fenologia_real", "date", "recommendation"]:
                if entities.get(field):
                    minimum_data += 1

            if minimum_data >= 2:
                decision.update({
                    "action": "START_GUIDED_VISIT_FROM_FREE_TEXT",
                    "should_fallback": False,
                    "reason": "visit has priority over secondary memory flows",
                })
                return decision

        if intent == "LIST_WEEK":
            decision.update({
                "action": "ROUTE_TO_WEEK_SCHEDULE",
                "should_fallback": False,
                "reason": "weekly schedule request",
            })
            return decision

        if intent == "LIST_LATE":
            decision.update({
                "action": "ROUTE_TO_STALE_CLIENTS",
                "should_fallback": False,
                "reason": "late clients ranking request",
            })
            return decision

        if intent == "DAILY_ROUTINE":
            decision.update({
                "action": "ROUTE_TO_DAILY_ROUTINE",
                "should_fallback": False,
                "reason": "daily routine request",
            })
            return decision

        if intent == "ORGANIZE_WEEK":
            decision.update({
                "action": "ROUTE_TO_WEEK_ORGANIZATION",
                "should_fallback": False,
                "reason": "week organization request",
            })
            return decision

        if intent == "LIST_MONTH":
            decision.update({
                "action": "ROUTE_TO_MONTH_VISITS",
                "should_fallback": False,
                "reason": "month visits request",
            })
            return decision

        if intent == "GENERATE_PDF":
            decision.update({
                "action": "ROUTE_TO_PDF",
                "should_fallback": False,
                "reason": "pdf request",
            })
            return decision

        if intent == "FIELD_DATA_SAVE":
            decision.update({
                "action": "ROUTE_TO_FIELD_DATA_SAVE",
                "should_fallback": False,
                "reason": "explicit field data save request",
            })
            return decision

        if intent == "FIELD_DATA_QUERY":
            decision.update({
                "action": "ROUTE_TO_FIELD_DATA_QUERY",
                "should_fallback": False,
                "reason": "explicit field data query request",
            })
            return decision

        return decision
