# Decisões

> Registro das decisões do projeto: contexto, opções, decisão e por quê / custo.
> Alimenta a seção de trade-offs do README.

---

## Fase 0 — Domínio e lote

### D-01 — Classificar pela natureza do evento, não pelo título
- **Contexto:** o doc 03 tem o título "Distribuição de Dividendos", mas o corpo descreve JCP (remuneração do capital próprio, PL × TJLP, IRRF de 17,5% com valor líquido). Classificar errado muda o tratamento tributário.
- **Opções:** (A) título; (B) rótulo "Tipo de evento" da tabela; (C) natureza (origem, base legal, forma de cálculo, tributação), com hierarquia natureza > rótulo > título.
- **Decisão:** C. Divergência entre os níveis, com a natureza convergente, gera alerta.
- **Por quê / custo:** título e rótulo são as evidências mais fáceis de estarem erradas; a natureza é o que determina o tratamento downstream. Custo: o prompt precisa ensinar os sinais de natureza (`dominio.md`, seção 1).

### D-02 — Lista simples de classes, sem subtipos
- **Contexto:** a primeira versão da taxonomia tinha tipo macro + subtipo (ex.: dividendo regular × intercalar).
- **Opções:** (A) macro + subtipo; (B) lista simples.
- **Decisão:** B: `DIVIDEND`, `JCP`, `BONUS_ISSUE`, `STOCK_SPLIT`, `REVERSE_SPLIT`, `UNDETERMINED`.
- **Por quê / custo:** uma classe = um tratamento. Os subtipos de dividendo não mudam o tratamento, e a terminologia de mercado é solta (o doc 05 chama de "intercalar" um dividendo "à conta de reservas de lucros"). Cada rótulo extra é mais uma chance de errar. Custo: nenhum para a auditoria, porque o termo literal do documento vai como evidência.

### D-03 — Classe `UNDETERMINED` com critérios fechados
- **Contexto:** uma lista fechada sem escape obriga o modelo a escolher alguma classe, mesmo quando não deveria.
- **Opções:** (A) sem classe de escape; (B) `UNDETERMINED` livre; (C) `UNDETERMINED` com motivos fechados.
- **Decisão:** C. Motivos: `OUT_OF_TAXONOMY`, `CONFLICTING_SIGNALS`, `INSUFFICIENT_EVIDENCE`. Motivo e classes candidatas são obrigatórios; sempre vai para revisão humana.
- **Por quê / custo:** sem escape, o erro possível é silencioso (classe errada com aparência plausível). Com escape, o erro possível é excesso de cautela, que custa tempo do operador e aparece no eval. Custo: risco de uso excessivo, controlado pela lista de quando não usar (título divergente, campo ausente e confiança moderada não são motivos).

### D-04 — `JCP` como sigla
- **Contexto:** as classes estão em inglês, e JCP não tem tradução consagrada.
- **Opções:** `INTEREST_ON_EQUITY`, `INTEREST_ON_CAPITAL`, `JCP`.
- **Decisão:** `JCP`.
- **Por quê / custo:** é o termo do operador e do mercado; "interest" em inglês remete a juros de dívida. Custo: um nome fora do padrão de idioma da lista.

### D-05 — `STOCK_SPLIT` incluído sem documento no lote
- **Contexto:** o lote não tem desdobramento.
- **Opções:** (A) só as classes presentes no lote; (B) incluir o desdobramento.
- **Decisão:** B.
- **Por quê / custo:** é a principal fonte de confusão com bonificação (ambos aumentam a quantidade de ações) e com grupamento (direção oposta). Custo: uma classe sem caso de teste no lote.

### D-06 — Divergência título × natureza gera alerta, não revisão (doc 03)
- **Contexto:** no doc 03, três sinais independentes de natureza convergem para JCP; só o título diverge.
- **Opções:** (A) revisão humana; (B) classificar como JCP, com alerta e sem revisão.
- **Decisão:** B.
- **Por quê / custo:** coerente com D-01. É a opção menos conservadora: se a classificação estiver errada, o erro muda a tributação. Pergunta provável na sessão ao vivo: "por que um aviso com título contraditório passou sem revisão?"

### D-07 — Campo adiado pelo emissor vai para revisão humana (doc 04)
- **Contexto:** a data de pagamento do doc 04 está "a definir (vide aviso complementar)". O registro está correto, mas incompleto.
- **Opções:** (A) revisão humana; (B) status próprio de pendência ("aguardando informação").
- **Decisão:** A. O campo sai vazio, com o motivo explícito.
- **Por quê / custo:** um único caminho para o humano é mais simples. Custo: o operador não distingue de imediato "conferir a extração" de "aguardar aviso complementar"; o motivo da revisão faz essa distinção.

### D-08 — Política para documentos escaneados adiada para a fase de OCR
- **Contexto:** o doc 07 é escaneado. Mandar todo escaneado para revisão elimina o risco de leitura, mas aumenta a carga do operador; tratar a leitura como sinal de confiança automatiza, mas depende das checagens cruzadas.
- **Opções:** (A) todo escaneado vai para revisão; (B) escaneado passa se a leitura bater nas checagens (golden record e líquido = bruto × (1 − alíquota)).
- **Decisão:** adiada para a fase em que o OCR for implementado. O gabarito assume leitura correta: doc 07 sem revisão.
- **Por quê / custo:** a escolha depende da qualidade do OCR, que ainda não existe. Custo: o roteamento do doc 07 no gabarito pode mudar.

### D-09 — Convenções de valor do gabarito
- **Contexto:** sem formato fixo, o eval acusa diferenças que são só de formato.
- **Opções (proporção, o ponto mais ambíguo):** (A) como no documento (`1:20`); (B) fator (`1.05`); (C) `antes:depois` (`20:21`).
- **Decisão:** uma linha por evento; datas em ISO 8601; decimais com ponto e todas as casas do documento; alíquota como fração (`0.175`); moeda em ISO 4217 (`BRL`); proporção `antes:depois` (grupamento `10:1`, bonificação `20:21`), provisória até a Fase 1; doc 06: data-base → `data_com` e início da negociação grupada → `data_ex`; doc 08: crédito das ações → `data_pagamento`; vazio = ausente, `n/a` = não se aplica; motivo da revisão em texto livre até a Fase 2.
- **Por quê / custo:** comparação exata e sem ambiguidade ("1:20" na bonificação pode ser lido nos dois sentidos; `antes:depois` não). Custo: proporção e papel das datas dependem de premissas da Fase 1 e podem exigir ajuste.

### D-10 — Entradas versionadas no repositório, fora de `evals/`
- **Contexto:** os PDFs e o golden record estavam em `evals/`, como se fossem fixtures de avaliação, e as pastas originais estavam no `.gitignore`.
- **Opções:** (A) manter em `evals/`; (B) fora do repositório, com instrução no README; (C) versionados em `documents/` e `golden_records/`.
- **Decisão:** C. `evals/` guarda só o que serve para avaliar o sistema (gabarito e script de eval).
- **Por quê / custo:** são entrada do sistema; quem clonar o repositório roda direto (gate da Fase 5). Custo: o repositório é público, então os dados ficam visíveis antes da entrega (são sintéticos).
