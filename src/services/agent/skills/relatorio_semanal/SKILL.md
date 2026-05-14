---
name: relatorio-semanal
description: Gera resumo automático das atividades da semana do consultor. Inclui estatísticas de visitas realizadas, clientes atendidos, culturas acompanhadas e pendências.
---

# Skill: Relatório Semanal

## Quando ativar

Mensagem do consultor que solicita resumo ou relatório da semana:
- "resumo da semana"
- "relatório semanal"
- "como foi minha semana"
- "balanço da semana"
- "o que fiz essa semana"
- "minhas atividades da semana"

## Dados incluídos

### Visitas realizadas
- Total de visitas no período (segunda a domingo atual)
- Visitas por status (done, planned, cancelled)
- Média de visitas por dia útil

### Clientes atendidos
- Quantidade de clientes únicos visitados
- Lista dos clientes com mais visitas

### Culturas acompanhadas
- Distribuição por cultura (Soja, Milho, Algodão)
- Fenologias mais frequentes

### Pendências
- Visitas planejadas ainda não realizadas
- Clientes sem visita há mais de 15 dias

## Formato de resposta

Texto formatado para chat:

```
📊 RESUMO DA SEMANA
📅 12/05 a 18/05/2026

✅ Visitas realizadas: 12
👥 Clientes atendidos: 8
🌱 Culturas: Soja (7), Milho (4), Algodão (1)

📈 Destaques:
• Cliente mais visitado: João Silva (3 visitas)
• Fenologia mais comum: R5 (5 visitas)

⚠️ Pendências:
• 3 visitas planejadas para esta semana
• 2 clientes sem visita há +15 dias
```

## Observações

- Não requer IA para processamento
- Dados são agregados diretamente do banco
- Período sempre considera semana atual (seg-dom)
- Se não houver visitas, retorna mensagem informativa
