# Decisões

> Registro das decisões do projeto: contexto, opções, decisão e por quê / custo.
> Alimenta a seção de trade-offs do README.

---

## Fase 0 — Domínio e lote

### D-01 — Classificar pela natureza do evento, não pelo título
- **Contexto:** o doc 03 tem o título "Distribuição de Dividendos", mas o corpo descreve JCP (remuneração do capital próprio, PL × TJLP, IRRF de 17,5% com valor líquido). Classificar errado muda o tratamento tributário.
- **Opções:** (A) título; (B) rótulo "Tipo de evento" da tabela; (C) natureza (origem, base legal, forma de cálculo, tributação), com hierarquia natureza > rótulo > título.
- **Decisão:** C. Divergência entre os níveis, com a natureza convergente, manda o documento para revisão humana com a classe já preenchida (D-06).
- **Por quê / custo:** título e rótulo são as evidências mais fáceis de estarem erradas; a natureza é o que determina o tratamento downstream. Custo: o prompt precisa ensinar os sinais de natureza (`dominio.md`, seção 1).

### D-02 — Lista simples de classes, sem subtipos
- **Contexto:** a primeira versão da taxonomia tinha tipo macro + subtipo (ex.: dividendo regular × intercalar).
- **Opções:** (A) macro + subtipo; (B) lista simples.
- **Decisão:** B: `DIVIDENDO`, `JCP`, `BONIFICACAO`, `DESDOBRAMENTO`, `GRUPAMENTO`, `INDETERMINADO`.
- **Por quê / custo:** uma classe = um tratamento. Os subtipos de dividendo não mudam o tratamento, e a terminologia de mercado é solta (o doc 05 chama de "intercalar" um dividendo "à conta de reservas de lucros"). Cada rótulo extra é mais uma chance de errar. Custo: nenhum para a auditoria, porque o termo literal do documento vai como evidência.

### D-03 — Classe `INDETERMINADO` com critérios fechados
- **Contexto:** uma lista fechada sem escape obriga o modelo a escolher alguma classe, mesmo quando não deveria.
- **Opções:** (A) sem classe de escape; (B) `INDETERMINADO` livre; (C) `INDETERMINADO` com motivos fechados.
- **Decisão:** C. Motivos: `FORA_DA_TAXONOMIA`, `SINAIS_CONFLITANTES`, `EVIDENCIA_INSUFICIENTE`. Motivo e classes candidatas são obrigatórios; sempre vai para revisão humana.
- **Por quê / custo:** sem escape, o erro possível é silencioso (classe errada com aparência plausível). Com escape, o erro possível é excesso de cautela, que custa tempo do operador e aparece no eval. Custo: risco de uso excessivo, controlado pela lista de quando não usar (título divergente, campo ausente e confiança moderada não são motivos).

### D-04 — Nomes das classes em português
- **Contexto:** a primeira versão da taxonomia usava nomes em inglês (`DIVIDEND`, `BONUS_ISSUE`, `STOCK_SPLIT`, `REVERSE_SPLIT`, `UNDETERMINED`), com `JCP` como exceção por não ter tradução consagrada.
- **Opções:** (A) inglês; (B) português.
- **Decisão:** B: `DIVIDENDO`, `JCP`, `BONIFICACAO`, `DESDOBRAMENTO`, `GRUPAMENTO`, `INDETERMINADO`. Maiúsculas e sem acento, para uso seguro em código; `JCP` fica como sigla de mercado.
- **Por quê / custo:** é a língua do operador, dos avisos e do glossário, e acaba a exceção do JCP. Custo: os nomes se afastam do padrão internacional; a correspondência com o ISO 20022 fica registrada em D-16.

### D-05 — `DESDOBRAMENTO` incluído sem documento no lote
- **Contexto:** o lote não tem desdobramento.
- **Opções:** (A) só as classes presentes no lote; (B) incluir o desdobramento.
- **Decisão:** B.
- **Por quê / custo:** é a principal fonte de confusão com bonificação (ambos aumentam a quantidade de ações) e com grupamento (direção oposta). Custo: uma classe sem caso de teste no lote.

### D-06 — Divergência título × natureza manda para revisão humana (doc 03)
- **Contexto:** no doc 03, três sinais independentes de natureza convergem para JCP; só o título diverge.
- **Opções:** (A) classificar como JCP e mandar para revisão humana, com a classe já preenchida; (B) classificar como JCP, com alerta e sem revisão.
- **Decisão:** A. A primeira versão era B; foi trocada pela opção conservadora.
- **Por quê / custo:** um erro de classificação muda a tributação, e um aviso que se contradiz é exatamente o caso em que um humano deve confirmar. O operador não refaz o trabalho: recebe a classe JCP com as evidências e só confirma. Custo: um documento a mais na fila de revisão.

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

---

## Fase 1 — Regras de negócio

### D-11 — Dígitos verificadores de ISIN e CNPJ implementados, mas desligados
- **Contexto:** 11 dos 13 ISINs e 11 dos 13 CNPJs do lote (fictícios) falham no cálculo. Os algoritmos foram conferidos com identificadores reais.
- **Opções:** (A) ligado, com revisão humana: os 8 documentos iriam para revisão; (B) alerta: dispararia em quase todo documento, e alerta que sempre dispara é ignorado; (C) não implementar; (D) implementar, desligado no arquivo de configuração.
- **Decisão:** D.
- **Por quê / custo:** com dados reais, a checagem pega erro de leitura de um único dígito, e ligá-la é trocar um parâmetro. Custo: neste lote, a regra não protege nada.

### D-12 — Calendário de pregões da B3, com feriados
- **Contexto:** R-DAT-03 (data ex = pregão seguinte à data com) e R-DAT-04 (datas de mercado em dia de pregão) precisam de um calendário. A data com define quem tem direito ao evento. Nenhuma data de mercado do lote cai em feriado; o único feriado no período (Corpus Christi, 04/06/2026) coincide só com uma data de aprovação.
- **Opções:** (A) dias úteis de segunda a sexta, sem feriados: a R-DAT-03 só poderia alertar, porque uma data ex logo depois de um feriado geraria alerta falso, e uma data num feriado passaria sem ser pega; (B) calendário da B3 com feriados.
- **Decisão:** B. R-DAT-03 e R-DAT-04 mandam para revisão humana. A fonte do calendário é decidida na Fase 3.
- **Por quê / custo:** com os feriados, as duas regras não têm falso positivo e pegam o erro mais comum de leitura em datas (um dígito ou um dia trocado) num campo que decide quem recebe. Custo: manter a fonte de feriados atualizada; fechamentos extraordinários do pregão não entram.

### D-13 — Até 2 retries, por alucinação ou por falha na chamada ao modelo
- **Contexto:** parte das falhas é passageira: alucinação do modelo (valor que o documento não sustenta) ou erro intermitente na chamada (tempo esgotado, limite de requisições, provedor indisponível). Um novo processamento resolve sem envolver o operador.
- **Opções:** (A) sem retry: toda falha vai direto para o comportamento da regra; (B) retry com histórico das tentativas no JSON do operador; (C) até 2 retries por tipo, com o histórico só no log técnico.
- **Decisão:** C. O retry é etapa do processamento, separada do comportamento das regras; cada tentativa (motivo, resposta do modelo, resultado) fica registrada no log técnico do documento. Alucinação: disparada só por R-GRD-01 e R-GRD-02 (valor sem respaldo no documento); a nova chamada informa o problema e pede o trecho de cada valor. A R-REQ-03 (campo que não se aplica à classe veio preenchido) não dispara retry: o valor costuma estar no documento, e o retry poderia apagar a prova de uma classificação errada (doc 03). Falha na chamada: repete a mesma chamada, com espera crescente; se persistir, revisão humana (R-PRC-01).
- **Por quê / custo:** menos revisões causadas por erro passageiro, com um mecanismo simples. Limitar o retry por alucinação a esses sinais evita insistir em inconsistências que estão no documento ou na base, o que induziria o modelo a inventar. Custo: até 2 chamadas extras por tipo de falha; o operador não vê no JSON que um valor foi corrigido num retry (a informação fica no log técnico).

### D-14 — Grounding verificado pelo código
- **Contexto:** o enunciado exige saber de onde veio cada valor, e valor inventado é o erro mais caro do domínio.
- **Opções:** (A) confiar no valor extraído; (B) pedir ao modelo que verifique a própria citação; (C) o código verifica que o trecho citado existe no documento e contém o valor.
- **Decisão:** C (R-GRD-01 e R-GRD-02), com normalização de formato para datas, decimais e percentuais, e regras próprias para valores derivados (proporção, classe, moeda, tipo de evento).
- **Por quê / custo:** checagem determinística, testável e sem custo de chamada; um modelo verificando a si mesmo compartilha os próprios pontos cegos. Custo: normalização por tipo de campo, e o grounding não prova que o valor pertence ao campo certo (só que está no documento).

### D-15 — Mensagens ao operador centralizadas
- **Contexto:** toda regra de revisão humana ou de alerta gera uma mensagem descritiva, com os valores envolvidos.
- **Opções:** (A) mensagem junto de cada regra; (B) catálogo único, indexado pelo ID da regra.
- **Decisão:** B. Nos documentos, a seção "Mensagens" de `regras.md`; no código, um único arquivo de mensagens com a mesma chave.
- **Por quê / custo:** revisar o tom e o conteúdo de todas as mensagens num lugar só; acrescentar uma regra é acrescentar uma linha. Custo: uma indireção entre a regra e o seu texto.

### D-16 — Taxonomia no nível de tipo de evento do ISO 20022, sem adotar os códigos
- **Contexto:** o ISO 20022 é o padrão de mensagens de eventos corporativos entre custodiantes. Ele classifica os eventos por tipo (`DVCA`, `BONU`, `SPLF`, `SPLR`…) e detalha indicadores e opções em outros níveis.
- **Opções:** (A) adotar os códigos ISO como classes; (B) taxonomia própria, sem relação com o padrão; (C) taxonomia própria no mesmo nível de tipo de evento, sem os indicadores e opções do padrão.
- **Decisão:** C. Quatro das cinco classes têm equivalente direto: `DIVIDENDO` ↔ `DVCA`, `BONIFICACAO` ↔ `BONU`, `DESDOBRAMENTO` ↔ `SPLF`, `GRUPAMENTO` ↔ `SPLR`. O `JCP` não tem equivalente direto, e a prática de mercado varia.
- **Por quê / custo:** mantém a taxonomia compatível com o padrão (um mapeamento futuro é uma tabela de correspondência), sem o custo de validar códigos e a prática de mercado do JCP agora. Custo: a saída não sai em ISO 20022; uma integração exigiria um adaptador.
