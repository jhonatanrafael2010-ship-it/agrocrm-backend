"""
================================================================
Unified Chat Handler
================================================================

Funções unificadas de processamento de chat que funcionam para
Telegram e Mobile/Site. Cada função retorna um dict com:
  - text: mensagem de resposta
  - status: próximo status do estado (ou None para deletar)
  - state_data: dados para salvar no estado (opcional)

O caller (telegram_webhook ou mobile_chat) é responsável por:
  - Enviar a mensagem (Telegram API ou retorno JSON)
  - Atualizar o estado no banco
================================================================
"""

import json
import re
from datetime import date as _date
from typing import Any, Dict, Optional, Tuple

from models import (
    Client, Property, Visit, Consultant,
    ChatbotConversationState, db
)


def normalize_lookup_text(text: str) -> str:
    import unicodedata
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_cancel_command(text: str) -> bool:
    normalized = normalize_lookup_text(text)
    return normalized in ("cancelar", "cancela", "cancel", "sair", "voltar")


def normalize_culture_input(text: str) -> Optional[str]:
    if not text:
        return None
    normalized = normalize_lookup_text(text)
    if "soja" in normalized:
        return "Soja"
    if "milho" in normalized:
        return "Milho"
    if "algodao" in normalized:
        return "Algodão"
    if normalized in ("soja", "milho", "algodao", "algodão"):
        return text.strip().title()
    return None


def is_valid_fenologia(text: str) -> bool:
    if not text:
        return False
    normalized = text.strip().upper()
    if re.match(r"^V\d{1,2}$", normalized):
        return True
    if re.match(r"^R\d{1,2}$", normalized):
        return True
    if normalized in ("VE", "VC", "VT", "PLANTIO", "EMERGENCIA", "EMERGÊNCIA", "FLORAÇÃO", "FLORACAO", "MATURAÇÃO", "MATURACAO"):
        return True
    return False


def parse_yes_no(text: str) -> Optional[bool]:
    normalized = normalize_lookup_text(text)
    if normalized in ("sim", "s", "yes", "y", "1", "ok", "positivo"):
        return True
    if normalized in ("nao", "não", "n", "no", "0", "negativo"):
        return False
    return None


def parse_human_date(text: str) -> Optional[_date]:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    normalized = normalize_lookup_text(text)
    today = datetime.now(ZoneInfo("America/Cuiaba")).date()

    if normalized in ("hoje", "today"):
        return today
    if normalized in ("ontem", "yesterday"):
        return today - timedelta(days=1)
    if normalized in ("anteontem",):
        return today - timedelta(days=2)
    if normalized in ("amanha", "amanhã", "tomorrow"):
        return today + timedelta(days=1)

    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m"):
        try:
            parsed = datetime.strptime(text.strip(), fmt)
            if fmt == "%d/%m":
                parsed = parsed.replace(year=today.year)
            return parsed.date()
        except ValueError:
            continue

    return None


class UnifiedChatResponse:
    def __init__(
        self,
        text: str,
        next_status: Optional[str] = None,
        state_data: Optional[Dict] = None,
        delete_state: bool = False,
        pdf_items: Optional[list] = None,
    ):
        self.text = text
        self.next_status = next_status
        self.state_data = state_data or {}
        self.delete_state = delete_state
        self.pdf_items = pdf_items

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "next_status": self.next_status,
            "state_data": self.state_data,
            "delete_state": self.delete_state,
            "pdf_items": self.pdf_items,
        }


class UnifiedChatHandler:
    """
    Handler unificado para processamento de mensagens de chat.
    Funciona para Telegram e Mobile/Site.
    """

    def __init__(self, platform: str, session_id: str, consultant: Optional[Consultant] = None):
        self.platform = platform
        self.session_id = session_id
        self.consultant = consultant
        self.consultant_id = consultant.id if consultant else None

    def get_state(self) -> Optional[ChatbotConversationState]:
        return ChatbotConversationState.query.filter_by(
            platform=self.platform,
            chat_id=self.session_id
        ).first()

    def ensure_state(self) -> ChatbotConversationState:
        state = self.get_state()
        if not state:
            state = ChatbotConversationState(
                platform=self.platform,
                chat_id=self.session_id,
                status="idle",
            )
            db.session.add(state)
            db.session.commit()
        return state

    def delete_state(self) -> None:
        state = self.get_state()
        if state:
            db.session.delete(state)
            db.session.commit()

    def update_state(self, status: str, **kwargs) -> ChatbotConversationState:
        state = self.ensure_state()
        state.status = status
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)
        db.session.commit()
        return state

    def handle_cancel(self) -> UnifiedChatResponse:
        return UnifiedChatResponse(
            text="❌ Operação cancelada.",
            delete_state=True,
        )

    def handle_guided_culture(self, message_text: str, state_data: Dict) -> UnifiedChatResponse:
        culture = normalize_culture_input(message_text)
        if not culture:
            return UnifiedChatResponse(
                text="🌱 Cultura não reconhecida.\nExemplos: Soja, Milho, Algodão.",
                next_status="awaiting_culture",
            )

        final_visit_payload = state_data.get("final_visit_payload") or {}
        final_visit_payload["culture"] = culture

        new_state_data = {
            **state_data,
            "final_visit_payload": final_visit_payload,
        }

        return UnifiedChatResponse(
            text="🌿 Informe a fenologia observada.\nExemplo: V4, V5, R1, Plantio, Emergência",
            next_status="awaiting_fenologia",
            state_data=new_state_data,
        )

    def handle_guided_fenologia(self, message_text: str, state_data: Dict) -> UnifiedChatResponse:
        text_upper = message_text.strip().upper()

        # Aceita fenologias descritivas
        fenologia_map = {
            "EMERGENCIA": "Emergência",
            "EMERGÊNCIA": "Emergência",
            "PLANTIO": "Plantio",
            "FLORACAO": "Floração",
            "FLORAÇÃO": "Floração",
            "MATURACAO": "Maturação",
            "MATURAÇÃO": "Maturação",
        }

        fenologia = fenologia_map.get(text_upper, text_upper if is_valid_fenologia(text_upper) else None)

        if not fenologia:
            return UnifiedChatResponse(
                text="🌿 Fenologia inválida.\nExemplo: V4, R1, Plantio, Emergência",
                next_status="awaiting_fenologia",
            )

        final_visit_payload = state_data.get("final_visit_payload") or {}
        final_visit_payload["fenologia_real"] = fenologia

        new_state_data = {
            **state_data,
            "final_visit_payload": final_visit_payload,
        }

        return UnifiedChatResponse(
            text="📅 Informe a data da visita.\nExemplo: hoje, ontem, 24/02/2026",
            next_status="awaiting_date",
            state_data=new_state_data,
        )

    def handle_guided_date(self, message_text: str, state_data: Dict) -> UnifiedChatResponse:
        parsed_date = parse_human_date(message_text)

        if not parsed_date:
            return UnifiedChatResponse(
                text="📅 Data não reconhecida.\nExemplo: hoje, ontem, 24/02/2026",
                next_status="awaiting_date",
            )

        final_visit_payload = state_data.get("final_visit_payload") or {}
        final_visit_payload["date"] = parsed_date.isoformat()

        new_state_data = {
            **state_data,
            "final_visit_payload": final_visit_payload,
        }

        return UnifiedChatResponse(
            text="💬 Informe as observações da visita.\nOu envie 'pular' para continuar sem observações.",
            next_status="awaiting_observations",
            state_data=new_state_data,
        )

    def handle_guided_observations(self, message_text: str, state_data: Dict) -> UnifiedChatResponse:
        final_visit_payload = state_data.get("final_visit_payload") or {}

        if normalize_lookup_text(message_text) not in ("pular", "skip", "-"):
            final_visit_payload["recommendation"] = message_text.strip()

        new_state_data = {
            **state_data,
            "final_visit_payload": final_visit_payload,
        }

        summary = self.build_visit_summary(final_visit_payload)

        return UnifiedChatResponse(
            text=summary,
            next_status="awaiting_final_confirmation",
            state_data=new_state_data,
        )

    def build_visit_summary(self, payload: Dict) -> str:
        client_id = payload.get("client_id")
        client_name = "—"
        if client_id:
            client = Client.query.get(client_id)
            if client:
                client_name = client.name

        property_id = payload.get("property_id")
        property_name = "—"
        if property_id:
            prop = Property.query.get(property_id)
            if prop:
                property_name = prop.name

        lines = [
            "📝 Resumo da visita",
            "",
            "🆕 Tipo: Nova visita",
            f"👤 Cliente: {client_name}",
            f"🏡 Fazenda: {property_name}",
            f"🌱 Cultura: {payload.get('culture') or '—'}",
            f"🌿 Fenologia: {payload.get('fenologia_real') or '—'}",
            f"📅 Data: {payload.get('date') or '—'}",
            f"💬 Observações: {payload.get('recommendation') or '—'}",
        ]

        products = payload.get("products") or []
        if products:
            lines.append("")
            lines.append("🧪 Produtos:")
            for p in products:
                lines.append(f"  - {p.get('product_name')} {p.get('dose')} {p.get('unit')}")

        lines.extend([
            "",
            "Responda com:",
            "✅ CONFIRMAR",
            "❌ CANCELAR",
        ])

        return "\n".join(lines)

    def handle_final_confirmation(self, message_text: str, state_data: Dict, photos: list = None) -> UnifiedChatResponse:
        normalized = normalize_lookup_text(message_text)

        if normalized in ("cancelar", "cancela", "cancel"):
            return self.handle_cancel()

        if normalized not in ("confirmar", "confirma", "confirmo", "ok", "sim"):
            return UnifiedChatResponse(
                text="Responda com CONFIRMAR ou CANCELAR.",
                next_status="awaiting_final_confirmation",
            )

        final_visit_payload = state_data.get("final_visit_payload") or {}

        # Criar a visita
        try:
            visit = Visit(
                client_id=final_visit_payload.get("client_id"),
                property_id=final_visit_payload.get("property_id"),
                plot_id=final_visit_payload.get("plot_id"),
                planting_id=final_visit_payload.get("planting_id"),
                consultant_id=final_visit_payload.get("consultant_id") or self.consultant_id or 1,
                culture=final_visit_payload.get("culture"),
                variety=final_visit_payload.get("variety"),
                fenologia_real=final_visit_payload.get("fenologia_real"),
                date=_date.fromisoformat(final_visit_payload["date"]) if final_visit_payload.get("date") else None,
                recommendation=final_visit_payload.get("recommendation"),
                status="done",
                source=self.platform,
            )
            db.session.add(visit)
            db.session.commit()

            # Salvar fotos se houver
            photo_urls = final_visit_payload.get("photos") or []
            if photo_urls:
                from models import Photo
                for url in photo_urls:
                    photo = Photo(visit_id=visit.id, url=url)
                    db.session.add(photo)
                db.session.commit()

            client_name = "—"
            if visit.client_id:
                client = Client.query.get(visit.client_id)
                if client:
                    client_name = client.name

            return UnifiedChatResponse(
                text=f"✅ Visita registrada com sucesso!\n\n👤 {client_name}\n🌱 {visit.culture or '—'}\n🌿 {visit.fenologia_real or '—'}\n📅 {visit.date.strftime('%d/%m/%Y') if visit.date else '—'}",
                delete_state=True,
            )

        except Exception as e:
            return UnifiedChatResponse(
                text=f"❌ Erro ao salvar visita: {str(e)}",
                delete_state=True,
            )

    def process_guided_flow(self, message_text: str, current_status: str) -> Optional[UnifiedChatResponse]:
        """Processa mensagem em fluxo guiado. Retorna None se não houver estado."""

        if is_cancel_command(message_text):
            return self.handle_cancel()

        state = self.get_state()
        if not state:
            return None

        try:
            state_data = json.loads(state.visit_preview_json or "{}")
        except Exception:
            state_data = {}

        if current_status == "awaiting_culture":
            return self.handle_guided_culture(message_text, state_data)

        if current_status == "awaiting_fenologia":
            return self.handle_guided_fenologia(message_text, state_data)

        if current_status == "awaiting_date":
            return self.handle_guided_date(message_text, state_data)

        if current_status == "awaiting_observations":
            return self.handle_guided_observations(message_text, state_data)

        if current_status == "awaiting_final_confirmation":
            return self.handle_final_confirmation(message_text, state_data)

        return None

    def apply_response(self, response: UnifiedChatResponse) -> None:
        """Aplica as mudanças de estado do response."""
        if response.delete_state:
            self.delete_state()
        elif response.next_status:
            state = self.ensure_state()
            state.status = response.next_status
            if response.state_data:
                state.visit_preview_json = json.dumps(response.state_data, ensure_ascii=False)
            if response.text:
                state.confirmation_text = response.text
            db.session.commit()
