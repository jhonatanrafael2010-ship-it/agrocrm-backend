---
name: diagnostico-praga
description: Identifica pragas e doenças agrícolas com base nos sintomas descritos. Retorna diagnóstico, sintomas característicos, nível de dano econômico e tratamentos recomendados para Soja, Milho e Algodão.
---

# Skill: Diagnóstico de Pragas e Doenças

## Quando ativar

Mensagem do consultor que:
- Pergunta sobre uma praga ou doença específica
- Descreve sintomas observados na lavoura
- Pede recomendação de tratamento para problema fitossanitário
- Usa termos como: "o que é", "como tratar", "sintomas de", "diagnóstico", "identificar", "praga", "doença", "fungo", "lagarta", "percevejo"

Não ativar para lançamento de visita (deixar CREATE_VISIT_LIKE_MESSAGE cuidar).

## Base de Conhecimento

### SOJA - Pragas

#### Lagarta-da-soja (Anticarsia gemmatalis)
- Sintomas: Desfolha intensa, folhas rendilhadas, presença de lagartas verdes com listras brancas longitudinais
- Nível de controle: 30% de desfolha no vegetativo, 15% no reprodutivo, ou 40 lagartas grandes/pano de batida
- Produtos: Metomil, Espinosade, Clorfenapir, Bacillus thuringiensis
- Dose referência: Metomil 0.6-1.0 L/ha, Bt 0.5-1.0 L/ha

#### Lagarta-falsa-medideira (Chrysodeixis includens)
- Sintomas: Desfolha com perfurações irregulares, lagarta verde-clara que se locomove "medindo palmos"
- Nível de controle: Igual à lagarta-da-soja
- Produtos: Clorantraniliprole, Flubendiamida, Indoxacarbe, Metoxifenozida
- Dose referência: Belt (Flubendiamida) 0.1 L/ha, Premio (Clorantraniliprole) 0.05-0.1 L/ha

#### Lagarta-do-cartucho (Spodoptera frugiperda)
- Sintomas: Desfolha severa, raspa folhas deixando-as esbranquiçadas, ataca vagens
- Nível de controle: 10 lagartas/pano de batida ou 30% desfolha
- Produtos: Clorantraniliprole, Clorfenapir, Spinosade
- Dose referência: Premio 0.05-0.1 L/ha

#### Percevejo-marrom (Euschistus heros)
- Sintomas: Retenção foliar, vagens chochas, grãos manchados e menores
- Nível de controle: 2 percevejos/pano de batida (R3-R5), 4 percevejos (semente)
- Produtos: Tiametoxam + Lambda-cialotrina, Imidacloprido + Bifentrina, Acefato
- Dose referência: Engeo Pleno 0.2-0.25 L/ha, Connect 0.75-1.0 L/ha

#### Percevejo-verde-pequeno (Piezodorus guildinii)
- Sintomas: Similar ao percevejo-marrom, mais agressivo
- Nível de controle: 2 percevejos/pano de batida
- Produtos: Mesmos do percevejo-marrom
- Dose referência: Engeo Pleno 0.2-0.25 L/ha

#### Mosca-branca (Bemisia tabaci)
- Sintomas: Folhas com fumagina (preta), amarelecimento, transmite viroses
- Nível de controle: Monitoramento com armadilhas amarelas
- Produtos: Espiromesifeno, Piriproxifeno, Ciantraniliprole
- Dose referência: Oberon 0.4-0.5 L/ha

#### Ácaro-rajado (Tetranychus urticae)
- Sintomas: Folhas bronzeadas, pontuações amareladas, teias na face inferior
- Nível de controle: Reboleiras com bronzeamento
- Produtos: Abamectina, Espiromesifeno, Propargito
- Dose referência: Abamectina 0.3-0.4 L/ha

### SOJA - Doenças

#### Ferrugem-asiática (Phakopsora pachyrhizi)
- Sintomas: Pústulas marrom-avermelhadas na face inferior das folhas, desfolha precoce
- Condições: Temperatura 18-26°C, umidade alta, molhamento foliar >6h
- Produtos: Trifloxistrobina + Protioconazol, Azoxistrobina + Benzovindiflupir, Mancozebe (multissítio)
- Dose referência: Fox (Triflox+Protio) 0.4 L/ha + Mancozebe 1.5-2.0 kg/ha
- Importante: Rotacionar grupos químicos, iniciar preventivo em R1

#### Mancha-alvo (Corynespora cassiicola)
- Sintomas: Lesões circulares com halo amarelado e ponto central escuro
- Condições: Umidade alta, temperaturas amenas
- Produtos: Fluxapiroxade + Piraclostrobina, Protioconazol + Trifloxistrobina
- Dose referência: Orkestra 0.3-0.35 L/ha

#### Antracnose (Colletotrichum truncatum)
- Sintomas: Manchas escuras em hastes e vagens, cancros deprimidos
- Condições: Alta umidade, chuvas frequentes
- Produtos: Carbendazim, Tiofanato-metílico + Fluazinam
- Dose referência: Carbendazim 0.5 L/ha

#### Oídio (Microsphaera diffusa)
- Sintomas: Pó branco-acinzentado na superfície das folhas
- Condições: Clima seco, temperaturas amenas
- Produtos: Enxofre, Trifloxistrobina, Tebuconazol
- Dose referência: Enxofre 2-3 kg/ha, Nativo 0.5 L/ha

#### Mofo-branco (Sclerotinia sclerotiorum)
- Sintomas: Micélio branco cotonoso em hastes, escleródios pretos
- Condições: Alta umidade, temperaturas amenas, dossel fechado
- Produtos: Fluazinam, Procimidona, Fluopyram
- Dose referência: Frowncide 1.0 L/ha

#### DFC - Síndrome da morte súbita (Fusarium spp.)
- Sintomas: Folhas com clorose internerval, necrose entre nervuras, raízes com podridão
- Condições: Solos compactados, excesso de umidade
- Produtos: Tratamento de sementes com Fludioxonil + Metalaxil
- Manejo: Rotação de culturas, descompactação do solo

### MILHO - Pragas

#### Lagarta-do-cartucho (Spodoptera frugiperda)
- Sintomas: Folhas raspadas, destruição do cartucho, presença de fezes
- Nível de controle: 20% de plantas atacadas
- Produtos: Clorantraniliprole, Metomil, Espinosade, Bt
- Dose referência: Premio 0.1 L/ha, Lannate 0.6-1.0 L/ha

#### Lagarta-da-espiga (Helicoverpa zea)
- Sintomas: Danos em espigas, grãos destruídos, presença na ponta da espiga
- Nível de controle: 5% de espigas atacadas
- Produtos: Clorantraniliprole, Indoxacarbe, Spinosade
- Dose referência: Premio 0.1 L/ha

#### Cigarrinha-do-milho (Dalbulus maidis)
- Sintomas: Transmite enfezamentos, plantas com encurtamento de entrenós
- Nível de controle: 3-5 cigarrinhas/planta na fase inicial
- Produtos: Tiametoxam, Imidacloprido (TS), Piretroides
- Dose referência: Cruiser 0.2 L/100kg sementes

#### Percevejo-barriga-verde (Dichelops spp.)
- Sintomas: Perfilhamento excessivo, folhas com perfurações em linha
- Nível de controle: 0.5 percevejo/m na emergência
- Produtos: Tiametoxam + Lambda-cialotrina, Bifentrina
- Dose referência: Engeo Pleno 0.25 L/ha

### MILHO - Doenças

#### Cercosporiose (Cercospora zeae-maydis)
- Sintomas: Lesões retangulares acinzentadas paralelas às nervuras
- Condições: Alta umidade, temperaturas 22-30°C
- Produtos: Azoxistrobina + Ciproconazol, Piraclostrobina + Epoxiconazol
- Dose referência: Priori Xtra 0.3 L/ha

#### Ferrugem-polissora (Puccinia polysora)
- Sintomas: Pústulas alaranjadas na face superior das folhas
- Condições: Temperaturas altas (>27°C), umidade
- Produtos: Triazóis + Estrobilurinas
- Dose referência: Opera 0.5-0.75 L/ha

#### Helmintosporiose (Exserohilum turcicum)
- Sintomas: Lesões alongadas necróticas, formato de charuto
- Condições: Temperaturas amenas, alta umidade
- Produtos: Azoxistrobina, Piraclostrobina + Fluxapiroxade
- Dose referência: Priori 0.2 L/ha

#### Enfezamentos (Molicutes)
- Sintomas: Vermelhão, avermelhamento de folhas, espigas múltiplas pequenas
- Vetor: Cigarrinha-do-milho
- Manejo: Controle do vetor, híbridos tolerantes, evitar plantios tardios

### ALGODÃO - Pragas

#### Bicudo-do-algodoeiro (Anthonomus grandis)
- Sintomas: Botões florais e maçãs perfurados, queda de estruturas
- Nível de controle: 5% de botões atacados
- Produtos: Malathion, Tiametoxam + Lambda-cialotrina, Clorpirifós
- Dose referência: Engeo Pleno 0.2 L/ha

#### Lagarta-das-maçãs (Heliothis virescens)
- Sintomas: Perfurações em botões, flores e maçãs
- Nível de controle: 5% de plantas com lagartas pequenas
- Produtos: Clorantraniliprole, Indoxacarbe, Spinosade
- Dose referência: Premio 0.1 L/ha

#### Pulgão-do-algodoeiro (Aphis gossypii)
- Sintomas: Folhas encarquilhadas, fumagina, mela
- Nível de controle: 50% de plantas com colônias
- Produtos: Imidacloprido, Tiametoxam, Flonicamida
- Dose referência: Evidence 0.2 kg/ha

#### Ácaro-rajado (Tetranychus urticae)
- Sintomas: Folhas bronzeadas, avermelhadas, com teias
- Nível de controle: Reboleiras com bronzeamento
- Produtos: Abamectina, Espiromesifeno
- Dose referência: Abamectina 0.4 L/ha

### ALGODÃO - Doenças

#### Ramulária (Ramularia areola)
- Sintomas: Manchas angulares esbranquiçadas na face inferior, esporulação branca
- Condições: Umidade alta, noites frias seguidas de dias quentes
- Produtos: Fluxapiroxade + Piraclostrobina, Carbendazim + Flutriafol
- Dose referência: Orkestra 0.3 L/ha

#### Ramulose (Colletotrichum gossypii var. cephalosporioides)
- Sintomas: Superbrotamento, necrose apical, "vassoura de bruxa"
- Condições: Chuvas frequentes, temperaturas amenas
- Produtos: Tiofanato-metílico, Carbendazim
- Dose referência: Cercobin 1.0 L/ha

#### Mancha-de-ramularia
- Ver Ramulária

## Formato de Resposta

Retornar JSON:

```json
{
  "intent": "PEST_DIAGNOSIS",
  "confidence": "high|medium|low",
  "diagnosis": {
    "name": "Nome da praga/doença",
    "type": "praga|doenca",
    "crop": "soja|milho|algodao",
    "symptoms": "Descrição dos sintomas",
    "control_threshold": "Nível de controle/dano econômico",
    "favorable_conditions": "Condições favoráveis (se doença)",
    "recommended_products": [
      {"name": "Nome comercial", "dose": "X L/ha ou kg/ha"}
    ],
    "management_tips": "Dicas de manejo integrado"
  },
  "similar_problems": ["outros problemas com sintomas similares"]
}
```

Se não identificar o problema com certeza, retornar confidence "low" e listar possíveis diagnósticos em `similar_problems`.

## Exemplos

Entrada: "o que é ferrugem asiática"
Saída: diagnosis.name="Ferrugem-asiática", type="doenca", crop="soja", symptoms="Pústulas marrom-avermelhadas...", confidence="high"

Entrada: "folhas da soja estão com manchas circulares e ponto no meio"
Saída: diagnosis.name="Mancha-alvo", symptoms="Lesões circulares com halo amarelado e ponto central escuro", confidence="high"

Entrada: "lagarta verde comendo as folhas do milho"
Saída: diagnosis.name="Lagarta-do-cartucho", type="praga", crop="milho", confidence="high"

Entrada: "como tratar percevejo na soja"
Saída: diagnosis.name="Percevejo-marrom", recommended_products=[Engeo Pleno, Connect], control_threshold="2 percevejos/pano de batida"
