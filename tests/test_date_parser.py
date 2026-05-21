"""
Testes para parse_human_date em routes.py

Roda com: pytest tests/test_date_parser.py -v
"""
import sys
from pathlib import Path
from datetime import date, timedelta

# Adiciona src ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Importa função de normalização e recria parse_human_date isoladamente
# (para não precisar carregar todo o Flask app)
import re
import unicodedata


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_human_date(text: str, base_date: date = None) -> date | None:
    """
    Cópia da função parse_human_date de routes.py para testes isolados.
    """
    if not text:
        return None

    today = base_date or date.today()
    normalized = _normalize_text(text).strip(" .,!?:;")

    # Mapa de números por extenso
    spelled_numbers = {
        "um": 1, "uma": 1, "1": 1,
        "dois": 2, "duas": 2, "2": 2,
        "tres": 3, "3": 3,
        "quatro": 4, "4": 4,
        "cinco": 5, "5": 5,
        "seis": 6, "6": 6,
        "sete": 7, "7": 7,
        "oito": 8, "8": 8,
        "nove": 9, "9": 9,
        "dez": 10, "10": 10,
        "onze": 11, "11": 11,
        "doze": 12, "12": 12,
        "treze": 13, "13": 13,
        "quatorze": 14, "catorze": 14, "14": 14,
        "quinze": 15, "15": 15,
    }

    def parse_number(s: str) -> int | None:
        s = s.strip()
        if s in spelled_numbers:
            return spelled_numbers[s]
        if s.isdigit():
            return int(s)
        return None

    # Casos exatos simples
    simple_map = {
        "hoje": 0,
        "agora": 0,
        "amanha": 1,
        "ontem": -1,
        "anteontem": -2,
        "antes de ontem": -2,
        "semana passada": -7,
        "semana retrasada": -14,
        "mes passado": -30,
    }

    if normalized in simple_map:
        return today + timedelta(days=simple_map[normalized])

    # Padrões flexíveis para "X dias atrás"
    days_ago_patterns = [
        r"^(\w+)\s+dias?\s+atras$",
        r"^h?a\s+(\w+)\s+dias?$",
        r"^faz\s+(\w+)\s+dias?$",
        r"^(\w+)\s+dias?$",
    ]

    for pattern in days_ago_patterns:
        match = re.match(pattern, normalized)
        if match:
            num = parse_number(match.group(1))
            if num and 1 <= num <= 60:
                return today - timedelta(days=num)

    # Padrões para semanas
    weeks_patterns = [
        r"^(\w+)\s+semanas?\s+atras$",
        r"^h?a\s+(\w+)\s+semanas?$",
        r"^faz\s+(\w+)\s+semanas?$",
    ]

    for pattern in weeks_patterns:
        match = re.match(pattern, normalized)
        if match:
            num = parse_number(match.group(1))
            if num and 1 <= num <= 12:
                return today - timedelta(days=num * 7)

    # dd/mm ou dd-mm
    match = re.fullmatch(r"(\d{1,2})[\/\-](\d{1,2})", normalized)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        try:
            return date(today.year, month, day)
        except ValueError:
            return None

    # dd/mm/yyyy ou dd-mm-yyyy
    match = re.fullmatch(r"(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})", normalized)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            return None

    # yyyy-mm-dd
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", normalized)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            return None

    return None


# ============================================================
# TESTES
# ============================================================

class TestSimpleDates:
    """Testes para palavras-chave simples"""

    BASE = date(2026, 5, 21)

    def test_hoje(self):
        assert parse_human_date("hoje", self.BASE) == date(2026, 5, 21)

    def test_hoje_maiusculo(self):
        assert parse_human_date("HOJE", self.BASE) == date(2026, 5, 21)

    def test_agora(self):
        assert parse_human_date("agora", self.BASE) == date(2026, 5, 21)

    def test_ontem(self):
        assert parse_human_date("ontem", self.BASE) == date(2026, 5, 20)

    def test_anteontem(self):
        assert parse_human_date("anteontem", self.BASE) == date(2026, 5, 19)

    def test_antes_de_ontem(self):
        assert parse_human_date("antes de ontem", self.BASE) == date(2026, 5, 19)

    def test_amanha(self):
        assert parse_human_date("amanhã", self.BASE) == date(2026, 5, 22)

    def test_semana_passada(self):
        assert parse_human_date("semana passada", self.BASE) == date(2026, 5, 14)


class TestDiasAtras:
    """Testes para 'X dias atrás' em várias formas"""

    BASE = date(2026, 5, 21)

    def test_dois_dias_atras(self):
        assert parse_human_date("dois dias atrás", self.BASE) == date(2026, 5, 19)

    def test_dois_dias_atras_sem_acento(self):
        assert parse_human_date("dois dias atras", self.BASE) == date(2026, 5, 19)

    def test_2_dias_atras(self):
        assert parse_human_date("2 dias atrás", self.BASE) == date(2026, 5, 19)

    def test_tres_dias_atras(self):
        assert parse_human_date("três dias atrás", self.BASE) == date(2026, 5, 18)

    def test_cinco_dias_atras(self):
        assert parse_human_date("cinco dias atrás", self.BASE) == date(2026, 5, 16)

    def test_dez_dias_atras(self):
        assert parse_human_date("dez dias atrás", self.BASE) == date(2026, 5, 11)

    def test_quinze_dias_atras(self):
        assert parse_human_date("quinze dias atrás", self.BASE) == date(2026, 5, 6)

    def test_ha_2_dias(self):
        assert parse_human_date("há 2 dias", self.BASE) == date(2026, 5, 19)

    def test_ha_dois_dias(self):
        assert parse_human_date("há dois dias", self.BASE) == date(2026, 5, 19)

    def test_faz_3_dias(self):
        assert parse_human_date("faz 3 dias", self.BASE) == date(2026, 5, 18)

    def test_faz_dois_dias(self):
        assert parse_human_date("faz dois dias", self.BASE) == date(2026, 5, 19)

    def test_a_2_dias(self):
        assert parse_human_date("a 2 dias", self.BASE) == date(2026, 5, 19)


class TestSemanas:
    """Testes para semanas"""

    BASE = date(2026, 5, 21)

    def test_uma_semana_atras(self):
        assert parse_human_date("uma semana atrás", self.BASE) == date(2026, 5, 14)

    def test_2_semanas_atras(self):
        assert parse_human_date("2 semanas atrás", self.BASE) == date(2026, 5, 7)

    def test_duas_semanas_atras(self):
        assert parse_human_date("duas semanas atrás", self.BASE) == date(2026, 5, 7)

    def test_ha_2_semanas(self):
        assert parse_human_date("há 2 semanas", self.BASE) == date(2026, 5, 7)


class TestFormatosBR:
    """Testes para formatos de data brasileiros"""

    BASE = date(2026, 5, 21)

    def test_dd_mm(self):
        assert parse_human_date("15/05", self.BASE) == date(2026, 5, 15)

    def test_dd_mm_yyyy(self):
        assert parse_human_date("15/05/2026", self.BASE) == date(2026, 5, 15)

    def test_dd_mm_yyyy_traco(self):
        assert parse_human_date("15-05-2026", self.BASE) == date(2026, 5, 15)


class TestFormatoISO:
    """Testes para formato ISO"""

    BASE = date(2026, 5, 21)

    def test_iso(self):
        assert parse_human_date("2026-05-15", self.BASE) == date(2026, 5, 15)


class TestInvalidos:
    """Testes para entradas inválidas"""

    BASE = date(2026, 5, 21)

    def test_texto_invalido(self):
        assert parse_human_date("blablabla", self.BASE) is None

    def test_vazio(self):
        assert parse_human_date("", self.BASE) is None

    def test_none(self):
        assert parse_human_date(None, self.BASE) is None

    def test_data_invalida(self):
        assert parse_human_date("32/13/2026", self.BASE) is None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
