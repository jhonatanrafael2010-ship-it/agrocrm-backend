from typing import Any, Dict

from .intent_classifier import IntentClassifier
from .entity_extractor import EntityExtractor
from .entity_resolver import EntityResolver
from .decision_engine import DecisionEngine
from .action_executor import ActionExecutor
from .skill_loader import interpret_with_skill


class AgentService:
    def __init__(self) -> None:
        self.intent_classifier = IntentClassifier()
        self.entity_extractor = EntityExtractor()
        self.entity_resolver = EntityResolver()
        self.decision_engine = DecisionEngine()
        self.action_executor = ActionExecutor()

    def process(self, message_text: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        context = context or {}
        intent_result = self.intent_classifier.classify(message_text, context=context)
        entities = self.entity_extractor.extract(message_text, context=context)
        
        if intent_result["intent"] == "CREATE_VISIT_LIKE_MESSAGE":
            skill_result = interpret_with_skill(
                message_text=message_text,
                skill_name="lancamento_visita",
                current_state=context.get("current_state", ""),
            )
            if skill_result and skill_result.get("parsed_visit"):
                parsed_visit = skill_result["parsed_visit"]
                # Campos que EntityExtractor detectou com mais precisão - não sobrescrever
                protected_fields = {"culture", "recommendation", "client_name", "variety", "visit_purpose"}
                for key, value in parsed_visit.items():
                    if key in protected_fields and entities.get(key):
                        # Mantém valor do EntityExtractor se já foi detectado
                        continue
                    if value is not None and value != "":
                        entities[key] = value
                intent_result["confidence"] = skill_result.get("confidence", "medium")
                intent_result["matched_by"] = "skill:lancamento_visita"
        
        entities = self.entity_resolver.resolve(entities, context=context)
        decision = self.decision_engine.decide(intent_result, entities, context=context)
        execution = self.action_executor.execute(decision, context=context)
        
        return {
            "intent_result": intent_result,
            "entities": entities,
            "decision": decision,
            "execution": execution,
        }