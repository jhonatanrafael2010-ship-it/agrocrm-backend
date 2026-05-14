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
import time
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional


# ================================================================
# Cache em memória com TTL (evita queries repetidas)
# ================================================================
_CACHE_TTL_SECONDS = 300  # 5 minutos
_cache: Dict[str, Any] = {}
_cache_timestamps: Dict[str, float] = {}


def _get_cached(key: str) -> Optional[Any]:
    """Retorna valor do cache se ainda válido, None caso contrário."""
    if key not in _cache:
        return None
    if time.time() - _cache_timestamps.get(key, 0) > _CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        _cache_timestamps.pop(key, None)
        return None
    return _cache[key]


def _set_cached(key: str, value: Any) -> None:
    """Armazena valor no cache com timestamp atual."""
    _cache[key] = value
    _cache_timestamps[key] = time.time()


def invalidate_entity_cache() -> None:
    """Limpa todo o cache. Chamar após criar/editar cliente/propriedade/talhão."""
    _cache.clear()
    _cache_timestamps.clear()


# Stopwords usadas pelo find_client_by_name do routes.py,
# replicadas aqui para manter compatibilidade 1:1 com a logica
# atual quando o usuario escreve "cliente Marcelo fazenda X ..."
_CLIENT_STOPWORDS = {
    "cliente", "fazenda", "faz", "propriedade", "talhao", "talhão",
    "visita", "visitar", "lancar", "lançar", "concluir", "nova",
    "hoje", "amanha", "amanhã", "ontem", "observacao", "observação",
    "fenologia", "cultura",
}

# Boost de score para clientes da carteira do consultor
_PORTFOLIO_BOOST = 0.15


def _get_consultant_portfolio_client_ids(consultant_id: int) -> set:
    """
    Retorna set de client_ids que o consultor já visitou.
    Usa cache para evitar queries repetidas.
    """
    if not consultant_id:
        return set()

    cache_key = f"portfolio:{consultant_id}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        from models import Visit, db

        # Busca client_ids distintos das visitas do consultor
        result = db.session.query(Visit.client_id).filter(
            Visit.consultant_id == consultant_id,
            Visit.client_id.isnot(None)
        ).distinct().all()

        client_ids = {row[0] for row in result}
        _set_cached(cache_key, client_ids)
        return client_ids
    except Exception as e:
        print(f"[EntityResolver] warning - portfolio query falhou: {e}")
        return set()


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
        consultant_id = context.get("consultant_id")

        result["client"] = _empty_resolved(result.get("client_name"))
        result["property"] = _empty_resolved(result.get("property_name"))
        result["plot"] = _empty_resolved(result.get("plot_name"))

        try:
            client = self._resolve_client(result.get("client_name"), consultant_id=consultant_id)
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
    def _resolve_client(self, client_name: Optional[str], consultant_id: Optional[int] = None) -> Dict[str, Any]:
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

        # Busca carteira do consultor para dar boost
        portfolio_client_ids = _get_consultant_portfolio_client_ids(consultant_id) if consultant_id else set()

        try:
            # Cache de clientes (todos)
            cache_key = "clients:all"
            clients = _get_cached(cache_key)

            if clients is None:
                clients = Client.query.all()
                _set_cached(cache_key, clients)
        except Exception as e:
            print(f"[EntityResolver] warning - query Client falhou: {e}")
            return _empty_resolved(client_name)

        scored = []
        for client in clients:
            score = _score_against(target_clean, client.name or "")

            # Boost para clientes da carteira do consultor
            if client.id in portfolio_client_ids:
                score = min(1.0, score + _PORTFOLIO_BOOST)

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
            cache_key = f"properties:{client_id or 'all'}"
            properties = _get_cached(cache_key)

            if properties is None:
                query = Property.query
                if client_id:
                    query = query.filter_by(client_id=client_id)
                properties = query.all()
                _set_cached(cache_key, properties)
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
            cache_key = f"plots:{property_id or 'all'}"
            plots = _get_cached(cache_key)

            if plots is None:
                query = Plot.query
                if property_id:
                    query = query.filter_by(property_id=property_id)
                plots = query.all()
                _set_cached(cache_key, plots)
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