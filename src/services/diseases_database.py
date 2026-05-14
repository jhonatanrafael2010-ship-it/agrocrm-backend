"""
================================================================
Base de Dados de Pragas e Doenças
================================================================

Base local com informações detalhadas e assertivas sobre
pragas e doenças das principais culturas brasileiras:
- Soja, Milho, Algodão
- Feijão, Trigo, Café
- Cana-de-açúcar, Sorgo

Fontes consultadas (Embrapa, Fundação MT, Agrolink):
- Circulares Técnicas e Manuais de Identificação
- Pesquisas regionais do Cerrado (MT, GO, MS, PR)
- Alertas fitossanitários e boletins técnicos

Vantagens sobre IA:
- Respostas consistentes e validadas por especialistas
- Inclui fotos dos sintomas (R2)
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
    {
        "slug": "percevejo-verde-pequeno",
        "name": "Percevejo Verde Pequeno",
        "scientific_name": "Piezodorus guildinii",
        "type": "praga",
        "crop": "soja",
        "keywords": ["percevejo verde", "piezodorus", "percevejo pequeno"],
        "symptoms": (
            "Mais AGRESSIVO que o percevejo marrom. "
            "Retenção foliar intensa (haste verde na colheita). "
            "Vagens chochas e grãos menores. "
            "Grãos manchados e enrugados, perda de qualidade. "
            "Percevejos verdes (~10mm) com espinho lateral."
        ),
        "favorable_conditions": (
            "Período reprodutivo da soja (R3-R6). "
            "Populações aumentam no final do ciclo. "
            "Áreas próximas a soja em dessecação."
        ),
        "control_threshold": (
            "2 percevejos por pano de batida (soja grão). "
            "1 percevejo por pano de batida (soja semente). "
            "MAIS EXIGENTE que percevejo marrom."
        ),
        "products": [
            {"name": "Engeo Pleno (Tiametoxam + Lambda-cialotrina)", "dose": "0.25 L/ha", "group": "Neonicotinoide + Piretroide"},
            {"name": "Connect (Imidacloprido + Beta-ciflutrina)", "dose": "1.0 L/ha", "group": "Neonicotinoide + Piretroide"},
            {"name": "Orthene (Acefato)", "dose": "0.5 kg/ha", "group": "Organofosforado"},
        ],
        "management_tips": (
            "Mais difícil de controlar que o percevejo marrom. "
            "Monitoramento frequente é essencial. "
            "Aplicações no início da manhã ou fim da tarde. "
            "Rotacionar grupos químicos."
        ),
    },
    {
        "slug": "lagarta-falsa-medideira",
        "name": "Lagarta Falsa-medideira",
        "scientific_name": "Chrysodeixis includens",
        "type": "praga",
        "crop": "soja",
        "keywords": ["falsa medideira", "chrysodeixis", "medideira", "lagarta verde"],
        "symptoms": (
            "Desfolha com perfurações IRREGULARES nas folhas. "
            "Lagarta verde-clara que se locomove 'MEDINDO PALMOS'. "
            "Folhas rendilhadas, ficam apenas nervuras. "
            "Fica na parte BAIXEIRA da planta (difícil visualização). "
            "Ataca vagens em infestações severas."
        ),
        "favorable_conditions": (
            "Clima quente e seco. "
            "Uso excessivo de inseticidas não seletivos. "
            "Ausência de inimigos naturais."
        ),
        "control_threshold": (
            "30% de desfolha no vegetativo. "
            "15% de desfolha no reprodutivo. "
            "40 lagartas grandes por pano de batida."
        ),
        "products": [
            {"name": "Premio (Clorantraniliprole)", "dose": "0.05-0.1 L/ha", "group": "Diamida"},
            {"name": "Belt (Flubendiamida)", "dose": "0.1 L/ha", "group": "Diamida"},
            {"name": "Intrepid (Metoxifenozida)", "dose": "0.3 L/ha", "group": "Diacilhidrazina"},
        ],
        "management_tips": (
            "DIAMIDAS são os mais eficientes. "
            "Aplicar com bico cônico para atingir parte baixa. "
            "Monitorar terço inferior da planta. "
            "Preservar inimigos naturais."
        ),
    },
    {
        "slug": "helicoverpa-armigera",
        "name": "Helicoverpa armigera",
        "scientific_name": "Helicoverpa armigera",
        "type": "praga",
        "crop": "soja",
        "keywords": ["helicoverpa", "lagarta da espiga", "lagarta das vagens"],
        "symptoms": (
            "Ataca VAGENS e estruturas reprodutivas. "
            "Perfurações em vagens, flores e ponteiros. "
            "Lagarta de coloração variável (verde a marrom). "
            "Pode consumir grãos em formação. "
            "POLÍFAGA - ataca soja, milho, algodão, tomate, feijão."
        ),
        "favorable_conditions": (
            "Temperatura alta. "
            "Períodos secos prolongados. "
            "Grande mobilidade - migra longas distâncias."
        ),
        "control_threshold": (
            "2 lagartas pequenas (<1.5cm) por metro. "
            "Monitorar vagens em R3-R6."
        ),
        "products": [
            {"name": "Premio (Clorantraniliprole)", "dose": "0.1 L/ha", "group": "Diamida"},
            {"name": "Pirate (Clorfenapir)", "dose": "0.75-1.0 L/ha", "group": "Análogo de pirazol"},
            {"name": "Avatar (Indoxacarbe)", "dose": "0.25-0.3 L/ha", "group": "Oxadiazina"},
        ],
        "management_tips": (
            "Monitoramento intensivo é crucial. "
            "Controle biológico com Trichogramma. "
            "Rotação de mecanismos de ação. "
            "Evitar piretróides isolados."
        ),
        "regional_notes": {
            "MT": "Alta pressão em plantios de algodão e soja.",
            "GO": "Comum em safrinha de milho e soja.",
        },
    },
    {
        "slug": "oidio-soja",
        "name": "Oídio",
        "scientific_name": "Microsphaera diffusa",
        "type": "doenca",
        "crop": "soja",
        "keywords": ["oidio", "oídio", "po branco", "pó branco", "microsphaera"],
        "symptoms": (
            "PÓ BRANCO-ACINZENTADO na superfície das folhas. "
            "Pode cobrir folhas, hastes, pecíolos e vagens. "
            "Folhas ficam com aspecto empoeirado. "
            "Em ataques severos, causa desfolha."
        ),
        "favorable_conditions": (
            "Clima SECO com temperaturas amenas (18-24°C). "
            "Baixa umidade relativa. "
            "Semeaduras tardias e safrinha. "
            "Cultivares suscetíveis."
        ),
        "control_threshold": (
            "Aplicar no início dos sintomas. "
            "Cultivares resistentes dispensam controle."
        ),
        "products": [
            {"name": "Nativo (Trifloxistrobina + Tebuconazol)", "dose": "0.5 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Enxofre", "dose": "2-3 kg/ha", "group": "Inorgânico"},
            {"name": "Score (Difenoconazol)", "dose": "0.2 L/ha", "group": "Triazol"},
        ],
        "management_tips": (
            "Cultivares resistentes são a melhor opção. "
            "Evitar semeaduras muito tardias. "
            "Enxofre é eficiente e barato."
        ),
    },
    {
        "slug": "nematoide-galhas",
        "name": "Nematoide das Galhas",
        "scientific_name": "Meloidogyne spp.",
        "type": "praga",
        "crop": "soja",
        "keywords": ["nematoide galhas", "meloidogyne", "galha", "nematoides"],
        "symptoms": (
            "GALHAS (engrossamentos) nas raízes. "
            "Raízes deformadas e com nódulos. "
            "Amarelecimento das folhas (clorose). "
            "Plantas murcham nas horas quentes. "
            "Redução do crescimento em reboleiras."
        ),
        "favorable_conditions": (
            "Solos arenosos. "
            "Monocultura de soja. "
            "Temperaturas altas."
        ),
        "control_threshold": (
            "Análise nematológica do solo antes do plantio. "
            "Mais de 300 juvenis por 100cm³ de solo é alto risco."
        ),
        "products": [
            {"name": "Tratamento de sementes com Avicta", "dose": "Conforme bula", "group": "Abamectina"},
            {"name": "Votivo (Bacillus firmus)", "dose": "Conforme bula", "group": "Biológico"},
        ],
        "management_tips": (
            "ROTAÇÃO com gramíneas (milho, sorgo). "
            "Cultivares resistentes são essenciais. "
            "Crotalária como cultura de cobertura reduz população. "
            "Evitar compactação do solo."
        ),
        "regional_notes": {
            "MT": "Comum em solos arenosos do norte.",
            "PR": "Áreas de monocultura apresentam altas populações.",
        },
    },
    {
        "slug": "nematoide-lesoes",
        "name": "Nematoide das Lesões",
        "scientific_name": "Pratylenchus brachyurus",
        "type": "praga",
        "crop": "soja",
        "keywords": ["pratylenchus", "nematoide lesoes", "lesões raiz"],
        "symptoms": (
            "Raízes com LESÕES NECRÓTICAS escuras. "
            "Raízes escurecidas e pouco desenvolvidas. "
            "Sistema radicular empobrecido. "
            "Sintomas no florescimento: amarelecimento, murcha. "
            "Plantas em reboleiras com desenvolvimento desigual."
        ),
        "favorable_conditions": (
            "Solos de textura média. "
            "Sucessão soja-milho sem rotação. "
            "Compactação do solo."
        ),
        "control_threshold": (
            "Análise de solo e raízes. "
            "Mais de 500 nematoides por 10g de raiz é crítico."
        ),
        "products": [
            {"name": "Avicta Completo", "dose": "Conforme bula", "group": "Abamectina + fungicida"},
            {"name": "Clariva (Pasteuria nishizawae)", "dose": "Conforme bula", "group": "Biológico"},
        ],
        "management_tips": (
            "Rotação com CROTALÁRIA é muito eficiente. "
            "Milheto também ajuda a reduzir. "
            "Evitar cultivares muito suscetíveis. "
            "Descompactação do solo."
        ),
    },
    {
        "slug": "dfc-morte-subita",
        "name": "Síndrome da Morte Súbita (DFC)",
        "scientific_name": "Fusarium solani f.sp. glycines",
        "type": "doenca",
        "crop": "soja",
        "keywords": ["morte subita", "dfc", "fusarium soja", "sms"],
        "symptoms": (
            "Clorose INTERNERVAL nas folhas (amarelo entre nervuras). "
            "Nervuras permanecem verdes. "
            "Necrose internerval castanha. "
            "Folíolos caem, PECÍOLOS ficam presos à haste. "
            "Raízes com podridão e coloração AVERMELHADA-PÚRPURA."
        ),
        "favorable_conditions": (
            "Solos FRIOS, ÚMIDOS e COMPACTADOS. "
            "Semeaduras muito precoces. "
            "Alta umidade no início do ciclo. "
            "Áreas com histórico da doença."
        ),
        "control_threshold": (
            "Doença de difícil controle químico. "
            "Foco em manejo preventivo."
        ),
        "products": [
            {"name": "Tratamento de sementes (Fludioxonil + Metalaxil)", "dose": "Conforme bula", "group": "Fungicida TS"},
        ],
        "management_tips": (
            "Cultivares tolerantes são a principal ferramenta. "
            "Evitar semeadura em solo frio e encharcado. "
            "Descompactação do solo. "
            "Rotação de culturas. "
            "Drenagem em áreas problemáticas."
        ),
        "regional_notes": {
            "PR": "Mais comum em áreas frias e úmidas.",
            "MS": "Áreas com compactação são mais afetadas.",
        },
    },
    # ============================================================
    # MILHO - DOENÇAS ADICIONAIS
    # ============================================================
    {
        "slug": "enfezamento-milho",
        "name": "Enfezamentos do Milho",
        "scientific_name": "Spiroplasma kunkelii / Phytoplasma",
        "type": "doenca",
        "crop": "milho",
        "keywords": ["enfezamento", "cigarrinha", "dalbulus", "vermelhao", "enfezamento palido", "enfezamento vermelho"],
        "symptoms": (
            "ENFEZAMENTO PÁLIDO: folhas amareladas, estrias cloróticas. "
            "ENFEZAMENTO VERMELHO: avermelhamento das folhas, bordas e pontas. "
            "Plantas com entrenós ENCURTADOS (aspecto de roseta). "
            "Espigas pequenas, múltiplas e mal granadas. "
            "Proliferação de espigas. "
            "Perdas podem chegar a 70%."
        ),
        "favorable_conditions": (
            "Presença da CIGARRINHA Dalbulus maidis (vetor). "
            "Milho tiguera (voluntário) como fonte de inóculo. "
            "Plantios tardios de safrinha. "
            "Áreas com milho o ano todo."
        ),
        "control_threshold": (
            "3-5 cigarrinhas por planta na fase inicial. "
            "Monitorar primeiras semanas após emergência."
        ),
        "products": [
            {"name": "Cruiser (Tiametoxam TS)", "dose": "0.2 L/100kg sementes", "group": "Neonicotinoide"},
            {"name": "Engeo Pleno (Tiametoxam + Lambda)", "dose": "0.25 L/ha foliar", "group": "Neonicotinoide + Piretroide"},
        ],
        "management_tips": (
            "ELIMINAR milho tiguera antes do plantio. "
            "Tratamento de sementes é fundamental. "
            "Híbridos tolerantes reduzem perdas. "
            "Evitar plantios muito tardios na safrinha. "
            "Não plantar milho próximo a lavouras adultas com enfezamento."
        ),
        "regional_notes": {
            "MT": "Problema grave na safrinha. Eliminar tiguera é crítico.",
            "GO": "Plantios tardios sofrem mais. Híbridos tolerantes são essenciais.",
            "MS": "Monitoramento da cigarrinha desde V1.",
            "PR": "Menor pressão que no Cerrado, mas atenção na safrinha.",
        },
    },
    {
        "slug": "podridao-colmo-milho",
        "name": "Podridão do Colmo",
        "scientific_name": "Fusarium spp. / Stenocarpella spp.",
        "type": "doenca",
        "crop": "milho",
        "keywords": ["podridao colmo", "podridão colmo", "fusarium milho", "diplodia", "stenocarpella"],
        "symptoms": (
            "Plantas com TOMBAMENTO ou acamamento. "
            "Lesões escuras nos entrenós basais. "
            "Colmo fica OCA (medula desintegrada). "
            "Pontos pretos (picnídios) na superfície do colmo. "
            "Morte prematura das plantas. "
            "Espigas caídas no solo."
        ),
        "favorable_conditions": (
            "Temperatura 28-30°C. "
            "Alta umidade após florescimento. "
            "Estresse hídrico seguido de chuvas. "
            "Alta população de plantas. "
            "Desequilíbrio nutricional (excesso de N, falta de K)."
        ),
        "control_threshold": (
            "Monitorar após florescimento. "
            "Antecipar colheita se houver tombamento."
        ),
        "products": [
            {"name": "Tratamento de sementes com fungicidas", "dose": "Conforme bula", "group": "Fungicida TS"},
        ],
        "management_tips": (
            "HÍBRIDOS resistentes são a principal ferramenta. "
            "Rotação de culturas. "
            "Eliminação de restos culturais. "
            "Evitar estresse hídrico e nutricional. "
            "Não atrasar colheita."
        ),
    },
    {
        "slug": "helmintosporiose-milho",
        "name": "Helmintosporiose (Mancha de Turcicum)",
        "scientific_name": "Exserohilum turcicum",
        "type": "doenca",
        "crop": "milho",
        "keywords": ["helmintosporiose", "turcicum", "exserohilum", "mancha charuto"],
        "symptoms": (
            "Lesões ALONGADAS em formato de CHARUTO. "
            "Manchas necróticas de cor palha a marrom. "
            "Lesões de 2,5 a 15 cm de comprimento. "
            "Começam nas folhas baixeiras. "
            "Podem coalescer e causar seca prematura."
        ),
        "favorable_conditions": (
            "Temperaturas amenas (18-27°C). "
            "Alta umidade e chuvas frequentes. "
            "Orvalho prolongado. "
            "Híbridos suscetíveis."
        ),
        "control_threshold": (
            "Aplicar ao detectar primeiras lesões. "
            "Híbridos suscetíveis: preventivo em V8-VT."
        ),
        "products": [
            {"name": "Priori Xtra (Azoxistrobina + Ciproconazol)", "dose": "0.3 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Opera (Piraclostrobina + Epoxiconazol)", "dose": "0.5-0.75 L/ha", "group": "Estrobilurina + Triazol"},
        ],
        "management_tips": (
            "Híbridos resistentes são muito eficientes. "
            "Rotação de culturas. "
            "Aplicação preventiva em áreas de risco."
        ),
    },
    {
        "slug": "mancha-branca-milho",
        "name": "Mancha Branca (Phaeosphaeria)",
        "scientific_name": "Phaeosphaeria maydis / Pantoea ananatis",
        "type": "doenca",
        "crop": "milho",
        "keywords": ["mancha branca", "phaeosphaeria", "mancha palha"],
        "symptoms": (
            "Lesões circulares a elípticas de cor PALHA/BRANCA. "
            "Manchas de 0,5 a 2 cm. "
            "Lesões com aspecto de palha seca. "
            "Podem coalescer formando grandes áreas necróticas. "
            "Afeta principalmente folhas, mas pode atingir bainhas."
        ),
        "favorable_conditions": (
            "Alta umidade e temperaturas amenas (20-25°C). "
            "Noites frias seguidas de dias quentes. "
            "Altitude elevada. "
            "Híbridos suscetíveis."
        ),
        "control_threshold": (
            "Aplicar no início dos sintomas. "
            "Áreas com histórico: preventivo em VT."
        ),
        "products": [
            {"name": "Priori Xtra (Azoxistrobina + Ciproconazol)", "dose": "0.3 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Fox (Trifloxistrobina + Protioconazol)", "dose": "0.4 L/ha", "group": "Estrobilurina + Triazol"},
        ],
        "management_tips": (
            "Híbridos resistentes são essenciais. "
            "Aplicação no momento correto. "
            "Rotação de culturas ajuda."
        ),
    },
    # ============================================================
    # ALGODÃO - DOENÇAS E PRAGAS ADICIONAIS
    # ============================================================
    {
        "slug": "ramularia-algodao",
        "name": "Ramulária (Mancha de Ramulária)",
        "scientific_name": "Ramulariopsis gossypii",
        "type": "doenca",
        "crop": "algodao",
        "keywords": ["ramularia", "ramulária", "mancha ramularia", "ramulariopsis"],
        "symptoms": (
            "Manchas ANGULARES na face inferior das folhas. "
            "Esporulação BRANCA característica (aspecto de talco). "
            "Manchas delimitadas pelas nervuras. "
            "Face superior: manchas verde-azuladas evoluindo para necrose. "
            "Desfolha prematura em ataques severos. "
            "Afeta produtividade e qualidade da fibra."
        ),
        "favorable_conditions": (
            "Alta umidade (>80%). "
            "Noites frias seguidas de dias quentes. "
            "Orvalho prolongado. "
            "Cultivares suscetíveis."
        ),
        "control_threshold": (
            "Iniciar aplicação PREVENTIVA 30 dias após emergência. "
            "Ou no estágio B1 (primeiro botão floral). "
            "Ou ao detectar condições favoráveis."
        ),
        "products": [
            {"name": "Orkestra (Fluxapiroxade + Piraclostrobina)", "dose": "0.3 L/ha", "group": "Carboxamida + Estrobilurina"},
            {"name": "Clorotalonil", "dose": "1.5-2.0 L/ha", "group": "Multissítio"},
            {"name": "Mancozebe", "dose": "2.0-2.5 kg/ha", "group": "Multissítio"},
            {"name": "Fox (Trifloxistrobina + Protioconazol)", "dose": "0.4 L/ha", "group": "Estrobilurina + Triazol"},
        ],
        "management_tips": (
            "MULTISSÍTIOS (clorotalonil, mancozebe) são essenciais na mistura. "
            "Rotacionar grupos químicos para evitar resistência. "
            "Intervalos de 10-14 dias em alta pressão. "
            "Cultivares menos suscetíveis quando disponíveis."
        ),
        "regional_notes": {
            "MT": "Principal problema fitossanitário do algodão. Controle intensivo necessário.",
        },
    },
    {
        "slug": "bicudo-algodoeiro",
        "name": "Bicudo do Algodoeiro",
        "scientific_name": "Anthonomus grandis",
        "type": "praga",
        "crop": "algodao",
        "keywords": ["bicudo", "anthonomus", "bicudo algodao"],
        "symptoms": (
            "Botões florais com ORIFÍCIOS de alimentação e postura. "
            "Botões com formato abaulado (não abrem). "
            "QUEDA de botões, flores e maçãs. "
            "Maçãs com orifícios e podridão. "
            "Perdas podem ser totais."
        ),
        "favorable_conditions": (
            "Presença de refúgios (soqueiras, restos culturais). "
            "Áreas sem vazio sanitário. "
            "Falta de destruição de soqueira."
        ),
        "control_threshold": (
            "5% de botões atacados. "
            "Monitorar desde primeiros botões."
        ),
        "products": [
            {"name": "Engeo Pleno (Tiametoxam + Lambda-cialotrina)", "dose": "0.2 L/ha", "group": "Neonicotinoide + Piretroide"},
            {"name": "Malathion", "dose": "1.5-2.0 L/ha", "group": "Organofosforado"},
            {"name": "Fipronil", "dose": "Conforme bula", "group": "Fenil pirazol"},
        ],
        "management_tips": (
            "DESTRUIÇÃO da soqueira é obrigatória por lei. "
            "Respeitar o vazio sanitário. "
            "Armadilhas com feromônio para monitoramento. "
            "Aplicações frequentes podem ser necessárias. "
            "Controle em bordadura é importante."
        ),
        "regional_notes": {
            "MT": "Vazio sanitário é lei estadual. Destruição de soqueira até data definida.",
            "GO": "Monitoramento com armadilhas desde emergência.",
        },
    },
    {
        "slug": "pulgao-algodao",
        "name": "Pulgão do Algodoeiro",
        "scientific_name": "Aphis gossypii",
        "type": "praga",
        "crop": "algodao",
        "keywords": ["pulgao", "pulgão", "aphis", "pulgao algodao"],
        "symptoms": (
            "Folhas ENCARQUILHADAS (enroladas para baixo). "
            "Presença de FUMAGINA (fungo preto sobre melado). "
            "Mela nas folhas e plantas pegajosas. "
            "Colônias na face inferior das folhas. "
            "Transmissor de viroses."
        ),
        "favorable_conditions": (
            "Tempo seco e quente. "
            "Desequilíbrio por uso de piretróides. "
            "Ausência de inimigos naturais."
        ),
        "control_threshold": (
            "50% de plantas com colônias em expansão. "
            "Atenção à presença de fumagina."
        ),
        "products": [
            {"name": "Evidence (Imidacloprido)", "dose": "0.2 kg/ha", "group": "Neonicotinoide"},
            {"name": "Actara (Tiametoxam)", "dose": "0.1-0.15 kg/ha", "group": "Neonicotinoide"},
            {"name": "Movento (Espiromesifeno)", "dose": "0.4-0.5 L/ha", "group": "Cetoenol"},
        ],
        "management_tips": (
            "Preservar inimigos naturais (joaninhas, crisopídeos). "
            "Evitar piretróides que causam ressurgência. "
            "Monitorar colônias em expansão."
        ),
    },
    # ============================================================
    # FEIJÃO - DOENÇAS E PRAGAS
    # ============================================================
    {
        "slug": "antracnose-feijao",
        "name": "Antracnose do Feijão",
        "scientific_name": "Colletotrichum lindemuthianum",
        "type": "doenca",
        "crop": "feijao",
        "keywords": ["antracnose feijao", "antracnose feijão", "antracnose do feijao", "antracnose do feijão", "colletotrichum lindemuthianum"],
        "symptoms": (
            "Nervuras com manchas alongadas AVERMELHADAS a PÚRPURA. "
            "Vagens com lesões DEPRIMIDAS circulares. "
            "Lesões com bordas escuras e centro claro. "
            "Em condições úmidas: massa rosada de esporos. "
            "Pecíolos e hastes também são afetados. "
            "Sementes manchadas."
        ),
        "favorable_conditions": (
            "Temperaturas moderadas (13-26°C). "
            "Alta umidade e chuvas frequentes. "
            "Sementes infectadas. "
            "Restos culturais contaminados."
        ),
        "control_threshold": (
            "Preventivo em áreas com histórico. "
            "Aplicar ao detectar primeiros sintomas."
        ),
        "products": [
            {"name": "Carbendazim", "dose": "0.5 L/ha", "group": "Benzimidazol"},
            {"name": "Opera (Piraclostrobina + Epoxiconazol)", "dose": "0.5 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Tratamento de sementes", "dose": "Conforme bula", "group": "Fungicida TS"},
        ],
        "management_tips": (
            "Sementes de boa qualidade são essenciais. "
            "Cultivares resistentes. "
            "Rotação de culturas (2-3 anos). "
            "Eliminação de restos culturais."
        ),
    },
    {
        "slug": "ferrugem-feijao",
        "name": "Ferrugem do Feijão",
        "scientific_name": "Uromyces appendiculatus",
        "type": "doenca",
        "crop": "feijao",
        "keywords": ["ferrugem feijao", "uromyces", "ferrugem feijão"],
        "symptoms": (
            "Manchas pequenas ESBRANQUIÇADAS nas folhas (início). "
            "Pústulas MARROM-AVERMELHADAS na face inferior. "
            "Pústulas liberam esporos de cor ferrugem. "
            "Desfolha prematura em ataques severos. "
            "Afeta folhas, vagens e hastes."
        ),
        "favorable_conditions": (
            "Temperatura entre 17-27°C (ótima 21°C). "
            "Alta umidade e molhamento foliar. "
            "Noites frias e dias quentes."
        ),
        "control_threshold": (
            "Aplicar ao detectar primeiras pústulas. "
            "Preventivo em épocas favoráveis."
        ),
        "products": [
            {"name": "Priori Xtra (Azoxistrobina + Ciproconazol)", "dose": "0.3 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Nativo (Trifloxistrobina + Tebuconazol)", "dose": "0.5 L/ha", "group": "Estrobilurina + Triazol"},
        ],
        "management_tips": (
            "Cultivares resistentes são muito eficientes. "
            "Rotação de culturas. "
            "Eliminação de restos culturais."
        ),
    },
    {
        "slug": "mancha-angular-feijao",
        "name": "Mancha Angular",
        "scientific_name": "Pseudocercospora griseola",
        "type": "doenca",
        "crop": "feijao",
        "keywords": ["mancha angular", "pseudocercospora", "angular feijao"],
        "symptoms": (
            "Lesões ANGULARES delimitadas pelas nervuras. "
            "Manchas de cor cinza a marrom-escuro. "
            "Halo AMARELO ao redor das lesões. "
            "Face inferior: esporulação escura em condições úmidas. "
            "Afeta folhas, vagens e sementes."
        ),
        "favorable_conditions": (
            "Temperatura 16-28°C (ótima 24°C). "
            "Alta umidade. "
            "Presente em praticamente todas as regiões produtoras."
        ),
        "control_threshold": (
            "Aplicar preventivamente em áreas com histórico. "
            "Ao detectar primeiros sintomas."
        ),
        "products": [
            {"name": "Opera (Piraclostrobina + Epoxiconazol)", "dose": "0.5 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Priori Xtra (Azoxistrobina + Ciproconazol)", "dose": "0.3 L/ha", "group": "Estrobilurina + Triazol"},
        ],
        "management_tips": (
            "Rotação de culturas é fundamental. "
            "Sementes sadias. "
            "Cultivares resistentes."
        ),
    },
    {
        "slug": "mosaico-dourado-feijao",
        "name": "Mosaico Dourado",
        "scientific_name": "Bean golden mosaic virus (BGMV)",
        "type": "doenca",
        "crop": "feijao",
        "keywords": ["mosaico dourado", "bgmv", "virose feijao", "mosca branca feijao"],
        "symptoms": (
            "MOSAICO amarelo-dourado intenso nas folhas. "
            "Folhas com manchas verde-escuras e amarelo-intenso. "
            "Enrolamento e deformação das folhas. "
            "Nanismo das plantas. "
            "Vagens malformadas e pequenas."
        ),
        "favorable_conditions": (
            "Alta população de MOSCA-BRANCA (vetor). "
            "Plantios próximos a fontes de inóculo. "
            "Épocas secas favorecem o vetor."
        ),
        "control_threshold": (
            "Controle preventivo da mosca-branca. "
            "Erradicar plantas doentes no início."
        ),
        "products": [
            {"name": "Imidacloprido (para vetor)", "dose": "Conforme bula", "group": "Neonicotinoide"},
            {"name": "Tiametoxam (para vetor)", "dose": "Conforme bula", "group": "Neonicotinoide"},
        ],
        "management_tips": (
            "Controlar a MOSCA-BRANCA é essencial. "
            "Cultivares resistentes são a melhor opção. "
            "Eliminar plantas hospedeiras do vírus. "
            "Evitar plantios escalonados na mesma área."
        ),
    },
    # ============================================================
    # TRIGO - DOENÇAS
    # ============================================================
    {
        "slug": "brusone-trigo",
        "name": "Brusone do Trigo",
        "scientific_name": "Pyricularia oryzae Triticum",
        "type": "doenca",
        "crop": "trigo",
        "keywords": ["brusone", "brusone trigo", "pyricularia trigo"],
        "symptoms": (
            "DESCOLORAÇÃO das espigas (esbranquiçadas). "
            "Espiga fica branca da infecção para cima. "
            "Grãos CHOCHOS e enrugados. "
            "Lesões nas folhas: elípticas com centro cinza. "
            "Lesões no nó da ráquis (ponto de estrangulamento)."
        ),
        "favorable_conditions": (
            "Temperatura >25°C. "
            "Alta umidade e chuvas durante espigamento. "
            "Mais de 10 horas de molhamento foliar. "
            "Mais problemática no CERRADO."
        ),
        "control_threshold": (
            "Aplicação preventiva no emborrachamento/espigamento. "
            "Difícil controle após infecção."
        ),
        "products": [
            {"name": "Stinger (Mancozebe)", "dose": "2.0-2.5 kg/ha", "group": "Multissítio"},
            {"name": "Nativo (Trifloxistrobina + Tebuconazol)", "dose": "0.75 L/ha", "group": "Estrobilurina + Triazol"},
        ],
        "management_tips": (
            "CULTIVARES resistentes são essenciais (principal ferramenta). "
            "Evitar semeaduras tardias no Cerrado. "
            "Época de semeadura que evite chuvas no espigamento. "
            "Multissítios ajudam no controle."
        ),
        "regional_notes": {
            "GO": "Principal problema do trigo no Cerrado.",
            "MS": "Atenção em áreas irrigadas.",
        },
    },
    {
        "slug": "giberela-trigo",
        "name": "Giberela",
        "scientific_name": "Fusarium graminearum",
        "type": "doenca",
        "crop": "trigo",
        "keywords": ["giberela", "fusarium trigo", "espiga branca"],
        "symptoms": (
            "Espiguetas DESPIGMENTADAS (cor de palha). "
            "Contraste com espiguetas verdes saudáveis. "
            "Massa rosada de esporos em condições úmidas. "
            "Grãos pequenos, enrugados e de cor rosada. "
            "Pode produzir MICOTOXINAS (DON, zearalenona)."
        ),
        "favorable_conditions": (
            "Chuvas durante FLORESCIMENTO. "
            "Temperatura 20-25°C. "
            "Alta umidade (>90%). "
            "Restos culturais de milho na área."
        ),
        "control_threshold": (
            "Aplicação no florescimento (50% das espigas floridas). "
            "Segunda aplicação se chuvas continuarem."
        ),
        "products": [
            {"name": "Caramba (Metconazol)", "dose": "1.0-1.5 L/ha", "group": "Triazol"},
            {"name": "Proline (Protioconazol)", "dose": "0.5 L/ha", "group": "Triazol"},
            {"name": "Piraclostrobina + Tiofanato-metílico", "dose": "Conforme bula", "group": "Estrobilurina + Benzimidazol"},
        ],
        "management_tips": (
            "Aplicação NO MOMENTO CORRETO é crucial (florescimento). "
            "Cultivares resistentes reduzem risco. "
            "Rotação de culturas (evitar milho anterior). "
            "Atenção às micotoxinas - afetam comercialização."
        ),
        "regional_notes": {
            "PR": "Principal doença do trigo no Sul.",
        },
    },
    {
        "slug": "mancha-amarela-trigo",
        "name": "Mancha Amarela",
        "scientific_name": "Drechslera tritici-repentis",
        "type": "doenca",
        "crop": "trigo",
        "keywords": ["mancha amarela", "drechslera", "mancha amarela trigo"],
        "symptoms": (
            "Manchas com HALO AMARELO característico. "
            "Centro necrótico marrom-claro. "
            "Manchas ovais a elípticas. "
            "Podem coalescer causando seca de folhas. "
            "Afeta principalmente folhas."
        ),
        "favorable_conditions": (
            "Alta umidade. "
            "Temperatura 15-25°C. "
            "Restos culturais infectados. "
            "Monocultura de trigo."
        ),
        "control_threshold": (
            "Aplicar ao detectar primeiras manchas. "
            "Preventivo em áreas com histórico."
        ),
        "products": [
            {"name": "Opera (Piraclostrobina + Epoxiconazol)", "dose": "0.5-0.75 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Priori Xtra (Azoxistrobina + Ciproconazol)", "dose": "0.3 L/ha", "group": "Estrobilurina + Triazol"},
        ],
        "management_tips": (
            "Rotação de culturas. "
            "Eliminação de restos. "
            "Cultivares resistentes."
        ),
    },
    {
        "slug": "ferrugem-folha-trigo",
        "name": "Ferrugem da Folha",
        "scientific_name": "Puccinia triticina",
        "type": "doenca",
        "crop": "trigo",
        "keywords": ["ferrugem trigo", "puccinia triticina", "ferrugem folha"],
        "symptoms": (
            "Pústulas LARANJA-AVERMELHADAS na face superior das folhas. "
            "Pústulas pequenas (1-2mm), ovaladas. "
            "Distribuídas aleatoriamente nas folhas. "
            "Podem coalescer em ataques severos. "
            "Causa seca prematura."
        ),
        "favorable_conditions": (
            "Temperatura 15-22°C. "
            "Alta umidade e orvalho. "
            "Cultivares suscetíveis."
        ),
        "control_threshold": (
            "Aplicar ao detectar primeiras pústulas. "
            "Preventivo em cultivares suscetíveis."
        ),
        "products": [
            {"name": "Priori Xtra (Azoxistrobina + Ciproconazol)", "dose": "0.3 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Nativo (Trifloxistrobina + Tebuconazol)", "dose": "0.5-0.75 L/ha", "group": "Estrobilurina + Triazol"},
        ],
        "management_tips": (
            "Cultivares resistentes são a principal ferramenta. "
            "Monitoramento frequente. "
            "Estrobilurinas + Triazóis são eficientes."
        ),
    },
    # ============================================================
    # CAFÉ - DOENÇAS E PRAGAS
    # ============================================================
    {
        "slug": "ferrugem-cafe",
        "name": "Ferrugem do Café",
        "scientific_name": "Hemileia vastatrix",
        "type": "doenca",
        "crop": "cafe",
        "keywords": ["ferrugem cafe", "ferrugem café", "ferrugem do cafe", "ferrugem do café", "hemileia", "hemileia vastatrix"],
        "symptoms": (
            "Manchas AMARELAS na face superior das folhas. "
            "PÓ ALARANJADO (esporos) na face inferior. "
            "Manchas circulares de 1-3 cm. "
            "Desfolha intensa em ataques severos. "
            "Reduz produção no ano seguinte."
        ),
        "favorable_conditions": (
            "Temperatura 21-25°C. "
            "Alta umidade e chuvas frequentes. "
            "Molhamento foliar prolongado. "
            "Lavouras adensadas. "
            "Alta carga pendente (frutos)."
        ),
        "control_threshold": (
            "Iniciar controle quando detectar 5% de incidência. "
            "Preventivo a partir de dezembro em safras altas."
        ),
        "products": [
            {"name": "Opera (Piraclostrobina + Epoxiconazol)", "dose": "0.5 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Oxicloreto de cobre", "dose": "2.0-3.0 kg/ha", "group": "Cúprico"},
            {"name": "Nativo (Trifloxistrobina + Tebuconazol)", "dose": "0.75 L/ha", "group": "Estrobilurina + Triazol"},
        ],
        "management_tips": (
            "Cultivares resistentes (gene SH) são excelentes. "
            "Cúpricos em preventivo. "
            "Sistêmicos em curativo. "
            "Nutrição equilibrada reduz suscetibilidade."
        ),
    },
    {
        "slug": "cercosporiose-cafe",
        "name": "Cercosporiose (Olho Pardo)",
        "scientific_name": "Cercospora coffeicola",
        "type": "doenca",
        "crop": "cafe",
        "keywords": ["cercosporiose", "cercospora", "olho pardo", "mancha olho pardo"],
        "symptoms": (
            "Manchas circulares com CENTRO CLARO e borda escura. "
            "Aspecto de OLHO PARDO característico. "
            "Afeta folhas, frutos e ramos. "
            "Em frutos: manchas deprimidas, amadurecimento desuniforme. "
            "Desfolha em plantas debilitadas."
        ),
        "favorable_conditions": (
            "Plantas em ESTRESSE (déficit hídrico, nutricional). "
            "Alta exposição solar. "
            "Deficiência de nitrogênio e potássio. "
            "Solos pobres."
        ),
        "control_threshold": (
            "Controle integrado com nutrição adequada. "
            "Aplicar fungicida ao detectar sintomas."
        ),
        "products": [
            {"name": "Oxicloreto de cobre", "dose": "2.0-3.0 kg/ha", "group": "Cúprico"},
            {"name": "Opera (Piraclostrobina + Epoxiconazol)", "dose": "0.5 L/ha", "group": "Estrobilurina + Triazol"},
        ],
        "management_tips": (
            "CORRIGIR NUTRIÇÃO é fundamental. "
            "Adubação equilibrada reduz doença. "
            "Irrigação em períodos secos. "
            "Cultivares menos suscetíveis."
        ),
    },
    {
        "slug": "bicho-mineiro-cafe",
        "name": "Bicho-mineiro do Café",
        "scientific_name": "Leucoptera coffeella",
        "type": "praga",
        "crop": "cafe",
        "keywords": ["bicho mineiro", "leucoptera", "minador"],
        "symptoms": (
            "MINAS nas folhas (larvas comem o mesofilo). "
            "Manchas secas irregulares nas folhas. "
            "Folhas ficam com aspecto de queimado. "
            "Desfolha intensa em ataques severos. "
            "Reduz área fotossintética."
        ),
        "favorable_conditions": (
            "Períodos SECOS e quentes. "
            "Baixa umidade relativa. "
            "Lavouras expostas ao sol. "
            "Ausência de inimigos naturais."
        ),
        "control_threshold": (
            "30% de folhas minadas. "
            "Ou 20% de folhas com minas ativas."
        ),
        "products": [
            {"name": "Voliam Targo (Clorantraniliprole + Abamectina)", "dose": "0.8 L/ha", "group": "Diamida + Avermectina"},
            {"name": "Premio (Clorantraniliprole)", "dose": "0.15 L/ha", "group": "Diamida"},
            {"name": "Actara (Tiametoxam) via solo", "dose": "1.0 kg/ha", "group": "Neonicotinoide"},
        ],
        "management_tips": (
            "Monitorar durante estação seca. "
            "Controle biológico com vespinhas parasitóides. "
            "Evitar desmatamento de áreas próximas. "
            "Sombreamento reduz ataque."
        ),
    },
    {
        "slug": "broca-cafe",
        "name": "Broca do Café",
        "scientific_name": "Hypothenemus hampei",
        "type": "praga",
        "crop": "cafe",
        "keywords": ["broca cafe", "broca do café", "hypothenemus"],
        "symptoms": (
            "ORIFÍCIOS nos frutos (coroa ou umbigo). "
            "Grãos perfurados e destruídos internamente. "
            "Queda de frutos verdes. "
            "Presença de pó (serragem) nos orifícios. "
            "Afeta qualidade e classificação do café."
        ),
        "favorable_conditions": (
            "Alta umidade. "
            "Frutos remanescentes (cisco no chão e na planta). "
            "Colheita tardia. "
            "Vizinhança com cafezais abandonados."
        ),
        "control_threshold": (
            "3-5% de frutos brocados (início do controle). "
            "Monitorar a partir de frutos chumbinho."
        ),
        "products": [
            {"name": "Endosulfan (quando permitido)", "dose": "Conforme bula", "group": "Organoclorado"},
            {"name": "Beauveria bassiana", "dose": "Conforme bula", "group": "Biológico"},
        ],
        "management_tips": (
            "COLHEITA BEM FEITA (não deixar frutos). "
            "Repasse para retirar frutos remanescentes. "
            "Controle biológico com Beauveria. "
            "Armadilhas com etanol + metanol."
        ),
    },
    # ============================================================
    # CANA-DE-AÇÚCAR - DOENÇAS E PRAGAS
    # ============================================================
    {
        "slug": "broca-cana",
        "name": "Broca da Cana",
        "scientific_name": "Diatraea saccharalis",
        "type": "praga",
        "crop": "cana",
        "keywords": ["broca cana", "diatraea", "broca colmo"],
        "symptoms": (
            "CORAÇÃO MORTO: secamento da folha central. "
            "Galerias internas no colmo. "
            "Orifícios de entrada nas hastes. "
            "Colmos quebram facilmente. "
            "Inversão de sacarose (açúcar vira álcool). "
            "Entrada de fungos nas galerias."
        ),
        "favorable_conditions": (
            "Clima quente e úmido. "
            "Áreas sem controle biológico. "
            "Variedades suscetíveis."
        ),
        "control_threshold": (
            "Monitorar desde o 3º mês após plantio. "
            "Índice de Intensidade de Infestação (I.I.) > 3%."
        ),
        "products": [
            {"name": "Cotesia flavipes (parasitoide)", "dose": "6.000 vespas/ha", "group": "Biológico"},
            {"name": "Trichogramma galloi (parasitoide de ovos)", "dose": "100.000/ha", "group": "Biológico"},
        ],
        "management_tips": (
            "CONTROLE BIOLÓGICO é o mais eficiente. "
            "Liberação de Cotesia em áreas infestadas. "
            "Trichogramma preventivo. "
            "Variedades resistentes. "
            "Colheita sem queima reduz mortalidade de parasitoides."
        ),
    },
    {
        "slug": "ferrugem-alaranjada-cana",
        "name": "Ferrugem Alaranjada da Cana",
        "scientific_name": "Puccinia kuehnii",
        "type": "doenca",
        "crop": "cana",
        "keywords": ["ferrugem alaranjada", "puccinia kuehnii", "ferrugem cana"],
        "symptoms": (
            "Pústulas ALARANJADAS a castanho-alaranjadas. "
            "NÃO escurecem com o tempo (diferencial). "
            "Distribuídas por toda superfície da folha. "
            "Agrupadas próximo à inserção da folha. "
            "Folhas secam em ataques severos."
        ),
        "favorable_conditions": (
            "Temperatura 17-23°C. "
            "Alta umidade. "
            "Variedades suscetíveis (ex: SP81-3250)."
        ),
        "control_threshold": (
            "Variedades suscetíveis: aplicação preventiva. "
            "Monitoramento visual."
        ),
        "products": [
            {"name": "Opera (Piraclostrobina + Epoxiconazol)", "dose": "0.5-0.75 L/ha (aéreo)", "group": "Estrobilurina + Triazol"},
            {"name": "Priori Xtra (Azoxistrobina + Ciproconazol)", "dose": "0.3 L/ha", "group": "Estrobilurina + Triazol"},
        ],
        "management_tips": (
            "VARIEDADES RESISTENTES são a principal ferramenta. "
            "Substituir variedades suscetíveis. "
            "Aplicação fungicida viável em variedades de alto valor. "
            "Monitorar lavouras."
        ),
    },
    {
        "slug": "cigarrinha-cana",
        "name": "Cigarrinha das Raízes",
        "scientific_name": "Mahanarva fimbriolata",
        "type": "praga",
        "crop": "cana",
        "keywords": ["cigarrinha cana", "mahanarva", "cigarrinha raiz"],
        "symptoms": (
            "Ninfas nas raízes: ESPUMA branca característica. "
            "Amarelecimento das folhas (injeção de toxinas). "
            "Secamento das folhas (de baixo para cima). "
            "Redução de ATR (açúcar). "
            "Perdas podem chegar a 30%."
        ),
        "favorable_conditions": (
            "Colheita sem queima (mantém palha). "
            "Alta umidade do solo. "
            "Período chuvoso."
        ),
        "control_threshold": (
            "5-10 ninfas por metro de sulco. "
            "Ou 2-3 adultos por metro."
        ),
        "products": [
            {"name": "Metarhizium anisopliae", "dose": "2-5 kg/ha", "group": "Biológico"},
            {"name": "Thiamethoxam (aplicação sulco)", "dose": "Conforme bula", "group": "Neonicotinoide"},
        ],
        "management_tips": (
            "CONTROLE BIOLÓGICO com Metarhizium é eficiente. "
            "Aplicar fungo no início das chuvas. "
            "Variedades resistentes. "
            "Manejo de palhada."
        ),
    },
    # ============================================================
    # SORGO - DOENÇAS E PRAGAS
    # ============================================================
    {
        "slug": "pulgao-verde-sorgo",
        "name": "Pulgão Verde do Sorgo",
        "scientific_name": "Schizaphis graminum",
        "type": "praga",
        "crop": "sorgo",
        "keywords": ["pulgao verde sorgo", "pulgão verde sorgo", "pulgao verde do sorgo", "pulgão verde do sorgo", "schizaphis graminum", "pulgao sorgo", "pulgão sorgo"],
        "symptoms": (
            "Colônias na face inferior das folhas. "
            "Manchas AVERMELHADAS nas folhas. "
            "Folhas secam das bordas para o centro. "
            "Redução do crescimento. "
            "Plantas podem morrer em infestações severas."
        ),
        "favorable_conditions": (
            "Períodos secos. "
            "Desequilíbrio por inseticidas não seletivos. "
            "Ausência de inimigos naturais."
        ),
        "control_threshold": (
            "Início de formação de colônias. "
            "Antes das manchas avermelhadas se expandirem."
        ),
        "products": [
            {"name": "Actara (Tiametoxam)", "dose": "0.1-0.15 kg/ha", "group": "Neonicotinoide"},
            {"name": "Engeo Pleno (Tiametoxam + Lambda)", "dose": "0.2 L/ha", "group": "Neonicotinoide + Piretroide"},
        ],
        "management_tips": (
            "PRESERVAR INIMIGOS NATURAIS (joaninhas, crisopídeos). "
            "Evitar piretróides em área. "
            "Híbridos tolerantes. "
            "Monitoramento frequente."
        ),
    },
    {
        "slug": "antracnose-sorgo",
        "name": "Antracnose do Sorgo",
        "scientific_name": "Colletotrichum sublineolum",
        "type": "doenca",
        "crop": "sorgo",
        "keywords": ["antracnose sorgo", "colletotrichum sorgo"],
        "symptoms": (
            "Manchas elípticas nas folhas com CENTRO CLARO. "
            "Bordas avermelhadas a púrpura. "
            "Pequenos pontos escuros (acérvulos) no centro. "
            "Ataca folhas, colmo e panículas. "
            "Causa seca prematura em ataques severos."
        ),
        "favorable_conditions": (
            "Alta umidade. "
            "Temperatura 22-30°C. "
            "Restos culturais infectados."
        ),
        "control_threshold": (
            "Aplicar ao detectar primeiros sintomas."
        ),
        "products": [
            {"name": "Opera (Piraclostrobina + Epoxiconazol)", "dose": "0.5 L/ha", "group": "Estrobilurina + Triazol"},
            {"name": "Priori Xtra (Azoxistrobina + Ciproconazol)", "dose": "0.3 L/ha", "group": "Estrobilurina + Triazol"},
        ],
        "management_tips": (
            "Híbridos resistentes são a melhor opção. "
            "Rotação de culturas. "
            "Eliminação de restos. "
            "Tratamento de sementes."
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

    best_score = 0.0

    # Match em keywords - prioriza matches mais específicos
    for keyword in disease.get("keywords", []):
        keyword_norm = normalize_text(keyword)
        if not keyword_norm:
            continue

        # Match EXATO: query == keyword
        if query_norm == keyword_norm:
            return 1.2  # Máximo score para match exato

        # Query contém keyword inteira E keyword é longa (específica)
        if keyword_norm in query_norm:
            # Score proporcional ao tamanho da keyword (mais longa = mais específica)
            specificity = len(keyword_norm) / len(query_norm)
            score = 0.9 + (specificity * 0.2)  # 0.9 a 1.1
            best_score = max(best_score, score)

        # Keyword contém query inteira
        elif query_norm in keyword_norm:
            specificity = len(query_norm) / len(keyword_norm)
            score = 0.85 + (specificity * 0.1)  # 0.85 a 0.95
            best_score = max(best_score, score)

    # Match no nome
    name_norm = normalize_text(disease.get("name", ""))
    if name_norm:
        if query_norm == name_norm:
            best_score = max(best_score, 1.15)
        elif name_norm in query_norm or query_norm in name_norm:
            best_score = max(best_score, 0.85)

    # Match no nome científico
    sci_name = normalize_text(disease.get("scientific_name", ""))
    if sci_name:
        if query_norm == sci_name:
            best_score = max(best_score, 1.1)
        elif sci_name in query_norm or query_norm in sci_name:
            best_score = max(best_score, 0.8)

    # Fuzzy match como fallback
    if best_score < 0.5:
        for keyword in disease.get("keywords", []):
            score = SequenceMatcher(None, query_norm, normalize_text(keyword)).ratio()
            best_score = max(best_score, score * 0.8)  # Fuzzy match com penalidade

        name_score = SequenceMatcher(None, query_norm, name_norm).ratio()
        best_score = max(best_score, name_score * 0.75)

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
