import re
import os
import request
import unicodedata
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text


def detect_intent(message: str) -> str:
    msg = normalize_text(message)

    visit_keywords = [
        "visita", "agendar", "agenda", "passar ai", "passar aqui",
        "vir aqui", "vir olhar", "olhar a lavoura", "avaliar",
        "check", "checagem", "inspecao", "inspecionar"
    ]

    issue_keywords = [
        "lagarta", "percevejo", "praga", "doenca", "fungo",
        "mancha", "amarelamento", "ataque", "problema"
    ]

    if any(k in msg for k in visit_keywords):
        return "create_visit"

    if any(k in msg for k in issue_keywords):
        return "report_issue"

    return "unknown"


def extract_culture(message: str) -> Optional[str]:
    msg = normalize_text(message)

    if "soja" in msg:
        return "Soja"
    if "milho" in msg:
        return "Milho"
    if "algodao" in msg or "algodão" in message.lower():
        return "Algodão"

    return None


def extract_fenology(message: str) -> Optional[str]:
    raw = message.strip()

    patterns = [
        r"\b(v\d+)\b",
        r"\b(r\d+)\b",
        r"\b(vt)\b",
        r"\b(vc)\b",
        r"\bve\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if match:
            return match.group(1).upper()

    return None


def extract_date_iso(message: str) -> Optional[str]:
    msg = normalize_text(message)
    today = date.today()

    if "hoje" in msg:
        return today.isoformat()

    if "amanha" in msg or "amanhã" in message.lower():
        return (today + timedelta(days=1)).isoformat()

    if "depois de amanha" in msg or "depois de amanhã" in message.lower():
        return (today + timedelta(days=2)).isoformat()

    # formato YYYY-MM-DD
    match_iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", message)
    if match_iso:
        return match_iso.group(1)

    # formato DD/MM/YYYY
    match_br = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", message)
    if match_br:
        dd, mm, yyyy = match_br.groups()
        return f"{yyyy}-{mm}-{dd}"

    return None


def extract_client_name(message: str) -> Optional[str]:
    patterns = [
        r"cliente[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(fazenda|propriedade|sitio|sítio|talhao|talhão|soja|milho|algodao|algodão|v\d+|r\d+|hoje|amanha|amanhã|aplicar)\b|$)",
        r"produtor[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(fazenda|propriedade|sitio|sítio|talhao|talhão|soja|milho|algodao|algodão|v\d+|r\d+|hoje|amanha|amanhã|aplicar)\b|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip(" .,-")
            if value:
                return value

    return None


def extract_property_name(message: str) -> Optional[str]:
    patterns = [
        r"fazenda[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(talhao|talhão|soja|milho|algodao|algodão|v\d+|r\d+|hoje|amanha|amanhã|aplicar)\b|$)",
        r"propriedade[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(talhao|talhão|soja|milho|algodao|algodão|v\d+|r\d+|hoje|amanha|amanhã|aplicar)\b|$)",
        r"sitio[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(talhao|talhão|soja|milho|algodao|algodão|v\d+|r\d+|hoje|amanha|amanhã|aplicar)\b|$)",
        r"sítio[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(talhao|talhão|soja|milho|algodao|algodão|v\d+|r\d+|hoje|amanha|amanhã|aplicar)\b|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip(" .,-")
            if value:
                return value

    return None


def extract_plot_name(message: str) -> Optional[str]:
    patterns = [
        r"talhao[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(soja|milho|algodao|algodão|v\d+|r\d+|hoje|amanha|amanhã|aplicar)\b|$)",
        r"talhão[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(soja|milho|algodao|algodão|v\d+|r\d+|hoje|amanha|amanhã|aplicar)\b|$)",
        r"area[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(soja|milho|algodao|algodão|v\d+|r\d+|hoje|amanha|amanhã|aplicar)\b|$)",
        r"área[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(soja|milho|algodao|algodão|v\d+|r\d+|hoje|amanha|amanhã|aplicar)\b|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip(" .,-")
            if value:
                return value

    return None


def extract_recommendation(message: str) -> str:
    msg = message.strip()

    recommendation_patterns = [
        r"aplicar[:\s]+(.+)",
        r"recomendacao[:\s]+(.+)",
        r"recomendação[:\s]+(.+)",
        r"produto[:\s]+(.+)",
    ]

    for pattern in recommendation_patterns:
        match = re.search(pattern, msg, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value:
                return value

    return ""


def parse_chatbot_message(message: str) -> Dict[str, Any]:
    intent = detect_intent(message)

    parsed: Dict[str, Any] = {
        "intent": intent,
        "raw_message": message,
        "client_name": extract_client_name(message),
        "property_name": extract_property_name(message),
        "plot_name": extract_plot_name(message),
        "culture": extract_culture(message),
        "fenologia_real": extract_fenology(message),
        "date": extract_date_iso(message),
        "recommendation": extract_recommendation(message),
        "status": "planned",
        "source": "chatbot",
        "confidence": "low",
    }

    filled_fields = sum(
        1 for key in [
            "client_name", "property_name", "plot_name",
            "culture", "fenologia_real", "date"
        ]
        if parsed.get(key)
    )

    if intent == "create_visit" and filled_fields >= 3:
        parsed["confidence"] = "high"
    elif intent in ("create_visit", "report_issue") and filled_fields >= 2:
        parsed["confidence"] = "medium"

    return parsed



@dataclass
class ChatAttachment:
    type: str
    file_id: Optional[str] = None
    file_url: Optional[str] = None
    mime_type: Optional[str] = None
    file_name: Optional[str] = None


@dataclass
class ChatMessage:
    platform: str
    chat_id: str
    user_id: str
    user_name: Optional[str]
    message_type: str
    text: Optional[str] = None
    caption: Optional[str] = None
    audio_file_id: Optional[str] = None
    photo_file_id: Optional[str] = None
    attachments: List[ChatAttachment] = field(default_factory=list)
    raw_payload: Dict[str, Any] = field(default_factory=dict)


class ChatbotService:
    """
    Serviço central do chatbot.
    Recebe uma mensagem padronizada do Telegram,
    organiza o payload e devolve uma estrutura interna.
    """

    def normalize_telegram_update(self, update: Dict[str, Any]) -> Optional[ChatMessage]:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return None

        chat = message.get("chat", {})
        from_user = message.get("from", {})

        chat_id = str(chat.get("id", ""))
        user_id = str(from_user.get("id", ""))
        user_name = from_user.get("first_name") or from_user.get("username")

        text = message.get("text")
        caption = message.get("caption")

        if text:
            return ChatMessage(
                platform="telegram",
                chat_id=chat_id,
                user_id=user_id,
                user_name=user_name,
                message_type="text",
                text=text,
                raw_payload=update,
            )

        voice = message.get("voice")
        audio = message.get("audio")
        if voice or audio:
            audio_obj = voice or audio
            return ChatMessage(
                platform="telegram",
                chat_id=chat_id,
                user_id=user_id,
                user_name=user_name,
                message_type="audio",
                caption=caption,
                audio_file_id=audio_obj.get("file_id"),
                attachments=[
                    ChatAttachment(
                        type="audio",
                        file_id=audio_obj.get("file_id"),
                        mime_type=audio_obj.get("mime_type"),
                        file_name=audio_obj.get("file_name"),
                    )
                ],
                raw_payload=update,
            )

        photos = message.get("photo")
        if photos:
            largest_photo = photos[-1]
            return ChatMessage(
                platform="telegram",
                chat_id=chat_id,
                user_id=user_id,
                user_name=user_name,
                message_type="photo",
                caption=caption,
                photo_file_id=largest_photo.get("file_id"),
                attachments=[
                    ChatAttachment(
                        type="photo",
                        file_id=largest_photo.get("file_id"),
                    )
                ],
                raw_payload=update,
            )

        document = message.get("document")
        if document:
            return ChatMessage(
                platform="telegram",
                chat_id=chat_id,
                user_id=user_id,
                user_name=user_name,
                message_type="document",
                caption=caption,
                attachments=[
                    ChatAttachment(
                        type="document",
                        file_id=document.get("file_id"),
                        mime_type=document.get("mime_type"),
                        file_name=document.get("file_name"),
                    )
                ],
                raw_payload=update,
            )

        return ChatMessage(
            platform="telegram",
            chat_id=chat_id,
            user_id=user_id,
            user_name=user_name,
            message_type="unknown",
            raw_payload=update,
        )

    def build_internal_summary(self, chat_message: ChatMessage) -> Dict[str, Any]:
        return {
            "platform": chat_message.platform,
            "chat_id": chat_message.chat_id,
            "user_id": chat_message.user_id,
            "user_name": chat_message.user_name,
            "message_type": chat_message.message_type,
            "text": chat_message.text,
            "caption": chat_message.caption,
            "audio_file_id": chat_message.audio_file_id,
            "photo_file_id": chat_message.photo_file_id,
            "attachments_count": len(chat_message.attachments),
        }

    def send_telegram_message(chat_id: str, text: str) -> Dict[str, Any]:
    token = os.getenv("8648977952:AAEHy9MBQwi3Gtum5IponlZvrG0qOnpsIoY")
    if not token:
        return {
            "ok": False,
            "error": "8648977952:AAEHy9MBQwi3Gtum5IponlZvrG0qOnpsIoY not configured"
        }

    url = f"https://api.telegram.org/bot{8648977952:AAEHy9MBQwi3Gtum5IponlZvrG0qOnpsIoY}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    try:
        response = requests.post(url, json=payload, timeout=20)
        return {
            "ok": response.ok,
            "status_code": response.status_code,
            "response": response.json() if response.content else {}
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }