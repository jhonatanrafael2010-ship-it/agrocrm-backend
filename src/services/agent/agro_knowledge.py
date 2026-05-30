# -*- coding: utf-8 -*-
"""
Base de conhecimento agrícola para parsing inteligente de visitas.
Mapeia variedades, contextos e termos técnicos para identificar cultura automaticamente.
"""

import re
from typing import Optional, Tuple

# =============================================================================
# VARIEDADES POR CULTURA
# Prefixos e padrões de variedades comerciais
# =============================================================================

SOJA_VARIETIES = {
    # Prefixos exclusivos de soja
    "TMG": True,      # Tropical Melhoramento e Genética
    "NS": True,       # Nidera Seeds
    "DM": True,       # Don Mario
    "BRS": True,      # Embrapa
    "NEO": True,      # GDM Seeds
    "BMX": True,      # Brasmax
    "NA": True,       # Nidera
    "SYN": True,      # Syngenta
    "CZ": True,       # Coodetec/BASF
    "CD": True,       # Coodetec
    "FTS": True,      # FT Sementes
    "BS": True,       # BASF
    "HO": True,       # Hokkaido
    "RA": True,       # Raizen
    "LG": True,       # Limagrain (soja)
}

MILHO_VARIETIES = {
    # Prefixos exclusivos de milho
    "AG": True,       # Agroceres
    "DKB": True,      # Dekalb
    "2B": True,       # Dow
    "30F": True,      # Pioneer
    "P": True,        # Pioneer (P3456, P4285)
    "BM": True,       # Biomatrix
    "SHS": True,      # Santa Helena Sementes
    "PRE": True,      # Precision
    "KWS": True,      # KWS
    "FS": True,       # FS Seeds
    "MG": True,       # Morgan
    "SG": True,       # SG Genética
    "RB": True,       # Riber
}

ALGODAO_VARIETIES = {
    # Prefixos de algodão
    "FM": True,       # FiberMax
    "TMG": False,     # TMG também tem algodão (TMG 44, TMG 47)
    "IMA": True,      # Instituto Mato-grossense do Algodão
    "DP": True,       # Deltapine
    "BRS": False,     # Embrapa também tem algodão
    "IAC": True,      # Instituto Agronômico de Campinas
}

# Padrões de variedades que podem ser de múltiplas culturas
AMBIGUOUS_VARIETIES = {
    "AS": ["Soja", "Milho"],  # Asgrow (pode ser soja ou milho)
    "M": ["Soja", "Milho"],   # Monsoy/Morgan
    "TMG": ["Soja", "Algodão"],
    "BRS": ["Soja", "Algodão", "Milho"],
}

# =============================================================================
# CONTEXTO POR CULTURA
# Palavras que indicam fortemente uma cultura específica
# =============================================================================

MILHO_CONTEXT = [
    # Estruturas da planta
    "espiga", "espigas", "espigueta", "espiguetas",
    "sabugo", "sabugos", "palha da espiga",
    "pendao", "pendão", "pendoamento",
    "cabelo", "cabelos", "estilo-estigma",

    # Métricas de milho
    "graos por espiga", "grãos por espiga",
    "fileiras por espiga", "fileira por espiga",
    "espigas por planta", "espiga por planta",
    "espigas por hectare", "espigas finais",
    "prolificidade",

    # Fenologia específica milho
    "VT",  # Pendoamento
    "embonecamento",

    # Doenças específicas milho
    "helmintosporiose", "cercospora zeae", "bipolaris",
    "enfezamento", "enfezamento vermelho", "enfezamento palido",
    "podridao do colmo", "podridão do colmo",
    "diplodia", "fusarium",
    "mancha branca", "phaeosphaeria",
    "ferrugem polissora", "ferrugem comum", "puccinia polysora",

    # Pragas específicas milho
    "lagarta do cartucho", "spodoptera frugiperda",
    "lagarta da espiga", "helicoverpa",
    "cigarrinha do milho", "dalbulus maidis",
    "percevejo barriga verde",

    # Termos gerais
    "milharal", "silagem",
]

SOJA_CONTEXT = [
    # Estruturas da planta
    "vagem", "vagens", "legume", "legumes",
    "no", "nó", "nos", "nós", "entrenó", "entrenós",
    "trifólio", "trifolio", "trifolios", "trifólios",
    "haste", "hastes", "ramificacao", "ramificação",

    # Métricas de soja
    "graos por vagem", "grãos por vagem",
    "vagens por planta", "vagem por planta",
    "nos por planta", "nós por planta",
    "altura de insercao", "altura de inserção",
    "primeiro no", "primeiro nó",

    # Fenologia específica soja
    "VE", "VC",  # Emergência e cotilédone
    "R1", "R2", "R3", "R4", "R5", "R5.1", "R5.2", "R5.3", "R5.4", "R5.5",
    "R6", "R7", "R8",
    "floracao", "floração", "enchimento de graos", "enchimento de grãos",
    "maturacao", "maturação", "ponto de colheita",

    # Doenças específicas soja
    "ferrugem asiatica", "ferrugem asiática", "phakopsora",
    "antracnose", "colletotrichum",
    "oidio", "oídio", "microsphaera", "erysiphe",
    "mofo branco", "sclerotinia",
    "DFC", "doencas de final de ciclo", "doenças de final de ciclo",
    "crestamento", "cercospora kikuchii", "septoria",
    "mancha alvo", "corynespora", "target spot",
    "podridao radicular", "podridão radicular", "fusarium", "rhizoctonia",
    "nematoide", "nematóide", "nematoides", "nematóides",
    "macrophomina", "podridao de carvao", "podridão de carvão",

    # Pragas específicas soja
    "lagarta da soja", "anticarsia", "anticarsia gemmatalis",
    "lagarta falsa medideira", "chrysodeixis", "pseudoplusia",
    "percevejo marrom", "euschistus", "percevejo verde", "nezara",
    "percevejo pequeno", "piezodorus", "edessa",
    "mosca branca", "bemisia", "aleyrodidae",
    "vaquinha", "diabrotica", "cerotoma",
    "acaro", "ácaro", "acaros", "ácaros",
    "trips", "tripes",

    # Termos gerais
    "sojicultura", "lavoura de soja",
]

ALGODAO_CONTEXT = [
    # Estruturas da planta
    "capulho", "capulhos", "pluma", "plumas",
    "maca", "maçã", "macas", "maçãs", "boll",
    "botao floral", "botão floral", "botoes florais", "botões florais",
    "bracteola", "bractéola",

    # Métricas de algodão
    "peso de capulho", "capulhos por planta",
    "maças por planta", "maçãs por planta",
    "arrobas por hectare", "@/ha",
    "fibra", "rendimento de fibra",
    "HVI", "micronaire", "comprimento de fibra",

    # Fenologia específica algodão
    "B1", "B2", "B3", "B4", "B5", "B6",  # Botão floral
    "F1", "F2", "F3", "F4", "F5",        # Floração
    "C1", "C2", "C3", "C4",              # Capulho
    "cut out", "cutout",

    # Doenças específicas algodão
    "ramularia", "ramulária", "ramulariose",
    "ramulose",
    "mancha de alternaria", "alternária",
    "mancha angular", "mancha de ramularia",
    "fusariose", "murcha de fusarium",
    "tombamento",

    # Pragas específicas algodão
    "bicudo", "anthonomus grandis",
    "lagarta das macas", "lagarta das maçãs", "heliothis",
    "lagarta rosada", "pectinophora",
    "curuquere", "alabama",
    "acaro rajado", "ácaro rajado", "tetranychus",
    "pulgao", "pulgão", "aphis",
    "mosca branca", "bemisia",
    "tripes", "thrips",

    # Termos gerais
    "cotonicultura", "lavoura de algodao", "lavoura de algodão",
    "algodoeiro",
]

# =============================================================================
# FUNÇÕES DE INFERÊNCIA
# =============================================================================

def normalize_text(text: str) -> str:
    """Normaliza texto para comparação."""
    if not text:
        return ""
    import unicodedata
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text


def extract_variety_with_culture(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrai variedade do texto e infere cultura.
    Retorna (variety, culture) ou (None, None).
    """
    if not text:
        return None, None

    # Padrões de variedades com números
    variety_patterns = [
        # Soja específicos
        r"\b(TMG\s*\d{3,4}(?:\s*[A-Z]*)?)\b",
        r"\b(NS\s*\d{3,4}(?:\s*IPRO)?)\b",
        r"\b(DM\s*\d{2,4}(?:i\d+)?(?:\s*IPRO)?)\b",
        r"\b(BMX\s*\w+\s*\d*(?:\s*IPRO)?)\b",
        r"\b(NEO\s*\d{3,4})\b",
        r"\b(CD\s*\d{3,4})\b",
        r"\b(SYN\s*\d{3,4})\b",

        # Milho específicos
        r"\b(AG\s*\d{4}(?:\s*PRO\d*)?)\b",
        r"\b(DKB\s*\d{3,4}(?:\s*PRO\d*)?)\b",
        r"\b(2B\s*\d{3,4}(?:\s*PWU)?)\b",
        r"\b(30F\d{2})\b",
        r"\b(P\s*\d{4}(?:\s*[A-Z]+)?)\b",
        r"\b(BM\s*\d{3,4})\b",
        r"\b(KWS\s*\d{3,4})\b",
        r"\b(MG\s*\d{3,4})\b",

        # Algodão específicos
        r"\b(FM\s*\d{3,4}(?:\s*[A-Z]+)?)\b",
        r"\b(IMA\s*\d{3,4})\b",
        r"\b(DP\s*\d{3,4})\b",

        # Ambíguos (precisam de contexto)
        r"\b(AS\s*\d{3,4}(?:\s*PRO\s*\d+)?)\b",
        r"\b(M\s*\d{4}(?:\s*IPRO)?)\b",
        r"\b(BRS\s*\d{3,4}(?:\s*[A-Z]*)?)\b",
    ]

    for pattern in variety_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            variety = match.group(1).upper().strip()
            variety = re.sub(r"\s+", " ", variety)  # Normaliza espaços

            # Determina cultura pelo prefixo
            prefix = variety.split()[0] if " " in variety else variety[:3]
            prefix = re.sub(r"\d+", "", prefix).strip()

            # Prefixos exclusivos
            if prefix in SOJA_VARIETIES and SOJA_VARIETIES[prefix]:
                return variety, "Soja"
            if prefix in MILHO_VARIETIES and MILHO_VARIETIES[prefix]:
                return variety, "Milho"
            if prefix in ALGODAO_VARIETIES and ALGODAO_VARIETIES[prefix]:
                return variety, "Algodão"

            # Prefixos ambíguos - retorna variedade sem cultura definida
            if prefix in AMBIGUOUS_VARIETIES:
                return variety, None

            return variety, None

    return None, None


def infer_culture_from_context(text: str) -> Optional[str]:
    """
    Infere cultura baseado em palavras-chave no texto.
    Usa pontuação para determinar a cultura mais provável.
    """
    if not text:
        return None

    text_lower = normalize_text(text)

    scores = {"Milho": 0, "Soja": 0, "Algodão": 0}

    # Conta ocorrências de contexto
    for keyword in MILHO_CONTEXT:
        keyword_norm = normalize_text(keyword)
        if keyword_norm in text_lower:
            scores["Milho"] += 2 if len(keyword_norm) > 5 else 1

    for keyword in SOJA_CONTEXT:
        keyword_norm = normalize_text(keyword)
        if keyword_norm in text_lower:
            scores["Soja"] += 2 if len(keyword_norm) > 5 else 1

    for keyword in ALGODAO_CONTEXT:
        keyword_norm = normalize_text(keyword)
        if keyword_norm in text_lower:
            scores["Algodão"] += 2 if len(keyword_norm) > 5 else 1

    # Menções diretas da cultura (peso alto)
    if "milho" in text_lower:
        scores["Milho"] += 10
    if "soja" in text_lower:
        scores["Soja"] += 10
    if "algodao" in text_lower or "algodão" in text.lower():
        scores["Algodão"] += 10

    # Retorna cultura com maior score (mínimo 2 para evitar falsos positivos)
    max_score = max(scores.values())
    if max_score >= 2:
        for culture, score in scores.items():
            if score == max_score:
                return culture

    return None


def infer_culture(text: str, variety: Optional[str] = None) -> Optional[str]:
    """
    Infere cultura combinando análise de variedade e contexto.
    Prioridade: contexto > variedade (contexto é mais específico)
    """
    # Primeiro tenta pelo contexto (mais confiável)
    context_culture = infer_culture_from_context(text)
    if context_culture:
        return context_culture

    # Se tem variedade, tenta pelo prefixo
    if variety:
        _, variety_culture = extract_variety_with_culture(variety)
        if variety_culture:
            return variety_culture

    # Tenta extrair variedade do texto completo
    _, text_variety_culture = extract_variety_with_culture(text)
    if text_variety_culture:
        return text_variety_culture

    return None


def parse_phenology(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrai fenologia e estágio do texto.
    Retorna (fenologia, estagio).
    """
    if not text:
        return None, None

    text_upper = text.upper()
    text_lower = normalize_text(text)

    fenologia = None
    estagio = None

    # Padrões de fenologia
    phenology_patterns = [
        # Soja/Milho vegetativo
        (r"\b(VE)\b", "VE", "Emergência"),
        (r"\b(VC)\b", "VC", "Vegetativo"),
        (r"\b(V\d{1,2})\b", None, "Vegetativo"),
        (r"\b(VT)\b", "VT", "Reprodutivo"),  # Milho - pendoamento

        # Soja reprodutivo
        (r"\b(R\d(?:\.\d)?)\b", None, "Reprodutivo"),

        # Algodão
        (r"\b(B\d)\b", None, "Vegetativo"),   # Botão floral
        (r"\b(F\d{1,2})\b", None, "Reprodutivo"),  # Floração
        (r"\b(C\d)\b", None, "Reprodutivo"),  # Capulho
    ]

    for pattern, fixed_fen, stage in phenology_patterns:
        match = re.search(pattern, text_upper)
        if match:
            fenologia = fixed_fen or match.group(1)
            estagio = stage
            break

    # Estágios por palavras-chave
    stage_keywords = {
        "Plantio": ["plantio", "plantando", "plantei", "semear", "semeadura", "semeando"],
        "Emergência": ["emergencia", "emergência", "emergindo", "nascendo"],
        "Vegetativo": ["vegetativo", "crescimento", "desenvolvimento vegetativo"],
        "Reprodutivo": ["reprodutivo", "floracao", "floração", "enchimento", "formacao de graos", "formação de grãos"],
        "Colheita": ["colheita", "colhendo", "colhido", "colher", "maturacao", "maturação", "ponto de colheita"],
    }

    if not estagio:
        for stage, keywords in stage_keywords.items():
            for kw in keywords:
                if normalize_text(kw) in text_lower:
                    estagio = stage
                    break
            if estagio:
                break

    return fenologia, estagio


def parse_date_flexible(text: str) -> Optional[str]:
    """
    Extrai data do texto em vários formatos.
    Retorna data no formato DD/MM/YYYY ou token relativo.
    """
    if not text:
        return None

    from datetime import date, timedelta

    text_lower = normalize_text(text)
    today = date.today()

    # Palavras relativas
    if "hoje" in text_lower or "agora" in text_lower:
        return today.strftime("%d/%m/%Y")

    if "ontem" in text_lower:
        return (today - timedelta(days=1)).strftime("%d/%m/%Y")

    if "anteontem" in text_lower or "antes de ontem" in text_lower:
        return (today - timedelta(days=2)).strftime("%d/%m/%Y")

    if "amanha" in text_lower:
        return (today + timedelta(days=1)).strftime("%d/%m/%Y")

    # X dias atrás
    days_ago = re.search(r"(\d+)\s*dias?\s*(?:atras|atrás)", text_lower)
    if days_ago:
        days = int(days_ago.group(1))
        if 1 <= days <= 365:
            return (today - timedelta(days=days)).strftime("%d/%m/%Y")

    # há X dias
    ha_days = re.search(r"(?:ha|há)\s*(\d+)\s*dias?", text_lower)
    if ha_days:
        days = int(ha_days.group(1))
        if 1 <= days <= 365:
            return (today - timedelta(days=days)).strftime("%d/%m/%Y")

    # Formatos numéricos
    # DD/MM/YYYY ou DD-MM-YYYY
    full_date = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", text)
    if full_date:
        dd, mm, yyyy = full_date.groups()
        return f"{dd.zfill(2)}/{mm.zfill(2)}/{yyyy}"

    # DD/MM/YY
    short_year = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})\b", text)
    if short_year:
        dd, mm, yy = short_year.groups()
        yyyy = f"20{yy}"
        return f"{dd.zfill(2)}/{mm.zfill(2)}/{yyyy}"

    # DD/MM (assume ano atual)
    day_month = re.search(r"\b(\d{1,2})[/\-](\d{1,2})\b", text)
    if day_month:
        dd, mm = day_month.groups()
        return f"{dd.zfill(2)}/{mm.zfill(2)}/{today.year}"

    # Dia da semana
    weekdays = {
        "segunda": 0, "seg": 0,
        "terca": 1, "ter": 1,
        "quarta": 2, "qua": 2,
        "quinta": 3, "qui": 3,
        "sexta": 4, "sex": 4,
        "sabado": 5, "sab": 5,
        "domingo": 6, "dom": 6,
    }

    for day_name, day_num in weekdays.items():
        if day_name in text_lower:
            current_weekday = today.weekday()
            diff = day_num - current_weekday
            if diff >= 0:
                diff -= 7  # Assume semana passada
            target = today + timedelta(days=diff)
            return target.strftime("%d/%m/%Y")

    return None
