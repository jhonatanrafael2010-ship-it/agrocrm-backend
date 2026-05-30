import re
import unicodedata
from typing import Any, Dict, List, Optional

from .agro_knowledge import (
    extract_variety_with_culture,
    infer_culture,
    parse_phenology,
    parse_date_flexible,
)


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
    def _is_structured_format(self, text: str) -> bool:
        """Detecta formato estruturado: linha1=data, linha3=estágio."""
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        if len(lines) < 3:
            return False
        date_pattern = re.compile(r"^\d{2}[/\-]\d{2}(?:[/\-]\d{2,4})?$")
        if not date_pattern.match(lines[0]):
            return False
        line3_lower = normalize_text(lines[2])
        stages = ["plantio", "emergencia", "vegetativo", "reprodutivo", "colheita"]
        return any(stage in line3_lower for stage in stages)

    def _parse_structured_format(self, text: str) -> Dict[str, Any]:
        """Parse formato estruturado de visita."""
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]

        # Linha 1: Data
        date_str = lines[0]
        date_match = re.search(r"(\d{2})[/\-](\d{2})[/\-]?(\d{2,4})?", date_str)
        if date_match:
            dd, mm = date_match.group(1), date_match.group(2)
            yyyy = date_match.group(3)
            if yyyy and len(yyyy) == 2:
                yyyy = "20" + yyyy
            elif not yyyy:
                from datetime import date as _date
                yyyy = str(_date.today().year)
            date_value = f"{dd}/{mm}/{yyyy}"
        else:
            date_value = date_str

        # Linha 2: Cliente
        client_name = lines[1] if len(lines) > 1 else ""

        # Linha 3: Estágio + Variedade
        estagio_line = lines[2] if len(lines) > 2 else ""
        visit_purpose = self.extract_visit_purpose(estagio_line)
        variety = self.extract_variety(estagio_line)

        # Se não encontrou variedade na linha 3, procura nas próximas
        if not variety:
            for i in range(3, min(len(lines), 6)):
                variety = self.extract_variety(lines[i])
                if variety:
                    break

        # Fenologia específica
        fenologia = self.extract_fenology(text)

        # Se não tem fenologia mas tem estágio, mapeia
        if not fenologia and visit_purpose:
            fenologia_map = {
                "Plantio": None,
                "Emergência": "VE",
                "Vegetativo": "V6",
                "Reprodutivo": "R1",
                "Colheita": None,
            }
            fenologia = fenologia_map.get(visit_purpose)

        # CV% (só para plantio)
        cv_percent = None
        if visit_purpose == "Plantio":
            cv_percent = self.extract_cv_percent(text)

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
        if visit_purpose:
            recommendation = f"[Estágio: {visit_purpose}]\n{recommendation}".strip()

        # Infere cultura usando base de conhecimento agrícola
        culture = infer_culture(text, variety)

        return {
            "raw_message": text,
            "client_name": client_name,
            "property_name": None,
            "plot_name": None,
            "culture": culture,
            "variety": variety,
            "visit_purpose": visit_purpose,
            "fenologia_real": fenologia,
            "date": date_value,
            "recommendation": recommendation,
            "products": [],
            "visit_index": None,
            "pdf_client_name": None,
            "cv_percent": cv_percent,
        }

    def extract(self, text: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        context = context or {}

        # Verifica se é formato estruturado primeiro
        if self._is_structured_format(text):
            return self._parse_structured_format(text)

        # Extrai variedade primeiro para ajudar na inferência de cultura
        variety = self.extract_variety(text)

        # Usa base de conhecimento agrícola para inferir cultura
        culture = infer_culture(text, variety)

        # Se não conseguiu inferir, usa método básico
        if not culture:
            culture = self.extract_culture(text)

        return {
            "raw_message": text,
            "client_name": self.extract_client_name(text),
            "property_name": self.extract_property_name(text),
            "plot_name": self.extract_plot_name(text),
            "culture": culture,
            "variety": variety,
            "visit_purpose": self.extract_visit_purpose(text),
            "fenologia_real": self.extract_fenology(text),
            "date": self.extract_date_token(text),
            "recommendation": self.extract_recommendation(text),
            "products": self.extract_products(text),
            "visit_index": self.extract_visit_index(text),
            "pdf_client_name": self.extract_pdf_client_reference(text),
            "cv_percent": self.extract_cv_percent(text),
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

    def extract_variety(self, message: str) -> Optional[str]:
        """Extrai variedade/cultivar usando padrões expandidos."""
        # Usa a função do agro_knowledge primeiro (mais completa)
        variety, _ = extract_variety_with_culture(message)
        if variety:
            return variety

        # Fallback para padrões básicos
        patterns = [
            r"\b(AS\s*\d{3,4}(?:\s*PRO\s*\d+)?)\b",   # AS 1868 PRO4
            r"\b(AG\s*\d{3,4}(?:\s*PRO\d*)?)\b",      # AG 9045
            r"\b(TMG\s*\d{3,4}(?:\s*[A-Z]*)?)\b",     # TMG 2381
            r"\b(M\s*\d{3,4}(?:\s*IPRO)?)\b",         # M 6410 IPRO
            r"\b(NS\s*\d{3,4}(?:\s*IPRO)?)\b",        # NS 7667 IPRO
            r"\b(DM\s*\d{2,4}(?:i\d+)?(?:\s*IPRO)?)\b",  # DM 68i70
            r"\b(DKB\s*\d{3,4}(?:\s*PRO\d*)?)\b",     # DKB 390
            r"\b(2B\s*\d{3,4}(?:\s*PWU)?)\b",         # 2B 810 PWU
            r"\b(30F\d{2})\b",                         # 30F53
            r"\b(P\s*\d{4}(?:\s*[A-Z]+)?)\b",         # P 3456
            r"\b(BMX\s*\w+\s*\d*(?:\s*IPRO)?)\b",     # BMX Potência
            r"\b(NEO\s*\d{3,4})\b",                    # NEO 610
            r"\b(BRS\s*\d{3,4}(?:\s*[A-Z]*)?)\b",     # BRS 388
            r"\b(FM\s*\d{3,4}(?:\s*[A-Z]+)?)\b",      # FM 985 GLT
            r"\b(IMA\s*\d{3,4})\b",                    # IMA 5801
        ]
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                result = match.group(1).upper().strip()
                return re.sub(r"\s+", " ", result)
        return None

    def extract_visit_purpose(self, message: str) -> Optional[str]:
        """Extrai objetivo da visita."""
        normalized = normalize_text(message)

        # Com prefixo "objetivo"
        purpose_match = re.search(r"objetivo[:\s]*(plantio|emergencia|vegetativo|reprodutivo|colheita)", normalized)
        if purpose_match:
            purpose_map = {
                "plantio": "Plantio",
                "emergencia": "Emergência",
                "vegetativo": "Vegetativo",
                "reprodutivo": "Reprodutivo",
                "colheita": "Colheita",
            }
            return purpose_map.get(purpose_match.group(1))

        # Sem prefixo, busca isolado
        if re.search(r"\bplantio\b", normalized):
            return "Plantio"
        if re.search(r"\bemergencia\b", normalized):
            return "Emergência"
        if re.search(r"\bvegetativo\b", normalized):
            return "Vegetativo"
        if re.search(r"\breprodutivo\b", normalized):
            return "Reprodutivo"
        if re.search(r"\bcolheita\b", normalized):
            return "Colheita"

        return None

    def extract_fenology(self, message: str) -> Optional[str]:
        raw = message.strip()
        normalized = normalize_text(raw)
        patterns = [r"\b(v\d+)\b", r"\b(r\d+)\b", r"\b(vt)\b", r"\b(vc)\b", r"\b(ve)\b"]
        for pattern in patterns:
            match = re.search(pattern, raw, flags=re.IGNORECASE)
            if match:
                return match.group(1).upper()
        if "emergencia" in normalized:
            return "Emergência"
        if "floracao" in normalized:
            return "Floração"
        if "maturacao" in normalized:
            return "Maturação"
        if "enchimento" in normalized:
            return "Enchimento de grãos"
        return None

    def extract_date_token(self, message: str) -> Optional[str]:
        msg = normalize_text(message)

        # Palavras-chave exatas (ordem importa - mais específico primeiro)
        simple_keywords = [
            ("semana passada", "semana passada"),
            ("semana retrasada", "semana retrasada"),
            ("mes passado", "mes passado"),
            ("antes de ontem", "anteontem"),
            ("anteontem", "anteontem"),
            ("ontem", "ontem"),
            ("hoje", "hoje"),
            ("agora", "hoje"),
            ("amanha", "amanha"),
        ]
        for keyword, result in simple_keywords:
            if keyword in msg:
                return result

        # Números por extenso expandido
        spelled_numbers = (
            "um|uma|dois|duas|tres|quatro|cinco|seis|sete|"
            "oito|nove|dez|onze|doze|treze|quatorze|catorze|quinze"
        )

        # Padrões flexíveis para "X dias atrás"
        # Aceita: "dois dias atras", "2 dias atrás", "ha 3 dias", "faz 2 dias", "a 3 dias", etc.
        days_ago_patterns = [
            rf"({spelled_numbers}|\d+)\s*dias?\s*atras",      # "dois dias atras", "2 dias atras"
            rf"h?a\s*({spelled_numbers}|\d+)\s*dias?",        # "ha 2 dias", "há dois dias", "a 3 dias"
            rf"faz\s*({spelled_numbers}|\d+)\s*dias?",        # "faz 2 dias", "faz dois dias"
        ]
        for pattern in days_ago_patterns:
            match = re.search(pattern, msg)
            if match:
                return match.group(0)

        # Padrões para semanas
        weeks_patterns = [
            rf"({spelled_numbers}|\d+)\s*semanas?\s*atras",
            rf"h?a\s*({spelled_numbers}|\d+)\s*semanas?",
            rf"faz\s*({spelled_numbers}|\d+)\s*semanas?",
        ]
        for pattern in weeks_patterns:
            match = re.search(pattern, msg)
            if match:
                return match.group(0)

        # Formato ISO: 2026-05-20
        match_iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", message)
        if match_iso:
            return match_iso.group(1)

        # Formato BR completo: DD/MM/YYYY
        match_br = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", message)
        if match_br:
            return match_br.group(1)

        # Formato BR curto: DD/MM
        match_br_short = re.search(r"\b(\d{1,2}/\d{1,2})\b", message)
        if match_br_short:
            return match_br_short.group(1)

        # "dia X" explícito (mas não números soltos como "60.000")
        match_day = re.search(r"\bdia\s+(\d{1,2})\b", msg)
        if match_day:
            return f"dia {match_day.group(1)}"

        return None

    def extract_client_name(self, message: str) -> Optional[str]:
        # Padrões com prefixo explícito
        explicit_patterns = [
            r"cliente[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(fazenda|propriedade|sitio|sítio|talhao|talhão|soja|milho|algodao|algodão|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar|produto|produtos|id|visita|data|fenologia|observacoes|observações|observacao|observação|emergencia|emergência|objetivo|as\s+\d|ag\s+\d)\b|$)",
            r"produtor[:\s]+([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(fazenda|propriedade|sitio|sítio|talhao|talhão|soja|milho|algodao|algodão|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar|produto|produtos|id|visita|data|fenologia|observacoes|observações|observacao|observação|emergencia|emergência|objetivo|as\s+\d|ag\s+\d)\b|$)",
        ]
        for pattern in explicit_patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip(" .,-")
                if value:
                    return value

        # Fallback: tenta extrair nome após data no início
        # Formato: "07/05/2026 Nome do Cliente Objetivo..."
        date_then_name = re.match(
            r"^\s*\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s]+?)(?=\s+(objetivo|fenologia|observacoes|observações|soja|milho|algodao|algodão|as\s+\d|ag\s+\d|vegetativo|reprodutivo|plantio|emergencia|colheita)\b)",
            message,
            flags=re.IGNORECASE
        )
        if date_then_name:
            value = date_then_name.group(1).strip(" .,-")
            if value and len(value) >= 3:
                return value

        # Fallback: nome no início seguido de palavras-chave
        # Formato: "Nome do Cliente AS 1868 PRO4 objetivo..."
        name_at_start = re.match(
            r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s]+?)(?=\s+(as\s+\d|ag\s+\d|objetivo|fenologia|soja|milho|algodao|algodão|v\d+|r\d+|vegetativo|reprodutivo|plantio|emergencia|colheita|observacoes|observações|propriedade|fazenda|faz\.)\b)",
            message.strip(),
            flags=re.IGNORECASE
        )
        if name_at_start:
            value = name_at_start.group(1).strip(" .,-")
            if value and len(value) >= 3:
                return value

        # Fallback: nome no início de mensagem multilinha (antes de quebra de linha)
        # Formato: "Marcos Puziski propriedade faz. X\nAS 1868..."
        first_line = message.strip().split('\n')[0].strip()
        name_before_prop = re.match(
            r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s]+?)(?=\s+(propriedade|fazenda|faz\.)\b)",
            first_line,
            flags=re.IGNORECASE
        )
        if name_before_prop:
            value = name_before_prop.group(1).strip(" .,-")
            if value and len(value) >= 3:
                return value

        return None

    def extract_property_name(self, message: str) -> Optional[str]:
        patterns = [
            r"fazenda[:\s]+([A-Za-zÀ-ÿ0-9\s\-\.]+?)(?=\s+(talhao|talhão|soja|milho|algodao|algodão|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar|as\s+\d|ag\s+\d)\b|\n|$)",
            r"propriedade[:\s]+([A-Za-zÀ-ÿ0-9\s\-\.]+?)(?=\s+(talhao|talhão|soja|milho|algodao|algodão|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar|as\s+\d|ag\s+\d)\b|\n|$)",
            # "propriedade faz. Nome" ou "propriedade faz Nome"
            r"propriedade\s+faz\.?\s*([A-Za-zÀ-ÿ0-9\s\-]+?)(?=\s+(talhao|talhão|soja|milho|algodao|algodão|v\d+|r\d+|hoje|ontem|amanha|amanhã|aplicar|as\s+\d|ag\s+\d)\b|\n|$)",
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

        # Padrões com prefixo explícito (prioridade)
        recommendation_patterns = [
            r"aplicar[:\s]+(.+)",
            r"recomendacao[:\s]+(.+)",
            r"recomendação[:\s]+(.+)",
            r"observações[:\s]+(.+)",
            r"observacoes[:\s]+(.+)",
            r"observação[:\s]+(.+)",
            r"observacao[:\s]+(.+)",
            r"obs[:\s]+(.+)",
        ]
        for pattern in recommendation_patterns:
            match = re.search(pattern, msg, flags=re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                if value:
                    return value

        # Fallback: captura texto livre APÓS data relativa e fenologia
        # Formato: "... R6 dois dias atrás [OBSERVAÇÕES AQUI]"
        lines = msg.split('\n')
        obs_lines = []
        found_fenology_or_date = False

        for line in lines:
            line_clean = line.strip()
            line_lower = normalize_text(line_clean)

            # Detecta linha com fenologia ou data
            has_fenology = bool(re.search(r'\b(v\d+|r\d+|vt|ve|vc)\b', line_lower))
            has_date = any(d in line_lower for d in ['hoje', 'ontem', 'amanha', 'dias atras', 'dia atras', 'semana passada'])
            has_date = has_date or bool(re.search(r'\d{1,2}[/-]\d{1,2}', line_clean))

            if has_fenology or has_date:
                found_fenology_or_date = True
                continue

            # Após encontrar fenologia/data, próximas linhas são observações
            # Ignora linhas que são só variedade, cultura ou dados já extraídos
            if found_fenology_or_date and line_clean:
                # Ignora linhas que são só variedade (AS 1868, AG 9045, etc)
                if re.match(r'^(as|ag|tmg|ns|dm)\s*\d{3,4}', line_lower):
                    continue
                # Ignora linhas que são só cultura
                if line_lower in ['soja', 'milho', 'algodao', 'algodão']:
                    continue
                # Ignora linhas que são só cliente/propriedade (já extraídos)
                if any(kw in line_lower for kw in ['cliente', 'produtor', 'fazenda', 'propriedade', 'talhao', 'talhão']):
                    continue
                obs_lines.append(line_clean)

        if obs_lines:
            # Preserva quebras de linha para o PDF
            return '\n'.join(obs_lines)

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

    def extract_cv_percent(self, text: str) -> Optional[str]:
        """Extrai CV% (Coeficiente de Variação) - usado em estágio de plantio."""
        patterns = [
            r"cv[%]?\s*(?:de\s+)?(\d+[.,]\d+)\s*%?",
            r"coeficiente\s*(?:de\s+)?(?:variacao|variação)\s*(?:de\s+)?(\d+[.,]\d+)\s*%?",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1).replace(",", ".") + "%"
        return None