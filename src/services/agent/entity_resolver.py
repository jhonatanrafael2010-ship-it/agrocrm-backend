"""
================================================================
EntityResolver
================================================================

Recebe o dict de entidades extraidas pelo EntityExtractor (que
sao apenas strings) e resolve contra o banco de dados,
devolvendo IDs reais e um score numerico de confianca por
entidade.

POR QUE ISSO IMPORTA:
  - O EntityExtractor devolve "client_name": "Marcelo".
  - Mas o banco pode ter dois Marcelos. Qual deles?
  - Antes, quem resolvia isso era codigo espalhado no routes.py.
  - Agora, o pipeline do agente passa a ter essa responsabilidade
    DENTRO dele, com formato padronizado e score numerico.

COMPATIBILIDADE:
  Este resolver NAO remove nada do dict original. Ele APENAS
  ADICIONA campos novos ao dict:
    - "client":   {"id", "name", "score", "candidates"}
    - "property": {"id", "name", "score", "candidates"}
    - "plot":     {"id", "name", "score", "candidates"}

  Os campos antigos "client_name", "property_name", "plot_name"
  permanecem exatamente como estavam. O DecisionEngine atual
  que le esses campos continua funcionando sem mudanca.

SEGURANCA:
  - Se qualquer busca falhar (banco offline, exception), o
    resolver silencia o erro e devolve score=0.0, id=None.
  - O fluxo do agente nunca para por causa de resolver.
  - Nao altera o banco. Apenas LE.
================================================================
"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional


# Stopwords usadas pelo find_client_by_name do routes.py,
# replicadas aqui para manter compatibilidade 1:1 com a logica
# atual quando o usuario escreve "cliente Marcelo fazenda X ..."
_CLIENT_STOPWORDS = {
    "cliente", "fazenda", "faz", "propriedade", "talhao", "talhão",
    "visita", "visitar", "lancar", "lançar", "concluir", "nova",
    "hoje", "amanha", "amanhã", "ontem", "observacao", "observação",
    "fenologia", "cultura",
}


def _normalize(text: str) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _empty_resolved(name: Optional[str]) -> Dict[str, Any]:
    """Formato canonico de uma entidade nao resolvida."""
    return {
        "id": None,
        "name": None,
        "raw_name": name or None,
        "score": 0.0,
        "candidates": [],
    }


def _resolved_with_item(item, score: float, raw_name: Optional[str], all_candidates: List) -> Dict[str, Any]:
    """Formato canonico de uma entidade resolvida."""
    try:
        return {
            "id": getattr(item, "id", None),
            "name": getattr(item, "name", None),
            "raw_name": raw_name or None,
            "score": round(float(score), 3),
            "candidates": [
                {
                    "id": getattr(c[0], "id", None),
                    "name": getattr(c[0], "name", None),
                    "score": round(float(c[1]), 3),
                }
                for c in all_candidates[:5]
            ],
        }
    except Exception:
        return _empty_resolved(raw_name)


def _score_against(target_norm: str, candidate_name: str) -> float:
    """Calcula score fuzzy entre target e candidate, no estilo
    do find_client_by_name existente no routes.py."""
    if not target_norm or not candidate_name:
        return 0.0

    current = _normalize(candidate_name)
    current_clean = re.sub(r"\s+", " ", current).strip()

    # match exato pega 1.0 direto
    if current_clean == target_norm:
        return 1.0

    # similaridade textual geral
    score_full = SequenceMatcher(None, target_norm, current_clean).ratio()

    # score por token (quantas palavras batem)
    target_tokens = target_norm.split()
    current_words = set(current_clean.split())
    token_hits = sum(1 for t in target_tokens if t in current_words)
    token_score = token_hits / max(len(target_tokens), 1)

    # bonus se um esta contido no outro
    containment_bonus = 0.0
    if target_norm and current_clean:
        if target_norm in current_clean or current_clean in target_norm:
            containment_bonus = 0.10

    return min(1.0, max(score_full, token_score * 0.95) + containment_bonus)


class EntityResolver:
    """
    Serviço de resolução de entidades contra o banco.
    Este resolver e INTENCIONALMENTE simples nesta primeira
    versao: reaproveita a logica fuzzy do routes.py e devolve
    score numerico. Pode ser sofisticado depois, com memoria
    contextual (carteira do consultor, historico recente, etc).
    """

    def resolve(
        self,
        entities: Dict[str, Any],
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Recebe o dict do EntityExtractor. Devolve o MESMO dict,
        ADICIONADO dos campos resolvidos "client", "property", "plot".

        Nunca lanca excecao. Em caso de erro, devolve o dict original
        com os campos resolvidos vazios (score=0, id=None).
        """
        context = context or {}
        result = dict(entities) if entities else {}

        result["client"] = _empty_resolved(result.get("client_name"))
        result["property"] = _empty_resolved(result.get("property_name"))
        result["plot"] = _empty_resolved(result.get("plot_name"))

        try:
            client = self._resolve_client(result.get("client_name"))
            result["client"] = client

            client_id = client.get("id")
            prop = self._resolve_property(result.get("property_name"), client_id=client_id)
            result["property"] = prop

            property_id = prop.get("id")
            plot = self._resolve_plot(result.get("plot_name"), property_id=property_id)
            result["plot"] = plot

        except Exception as e:
            # nunca deixa o fluxo do agente quebrar por causa do resolver
            print(f"[EntityResolver] warning - falha na resolucao: {e}")

        return result

    # ================================================================
    # Cliente
    # ================================================================
    def _resolve_client(self, client_name: Optional[str]) -> Dict[str, Any]:
        if not client_name:
            return _empty_resolved(client_name)

        try:
            from models import Client
        except Exception as e:
            print(f"[EntityResolver] warning - import Client falhou: {e}")
            return _empty_resolved(client_name)

        target = _normalize(client_name)
        target = re.sub(r"\s+", " ", target).strip()
        if not target:
            return _empty_resolved(client_name)

        # remove stopwords para lidar com "cliente Marcelo" etc
        target_tokens = [t for t in target.split() if t not in _CLIENT_STOPWORDS]
        target_clean = " ".join(target_tokens).strip() or target

        try:
            clients = Client.query.all()
        except Exception as e:
            print(f"[EntityResolver] warning - query Client falhou: {e}")
            return _empty_resolved(client_name)

        scored = []
        for client in clients:
            score = _score_against(target_clean, client.name or "")
            scored.append((client, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            return _empty_resolved(client_name)

        best_client, best_score = scored[0]

        # threshold: 0.58 e o mesmo piso que o routes.py usa para
        # sugerir com confirmacao. Abaixo disso, tratamos como nao
        # resolvido.
        if best_score < 0.58:
            return {
                "id": None,
                "name": None,
                "raw_name": client_name,
                "score": round(float(best_score), 3),
                "candidates": [
                    {"id": c.id, "name": c.name, "score": round(float(s), 3)}
                    for c, s in scored[:5]
                    if s >= 0.45
                ],
            }

        return _resolved_with_item(best_client, best_score, client_name, scored)

    # ================================================================
    # Propriedade
    # ================================================================
    def _resolve_property(self, property_name: Optional[str], client_id: Optional[int] = None) -> Dict[str, Any]:
        if not property_name:
            return _empty_resolved(property_name)

        try:
            from models import Property
        except Exception as e:
            print(f"[EntityResolver] warning - import Property falhou: {e}")
            return _empty_resolved(property_name)

        target = _normalize(property_name)
        if not target:
            return _empty_resolved(property_name)

        try:
            query = Property.query
            if client_id:
                query = query.filter_by(client_id=client_id)
            properties = query.all()
        except Exception as e:
            print(f"[EntityResolver] warning - query Property falhou: {e}")
            return _empty_resolved(property_name)

        scored = []
        for prop in properties:
            score = _score_against(target, prop.name or "")
            scored.append((prop, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            return _empty_resolved(property_name)

        best_prop, best_score = scored[0]

        # threshold alinhado com o find_property_by_name do routes.py
        if best_score < 0.65:
            return {
                "id": None,
                "name": None,
                "raw_name": property_name,
                "score": round(float(best_score), 3),
                "candidates": [
                    {"id": p.id, "name": p.name, "score": round(float(s), 3)}
                    for p, s in scored[:5]
                    if s >= 0.55
                ],
            }

        return _resolved_with_item(best_prop, best_score, property_name, scored)

    # ================================================================
    # Talhao
    # ================================================================
    def _resolve_plot(self, plot_name: Optional[str], property_id: Optional[int] = None) -> Dict[str, Any]:
        if not plot_name:
            return _empty_resolved(plot_name)

        try:
            from models import Plot
        except Exception as e:
            print(f"[EntityResolver] warning - import Plot falhou: {e}")
            return _empty_resolved(plot_name)

        target = _normalize(plot_name)
        if not target:
            return _empty_resolved(plot_name)

        try:
            query = Plot.query
            if property_id:
                query = query.filter_by(property_id=property_id)
            plots = query.all()
        except Exception as e:
            print(f"[EntityResolver] warning - query Plot falhou: {e}")
            return _empty_resolved(plot_name)

        scored = []
        for plot in plots:
            score = _score_against(target, plot.name or "")
            scored.append((plot, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            return _empty_resolved(plot_name)

        best_plot, best_score = scored[0]

        if best_score < 0.65:
            return {
                "id": None,
                "name": None,
                "raw_name": plot_name,
                "score": round(float(best_score), 3),
                "candidates": [
                    {"id": p.id, "name": p.name, "score": round(float(s), 3)}
                    for p, s in scored[:5]
                    if s >= 0.55
                ],
            }

        return _resolved_with_item(best_plot, best_score, plot_name, scored)