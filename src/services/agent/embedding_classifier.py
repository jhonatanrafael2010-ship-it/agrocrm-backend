"""
================================================================
Embedding-based Intent Classifier with Cache
================================================================

Usa embeddings (OpenAI text-embedding-3-small) para classificar
mensagens semanticamente. Inclui:
- Exemplos de referência para cada intent
- Similaridade de cosseno para matching
- Cache em memória para evitar chamadas repetidas

Ordem de uso no pipeline:
1. Heurística (regex/keywords) - rápido, sem custo
2. Cache de embeddings - se já viu mensagem similar
3. Embedding classifier - calcula embedding e compara
4. AI fallback (gpt-4o-mini) - último recurso
================================================================
"""

import hashlib
import json
import os
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple
import math


# ================================================================
# EXEMPLOS DE REFERÊNCIA PARA CADA INTENT
# Cada intent tem frases típicas que serão convertidas em embeddings
# ================================================================

INTENT_EXAMPLES = {
    "LIST_WEEK": [
        "agenda da semana",
        "quais visitas tenho essa semana",
        "me passa a agenda da semana",
        "visitas pendentes da semana",
        "o que tenho marcado pra semana",
    ],
    "DAILY_ROUTINE": [
        "agenda de hoje",
        "o que tenho hoje",
        "visitas de hoje",
        "rotina do dia",
        "prioridades de hoje",
    ],
    "GENERATE_PDF": [
        "gera pdf da ultima visita",
        "pdf do cliente joao",
        "me manda o pdf",
        "relatorio em pdf",
        "documento da visita",
    ],
    "LIST_LATE": [
        "clientes atrasados",
        "quem nao visito ha tempo",
        "clientes sem visita",
        "ranking de atraso",
        "clientes mais atrasados",
    ],
    "PLANTING_DAYS": [
        "dias de plantado",
        "quantos dias de plantio",
        "quanto tempo de plantado",
        "idade da lavoura",
        "dias desde o plantio",
    ],
    "LIST_MONTH": [
        "visitas do mes",
        "o que fiz esse mes",
        "minhas visitas do mes",
        "relatorio mensal",
        "atividades do mes",
    ],
    "WEEKLY_REPORT": [
        "resumo da semana",
        "como foi minha semana",
        "balanco semanal",
        "o que fiz essa semana",
        "relatorio semanal",
    ],
    "PEST_DIAGNOSIS": [
        "o que e ferrugem asiatica",
        "como tratar lagarta",
        "sintomas de antracnose",
        "qual praga ataca soja",
        "como controlar percevejo",
    ],
    "CONFIRM": [
        "confirma",
        "isso mesmo",
        "pode confirmar",
        "ta certo",
        "fechado",
    ],
    "CANCEL": [
        "cancela",
        "nao quero mais",
        "deixa pra la",
        "esquece",
        "cancelar",
    ],
    "ORGANIZE_WEEK": [
        "organiza minha semana",
        "me ajuda a planejar a semana",
        "monta minha agenda",
        "planeja minhas visitas",
        "distribui os clientes na semana",
    ],
    "FIELD_DATA_SAVE": [
        "salva dados de campo",
        "anota no perfil do cliente",
        "perfil comercial do produtor",
        "registra informacao do cliente",
        "guarda esse dado",
    ],
    "FIELD_DATA_QUERY": [
        "mostra perfil do cliente",
        "o que sei sobre o produtor",
        "consulta dados de campo",
        "informacoes do cliente",
        "historico do produtor",
    ],
}

# Threshold de similaridade para considerar um match
SIMILARITY_THRESHOLD = 0.82

# Cache settings - reduzido para economizar memória no Render (512MB limit)
CACHE_MAX_SIZE = 100  # Apenas 100 classificações em memória
CACHE_TTL_SECONDS = 3600 * 6  # 6 horas (não 24)

# Path para persistir cache e embeddings de referência
CACHE_DIR = Path(__file__).parent / ".embedding_cache"


class EmbeddingCache:
    """
    Cache em memória + disco para embeddings e classificações.

    Estrutura do cache:
    - message_hash -> {embedding, classification, timestamp}
    - Evita recalcular embeddings para mensagens idênticas
    - Também faz lookup por similaridade para mensagens parecidas
    """

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        self._reference_embeddings: Dict[str, List[List[float]]] = {}
        self._ref_file = CACHE_DIR / "reference_embeddings.json"
        self._refs_loaded = False
        # NÃO carrega do disco na inicialização (lazy loading)

    def _hash_message(self, text: str) -> str:
        """Hash normalizado da mensagem."""
        normalized = text.strip().lower()
        return hashlib.md5(normalized.encode()).hexdigest()

    def _ensure_refs_loaded(self):
        """Carrega embeddings de referência do disco (lazy loading)."""
        if self._refs_loaded:
            return
        try:
            if self._ref_file.exists():
                self._reference_embeddings = json.loads(
                    self._ref_file.read_text(encoding="utf-8")
                )
                print(f"[EmbeddingCache] referências carregadas: {len(self._reference_embeddings)} intents")
            self._refs_loaded = True
        except Exception as e:
            print(f"[EmbeddingCache] erro ao carregar referências: {e}")
            self._refs_loaded = True

    def save_reference_embeddings(self):
        """Salva embeddings de referência no disco."""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self._ref_file.write_text(
                json.dumps(self._reference_embeddings, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"[EmbeddingCache] erro ao salvar referências: {e}")

    def get_cached_classification(self, text: str) -> Optional[Dict[str, Any]]:
        """Retorna classificação cacheada se existir."""
        msg_hash = self._hash_message(text)
        with self._lock:
            entry = self._cache.get(msg_hash)
            if entry and time.time() - entry.get("timestamp", 0) < CACHE_TTL_SECONDS:
                return entry.get("classification")
        return None

    def get_cached_embedding(self, text: str) -> Optional[List[float]]:
        """Embeddings não são mais cacheados para economizar memória."""
        return None

    def cache_result(
        self,
        text: str,
        embedding: List[float],
        classification: Dict[str, Any]
    ):
        """Armazena resultado no cache (apenas classificação, não embedding para economizar memória)."""
        msg_hash = self._hash_message(text)
        with self._lock:
            # Limpa cache se muito grande
            if len(self._cache) >= CACHE_MAX_SIZE:
                # Remove 20% mais antigas
                sorted_entries = sorted(
                    self._cache.items(),
                    key=lambda x: x[1].get("timestamp", 0)
                )
                for key, _ in sorted_entries[:CACHE_MAX_SIZE // 5]:
                    del self._cache[key]

            # NÃO armazena embedding para economizar memória (~37KB cada)
            self._cache[msg_hash] = {
                "classification": classification,
                "timestamp": time.time(),
            }

            # Cache em memória apenas, não persiste (economiza I/O e memória)

    def get_reference_embeddings(self) -> Dict[str, List[List[float]]]:
        """Retorna embeddings de referência (lazy loading)."""
        self._ensure_refs_loaded()
        return self._reference_embeddings

    def set_reference_embeddings(self, embeddings: Dict[str, List[List[float]]]):
        """Define embeddings de referência."""
        self._reference_embeddings = embeddings
        self.save_reference_embeddings()

    def find_similar_cached(
        self,
        embedding: List[float],
        threshold: float = 0.95
    ) -> Optional[Dict[str, Any]]:
        """
        Busca no cache uma classificação com embedding similar.
        Usado para mensagens ligeiramente diferentes mas semanticamente iguais.
        """
        with self._lock:
            now = time.time()
            for entry in self._cache.values():
                if now - entry.get("timestamp", 0) >= CACHE_TTL_SECONDS:
                    continue
                cached_emb = entry.get("embedding")
                if cached_emb:
                    sim = cosine_similarity(embedding, cached_emb)
                    if sim >= threshold:
                        return entry.get("classification")
        return None

    def clear(self):
        """Limpa todo o cache em memória."""
        with self._lock:
            self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache."""
        with self._lock:
            ref_count = sum(len(v) for v in self._reference_embeddings.values())
            return {
                "cache_entries": len(self._cache),
                "cache_max_size": CACHE_MAX_SIZE,
                "reference_intents": len(self._reference_embeddings),
                "reference_embeddings": ref_count,
                "refs_loaded": self._refs_loaded,
            }


# Instância global do cache
_cache = EmbeddingCache()


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calcula similaridade de cosseno entre dois vetores."""
    if len(vec1) != len(vec2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def get_embedding(text: str, client=None) -> Optional[List[float]]:
    """
    Obtém embedding para um texto usando OpenAI.
    Usa cache se disponível.
    """
    if not text:
        return None

    # Verifica cache primeiro
    cached = _cache.get_cached_embedding(text)
    if cached:
        return cached

    if not os.getenv("OPENAI_API_KEY"):
        return None

    try:
        if client is None:
            from openai import OpenAI
            client = OpenAI()

        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    except Exception as e:
        print(f"[EmbeddingClassifier] erro ao obter embedding: {e}")
        return None


def get_embeddings_batch(texts: List[str], client=None) -> List[Optional[List[float]]]:
    """Obtém embeddings para múltiplos textos em uma única chamada."""
    if not texts:
        return []

    if not os.getenv("OPENAI_API_KEY"):
        return [None] * len(texts)

    try:
        if client is None:
            from openai import OpenAI
            client = OpenAI()

        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [item.embedding for item in response.data]

    except Exception as e:
        print(f"[EmbeddingClassifier] erro batch: {e}")
        return [None] * len(texts)


def initialize_reference_embeddings(force: bool = False) -> bool:
    """
    Inicializa embeddings de referência para cada intent.
    Chamado uma vez na inicialização ou quando force=True.

    Retorna True se os embeddings foram gerados.
    """
    ref_embeddings = _cache.get_reference_embeddings()

    # Se já tem embeddings e não está forçando, pula
    if ref_embeddings and not force:
        return False

    if not os.getenv("OPENAI_API_KEY"):
        print("[EmbeddingClassifier] OPENAI_API_KEY não configurada")
        return False

    print("[EmbeddingClassifier] Gerando embeddings de referência...")

    try:
        from openai import OpenAI
        client = OpenAI()

        new_embeddings: Dict[str, List[List[float]]] = {}

        for intent, examples in INTENT_EXAMPLES.items():
            embeddings = get_embeddings_batch(examples, client)
            # Filtra None
            valid_embeddings = [e for e in embeddings if e is not None]
            if valid_embeddings:
                new_embeddings[intent] = valid_embeddings
                print(f"  - {intent}: {len(valid_embeddings)} embeddings")

        _cache.set_reference_embeddings(new_embeddings)
        print("[EmbeddingClassifier] Embeddings de referência salvos")
        return True

    except Exception as e:
        print(f"[EmbeddingClassifier] erro ao inicializar: {e}")
        return False


def classify_with_embeddings(
    message_text: str,
    context: Dict[str, Any] | None = None
) -> Optional[Dict[str, Any]]:
    """
    Classifica mensagem usando similaridade de embeddings.

    Retorna:
    - Dict com intent, confidence, matched_by se encontrar match
    - None se não encontrar match acima do threshold
    """
    if not message_text:
        return None

    # 1. Verifica cache de classificação exata
    cached_classification = _cache.get_cached_classification(message_text)
    if cached_classification:
        cached_classification["matched_by"] = "embedding_cache_exact"
        return cached_classification

    # 2. Obtém embedding da mensagem
    message_embedding = get_embedding(message_text)
    if not message_embedding:
        return None

    # 3. Verifica cache por similaridade (mensagens parecidas)
    similar_cached = _cache.find_similar_cached(message_embedding, threshold=0.95)
    if similar_cached:
        # Cacheia esta mensagem também
        _cache.cache_result(message_text, message_embedding, similar_cached)
        result = similar_cached.copy()
        result["matched_by"] = "embedding_cache_similar"
        return result

    # 4. Compara com embeddings de referência
    ref_embeddings = _cache.get_reference_embeddings()
    if not ref_embeddings:
        # Tenta inicializar
        if not initialize_reference_embeddings():
            return None
        ref_embeddings = _cache.get_reference_embeddings()

    best_intent = None
    best_similarity = 0.0
    best_example_idx = 0

    for intent, embeddings_list in ref_embeddings.items():
        for idx, ref_emb in enumerate(embeddings_list):
            sim = cosine_similarity(message_embedding, ref_emb)
            if sim > best_similarity:
                best_similarity = sim
                best_intent = intent
                best_example_idx = idx

    # 5. Verifica threshold
    if best_similarity < SIMILARITY_THRESHOLD:
        return None

    # 6. Determina confidence baseado na similaridade
    if best_similarity >= 0.92:
        confidence = "high"
    elif best_similarity >= 0.85:
        confidence = "medium"
    else:
        confidence = "low"

    result = {
        "intent": best_intent,
        "confidence": confidence,
        "matched_by": "embedding_similarity",
        "similarity_score": round(best_similarity, 4),
    }

    # Cacheia resultado
    _cache.cache_result(message_text, message_embedding, result)

    return result


def get_cache_stats() -> Dict[str, Any]:
    """Retorna estatísticas do cache para monitoramento."""
    ref_embeddings = _cache.get_reference_embeddings()
    return {
        "cache_size": len(_cache._cache),
        "cache_max_size": CACHE_MAX_SIZE,
        "reference_intents": len(ref_embeddings),
        "reference_examples_total": sum(
            len(v) for v in ref_embeddings.values()
        ) if ref_embeddings else 0,
        "similarity_threshold": SIMILARITY_THRESHOLD,
    }


def invalidate_cache():
    """Limpa todo o cache. Útil para debug/testes."""
    global _cache
    _cache = EmbeddingCache()
