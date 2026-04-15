import re
import unicodedata
from typing import Any, Dict, List, Optional


PRODUCT_UNITS = ["L/ha", "mL/ha", "kg/ha", "g/ha", "%", "p.c"]


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class EntityExtractor:
    def extract(self, text: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        context = context or {}

        return {
            "raw_message": text,
            "client_name": self.extract_client_name(text),
            "property_name": self.extract_property_name(text),
            "plot_name": self.extract_plot_name(text),
            "culture": self.extract_culture(text),
            "fenologia_real": self.extract_fenology(text),
            "date": self.extract_date_token(text),
            "recommendation": self.extract_recommendation(text),
            "products": self.extract_products(text),
            "visit_index": self.extract_visit_index(text),
            "pdf_client_name": self.extract_pdf_client_reference(text),
        }

    def extract_culture(self, message: str) -> Optional[str]:
        msg = normalize_text(message)
        if "soja" in msg:
            return "Soja"
        if "milho" in msg:
            return "Milho"
        if "algodao" in msg:
            return "Algodão"
        return None

    def extract_fenology(self, message: str) -> Optional[str]:
        raw = message.strip()
        patterns = [r"\b(v\d+)\b", r"\b(r\d+)\b", r"\b(vt)\b", r"\b(vc)\b", r"\bve\b"]
        for pattern in patterns:
            match = re.search(pattern, raw, flags=re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return None

    def extract_date_token(self, message: str) -> Optional[str]:
        msg = normalize_text(message)

        if "hoje" in msg:
            return "hoje"
        if "ontem" in msg:
            return "ontem"
        if "amanha" in msg:
            return "amanha"
        if "anteontem" in msg:
            return "anteontem"
        if "semana passada" in msg:
            return "semana passada"

        match_iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", message)
        if match_iso:
            return match_iso.group(1)

        match_br = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", message)
        if match_br:
            return match_br.group(1)

        match_br_short = re.search(r"\b(\d{1,2}/\d{1,2})\b", message)
        if match_br_short:
            return match_br_short.group(1)

        match_day = re.search(r"\b(dia\s+\d{1,2}|\d{1,2})\b", msg)
        if match_day:
            token = match_day.group(1)
            if token.isdigit() or token.startswith("dia "):
                return token

        return None

    def extract_client_name(self, message: str) -> Optional[str]:
        patterns = [
            r"cliente[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(fazenda|propriedade|sitio|sítio|talhao|talhão|soja|milho|algodao|algodão|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar|produto|produtos|id|visita)\b|$)",
            r"produtor[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(fazenda|propriedade|sitio|sítio|talhao|talhão|soja|milho|algodao|algodão|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar|produto|produtos|id|visita)\b|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip(" .,-")
                if value:
                    return value
        return None

    def extract_property_name(self, message: str) -> Optional[str]:
        patterns = [
            r"fazenda[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(talhao|talhão|soja|milho|algodao|algodão|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar)\b|$)",
            r"propriedade[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(talhao|talhão|soja|milho|algodao|algodão|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar)\b|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip(" .,-")
                if value:
                    return value
        return None

    def extract_plot_name(self, message: str) -> Optional[str]:
        patterns = [
            r"talhao[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(soja|milho|algodao|algodão|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar)\b|$)",
            r"talhão[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(soja|milho|algodao|algodão|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar)\b|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip(" .,-")
                if value:
                    return value
        return None

    def extract_recommendation(self, message: str) -> str:
        msg = message.strip()
        recommendation_patterns = [
            r"aplicar[:\s]+(.+)",
            r"recomendacao[:\s]+(.+)",
            r"recomendação[:\s]+(.+)",
            r"observacoes[:\s]+(.+)",
            r"observação[:\s]+(.+)",
            r"observacao[:\s]+(.+)",
            r"obs[:\s]+(.+)",
            r"produto[:\s]+(.+)",
        ]
        for pattern in recommendation_patterns:
            match = re.search(pattern, msg, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if value:
                    return value
        return ""

    def normalize_decimal_str(self, value: str) -> str:
        return value.replace(",", ".").strip() if value else ""

    def normalize_unit_text(self, unit_raw: str) -> str:
        if not unit_raw:
            return ""
        unit = unit_raw.strip().lower().replace(" ", "")
        mapping = {
            "l/ha": "L/ha",
            "lha": "L/ha",
            "ml/ha": "mL/ha",
            "mlha": "mL/ha",
            "kg/ha": "kg/ha",
            "kgha": "kg/ha",
            "g/ha": "g/ha",
            "gha": "g/ha",
            "%": "%",
            "pc": "p.c",
            "p.c": "p.c",
        }
        return mapping.get(unit, unit_raw.strip())

    def clean_product_name(self, raw_name: str) -> str:
        if not raw_name:
            return ""
        value = raw_name.strip(" .,-;:")
        garbage_prefixes = [
            "aplicacao de produtos",
            "aplicação de produtos",
            "produto",
            "produtos",
            "apliquei",
            "aplicar",
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

    def extract_products(self, message: str) -> List[Dict[str, Any]]:
        if not message:
            return []
        text = message.strip()
        unit_pattern = (
            r"(L/ha|mL/ha|kg/ha|g/ha|%|p\.c|"
            r"l por hectare|ml por hectare|kg por hectare|g por hectare|"
            r"litro por hectare|litros por hectare|mililitro por hectare|mililitros por hectare)"
        )
        pattern = rf"([A-Za-zÀ-ÿ0-9\-\+\./ ]{{2,}}?)\s+(\d+[\.,]?\d*)\s*{unit_pattern}\b"

        found = []
        seen = set()
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            raw_name = match.group(1).strip(" .,-;:")
            dose = self.normalize_decimal_str(match.group(2))
            unit = self.normalize_unit_text(match.group(3))
            product_name = self.clean_product_name(raw_name)
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
                "application_date": self.extract_date_token(message),
            })
        return found

    def extract_visit_index(self, text: str) -> Optional[int]:
        normalized = normalize_text(text)
        patterns = [
            r"(?:visita\s+)?(\d+)$",
            r"lancar\s+(?:a\s+)?(?:visita\s+)?(\d+)$",
            r"concluir\s+(?:a\s+)?(?:visita\s+)?(\d+)$",
            r"pdf\s+(\d+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                try:
                    return int(match.group(1))
                except Exception:
                    return None
        return None

    def extract_pdf_client_reference(self, text: str) -> Optional[str]:
        raw = (text or "").strip()
        normalized = normalize_text(raw)
        patterns = [
            r"^pdf do cliente (.+)$",
            r"^pdf do (.+)$",
            r"^manda o pdf do (.+)$",
            r"^pdf da ultima do (.+)$",
            r"^pdf da última do (.+)$",
        ]
        for pattern in patterns:
            match = re.match(pattern, normalized)
            if match:
                value = raw[match.start(1):].strip(" .,-")
                if value:
                    return value
        return None