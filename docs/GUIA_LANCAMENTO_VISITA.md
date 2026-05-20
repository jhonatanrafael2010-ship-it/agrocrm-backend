# Guia de Lançamento de Visitas pelo Bot

## Resumo Rápido

Para a visita ser vinculada corretamente, o mais importante é **identificar o cliente**. Propriedade e talhão são opcionais.

---

## O que o bot precisa para vincular a visita

| Obrigatório | Importância |
|-------------|-------------|
| **Nome do cliente** | ESSENCIAL - sem isso a visita fica solta |
| Cultura (soja/milho/algodão) | Ajuda a organizar |
| Fenologia (V4, R2, etc) | Ajuda a organizar |
| Data (hoje, ontem, 15/05) | Define quando foi |

| Opcional | Quando usar |
|----------|-------------|
| Fazenda/Propriedade | Só se o cliente tem mais de uma |
| Talhão | Só se precisa rastrear por talhão |

---

## Formatos de Mensagem

### Formato IDEAL (vínculo garantido)
```
cliente: João Silva Soja V4 hoje aplicar Priori 0.6 L/ha
```
ou
```
cliente: João Silva fazenda: Santa Maria Soja R2 ontem lagarta alta
```

### Formato BOM (funciona bem se nome for único)
```
João Silva Soja V4 hoje aplicar fungicida
```

### Formato MÍNIMO (risco de não vincular)
```
João Soja V4
```
> Se existir mais de um "João", pode vincular ao errado ou não vincular

---

## Dicas para garantir o vínculo

### 1. Use nome completo ou único
```
❌ "Marcelo milho VT"           → pode ter vários Marcelos
✅ "Marcelo Alonso milho VT"    → mais específico
✅ "cliente: Marcelo milho VT"  → força busca por nome
```

### 2. Clientes que você já visitou têm prioridade
O sistema dá **+15% de preferência** para clientes da sua carteira (que você já visitou antes). Isso ajuda quando há nomes parecidos.

### 3. Use prefixos quando necessário
```
cliente: Nome do Produtor
fazenda: Nome da Fazenda  
talhão: Nome do Talhão
```

---

## Quando a visita NÃO vincula

| Situação | Por que | Solução |
|----------|---------|---------|
| Nome muito curto | "João" pode ter vários | Usar nome completo |
| Nome com erro de digitação | Sistema não encontra | Corrigir ou usar prefixo `cliente:` |
| Cliente novo (nunca visitado) | Não está na sua carteira | Usar nome completo e exato |
| Produtor não cadastrado | Não existe no sistema | Cadastrar primeiro no app |

---

## Estrutura de Dados do Sistema

```
Cliente (obrigatório)
   └── Propriedade (opcional) - só se tiver mais de uma fazenda
          └── Talhão (opcional) - só se precisar rastrear por talhão
                 └── Plantio (automático) - criado pela visita de plantio
```

**Na prática:** A maioria das visitas só precisa do cliente!

---

## Exemplos Práticos

### Visita simples
```
Marcelo Alonso Soja V4 hoje observei mosca branca
```
✅ Vincula ao cliente "Marcelo Alonso"

### Visita com recomendação
```
João Pedro Silva milho VT amanhã aplicar Premio 0.1 L/ha e Engeo 0.25 L/ha
```
✅ Vincula ao cliente + extrai produtos

### Visita com fazenda (cliente tem múltiplas)
```
cliente: José Ferreira fazenda: Boa Vista soja R2 hoje ferrugem início
```
✅ Vincula cliente + propriedade

### Visita mínima
```
Evaristo soja V6 lagarta
```
⚠️ Funciona se "Evaristo" for único. Assume data = hoje.

---

## Checklist Rápido

Antes de enviar, sua mensagem tem:

- [ ] Nome do cliente (completo ou único)?
- [ ] Cultura (soja/milho/algodão)?
- [ ] Fenologia (V1-V20, R1-R8, VT)?
- [ ] Data (hoje/ontem/amanhã/DD-MM)?

Se marcou pelo menos **nome + cultura + fenologia**, a visita deve vincular corretamente!

---

## Dúvidas Frequentes

**P: Preciso cadastrar fazenda para cada cliente?**
R: Não. Só cadastre se o cliente tiver mais de uma propriedade.

**P: Preciso cadastrar talhões?**
R: Não. Só cadastre se precisar rastrear visitas por talhão específico.

**P: A visita ficou sem vínculo, o que faço?**
R: Pode vincular manualmente pelo app. Para próxima vez, use nome completo do cliente.

**P: Posso enviar áudio?**
R: Sim! O áudio é transcrito automaticamente. Fale claramente o nome do cliente.
