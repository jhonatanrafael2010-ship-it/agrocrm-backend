"""
================================================================
ConversationMemory
================================================================

Memória de curto prazo para conversas do chatbot.
Armazena as últimas N mensagens de cada chat para permitir
que o agente entenda referências contextuais.

Exemplo:
  Msg 1: "visita no Marcelo soja R5"
  Msg 2: "adiciona que tinha lagarta"
  → O agente sabe que "adiciona" se refere à visita do Marcelo

STORAGE:
  Cache em memória com TTL. Não persiste no banco.
  Se o servidor reiniciar, o histórico é perdido (aceitável).

PRIVACIDADE:
  Mensagens antigas são automaticamente removidas após TTL.
  Máximo de 10 mensagens por conversa.
================================================================
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


# Configurações
MAX_MESSAGES_PER_CHAT = 10
MESSAGE_TTL_SECONDS = 1800  # 30 minutos
CLEANUP_INTERVAL_SECONDS = 300  # Limpa cache a cada 5 min


@dataclass
class ConversationMessage:
    """Uma mensagem no histórico."""
    text: str
    timestamp: float
    role: str = "user"  # "user" ou "assistant"
    intent: Optional[str] = None
    entities: Optional[Dict[str, Any]] = None
    visit_id: Optional[int] = None  # Se criou uma visita


@dataclass
class ConversationContext:
    """Contexto extraído do histórico para o agente."""
    recent_messages: List[str]
    last_intent: Optional[str] = None
    last_entities: Optional[Dict[str, Any]] = None
    last_visit_id: Optional[int] = None
    last_client_name: Optional[str] = None
    last_culture: Optional[str] = None
    has_pending_action: bool = False


# Cache global: {chat_key: [ConversationMessage, ...]}
_memory_cache: Dict[str, List[ConversationMessage]] = {}
_last_cleanup: float = 0


def _chat_key(platform: str, chat_id: str) -> str:
    """Gera chave única para o chat."""
    return f"{platform}:{chat_id}"


def _cleanup_old_messages() -> None:
    """Remove mensagens expiradas do cache."""
    global _last_cleanup

    now = time.time()
    if now - _last_cleanup < CLEANUP_INTERVAL_SECONDS:
        return

    _last_cleanup = now
    cutoff = now - MESSAGE_TTL_SECONDS

    keys_to_delete = []
    for key, messages in _memory_cache.items():
        # Remove mensagens antigas
        _memory_cache[key] = [m for m in messages if m.timestamp > cutoff]
        # Se ficou vazio, marca para deletar
        if not _memory_cache[key]:
            keys_to_delete.append(key)

    for key in keys_to_delete:
        del _memory_cache[key]


def add_message(
    platform: str,
    chat_id: str,
    text: str,
    role: str = "user",
    intent: Optional[str] = None,
    entities: Optional[Dict[str, Any]] = None,
    visit_id: Optional[int] = None,
) -> None:
    """
    Adiciona uma mensagem ao histórico do chat.

    Args:
        platform: telegram, whatsapp, mobile
        chat_id: ID do chat
        text: Texto da mensagem
        role: "user" ou "assistant"
        intent: Intent detectado (opcional)
        entities: Entidades extraídas (opcional)
        visit_id: ID da visita criada (opcional)
    """
    _cleanup_old_messages()

    key = _chat_key(platform, chat_id)

    if key not in _memory_cache:
        _memory_cache[key] = []

    message = ConversationMessage(
        text=text,
        timestamp=time.time(),
        role=role,
        intent=intent,
        entities=entities,
        visit_id=visit_id,
    )

    _memory_cache[key].append(message)

    # Mantém apenas as últimas N mensagens
    if len(_memory_cache[key]) > MAX_MESSAGES_PER_CHAT:
        _memory_cache[key] = _memory_cache[key][-MAX_MESSAGES_PER_CHAT:]


def get_recent_messages(
    platform: str,
    chat_id: str,
    limit: int = 5,
) -> List[ConversationMessage]:
    """
    Retorna as últimas N mensagens do chat.

    Args:
        platform: telegram, whatsapp, mobile
        chat_id: ID do chat
        limit: Número máximo de mensagens

    Returns:
        Lista de mensagens (mais recente por último)
    """
    _cleanup_old_messages()

    key = _chat_key(platform, chat_id)
    messages = _memory_cache.get(key, [])

    # Filtra mensagens expiradas
    cutoff = time.time() - MESSAGE_TTL_SECONDS
    valid_messages = [m for m in messages if m.timestamp > cutoff]

    return valid_messages[-limit:]


def get_conversation_context(
    platform: str,
    chat_id: str,
) -> ConversationContext:
    """
    Extrai contexto útil do histórico para o agente.

    Retorna um objeto com:
    - recent_messages: textos das últimas mensagens
    - last_intent: último intent detectado
    - last_entities: últimas entidades extraídas
    - last_visit_id: ID da última visita criada
    - last_client_name: último cliente mencionado
    - last_culture: última cultura mencionada
    - has_pending_action: se há ação pendente
    """
    messages = get_recent_messages(platform, chat_id, limit=5)

    context = ConversationContext(
        recent_messages=[m.text for m in messages],
    )

    # Busca informações da última mensagem do usuário com dados
    for msg in reversed(messages):
        if msg.role != "user":
            continue

        if msg.intent and not context.last_intent:
            context.last_intent = msg.intent

        if msg.entities:
            if not context.last_entities:
                context.last_entities = msg.entities

            # Extrai cliente e cultura
            if not context.last_client_name:
                client = msg.entities.get("client") or {}
                context.last_client_name = client.get("name") or msg.entities.get("client_name")

            if not context.last_culture:
                context.last_culture = msg.entities.get("culture")

        if msg.visit_id and not context.last_visit_id:
            context.last_visit_id = msg.visit_id

    # Verifica se há ação pendente (última mensagem foi do assistant pedindo algo)
    if messages and messages[-1].role == "assistant":
        last_text = messages[-1].text.lower()
        pending_keywords = ["confirma", "deseja", "qual", "?"]
        context.has_pending_action = any(k in last_text for k in pending_keywords)

    return context


def clear_chat_memory(platform: str, chat_id: str) -> None:
    """Limpa o histórico de um chat específico."""
    key = _chat_key(platform, chat_id)
    if key in _memory_cache:
        del _memory_cache[key]


def update_last_message_with_result(
    platform: str,
    chat_id: str,
    intent: Optional[str] = None,
    entities: Optional[Dict[str, Any]] = None,
    visit_id: Optional[int] = None,
) -> None:
    """
    Atualiza a última mensagem do usuário com os resultados do processamento.
    Chamado após o agente processar a mensagem.
    """
    key = _chat_key(platform, chat_id)
    messages = _memory_cache.get(key, [])

    if not messages:
        return

    # Encontra a última mensagem do usuário
    for msg in reversed(messages):
        if msg.role == "user":
            if intent:
                msg.intent = intent
            if entities:
                msg.entities = entities
            if visit_id:
                msg.visit_id = visit_id
            break
