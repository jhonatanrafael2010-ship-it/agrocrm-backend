---
name: lancamento-visita
description: Interpreta mensagem livre do consultor (texto ou áudio transcrito) descrevendo uma visita técnica agrícola e extrai payload estruturado pronto para criar Visit no banco. Aciona quando a mensagem menciona cliente, fazenda, cultura, fenologia ou recomendação técnica. Suporta foto anexa.
---

# Skill: Lançamento de Visita

## Quando ativar

Mensagem do consultor no Telegram que descreve uma visita realizada ou a realizar, com pelo menos 2 destes sinais:
- Nome de cliente ou produtor
- Nome de fazenda ou propriedade
- Cultura (Soja, Milho, Algodão)
- Fenologia (V1-V20, R1-R6, VE, VC, VT)
- Data (hoje, ontem, DD/MM, DD/MM/YYYY)
- Verbo de recomendação (aplicar, recomendar, observar)
- Foto anexa com caption descritiva

Não ativar se mensagem for comando direto (pdf, agenda, cancelar, confirmar).

## Entidades obrigatórias

- `client_name`: nome do produtor
- `culture`: Soja | Milho | Algodão
- `fenologia_real`: código V/R válido
- `date`: token temporal

## Entidades opcionais

- `property_name`: fazenda
- `plot_name`: talhão
- `variety`: variedade
- `recommendation`: texto livre pós "aplicar" ou "obs"
- `products`: lista com product_name, dose, unit

## Regras de fenologia por cultura

Soja: VE, VC, V1-V8, R1-R8
Milho: VE, V1-V20, VT, R1-R6
Algodão: V1-V20, B1-B6, F1-F12

Se fenologia não bater com cultura, solicitar confirmação.

## Unidades válidas

L/ha, mL/ha, kg/ha, g/ha, %, p.c

Normalizar variações: "l por hectare" → L/ha, "kgha" → kg/ha.

## Threshold de confiança

- high: 4+ entidades preenchidas e cliente resolvido com score ≥ 0.80
- medium: 3 entidades ou cliente com score 0.58-0.79
- low: abaixo disso → pedir confirmação

## Fluxo de saída

Retornar JSON:

```json
{
  "intent": "CREATE_VISIT_LIKE_MESSAGE",
  "confidence": "high",
  "parsed_visit": {
    "client_name": "...",
    "property_name": "...",
    "culture": "...",
    "fenologia_real": "...",
    "date": "...",
    "recommendation": "...",
    "products": []
  }
}
```

## Fotos

Se mensagem vier com foto anexa, marcar `has_photo: true` no payload. Foto já vem tratada pelo `resolve_pending_photo_for_message`. Skill não processa imagem, apenas sinaliza presença.

## Casos especiais

Áudio transcrito: tolerar falhas de transcrição em nomes próprios. Priorizar match fuzzy contra carteira do consultor via EntityResolver.

Mensagem fragmentada: se faltar cultura mas houver fenologia, inferir cultura provável (V1-V8 sem contexto → Soja como default, confirmar).

Correção em fluxo: se estado atual for `awaiting_*`, não ativar skill. Deixar STATEFUL_REPLY cuidar.

## Exemplos

Entrada: "marcelo alonso soja v4 hoje aplicar fungicida priori 0.6 L/ha"
Saída: client_name=Marcelo Alonso, culture=Soja, fenologia_real=V4, date=hoje, recommendation=aplicar fungicida priori 0.6 L/ha, products=[{product_name: "Priori", dose: "0.6", unit: "L/ha"}]

Entrada: "visita evaristo faz boa vista milho vt amanha obs lagarta alta"
Saída: client_name=Evaristo, property_name=Boa Vista, culture=Milho, fenologia_real=VT, date=amanha, recommendation=lagarta alta

Entrada: [foto] caption "ivan r2 ferrugem"
Saída: client_name=Ivan, fenologia_real=R2, recommendation=ferrugem, has_photo=true, confidence=low (faltam dados)
