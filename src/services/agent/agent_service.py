from typing import Any, Dict

from .intent_classifier import IntentClassifier
from .entity_extractor import EntityExtractor
from .entity_resolver import EntityResolver
from .decision_engine import DecisionEngine
from .action_executor import ActionExecutor


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

        # Enriquece as entidades com IDs reais do banco e score de confianca.
        # Nao remove nada do dict original - apenas adiciona os campos
        # "client", "property", "plot" com a versao resolvida.
        entities = self.entity_resolver.resolve(entities, context=context)

        decision = self.decision_engine.decide(intent_result, entities, context=context)
        execution = self.action_executor.execute(decision, context=context)

        return {
            "intent_result": intent_result,
            "entities": entities,
            "decision": decision,
            "execution": execution,
        }