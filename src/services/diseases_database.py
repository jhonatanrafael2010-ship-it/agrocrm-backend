"""
================================================================
Base de Dados de Pragas e Doenças
================================================================

Base local com informações detalhadas e assertivas sobre
pragas e doenças de soja, milho e algodão.

Vantagens sobre IA:
- Respostas consistentes e validadas
- Inclui fotos dos sintomas
- Não depende de API externa
- Mais rápido e barato

As imagens ficam no R2: {R2_PUBLIC_BASE_URL}/diseases/{slug}.jpg
================================================================
"""

import os
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional


def get_r2_base_url() -> str:
    return (os.environ.get("R2_PUBLIC_BASE_URL") or "").rstrip("/")


def get_disease_image_url(slug: str) -> str:
    """Retorna URL da imagem no R2."""
    base = get_r2_base_url()
    if not base:
        return ""
    return f"{base}/diseases/{slug}.jpg"


# ================================================================
# BASE DE DADOS DE DOENÇAS
# ================================================================

DISEASES_DATABASE: List[Dict[str, Any]] = [
    # ============================================================
    # SOJA - DOENÇAS
    # ============================================================
    {
        "slug": "ferrugem-asiatica",
        "name": "Ferrugem Asiática",
        "scientific_name": "Phakopsora pachyrhizi",
        "type": "doenca",
        "crop": "soja",
        "keywords": ["ferrugem", "ferrugem asiatica", "ferrugem asiática", "phakopsora"],
        "symptoms": (
            "Pequenas lesões de cor castanha a marrom-escura na face inferior das folhas. "
            "Pústulas (urédias) liberam esporos de cor bege a marrom. "
            "Lesões podem coalescer, causando amarelecimento e queda prematura das folhas. "
            "Inicia nas folhas baixeiras e progride para o topo da planta."
        ),
        "favorable_conditions": (
            "Temperatura entre 18-26°C (ótima 22°C). "
            "Umidade relativa acima de 80%. "
            "Molhamento foliar por mais de 6 horas. "
            "Períodos chuvosos e noites com orvalho prolongado."
        ),
        "control_threshold": (
            "Monitoramento constante a partir de R1. "
            "Primeira aplicação preventiva em R1 ou ao detectar primeiras pústulas na região. "
            "Consultar vazio sanitário e alertas fitossanitários da região."
        ),
        "products": [
            {"name": "Fox (Trifloxistrobina + Protioconazol)", "dose": "0.4 L/ha", "group": "Triazol + Estrobilurina"},
            {"name": "Elatus (Azoxistrobina + Benzovindiflupir)", "dose": "0.2 L/ha", "group": "Estrobilurina + Carboxamida"},
            {"name": "Mancozebe", "dose": "1.5-2.0 kg/ha", "group": "Multissítio (sempre em mistura)"},
            {"name": "Orkestra (Fluxapiroxade + Piraclostrobina)", "dose": "0.3 L/ha", "group": "Carboxamida + Estrobilurina"},
        ],
        "management_tips": (
            "ROTAÇÃO DE GRUPOS QUÍMICOS É ESSENCIAL para evitar resistência. "
            "Usar multissítio (mancozebe, clorotalonil) em todas as aplicações. "
            "Intervalo máximo de 14 dias entre aplicações em alta pressão. "
            "Variedades com gene de resistência ajudam mas não dispensam fungicida. "
            "Respeitar o vazio sanitário da região."
        ),
    },
    {
        "slug": "mancha-alvo",
        "name": "Mancha Alvo",
        "scientific_name": "Corynespora cassiicola",
        "type": "doenca",
        "crop": "soja",
        "keywords": ["mancha alvo", "corynespora", "alvo", "mancha com ponto"],
        "symptoms": (
            "Lesões circulares com PONTO CENTRAL ESCURO característico (olho de alvo). "
            "Halo amarelado ao redor da lesão. "
            "Lesões podem atingir 2 cm de diâmetro. "
            "Ataca folhas, hastes, vagens e sementes. "
            "Causa desfolha severa em cultivares suscetíveis."
        ),
        "favorable_conditions": (
            "Temperatura entre 20-28°C. "
            "Alta umidade e chuvas frequentes. "
            "Monocultura de soja e áreas com histórico. "
            "Cultivares suscetíveis."
        ),
        "control_threshold": (
            "Monitorar a partir do fechamento das entrelinhas. "
            "Aplicar preventivamente em áreas com histórico. "
            "Primeiros sintomas: aplicação imediata."
        ),
        "products": [
            {"name": "Orkestra (Fluxapiroxade + Piraclostrobina)", "dose": "0.3-0.35 L/ha", "group": "Carboxamida + Estrobilurina"},
            {"name": "Fox (Trifloxistrobina + Protioconazol)", "dose": "0.4 L/ha", "group": "Triazol + Estrobilurina"},
            {"name": "Aproach Prima (Picoxistrobina + Ciproconazol)", "dose": "0.3 L/ha", "group": "Triazol + Estrobilurina"},
        ],
        "management_tips": (
            "Cultivares resistentes são a principal ferramenta de manejo. "
            "Rotação de culturas reduz inóculo no solo. "
            "Tratamento de sementes ajuda no controle inicial. "
            "Carboxamidas têm melhor eficiência para esta doença."
        ),
    },
    {
        "slug": "mofo-branco",
        "name": "Mofo Branco",
        "scientific_name": "Sclerotinia sclerotiorum",
        "type": "doenca",
        "crop": "soja",
        "keywords": ["mofo branco", "sclerotinia", "mofo", "esclerodinia", "podridao branca"],
        "symptoms": (
            "Micélio branco COTONOSO nas hastes, especialmente próximo ao solo. "
            "Escleródios pretos (estruturas de resistência) dentro das hastes. "
            "Murcha e morte de plantas. "
            "Hastes ficam esbranquiçadas e ocas. "
            "Sintomas aparecem em reboleiras."
        ),
        "favorable_conditions": (
            "Temperatura amena (15-25°C). "
            "Alta umidade (>70%) e chuvas frequentes. "
            "Dossel fechado que mantém umidade. "
            "Solos com histórico e alta população de escleródios."
        ),
        "control_threshold": (
            "Aplicar no fechamento das entrelinhas (pré-floração). "
            "Segunda aplicação 10-14 dias após, se condições favoráveis. "
            "Áreas com histórico: aplicação obrigatória."
        ),
        "products": [
            {"name": "Frowncide (Fluazinam)", "dose": "1.0 L/ha", "group": "Fenilpiridinilamina"},
            {"name": "Sumilex (Procimidona)", "dose": "1.0 kg/ha", "group": "Dicarboximida"},
            {"name": "Verango Prime (Fluopyram)", "dose": "0.4 L/ha", "group": "Carboxamida"},
        ],
        "management_tips": (
            "Manejo de plantas daninhas reduz umidade no dossel. "
            "Espaçamento maior entre linhas ajuda na ventilação. "
            "Rotação com gramíneas (milho, sorgo) reduz inóculo. "
            "Controle biológico com Trichoderma pode auxiliar. "
            "Evitar plantio muito adensado em áreas de risco."
        ),
    },
    {
        "slug": "antracnose-soja",
        "name": "Antracnose",
        "scientific_name": "Colletotrichum truncatum",
        "type": "doenca",
        "crop": "soja",
        "keywords": ["antracnose", "colletotrichum", "cancro", "vagem preta"],
        "symptoms": (
            "Manchas escuras deprimidas (cancros) em hastes e vagens. "
            "Vagens ficam retorcidas e escurecidas. "
            "Sementes manchadas e de baixa qualidade. "
            "Em hastes: lesões marrons a pretas, deprimidas."
        ),
        "favorable_conditions": (
            "Alta umidade e chuvas frequentes durante enchimento de grãos. "
            "Temperatura entre 22-28°C. "
            "Sementes infectadas como fonte de inóculo."
        ),
        "control_threshold": "Tratamento de sementes obrigatório. Aplicações foliares a partir de R3.",
        "products": [
            {"name": "Carbendazim", "dose": "0.5 L/ha", "group": "Benzimidazol"},
            {"name": "Cercobin (Tiofanato-metílico)", "dose": "0.5 L/ha", "group": "Benzimidazol"},
            {"name": "Comet (Piraclostrobina)", "dose": "0.3 L/ha", "group": "Estrobilurina"},
        ],
        "management_tips": (
            "Tratamento de sementes é fundamental. "
            "Usar sementes de boa qualidade sanitária. "
            "Rotação de culturas. "
            "Evitar colheita em condições muito úmidas."
        ),
    },
    # ============================================================
    # MILHO - DOENÇAS
    # ============================================================
    {
        "slug": "mancha-bipolaris",
        "name": "Mancha de Bipolaris",
        "scientific_name": "Bipolaris maydis / Bipolaris zeicola",
        "type": "doenca",
        "crop": "milho",
        "keywords": ["bipolaris", "mancha bipolaris", "helmintosporio", "mancha do milho"],
        "symptoms": (
            "Lesões PEQUENAS A MÉDIAS (0.5-2 cm), formato oval a alongado. "
            "Cor palha no centro com BORDOS CASTANHOS bem definidos. "
            "Lesões podem coalescer em condições favoráveis. "
            "Ataca principalmente folhas abaixo da espiga. "
            "Em ataques severos, folhas secam prematuramente."
        ),
        "favorable_conditions": (
            "Temperatura entre 20-32°C (ótima 25-30°C). "
            "Alta umidade e molhamento foliar prolongado. "
            "Plantios tardios (safrinha) são mais afetados. "
            "Híbridos suscetíveis e monocultura."
        ),
        "control_threshold": (
            "Aplicar ao detectar primeiras lesões, especialmente em híbridos suscetíveis. "
            "Preventivo recomendado em áreas com histórico a partir de V8-V10. "
            "Monitorar principalmente folhas do terço inferior."
        ),
        "products": [
            {"name": "Priori Xtra (Azoxistrobina + Ciproconazol)", "dose": "0.3 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Opera (Piraclostrobina + Epoxiconazol)", "dose": "0.5-0.75 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Fox (Trifloxistrobina + Protioconazol)", "dose": "0.4 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Orkestra (Fluxapiroxade + Piraclostrobina)", "dose": "0.3 L/ha", "group": "Carboxamida + Estrobilurina"},
        ],
        "management_tips": (
            "HÍBRIDOS RESISTENTES são a principal ferramenta de manejo. "
            "Rotação de culturas reduz inóculo. "
            "Evitar plantios muito tardios em regiões de risco. "
            "Boa nutrição da planta aumenta tolerância. "
            "Aplicação preventiva é mais eficiente que curativa."
        ),
    },
    {
        "slug": "cercosporiose-milho",
        "name": "Cercosporiose",
        "scientific_name": "Cercospora zeae-maydis",
        "type": "doenca",
        "crop": "milho",
        "keywords": ["cercospora", "cercosporiose", "mancha cinzenta", "gray leaf spot"],
        "symptoms": (
            "Lesões RETANGULARES alongadas, PARALELAS ÀS NERVURAS. "
            "Cor cinza a castanho-acinzentada. "
            "Bordas bem definidas pelas nervuras da folha. "
            "Em ataques severos, folhas ficam totalmente necrosadas. "
            "Começa nas folhas baixeiras e progride para cima."
        ),
        "favorable_conditions": (
            "Alta umidade (>95%) por períodos prolongados. "
            "Temperatura entre 22-30°C. "
            "Noites com orvalho pesado. "
            "Plantio direto sobre restos culturais de milho."
        ),
        "control_threshold": (
            "Aplicar preventivamente em V8-VT em híbridos suscetíveis. "
            "Em híbridos tolerantes, monitorar e aplicar se necessário. "
            "Duas aplicações podem ser necessárias em alta pressão."
        ),
        "products": [
            {"name": "Priori Xtra (Azoxistrobina + Ciproconazol)", "dose": "0.3 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Abacus HC (Piraclostrobina + Epoxiconazol)", "dose": "0.35 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Aproach Prima (Picoxistrobina + Ciproconazol)", "dose": "0.3 L/ha", "group": "Estrobilurina + Triazol"},
        ],
        "management_tips": (
            "Híbridos com resistência genética são fundamentais. "
            "Rotação de culturas com soja ou outra não-gramínea. "
            "Evitar plantio direto sobre resteva de milho infectado. "
            "Adubação equilibrada, especialmente potássio."
        ),
    },
    {
        "slug": "helmintosporiose-milho",
        "name": "Helmintosporiose / Queima de Turcicum",
        "scientific_name": "Exserohilum turcicum",
        "type": "doenca",
        "crop": "milho",
        "keywords": ["helmintosporiose", "turcicum", "queima", "exserohilum", "charuto"],
        "symptoms": (
            "Lesões GRANDES (5-15 cm), formato de CHARUTO ou elípticas. "
            "Cor palha a castanho-acinzentada. "
            "Lesões podem coalescer e queimar toda a folha. "
            "Ataque severo causa secamento prematuro ('queima'). "
            "Reduz drasticamente a área fotossintética."
        ),
        "favorable_conditions": (
            "Temperatura amena (18-27°C, ótima 22°C). "
            "Alta umidade e orvalho noturno. "
            "Mais comum em altitudes elevadas e regiões sul. "
            "Plantios de inverno/safrinha."
        ),
        "control_threshold": (
            "Aplicar ao detectar primeiras lesões, antes da expansão. "
            "Em áreas de risco, aplicação preventiva em V8-V10. "
            "Híbridos suscetíveis: duas aplicações podem ser necessárias."
        ),
        "products": [
            {"name": "Opera (Piraclostrobina + Epoxiconazol)", "dose": "0.5-0.75 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Priori (Azoxistrobina)", "dose": "0.2-0.25 L/ha", "group": "Estrobilurina"},
            {"name": "Nativo (Trifloxistrobina + Tebuconazol)", "dose": "0.5-0.75 L/ha", "group": "Estrobilurina + Triazol"},
        ],
        "management_tips": (
            "Híbridos resistentes são muito eficientes. "
            "Rotação de culturas e eliminação de restos. "
            "Evitar estresse hídrico e nutricional. "
            "Aplicação precoce é mais eficiente."
        ),
    },
    {
        "slug": "ferrugem-polissora",
        "name": "Ferrugem Polissora",
        "scientific_name": "Puccinia polysora",
        "type": "doenca",
        "crop": "milho",
        "keywords": ["ferrugem polissora", "polissora", "puccinia", "ferrugem alaranjada"],
        "symptoms": (
            "Pústulas PEQUENAS, circulares, cor ALARANJADA intensa. "
            "Distribuídas na FACE SUPERIOR das folhas (diferencial). "
            "Alta densidade de pústulas em ataques severos. "
            "Causa secamento rápido das folhas. "
            "Muito agressiva em condições favoráveis."
        ),
        "favorable_conditions": (
            "Temperatura ALTA (>27°C). "
            "Alta umidade e chuvas frequentes. "
            "Mais comum em regiões tropicais e baixas altitudes. "
            "Plantios tardios da safrinha."
        ),
        "control_threshold": (
            "Aplicar ao detectar primeiras pústulas. "
            "Em regiões de risco, preventivo em VT. "
            "Progressão muito rápida - não atrasar aplicação."
        ),
        "products": [
            {"name": "Priori Xtra (Azoxistrobina + Ciproconazol)", "dose": "0.3 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Opera (Piraclostrobina + Epoxiconazol)", "dose": "0.5-0.75 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Fox (Trifloxistrobina + Protioconazol)", "dose": "0.4 L/ha", "group": "Estrobilurina + Triazol"},
        ],
        "management_tips": (
            "Híbridos resistentes são essenciais em regiões de risco. "
            "Monitoramento frequente em plantios tardios. "
            "Estrobilurinas têm boa eficiência. "
            "Evitar plantios muito tardios em regiões quentes."
        ),
    },
    # ============================================================
    # SOJA/MILHO - PRAGAS
    # ============================================================
    {
        "slug": "lagarta-do-cartucho",
        "name": "Lagarta-do-cartucho",
        "scientific_name": "Spodoptera frugiperda",
        "type": "praga",
        "crop": "milho",
        "keywords": ["lagarta cartucho", "spodoptera", "lagarta do milho", "cartucho"],
        "symptoms": (
            "Folhas com RASPAGEM inicial (folhas esbranquiçadas). "
            "PERFURAÇÕES irregulares nas folhas expandidas. "
            "Destruição do CARTUCHO (folhas centrais enroladas). "
            "Presença de FEZES no cartucho e axilas foliares. "
            "Lagarta cinza-escura com linhas longitudinais e Y invertido na cabeça."
        ),
        "favorable_conditions": (
            "Tempo seco e quente acelera ciclo. "
            "Plantios tardios sofrem maior pressão. "
            "Falta de inimigos naturais."
        ),
        "control_threshold": (
            "Nota de dano ≥3 (escala Davis) ou 20% de plantas com folhas raspadas. "
            "Lagartas pequenas (<1.5 cm) são mais fáceis de controlar. "
            "Monitorar 2x por semana em períodos críticos."
        ),
        "products": [
            {"name": "Premio (Clorantraniliprole)", "dose": "0.05-0.1 L/ha", "group": "Diamida"},
            {"name": "Belt (Flubendiamida)", "dose": "0.1 L/ha", "group": "Diamida"},
            {"name": "Lannate (Metomil)", "dose": "0.6-1.0 L/ha", "group": "Carbamato"},
            {"name": "Tracer (Spinosade)", "dose": "0.05-0.1 L/ha", "group": "Espinosina"},
        ],
        "management_tips": (
            "Aplicar nas horas mais frescas (início da manhã ou fim da tarde). "
            "Dirigir jato para o cartucho. "
            "Lagartas grandes são mais difíceis de controlar. "
            "Rotação de mecanismos de ação é importante. "
            "Milho Bt reduz pressão mas requer refúgio."
        ),
    },
    {
        "slug": "percevejo-marrom",
        "name": "Percevejo Marrom",
        "scientific_name": "Euschistus heros",
        "type": "praga",
        "crop": "soja",
        "keywords": ["percevejo marrom", "euschistus", "percevejo", "fede-fede"],
        "symptoms": (
            "Retenção foliar (folhas verdes na colheita). "
            "Vagens chochas ou com grãos menores. "
            "Grãos manchados e enrugados. "
            "Presença de percevejos marrons (15mm) com espinho no pronoto. "
            "Cheiro característico quando perturbados."
        ),
        "favorable_conditions": (
            "Período reprodutivo da soja (R3-R6). "
            "Clima seco que mantém populações altas. "
            "Proximidade com áreas de soja em dessecação."
        ),
        "control_threshold": (
            "2 percevejos por pano de batida (soja grão). "
            "1 percevejo por pano de batida (soja semente). "
            "Monitorar de R3 até R7."
        ),
        "products": [
            {"name": "Engeo Pleno (Tiametoxam + Lambda-cialotrina)", "dose": "0.2-0.25 L/ha", "group": "Neonicotinoide + Piretroide"},
            {"name": "Connect (Imidacloprido + Beta-ciflutrina)", "dose": "0.75-1.0 L/ha", "group": "Neonicotinoide + Piretroide"},
            {"name": "Orthene (Acefato)", "dose": "0.4-0.5 kg/ha", "group": "Organofosforado"},
        ],
        "management_tips": (
            "Monitoramento com pano de batida é essencial. "
            "Bater vigorosamente as plantas sobre o pano. "
            "Aplicar no início da manhã ou fim da tarde. "
            "Adultos são mais difíceis de controlar que ninfas. "
            "Evitar piretroide isolado para não selecionar resistência."
        ),
    },
]


def normalize_text(text: str) -> str:
    """Normaliza texto para busca."""
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def calculate_match_score(query: str, disease: Dict[str, Any]) -> float:
    """Calcula score de match entre query e doença."""
    query_norm = normalize_text(query)
    if not query_norm:
        return 0.0

    # Match exato em keywords
    for keyword in disease.get("keywords", []):
        if normalize_text(keyword) in query_norm or query_norm in normalize_text(keyword):
            return 1.0

    # Match parcial no nome
    name_norm = normalize_text(disease.get("name", ""))
    if name_norm and (name_norm in query_norm or query_norm in name_norm):
        return 0.95

    # Match no nome científico
    sci_name = normalize_text(disease.get("scientific_name", ""))
    if sci_name and (sci_name in query_norm or query_norm in sci_name):
        return 0.9

    # Fuzzy match
    best_score = 0.0
    for keyword in disease.get("keywords", []):
        score = SequenceMatcher(None, query_norm, normalize_text(keyword)).ratio()
        best_score = max(best_score, score)

    name_score = SequenceMatcher(None, query_norm, name_norm).ratio()
    best_score = max(best_score, name_score * 0.9)

    return best_score


def find_disease(query: str, crop: str = None) -> Optional[Dict[str, Any]]:
    """
    Busca doença na base de dados.
    Retorna a doença com maior score de match.
    """
    if not query:
        return None

    candidates = []
    for disease in DISEASES_DATABASE:
        # Filtrar por cultura se especificada
        if crop and disease.get("crop") != crop.lower():
            continue

        score = calculate_match_score(query, disease)
        if score >= 0.5:
            candidates.append((disease, score))

    if not candidates:
        return None

    # Retorna a melhor match
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]


def format_disease_response(disease: Dict[str, Any]) -> Dict[str, Any]:
    """
    Formata resposta da doença para a API/chat.
    Inclui URL da imagem.
    """
    image_url = get_disease_image_url(disease.get("slug", ""))

    return {
        "found": True,
        "source": "local_database",
        "disease": {
            "slug": disease.get("slug"),
            "name": disease.get("name"),
            "scientific_name": disease.get("scientific_name"),
            "type": disease.get("type"),
            "crop": disease.get("crop"),
            "symptoms": disease.get("symptoms"),
            "favorable_conditions": disease.get("favorable_conditions"),
            "control_threshold": disease.get("control_threshold"),
            "products": disease.get("products", []),
            "management_tips": disease.get("management_tips"),
            "image_url": image_url if image_url else None,
        },
    }


def search_disease(query: str, crop: str = None) -> Dict[str, Any]:
    """
    Busca e retorna resposta formatada.
    Se não encontrar, retorna found=False.
    """
    disease = find_disease(query, crop)

    if disease:
        return format_disease_response(disease)

    return {
        "found": False,
        "source": "local_database",
        "disease": None,
        "suggestions": get_similar_diseases(query, crop, limit=3),
    }


def get_similar_diseases(query: str, crop: str = None, limit: int = 3) -> List[str]:
    """Retorna nomes de doenças similares para sugestão."""
    candidates = []
    for disease in DISEASES_DATABASE:
        if crop and disease.get("crop") != crop.lower():
            continue
        score = calculate_match_score(query, disease)
        if score >= 0.3:
            candidates.append((disease.get("name"), score))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in candidates[:limit]]


def get_all_diseases(crop: str = None) -> List[Dict[str, Any]]:
    """Lista todas as doenças, opcionalmente filtradas por cultura."""
    result = []
    for disease in DISEASES_DATABASE:
        if crop and disease.get("crop") != crop.lower():
            continue
        result.append({
            "slug": disease.get("slug"),
            "name": disease.get("name"),
            "type": disease.get("type"),
            "crop": disease.get("crop"),
        })
    return result
