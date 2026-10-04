# Inventário do lote — Fase 0

> Registro do que o sistema vai enfrentar: os 8 avisos e a base de referência. São fatos sobre este lote; o documento congela depois da Fase 0.
> Classes e vocabulário: `dominio.md`. Decisões: `decisoes.md`. Respostas esperadas: `evals/gabarito.csv`.

---

## 1. Visão geral

| Doc | Formato | Classe esperada | Problema principal | Revisão humana? |
|---|---|---|---|---|
| 01 | nativo | `DIVIDENDO` | Menção a IRRF num dividendo: não é sinal de JCP nem gera valor líquido | não |
| 02 | nativo | `JCP` | Baixa (caso base de JCP); aprovação só no corpo | não |
| 03 | nativo | `JCP` | Título "Distribuição de Dividendos" contradiz o corpo, que descreve JCP | sim |
| 04 | nativo | `JCP` | Data de pagamento "a definir": não inventar | sim |
| 05 | nativo | `DIVIDENDO` | Data de pagamento (10/07) anterior à data com (15/07) | sim |
| 06 | nativo | `GRUPAMENTO` | Sem valor, moeda e pagamento: "não se aplica" ≠ "ausente" | não |
| 07 | escaneado | `JCP` | Leitura de imagem com ruído; valores com 10 casas decimais | não¹ |
| 08 | nativo | `BONIFICACAO` | Emissor ausente do golden record; custo atribuído (R$) não é pagamento | sim |

¹ O gabarito assume leitura correta e confiança do OCR acima do limite (D-08).

---

## 2. Onde cada campo aparece

Legenda: **T** = só na tabela · **C** = só no corpo · **T+C** = nos dois · **n/a** = não se aplica.

| Doc | Rótulo do tipo (tabela) | Aprovação | Data com | Data ex | Pagamento | Valor / proporção | Alíquota | Moeda |
|---|---|---|---|---|---|---|---|---|
| 01 | "Dividendo" | T+C (RCA) | T+C | T+C | T | bruto ON: T | n/a (regra por beneficiário, C) | R$ |
| 02 | "Juros sobre o Capital Próprio (JCP)" | C (RCA) | T+C | T+C | T | bruto e líquido PN: T | T+C | R$ |
| 03 | "Natureza do provento: Remuneração do capital próprio" (título diverge) | C (RCA) | T+C | T+C | T | bruto e líquido ON: T | T+C | R$ |
| 04 | "Juros sobre o Capital Próprio (JCP)" | C (RCA) | T+C | T+C | "a definir": T+C | bruto e líquido ON: T | T+C | R$ |
| 05 | "Dividendo intercalar" | T+C (RCA) | T+C | T+C | T | bruto ON: T | n/a | R$ |
| 06 | "Grupamento de ações (inplit)" | C (AGE) | T+C (data-base) | T+C (início da negociação grupada) | n/a | proporção 10:1: T+C | n/a | n/a |
| 07 | "Juros sobre o Capital Próprio (JCP)" | C (RCA) | T+C | T+C | T | bruto e líquido PN: T | T+C | R$ |
| 08 | "Bonificação em ações" | C (AGE) | T+C | T+C | T (crédito das ações) | proporção 1:20 e custo atribuído: T+C | n/a | R$ (custo atribuído) |

**Leitura da matriz:**
- Identificação está em todos os documentos: emissor e CNPJ no cabeçalho; ticker e ISIN na linha "Código de negociação".
- A data de aprovação só está na tabela nos docs 01 e 05. Nos demais, só no corpo: extrair apenas da tabela perde o campo.
- Pagamento e valores em dinheiro só aparecem na tabela (fonte única, sem confirmação cruzada). Data com, data ex e alíquota aparecem nos dois lugares, então a concordância corpo × tabela é um sinal de confiança disponível.

---

## 3. Fichas por documento

### Doc 01 — Energética Vale do Tietê · `DIVIDENDO`
- **Problemas:** o parágrafo sobre IRRF de 10% sobre o que exceder R$ 50 mil/mês por beneficiário. Não é sinal de JCP e não gera valor líquido por ação. Valor com 10 casas decimais.
- **Deduzido:** nada relevante; caso base de dividendo. Natureza ("resultado do exercício") e rótulo convergem.
- **Golden:** match em todas as chaves (classe ON).
- **Revisão:** não.

### Doc 02 — Banco Meridional do Brasil · `JCP`
- **Problemas:** "imputado aos dividendos obrigatórios" pode puxar para `DIVIDENDO`. Data de aprovação só no corpo.
- **Deduzido:** classe confirmada por rótulo, base legal (art. 9º da Lei 9.249/95) e tributação. Líquido = bruto × 0,825 confere.
- **Golden:** match em todas as chaves (classe PN).
- **Revisão:** não.

### Doc 03 — Companhia Siderúrgica Paranaense · `JCP`
- **Classe:** `JCP`, apesar do título. Três sinais de natureza convergem:
  1. "a título de remuneração do capital próprio": expressão legal do JCP (art. 9º da Lei 9.249/95);
  2. "calculados sobre as contas do patrimônio líquido e limitados à variação pro rata die da TJLP": forma de cálculo e limite do JCP;
  3. IRRF de 17,5% sobre o bruto, com valor líquido por ação informado: tratamento tributário do JCP.
- A tabela não tem a linha "Tipo de evento"; no lugar aparece "Natureza do provento (conforme corpo do aviso)".
- "Imputado ao dividendo mínimo obrigatório" não torna o evento dividendo (ver glossário em `dominio.md`).
- Data de aprovação só no corpo. Líquido = bruto × 0,825 confere.
- **Golden:** match em todas as chaves (classe ON).
- **Revisão:** sim, por divergência entre título e natureza (D-06); a classe JCP já vai preenchida para o operador confirmar.

### Doc 04 — Rede Varejo Brasil · `JCP`
- **Problemas:** data de pagamento "A definir (vide aviso complementar)", na tabela e em destaque no corpo. Risco de o modelo inventar uma data ou reaproveitar outra (ex.: data ex).
- **Deduzido:** o campo não falta por falha de leitura: foi adiado pelo emissor. Sai `null` com esse motivo explícito. Classe por rótulo e tributação; líquido confere. Aprovação só no corpo.
- **Golden:** match em todas as chaves (classe ON).
- **Revisão:** sim. O registro está correto, mas incompleto, e depende de aviso complementar (D-07).

### Doc 05 — Aurora Saneamento · `DIVIDENDO`
- **Problemas:** data de pagamento 10/07/2026 anterior à data com (15/07) e à data ex (16/07). Pagar antes de saber quem tem direito é impossível.
- **Deduzido:** não há como saber qual data está errada: o corpo não repete a data de pagamento. Não corrigir; extrair como está e sinalizar. Natureza: "dividendos intercalares à conta de reservas de lucros"; o termo literal vai como evidência.
- **Golden:** match em todas as chaves (classe ON).
- **Revisão:** sim, por violação da ordem das datas.

### Doc 06 — Petroquímica Litoral · `GRUPAMENTO`
- **Problemas:** não há valor em R$, moeda nem data de pagamento. Esses campos são "não se aplica", não "ausentes", e não podem disparar revisão por falta. Há datas próprias do evento (início da negociação grupada, período de ajuste de frações).
- **Deduzido:** "data-base do grupamento" (26/06) ocupa o papel da data com; "início da negociação grupada" (29/06), o da data ex. Direção da proporção: 10 antigas → 1 nova. O título usa "Inplit", sinônimo de grupamento. Aprovação por AGE, só no corpo.
- **Golden:** match em todas as chaves (classe ON).
- **Revisão:** não.

### Doc 07 — Telecom Norte Participações · `JCP`
- **Problemas:** PDF escaneado (imagem, sem texto selecionável), com ruído de fundo, leve inclinação e artefatos nas linhas pontilhadas (",,,,,,"). Valores com 10 casas são o ponto mais frágil da leitura.
- **Deduzido:** o conteúdo é íntegro e coerente. A conta líquido = bruto × 0,825 confere e funciona como verificação da leitura: um dígito lido errado quebra a conta. Aprovação só no corpo.
- **Golden:** match em todas as chaves (classe PN).
- **Revisão:** não, assumindo leitura correta e confiança do OCR acima do limite (D-08).

### Doc 08 — Construtora Horizonte · `BONIFICACAO`
- **Problemas:** (1) o emissor não consta no golden record, por nenhuma chave; (2) o custo atribuído de R$ 7,82/ação é base fiscal, não pagamento, e o modelo pode extraí-lo como "valor" do evento.
- **Deduzido:** "crédito das ações bonificadas" (26/06) ocupa o papel da data de pagamento. Proporção: 1 ação nova para cada 20 (5%). Aprovação por AGE, só no corpo.
- **Golden:** sem registro; a identidade do emissor não pode ser validada.
- **Revisão:** sim, por emissor fora da base de referência.

---

## 4. Golden record

- **Campos que vêm do aviso e são cruzados com a base:** emissor, cnpj, isin, ticker, classe.
- **Campos só de referência** (não aparecem nos avisos; servem para validar): segmento_listagem, status. Todos os registros estão `ativo`, então nenhuma regra de status tem caso de teste no lote.

**Cruzamento:**
- **Docs 01–07:** batem com a base em todas as chaves (CNPJ, ISIN, ticker, nome e classe). Nenhuma divergência.
- **Doc 08:** Construtora Horizonte S.A. (CNPJ 09.888.999/0001-21, CNHZ3, BRCNHZACNOR5) não tem registro por nenhuma chave.
- **5 registros sem documento:** Agro Cerrado, Logística Atlântico, Seguradora Pampa, Mineração Serra Azul e Águas do Planalto. A base é o universo de emissores, não um espelho do lote: a validação busca por chave e nunca assume correspondência 1:1.

**Chave de cruzamento:** como todas as chaves batem, o lote não força a escolha, mas a política precisa existir. Proposta: ISIN como chave primária (identifica o ativo do evento), CNPJ como confirmação (identifica o emissor), nome só como sinal fraco (os cabeçalhos vêm em maiúsculas; exige normalizar caixa e acentos).

**Dígito verificador do ISIN:** 11 dos 13 ISINs (12 da base + doc 08) falham no cálculo; os 2 que passam são coincidência (~1 em 10). O algoritmo foi conferido com ISINs reais (PETR4, VALE3). Os ISINs são fictícios, como o enunciado avisa.

---

## 5. Pendências para as próximas fases

### Regras de coerência (Fase 1)
Os candidatos a regra levantados aqui foram consolidados em `regras.md`, incluindo os campos obrigatórios por classe.

### Contrato e incerteza (Fase 2)
- Formato do JSON de saída: objeto único, formato por tipo ou híbrido (extração em objeto único; saída em dois formatos, dinheiro e ações).
- Status por campo no schema (encontrado, não encontrado, não se aplica, adiado pelo emissor): exigido pelos docs 04 e 06 e por D-07.
- Representação canônica da proporção: provisória `antes:depois` (D-09).
- Papel das datas por classe: provisório (D-09); usado em `regras.md`, seção 3.
- Precisão numérica: valores com até 10 casas decimais → decimal exato, nunca float.
- Sinal de confiança: concordância corpo × tabela (data com, data ex e alíquota aparecem nos dois lugares).
- Sinal de confiança em escaneados: confiança do OCR nas palavras de cada valor; limite a definir (D-08).
