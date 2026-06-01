import re
import os
import requests
import unicodedata
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from services.agent.agro_knowledge import infer_culture, extract_variety_with_culture


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

    if "depois de amanha" in msg or "depois de amanhã" in message.lower():
        return (today + timedelta(days=2)).isoformat()

    if "amanha" in msg or "amanhã" in message.lower():
        return (today + timedelta(days=1)).isoformat()

    if "anteontem" in msg:
        return (today - timedelta(days=2)).isoformat()

    if "ontem" in msg:
        return (today - timedelta(days=1)).isoformat()

    # "X dias atrás" / "há X dias"
    match_days_ago = re.search(r"(\d+)\s*dias?\s*atr[aá]s", msg)
    if match_days_ago:
        return (today - timedelta(days=int(match_days_ago.group(1)))).isoformat()

    match_ha_days = re.search(r"h[aá]\s+(\d+)\s*dias?", msg)
    if match_ha_days:
        return (today - timedelta(days=int(match_ha_days.group(1)))).isoformat()

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


def extract_estagio(message: str) -> Optional[str]:
    """Extrai estágio macro: Plantio, Emergência, Vegetativo, Reprodutivo, Colheita."""
    msg = normalize_text(message)

    if "plantio" in msg:
        return "Plantio"
    if "emergencia" in msg:
        return "Emergência"
    if "vegetativo" in msg:
        return "Vegetativo"
    if "reprodutivo" in msg:
        return "Reprodutivo"
    if "colheita" in msg:
        return "Colheita"

    return None


def extract_cv_percent(message: str) -> Optional[str]:
    """Extrai CV% (Coeficiente de Variação) - usado em plantio."""
    patterns = [
        r"cv[%]?\s*(?:de\s+)?(\d+[.,]\d+)\s*%?",
        r"coeficiente\s*(?:de\s+)?(?:varia[çc][aã]o)\s*(?:de\s+)?(\d+[.,]\d+)\s*%?",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1).replace(",", ".") + "%"

    return None


def extract_variety_from_text(message: str) -> Optional[str]:
    """Extrai variedade do texto (ex: AS 1868 PRO4, AS 1868 PRO 4)."""
    patterns = [
        r"\b(AS\s*\d{4}\s*(?:PRO\s*\d+)?)\b",
        r"\b(M\s*\d{4}\s*(?:PRO\s*\d+)?)\b",
        r"\b(DM\s*\d{4})\b",
        r"\b(BRS\s*\d{4})\b",
        r"\b(TMG\s*\d{4})\b",
        r"\b(NS\s*\d{4})\b",
        r"\b(NEO\s*\d{3,4})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1).strip().upper()

    return None


def is_structured_format(message: str) -> bool:
    """Detecta se a mensagem está no formato estruturado (linha 1=data, linha 2=cliente, etc)."""
    lines = [l.strip() for l in message.strip().split("\n") if l.strip()]
    if len(lines) < 3:
        return False

    # Linha 1 deve ser apenas uma data
    date_pattern = re.compile(r"^\d{2}[/\-]\d{2}[/\-]?\d{0,4}$")
    if not date_pattern.match(lines[0]):
        return False

    # Linha 3 deve conter estágio
    line3_lower = normalize_text(lines[2])
    return any(s in line3_lower for s in ["plantio", "emergencia", "vegetativo", "reprodutivo", "colheita"])


def parse_structured_message(message: str) -> Dict[str, Any]:
    """
    Parse formato estruturado:
    Linha 1: Data
    Linha 2: Cliente
    Linha 3: Estágio + Variedade
    Linhas 4+: Observações
    """
    lines = [l.strip() for l in message.strip().split("\n") if l.strip()]

    # Linha 1: Data
    date_str = lines[0] if len(lines) > 0 else ""
    match_br = re.search(r"(\d{2})/(\d{2})/(\d{4})", date_str)
    if match_br:
        dd, mm, yyyy = match_br.groups()
        date_iso = f"{yyyy}-{mm}-{dd}"
    else:
        date_iso = None

    # Linha 2: Cliente
    client_name = lines[1] if len(lines) > 1 else ""

    # Linha 3: Estágio + Variedade
    estagio_line = lines[2] if len(lines) > 2 else ""
    estagio = extract_estagio(estagio_line)
    variety = extract_variety_from_text(estagio_line)

    # Se não encontrou variedade na linha 3, procura nas próximas
    if not variety:
        for i in range(3, min(len(lines), 6)):
            variety = extract_variety_from_text(lines[i])
            if variety:
                break

    # Extrai fenologia específica (V1-V14, R1-R8)
    fenologia = extract_fenology(message)

    # Se não tem fenologia mas tem estágio, mapeia
    if not fenologia and estagio:
        fenologia_map = {
            "Plantio": None,
            "Emergência": "VE",
            "Vegetativo": "V6",
            "Reprodutivo": "R1",
            "Colheita": None,
        }
        fenologia = fenologia_map.get(estagio)

    # CV% (só para plantio)
    cv_percent = None
    if estagio == "Plantio":
        cv_percent = extract_cv_percent(message)

    # Observações: linhas 4+ (exceto CV)
    obs_lines = []
    for i in range(3, len(lines)):
        line = lines[i]
        # Não inclui linha de CV nas observações
        if not re.search(r"cv[%]?\s*(?:de\s+)?[\d]", line, re.IGNORECASE):
            obs_lines.append(line)

    recommendation = "\n".join(obs_lines).strip()

    # Adiciona CV e estágio como metadados na recomendação
    if cv_percent:
        recommendation = f"[CV%: {cv_percent}]\n{recommendation}".strip()
    if estagio:
        recommendation = f"[Estágio: {estagio}]\n{recommendation}".strip()

    # Infere cultura usando base de conhecimento agrícola
    culture = infer_culture(message, variety)

    return {
        "intent": "create_visit",
        "raw_message": message,
        "client_name": client_name,
        "property_name": None,
        "plot_name": None,
        "culture": culture,
        "variety": variety,
        "fenologia_real": fenologia,
        "estagio": estagio,
        "date": date_iso,
        "recommendation": recommendation,
        "cv_percent": cv_percent,
        "status": "done",
        "source": "chatbot",
        "confidence": "high" if client_name and variety else "medium",
        "products": [],
        "visit_id": None,
    }


def extract_client_name(message: str) -> Optional[str]:
    # Aceita: "cliente Marcos Puziski\n", "Cliente: João Silva fazenda X",
    # "produtor Pedro da Silva v4". Para linha multi, pega até \n ou delimitador.
    patterns = [
        r"cliente[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\n|\s+(fazenda|propriedade|sitio|sítio|talhao|talhão|reprodutivo|variedade|cultura|soja|milho|algodao|algodão|area|área|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar|produto|produtos|id|visita|data|fenologia|\d{2}/\d{2})\b|$)",
        r"produtor[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\n|\s+(fazenda|propriedade|sitio|sítio|talhao|talhão|reprodutivo|variedade|cultura|soja|milho|algodao|algodão|area|área|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar|produto|produtos|id|visita|data|fenologia|\d{2}/\d{2})\b|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip(" .,-\n\r\t")
            if value:
                return value

    return None


def extract_property_name(message: str) -> Optional[str]:
    patterns = [
        r"fazenda[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\n|\s+(talhao|talhão|reprodutivo|variedade|cultura|soja|milho|algodao|algodão|area|área|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar|data|fenologia|\d{2}/\d{2})\b|$)",
        r"propriedade[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\n|\s+(talhao|talhão|reprodutivo|variedade|cultura|soja|milho|algodao|algodão|area|área|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar|data|fenologia|\d{2}/\d{2})\b|$)",
        r"sitio[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\n|\s+(talhao|talhão|reprodutivo|variedade|cultura|soja|milho|algodao|algodão|area|área|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar|data|fenologia|\d{2}/\d{2})\b|$)",
        r"sítio[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\n|\s+(talhao|talhão|reprodutivo|variedade|cultura|soja|milho|algodao|algodão|area|área|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar|data|fenologia|\d{2}/\d{2})\b|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip(" .,-\n\r\t")
            if value:
                return value

    return None


def extract_plot_name(message: str) -> Optional[str]:
    patterns = [
        r"talhao[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\n|\s+(soja|milho|algodao|algodão|reprodutivo|variedade|cultura|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar|data|fenologia|\d{2}/\d{2})\b|$)",
        r"talhão[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\n|\s+(soja|milho|algodao|algodão|reprodutivo|variedade|cultura|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar|data|fenologia|\d{2}/\d{2})\b|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip(" .,-\n\r\t")
            if value:
                return value

    return None


def extract_recommendation(message: str) -> str:
    msg = message.strip()

    recommendation_patterns = [
        r"(?:observacoes|observações|observação|observacao|obs)\s*[:,\-]?\s*([\s\S]+)$",
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

    # Fallback: se mensagem tem múltiplas linhas e nenhum marcador bateu,
    # tudo que vem DEPOIS dos campos estruturados (data, cliente, fazenda,
    # talhão, cultura, fenologia, variedade, reprodutivo) vira observação.
    lines = [ln.strip() for ln in msg.split("\n") if ln.strip()]
    if len(lines) <= 1:
        return ""

    structured_prefixes = (
        "lancar visita", "lançar visita", "nova visita",
        "data ", "data:",
        "cliente ", "cliente:",
        "produtor ", "produtor:",
        "fazenda ", "fazenda:",
        "propriedade ", "propriedade:",
        "talhao ", "talhao:", "talhão ", "talhão:",
        "cultura ", "cultura:",
        "fenologia ", "fenologia:",
        "variedade ", "variedade:",
        "reprodutivo ", "reprodutivo:",
    )

    free_lines = []
    for ln in lines:
        ln_lower = ln.lower()
        if ln_lower.startswith(structured_prefixes):
            continue
        # pula data isolada DD/MM/YYYY
        if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", ln):
            continue
        free_lines.append(ln)

    if free_lines:
        return " ".join(free_lines).strip()

    return ""


PRODUCT_UNITS = ["L/ha", "mL/ha", "kg/ha", "g/ha", "%", "p.c"]


def normalize_decimal_str(value: str) -> str:
    if not value:
        return ""
    return value.replace(",", ".").strip()


def normalize_unit_text(unit_raw: str) -> str:
    if not unit_raw:
        return ""

    unit = unit_raw.strip().lower()
    unit = unit.replace(" ", "")

    mapping = {
        "l/ha": "L/ha",
        "lha": "L/ha",
        "litro/ha": "L/ha",
        "litros/ha": "L/ha",
        "litroporhectare": "L/ha",
        "litrosporhectare": "L/ha",
        "lporhectare": "L/ha",

        "ml/ha": "mL/ha",
        "mlha": "mL/ha",
        "mililitro/ha": "mL/ha",
        "mililitros/ha": "mL/ha",
        "mlporhectare": "mL/ha",
        "mililitroporhectare": "mL/ha",
        "mililitrosporhectare": "mL/ha",

        "kg/ha": "kg/ha",
        "kgha": "kg/ha",
        "kgporhectare": "kg/ha",

        "g/ha": "g/ha",
        "gha": "g/ha",
        "gporhectare": "g/ha",

        "%": "%",
        "pc": "p.c",
        "p.c": "p.c",
    }

    return mapping.get(unit, unit_raw.strip())


def clean_product_name(raw_name: str) -> str:
    if not raw_name:
        return ""

    value = raw_name.strip(" .,-;:")

    garbage_prefixes = [
        "aplicacao de produtos",
        "aplicação de produtos",
        "aplicacao de produto",
        "aplicação de produto",
        "produto",
        "produtos",
        "apliquei",
        "aplicar",
        "aplicacao",
        "aplicação",
        "de",
        "e",
    ]

    normalized = value.lower().strip()
    changed = True
    while changed:
        changed = False
        for prefix in garbage_prefixes:
            if normalized.startswith(prefix + " "):
                value = value[len(prefix):].strip(" .,-;:")
                normalized = value.lower().strip()
                changed = True

    return value


def extract_products(message: str) -> List[Dict[str, Any]]:
    if not message:
        return []

    text = message.strip()

    unit_pattern = (
        r"(L/ha|mL/ha|kg/ha|g/ha|%|p\.c|"
        r"l por hectare|ml por hectare|kg por hectare|g por hectare|"
        r"litro por hectare|litros por hectare|mililitro por hectare|mililitros por hectare)"
    )

    patterns = [
        rf"([A-Za-zÀ-ÿ0-9\-\+\./ ]{{2,}}?)\s+(\d+[\.,]?\d*)\s*{unit_pattern}\b",
    ]

    found = []
    seen = set()

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            raw_name = match.group(1).strip(" .,-;:")
            dose = normalize_decimal_str(match.group(2))
            unit = normalize_unit_text(match.group(3))
            product_name = clean_product_name(raw_name)

            if not product_name or not dose or not unit:
                continue

            key = (product_name.lower(), dose, unit.lower())
            if key in seen:
                continue
            seen.add(key)

            found.append({
                "product_name": product_name,
                "dose": dose,
                "unit": unit,
                "application_date": extract_date_iso(message),
            })

    return found


def extract_visit_id(message: str) -> Optional[int]:
    if not message:
        return None

    patterns = [
        r"\bid\s+da\s+visita\s+(\d+)\b",
        r"\bvisita\s+id\s+(\d+)\b",
        r"\bid\s+visita\s+(\d+)\b",
        r"\bvisita\s+(\d{3,})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None

    return None


def parse_chatbot_message(message: str) -> Dict[str, Any]:
    # Verifica se é formato estruturado (linha 1=data, linha 2=cliente, etc)
    if is_structured_format(message):
        return parse_structured_message(message)

    # Formato livre (comportamento original)
    intent = detect_intent(message)

    parsed: Dict[str, Any] = {
        "intent": intent,
        "raw_message": message,
        "client_name": extract_client_name(message),
        "property_name": extract_property_name(message),
        "plot_name": extract_plot_name(message),
        "culture": extract_culture(message),
        "variety": extract_variety_from_text(message),
        "fenologia_real": extract_fenology(message),
        "estagio": extract_estagio(message),
        "date": extract_date_iso(message),
        "recommendation": extract_recommendation(message),
        "cv_percent": extract_cv_percent(message),
        "status": "planned",
        "source": "chatbot",
        "confidence": "low",
        "products": extract_products(message),
        "visit_id": extract_visit_id(message),
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


def send_telegram_document(chat_id: str, file_bytes: bytes, filename: str, caption: str = "") -> Dict[str, Any]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return {
            "ok": False,
            "error": "TELEGRAM_BOT_TOKEN not configured"
        }

    url = f"https://api.telegram.org/bot{token}/sendDocument"

    files = {
        "document": (filename, file_bytes, "application/pdf")
    }
    data = {
        "chat_id": chat_id,
        "caption": caption or ""
    }

    try:
        response = requests.post(url, data=data, files=files, timeout=60)
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



def send_telegram_message(
    chat_id: str,
    text: str,
    parse_mode: str = None,
    reply_markup: Dict[str, Any] = None
) -> Dict[str, Any]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return {
            "ok": False,
            "error": "TELEGRAM_BOT_TOKEN not configured"
        }

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    if parse_mode:
        payload["parse_mode"] = parse_mode

    if reply_markup:
        payload["reply_markup"] = reply_markup

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


def send_telegram_photo(chat_id: str, photo_url: str, caption: str = None) -> Dict[str, Any]:
    """Envia uma foto via Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return {
            "ok": False,
            "error": "TELEGRAM_BOT_TOKEN not configured"
        }

    url = f"https://api.telegram.org/bot{token}/sendPhoto"

    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
    }

    if caption:
        payload["caption"] = caption

    try:
        response = requests.post(url, json=payload, timeout=30)
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