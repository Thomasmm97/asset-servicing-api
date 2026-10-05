# Decisões

> Registro das decisões do projeto: contexto, opções, decisão e por quê / custo.
> Alimenta a seção de trade-offs do README.

---

## Escopo da entrega (In)

O que esta entrega faz. Por prazo, Out, Deferred e premissas não foram formalizados: o que não está nesta lista não entra nesta entrega (ex.: API, interface para o operador, banco de dados).

- Execução em lote, pela linha de comando, sobre a pasta `entrada/documentos/`.
- Leitura de PDF nativo e OCR para escaneado, com confiança por palavra (D-08).
- Extração dos campos mínimos do enunciado, com evidência (página e trecho) por campo.
- Classificação na taxonomia de `dominio.md`.
- Validação pelas regras de `regras.md`, incluindo a base de referência, via tools.
- Confiança por campo e roteamento para revisão humana, com motivo.
- Saída: um objeto JSON por documento + relatório de exceções do lote, num único arquivo (D-31).
- Script de avaliação contra `tests/evals/gabarito.csv`.

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

### D-08 — Documento escaneado: confiança do OCR por campo
- **Contexto:** o doc 07 é escaneado. Mandar todo escaneado para revisão elimina o risco de leitura, mas aumenta a carga do operador.
- **Opções:** (A) todo escaneado vai para revisão; (B) escaneado passa pelas mesmas regras, e a confiança que o OCR atribui às palavras de cada valor entra na confiança do campo: abaixo do limite, o campo vai para revisão humana.
- **Decisão:** B. O limite é definido no modelo de confiança (Fase 2) e calibrado na Fase 4. O gabarito assume leitura correta e confiança acima do limite: doc 07 sem revisão.
- **Por quê / custo:** usa um sinal que só o OCR tem (a certeza da leitura de cada palavra), campo a campo, em vez de tratar o documento inteiro como suspeito. Restrição para a Fase 3: a ferramenta de OCR precisa devolver a confiança e a posição de cada palavra, para o código achar as palavras do valor dentro da citação; leitura só por visão do LLM não dá esse sinal. Custo: calibrar o limite; uma leitura errada com confiança alta continua dependendo do grounding e das checagens cruzadas (ex.: R-VAL-02).

### D-09 — Convenções de valor do gabarito
- **Contexto:** sem formato fixo, o eval acusa diferenças que são só de formato.
- **Opções (proporção, o ponto mais ambíguo):** (A) como no documento (`1:20`); (B) fator (`1.05`); (C) `antes:depois` (`20:21`).
- **Decisão:** uma linha por evento; datas em ISO 8601; decimais com ponto e todas as casas do documento; alíquota como fração (`0.175`); moeda em ISO 4217 (`BRL`); proporção `antes:depois` (grupamento `10:1`, bonificação `20:21`), confirmada na Fase 1 (R-PRO-01 e R-PRO-02); papel das datas conforme a tabela "Papel das datas por classe" de `regras.md`, seção 4 (ex.: doc 06, data-base → `data_com` e início da negociação grupada → `data_ex`; doc 08, crédito das ações → `data_pagamento`); vazio = ausente, `n/a` = não se aplica; motivo da revisão como ID da regra (`R-CLS-01`; mais de um separado por `;`).
- **Por quê / custo:** comparação exata e sem ambiguidade ("1:20" na bonificação pode ser lido nos dois sentidos; `antes:depois` não). Com o ID da regra, o eval confere se o documento foi para revisão pelo motivo certo, e não só se foi. Custo: o gabarito depende dos IDs das regras; renumerar uma regra exige atualizar o gabarito.

### D-10 — Entradas versionadas no repositório, fora de `tests/evals/`
- **Contexto:** os PDFs e o golden record estavam em `tests/evals/`, como se fossem fixtures de avaliação, e as pastas originais estavam no `.gitignore`.
- **Opções:** (A) manter em `tests/evals/`; (B) fora do repositório, com instrução no README; (C) versionados em `documents/` e `golden_records/`.
- **Decisão:** C. `tests/evals/` guarda só o que serve para avaliar o sistema (gabarito e script de eval). Na Fase 5, as duas entradas foram reunidas em `entrada/` (`entrada/documentos/` e `entrada/golden_records.csv`, sem espaço no nome), espelhando `saida/`.
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
- **Decisão:** C. O retry é etapa do processamento, separada do comportamento das regras; cada tentativa (motivo, resposta do modelo, resultado) fica registrada no log técnico do documento. Alucinação: disparada só por R-GRD-01 e R-GRD-02 (valor sem respaldo no documento); a nova chamada informa o problema e pede o trecho de cada valor. A R-REQ-03 (campo que não se aplica à classe veio preenchido) não dispara retry: o valor costuma estar no documento, e o retry poderia apagar a prova de uma classificação errada (doc 03). Falha na chamada: repete a mesma chamada, com espera crescente; se persistir, o documento sai com status `ERRO` e código `FALHA_MODELO` (D-18; antes, revisão humana pela R-PRC-01).
- **Por quê / custo:** menos revisões causadas por erro passageiro, com um mecanismo simples. Limitar o retry por alucinação a esses sinais evita insistir em inconsistências que estão no documento ou na base, o que induziria o modelo a inventar. Custo: até 2 chamadas extras por tipo de falha; o operador não vê no JSON que um valor foi corrigido num retry (a informação fica no log técnico).
- **Evidência (teste de estocasticidade, 400 execuções, D-29):**
  - falha na chamada: 13 chamadas receberam erro 429 na primeira tentativa (limite de 20 requisições por minuto da conta no OpenRouter), e o retry com espera resolveu todas; nenhuma execução terminou em `FALHA_MODELO`;
  - alucinação: 33 execuções tiveram citações que o grounding não achou no texto, e o retry com o problema informado resolveu todas.

  Cada caso está no trace da execução (D-30).

### D-14 — Grounding verificado pelo código
- **Contexto:** o enunciado exige saber de onde veio cada valor, e valor inventado é o erro mais caro do domínio.
- **Opções:** (A) confiar no valor extraído; (B) pedir ao modelo que verifique a própria citação; (C) o código verifica que o trecho citado existe no documento e contém o valor.
- **Decisão:** C (R-GRD-01 e R-GRD-02), com normalização de formato para datas, decimais e percentuais, e regras próprias para valores derivados (proporção, classe, moeda, tipo de evento).
- **Por quê / custo:** checagem determinística, testável e sem custo de chamada; um modelo verificando a si mesmo compartilha os próprios pontos cegos. Custo: normalização por tipo de campo, e o grounding não prova que o valor pertence ao campo certo (só que está no documento); esse risco é reduzido, não eliminado, pelo sinal "rótulo do campo na citação" (D-20).

### D-15 — Mensagens ao operador centralizadas
- **Contexto:** toda regra de revisão humana ou de alerta gera uma mensagem descritiva, com os valores envolvidos.
- **Opções:** (A) mensagem junto de cada regra; (B) catálogo único, indexado pelo ID da regra.
- **Decisão:** B. Nos documentos, a seção "Mensagens" de `regras.md`, com a descrição curta de cada regra (mostrada em `regras_aprovadas` quando ela passa), a mensagem (mostrada no campo quando ela falha) e as mensagens dos erros de processamento (D-18); no código, um único arquivo de textos com a mesma chave.
- **Por quê / custo:** revisar o tom e o conteúdo de todas as mensagens num lugar só; acrescentar uma regra é acrescentar uma linha. Custo: uma indireção entre a regra e o seu texto.

### D-16 — Taxonomia no nível de tipo de evento do ISO 20022, sem adotar os códigos
- **Contexto:** o ISO 20022 é o padrão de mensagens de eventos corporativos entre custodiantes. Ele classifica os eventos por tipo (`DVCA`, `BONU`, `SPLF`, `SPLR`…) e detalha indicadores e opções em outros níveis.
- **Opções:** (A) adotar os códigos ISO como classes; (B) taxonomia própria, sem relação com o padrão; (C) taxonomia própria no mesmo nível de tipo de evento, sem os indicadores e opções do padrão.
- **Decisão:** C. Quatro das cinco classes têm equivalente direto: `DIVIDENDO` ↔ `DVCA`, `BONIFICACAO` ↔ `BONU`, `DESDOBRAMENTO` ↔ `SPLF`, `GRUPAMENTO` ↔ `SPLR`. O `JCP` não tem equivalente direto, e a prática de mercado varia.
- **Por quê / custo:** mantém a taxonomia compatível com o padrão (um mapeamento futuro é uma tabela de correspondência), sem o custo de validar códigos e a prática de mercado do JCP agora. Custo: a saída não sai em ISO 20022; uma integração exigiria um adaptador.

---

## Fase 2 — Contrato de saída

### D-17 — Formato da saída: extração plana, saída só com as chaves da classe
- **Contexto:** cada classe tem campos diferentes (provento em dinheiro × evento em ações), e o operador precisa auditar cada valor sem reabrir o documento.
- **Opções:** (A) objeto único, com todos os campos em todo documento e os que não se aplicam marcados; (B) formato por classe já na extração do modelo; (C) híbrido: o modelo extrai tudo num objeto plano, e o código monta a saída só com as chaves da classe.
- **Decisão:** C. `tipo_evento` fica no topo, porque define as chaves de `campos`. Os campos se agrupam em `emissor` (razão social, CNPJ) e `ativo` (ISIN, ticker, classe), seguidos das datas e dos valores da classe; `INDETERMINADO` leva as chaves comuns e todo campo extraído com valor. Cada campo traz valor, citação (no tipo de evento, citações), confiança, `revisao_humana`, motivos e alertas; os campos de emissor e ativo trazem também o resultado da base de referência, e os valores monetários, a moeda. Sem status por campo, ao contrário do que sugere a metodologia: as chaves por classe eliminam o "não se aplica", e os motivos explicam "não encontrado" e "adiado". Schema completo em `contrato.md`.
- **Por quê / custo:** a extração plana preserva a prova de uma classificação errada: no doc 03, um JCP classificado como `DIVIDENDO` teria o valor líquido extraído, e a R-REQ-03 dispararia em vez de o valor sumir (na opção B, ele nem seria pedido ao modelo). A saída por classe mostra ao operador só o que importa para aquele evento. Custo: uma etapa de montagem no código; um valor que não se aplica à classe não tem chave e aparece só na mensagem da R-REQ-03 (no `tipo_evento`) e no log técnico.

### D-18 — Status do documento e erro de processamento
- **Contexto:** o JSON precisa dizer se o registro pode seguir para os processos seguintes e, quando o documento não pode ser processado (falha na chamada ao modelo, PDF corrompido, OCR), o que aconteceu. Num arquivo não existe um canal separado para o status, como o código HTTP no cabeçalho de uma resposta.
- **Padrões considerados:** código HTTP + corpo (o status vai no cabeçalho; num arquivo, copiar códigos numéricos seria imitação sem transporte); RFC 9457, Problem Details (objeto de erro com tipo e detalhe, presente só quando há erro); JSend (`status` com `success`, `fail` para dados com problema e `error` para exceção no processamento, com `message` e `code`).
- **Opções:** (A) `revisao_humana` booleano + objeto `erro`: mantinha o booleano decidido antes, mas criava duas chaves dependentes (erro exige `revisao_humana: true`), e quem lesse só o booleano não distinguiria revisar de reprocessar; (B) envelope com `processado` + `erro` + `revisao_humana`: padrão conhecido, mas são três chaves que podem se contradizer; (C) híbrido: `status` de três estados, como no JSend, + objeto `erro` enxuto, como no Problem Details.
- **Decisão:** C. `status`: `APROVADO` (success), `REVISAO_HUMANA` (fail: o documento foi lido, mas os dados têm problema) ou `ERRO` (error: o documento não pôde ser processado). `erro`: `null`, ou `{codigo, mensagem}`, com código de uma lista fechada (`FALHA_MODELO`, `PDF_ILEGIVEL`, `FALHA_OCR`, `ERRO_INTERNO`) e mensagem do catálogo (D-15); com erro, `tipo_evento` e `campos` saem `null`. O `status` substitui o booleano `revisao_humana` no nível do documento; nos campos, o booleano continua. A falha na chamada ao modelo, antes a R-PRC-01 com revisão humana, passa a ser o código `FALHA_MODELO`.
- **Por quê / custo:** uma única chave responde "pode seguir?" (só `APROVADO` segue) e "o que fazer" (revisar ou reprocessar), e o código do erro permite filtrar e tratar por tipo sem ler o texto. Custo: o eval traduz o `status` para a coluna `revisao_humana` do gabarito (`REVISAO_HUMANA` e `ERRO` → sim); um tipo novo de erro é uma linha a mais na lista de códigos.

### D-19 — Agregação da confiança por campo: o mínimo
- **Contexto:** o modelo gera cada valor em vários tokens, e o OCR lê cada valor em uma ou mais palavras; cada token e cada palavra têm a sua probabilidade. O logprob do modelo é normalizado para 0–1 (probabilidade = e^logprob; ex.: −0,01 → 0,990), e a confiança do OCR também. O limite de revisão (R-CNF-01 e R-CNF-02) precisa de um número só por campo.
- **Opções:** (A) probabilidade conjunta (produto); (B) média; (C) mínimo. Exemplo com limite de 0,95 (provisório); o número de tokens de cada valor depende do tokenizador:

  | Agregação | Fórmula | CNPJ (10 tokens a 0,99) | `BRL` (1 token a 0,99) | CNPJ (9 tokens a 0,999 + 1 a 0,70) |
  |---|---|---|---|---|
  | Conjunta | Produto: 0,99 × 0,99 × … | 0,99¹⁰ = 0,904: revisão ¹ | 0,99 | 0,694: revisão |
  | Média | Soma ÷ quantidade | 0,99 | 0,99 | 0,969: passa ² |
  | Mínimo | O menor token | 0,99 | 0,99 | 0,70: revisão ³ |

  ¹ A conjunta pune o tamanho, não a dúvida: cada token tem 99% de certeza, mas o produto de 10 deles fica abaixo do limite, enquanto um valor de 1 token, igualmente certo, passa.
  ² A média dilui um dígito duvidoso, que é justamente o erro que importa.
  ³ O mínimo responde à pergunta certa (existe algum pedaço do valor de que o modelo não tem certeza?), sem depender do tamanho do valor.
- **Decisão:** C, para as palavras do OCR; vale também para os tokens do modelo, se o logprob for ligado (hoje desligado, D-20).
- **Por quê / custo:** basta um dígito incerto para o valor estar errado. Custo: o mínimo é severo, porque um único token ou palavra abaixo do limite manda o campo para revisão; em escaneados, isso pode aumentar a fila (calibrar na Fase 4).

### D-20 — Modelo de confiança: limites, três níveis e confirmações
- **Contexto:** o enunciado pede níveis de confiança justificados e roteamento dos campos de baixa confiança. O sinal medido por campo é a legibilidade do texto (confiança do OCR, só em escaneados, agregada pelo mínimo, D-19). O logprob do modelo foi considerado como segundo sinal e ficou desligado (ver "Revisão" abaixo e D-26).
- **Opções:** (A) três níveis calculados por sinais; (B) dois níveis (ALTA/BAIXA): um valor de fonte única viraria ALTA (exagera) ou BAIXA (os 8 documentos iriam para a fila); (C) nota numérica de 0 a 1 por soma ponderada: com 8 documentos, os pesos seriam arbitrários e a precisão, falsa; (D) autoavaliação declarada pelo modelo: mal calibrada e contrária ao princípio "confiança se calcula, não se pergunta".
- **Decisão:** A, com os limites como porta de entrada:
  - **BAIXA:** OCR abaixo de 0,70 (D-23) → revisão humana pela R-CNF-01.
  - **ALTA:** acima dos limites e pelo menos uma confirmação: rótulo do campo na citação (o rótulo mais próximo do valor é o do campo, conferido pelo código), base de referência, R-DAT-03 (data com e data ex) ou R-VAL-02 (bruto, alíquota e líquido do JCP); no tipo de evento, dois ou mais sinais de natureza.
  - **MÉDIA:** acima dos limites, sem confirmação. Segue automático: todo documento do lote tem ao menos um campo de fonte única, e mandar MÉDIA para revisão levaria os 8 para a fila. É onde o risco residual se concentra, e o eval acompanha.
  - Uma citação por campo (no tipo de evento, várias). A concordância entre tabela e corpo como confirmação foi considerada e deixada de fora: simplifica, e o rótulo cobre o erro típico (valor real no campo errado).
  - A confiança mede a leitura; a coerência é das regras. No doc 05, a data de pagamento sai ALTA e vai para revisão pela R-DAT-02: o operador sabe que a leitura está certa e que o erro está no aviso.
- **Mitigações:** o prompt pede a menor citação (a linha da tabela com o rótulo; senão, a menor frase com rótulo e valor); o código confere o rótulo mais próximo; um sinônimo ausente da lista só rebaixa para MÉDIA, nunca manda para revisão.
- **Por quê / custo:** cada nível tem causa verificável e justificativa legível. Custo:
  - limite sem calibração estatística com 8 documentos (decidido por critério, vigiado pela métrica de erros não roteados);
  - um aviso que se contradiz entre tabela e corpo passa sem ser notado nos campos sem outra checagem cruzada (proporção, custo atribuído, data de aprovação), e, em escaneados, um dígito mal lido numa das ocorrências só é pego pela R-CNF-01; data com e data ex, valores do JCP e identificadores seguem cobertos pela R-DAT-03, pela R-VAL-02/03 e pela base;
  - evolução não feita: citações múltiplas com uma regra "valor da tabela = valor do corpo".
- **Revisão (logprob desligado):** a primeira versão tinha dois sinais medidos, o OCR e o logprob do modelo (probabilidade mínima dos tokens do valor, limite de 0,95, R-CNF-02). Na reflexão sobre o que cada mecanismo pega:

  | Tipo de erro | Já coberto por | O logprob acrescenta? |
  |---|---|---|
  | Valor inventado ou dígito transcrito errado | grounding literal (D-14, D-24) | Não |
  | OCR leu um dígito errado | confiança do OCR, regras cruzadas | Não: o modelo copia com certeza o que o OCR leu |
  | Valor real no campo errado | rótulo na citação, regras cruzadas | Pouco |
  | Escolha entre candidatos parecidos, classificação ambígua, valor derivado | R-CLS-01, sinais de natureza, R-PRO-02 | Sim: mede a hesitação do modelo |

  O logprob só traz sinal único onde o modelo interpreta ou escolhe; na cópia literal, que é a maioria dos campos depois da D-24, os tokens ficam em 1,0. E mantê-lo exigiria um modelo sem raciocínio, justamente o tipo que erra mais onde o logprob seria útil. Decisão: logprob desligado, modelo de raciocínio (D-26); a R-CNF-02 fica documentada e desligada, e `confianca.modelo` sai `null`. Custo: perde-se a medida de hesitação na classificação, que fica a cargo da R-CLS-01, da exigência de dois sinais de natureza para ALTA e do `INDETERMINADO` com motivos fechados.

### D-21 — O documento é a unidade de roteamento
- **Contexto:** os motivos de revisão ficam nos campos, mas os processos seguintes tratam o evento inteiro.
- **Opções:** (A) roteamento por campo: os campos aprovados seguem e os outros esperam; (B) qualquer campo em revisão leva o documento inteiro para revisão, e a marcação do campo mostra onde olhar.
- **Decisão:** B. O `status` é derivado pelo código: `ERRO` se o processamento falhou; senão `REVISAO_HUMANA` se algum campo (ou o `tipo_evento`) tem `revisao_humana: true`; senão `APROVADO`.
- **Por quê / custo:** não existe provento aprovado em parte: sem a data de pagamento ou com a classe em dúvida, o cálculo do evento inteiro não pode seguir. Custo: o operador abre o documento inteiro, guiado pelas marcações dos campos.

---

## Fase 3 — Arquitetura

### D-22 — Leitura de PDF nativo: PyMuPDF
- **Contexto:** 7 dos 8 avisos têm camada de texto. A leitura precisa devolver o texto na ordem certa (rótulo junto do valor, para a checagem de rótulo da D-20), a posição de cada palavra e, no escaneado, a página como imagem para o OCR.
- **Opções testadas nos 7 nativos:**

  | Biblioteca | Tempo | Valores do gabarito achados | Posição por palavra | Observação |
  |---|---|---|---|---|
  | PyMuPDF | 22 ms | 49/49 | sim | Mantém inteiro o rótulo de várias linhas ("Imposto de Renda Retido na Fonte" → "17,5%") |
  | pdfplumber | 138 ms | 49/49 | sim | Rótulo e valor na mesma linha, mas quebra o rótulo de várias linhas ao meio ("Imposto de Renda Retido na 17,5% Fonte") |
  | pypdf | 33 ms | 49/49 | não | Só texto |

  Também considerados: mandar o PDF direto ao modelo (o grounding precisa do texto local de qualquer forma, e o modelo e o código passariam a ver textos diferentes) e o Docling (D-23).
- **Decisão:** PyMuPDF.
- **Por quê / custo:** os três acertam igual; o PyMuPDF é o mais rápido, dá a posição de cada palavra, não quebra o rótulo de várias linhas (o que atrapalharia a checagem do rótulo mais próximo) e renderiza a página para o OCR, sem uma segunda dependência. O pypdf não dá posição por palavra. Custo: licença AGPL (aceitável num case; num produto fechado, exigiria licença comercial ou a troca pelo pdfplumber); rótulo e valor saem em linhas seguidas, não na mesma linha, o que a normalização de espaços do grounding resolve.

### D-23 — OCR: Tesseract, com limite de 0,70
- **Contexto:** o doc 07 é escaneado. A D-08 exige confiança por palavra, e a D-20 exige o rótulo junto do valor na citação.
- **Opções testadas no doc 07:**

  | Ferramenta | Tempo | Valores do gabarito achados | Confiança | Tabela |
  |---|---|---|---|---|
  | Tesseract 5.5 (`pytesseract`, 300 dpi) | 1,8 s | 9/9 | Por palavra: 0,74 a 0,96 nos valores | Linha preservada ("Data-base (data com) ...... 22/06/2026") |
  | Docling 2.133 (motor RapidOCR) | 184 s na 1ª execução, com download de modelos | 9/9 | Só por página (OCR 0,98; layout 0,83) | Leu por colunas (rótulos de um lado, valores do outro) e perdeu o "J" de "Juros" |

  Considerados sem teste: EasyOCR e PaddleOCR (pesados), serviços em nuvem (credenciais, custo, dados saem do ambiente), visão do modelo (sem confiança de OCR).
- **Decisão:** Tesseract, com o limite da R-CNF-01 em 0,70.
- **Por quê / custo:** é o único que entrega o que a D-08 e a D-20 exigem: confiança por palavra e o rótulo junto do valor. Usar o Tesseract como motor dentro do Docling não resolveria, porque a confiança continua por página e a leitura, por colunas. Limite: as leituras corretas do doc 07 ficaram entre 0,74 (o ISIN, com o parêntese grudado na palavra) e 0,96; com 0,95, cinco campos lidos certo iriam para revisão, e 0,70 fica logo abaixo da menor leitura correta. Custo: calibrado com um único escaneado, e a confiança do Tesseract é uma escala própria, não uma probabilidade; uma leitura errada com confiança acima de 0,70 passa pela R-CNF-01 e fica a cargo do grounding e das checagens cruzadas; é preciso instalar o Tesseract com o idioma português (`brew install tesseract tesseract-lang`).

### D-24 — O modelo copia o valor literal; o código normaliza
- **Contexto:** o contrato exige formatos fixos (D-09: datas ISO, decimais com ponto e todas as casas, alíquota como fração). No teste com o `gpt-4o-mini`, pedir o valor já normalizado fez o modelo devolver `0.4275` para "R$ 0,4275000000": cortou os zeros, e o último token saiu com probabilidade 0,562, por indecisão de formato, não de leitura. O `gpt-4o` acertou o mesmo formato com probabilidade 1,0, mas a questão de desenho continua.
- **Opções:** (A) o modelo devolve o valor já normalizado, e o grounding converte o valor de volta para as formas do documento antes de procurá-lo no trecho; (B) o modelo copia o valor como está no documento ("0,4275000000", "12/06/2026"), e o código normaliza para o formato do contrato.
- **Decisão:** B para valores literais (identificadores, datas, valores, alíquota). Valores derivados (proporção, classe, moeda, tipo de evento) continuam vindo do modelo já interpretados, conferidos pelas regras de derivação da R-GRD-02.
- **Por quê / custo:** decisões de formato saem do modelo (com logprobs, elas também baixariam a probabilidade sem ter relação com a leitura); o grounding vira uma comparação literal (mais simples e mais forte); as convenções da D-09 ficam garantidas por código testável, sem depender de o modelo obedecer ao prompt; um literal que o normalizador não entende é um erro claro, que vai para revisão. Na opção A, o grounding precisaria gerar todas as formas possíveis de cada valor (12/06/2026, 12 de junho de 2026…) e erros de formato do modelo virariam divergência com o gabarito. Custo: um normalizador por tipo de campo (data, inclusive por extenso; decimal; percentual), que já existiria de qualquer forma na opção A, só que no sentido inverso.

### D-25 — Cache de prompt do provider e paralelismo entre documentos
- **Contexto:** o lote e o eval fazem várias chamadas ao modelo com a mesma parte fixa (instruções, taxonomia, schema, rótulos) e textos de documento diferentes.
- **Opções:** (A) chamadas em série, sem cuidado com o cache; (B) tudo em paralelo desde a primeira chamada; (C) prompt com a parte fixa primeiro e o documento por último; a primeira chamada em série, para gravar o prefixo no cache do provider, e as demais em paralelo (`concurrent.futures.ThreadPoolExecutor`).
- **Decisão:** C, no lote e no eval. Na OpenAI, o cache de prompt é automático para prefixos idênticos de 1.024 tokens ou mais (não há `cache_control` explícito, que é do Claude e do Gemini); o log registra `cached_tokens` de cada chamada para provar o acerto. Dentro de um documento, as etapas continuam em série, porque cada uma depende da anterior. O cache local de respostas (reprodutibilidade e clone limpo sem chave) é outra coisa e continua.
- **Por quê / custo:** na opção B, as chamadas simultâneas chegariam antes de o prefixo estar no cache e pagariam o prompt inteiro; com C, a primeira paga e as demais reaproveitam, com menor custo e latência. As chamadas são de rede e o Tesseract roda em outro processo, então threads bastam. Custo: número de workers configurável por causa do limite de requisições (o backoff da D-13 continua); gravação atômica no cache local (arquivo temporário + renomeação), porque várias threads escrevem ao mesmo tempo; saída ordenada pelo nome do documento, para o resultado não depender da ordem de término.

### D-26 — Modelo: `openai/gpt-5.6-luna` pelo OpenRouter
- **Contexto:** o modelo extrai, classifica e chama as ferramentas de validação. A chave disponível é do OpenRouter (API compatível com o SDK da OpenAI).
- **Opções testadas:** (A) `openai/gpt-4o-mini`: devolve logprobs, mas cortou os zeros de "0,4275000000" quando pedimos o valor normalizado; (B) `openai/gpt-4o-2024-11-20`: devolve logprobs e manteve o formato; (C) `openai/gpt-5.6-luna`: modelo de raciocínio, mais capaz e mais barato (US$ 0,20 / 1,20 por milhão de tokens), sem logprobs ("logprobs are not supported with reasoning models"); (D) híbrido: `gpt-4o` na extração e `luna` na validação.
- **Teste no doc 03** (o caso mais difícil: o título diz "Dividendos", a natureza é JCP), com saída estruturada e pedido de logprobs:

  | Modelo | Logprobs na prática | Classificação | Tempo | US$ por milhão de tokens (entrada / saída) |
  |---|---|---|---|---|
  | `gpt-5.6-luna` | não | JCP ✓ | 2,4 s | 0,20 / 1,20 |
  | `gpt-4o-2024-11-20` | sim | JCP ✓ (probabilidade de J = 1,0) | 1,3 s | 2,50 / 10,00 |
  | `qwen3.7-plus` | sim | JCP ✓ (J = 1,0) | 35,5 s | 0,32 / 1,28 |
  | `deepseek-v4-pro` | sim, misturados com tokens especiais | JCP ✓ | 13,0 s | 0,21 / 0,42 |
  | `grok-4.3` | não (anunciado pelo OpenRouter, não devolvido) | JCP ✓ | 5,5 s | 1,25 / 2,50 |
  | `gpt-oss-120b` | sim | DIVIDENDO ✗ (J 0,56 × D 0,39) | 2,8 s | 0,04 / 0,17 |

  Um caso só, não é benchmark. Os modelos fortes acertaram com probabilidade 1,0, e o logprob só mostrou hesitação no modelo fraco que errou. Todos copiaram os valores literais exatamente (D-24).
- **Decisão:** C, em todas as etapas, com a versão no `config.py`.
- **Por quê / custo:** o risco que sobra depois do grounding literal, do rótulo e das regras está nas decisões de interpretação (classificação, escolha entre candidatos, valores derivados), exatamente onde um modelo de raciocínio é mais forte. O híbrido seria mais um modelo para configurar e defender, com pouco ganho, porque o código já impõe as ferramentas que faltarem. Custo: sem logprobs (D-20, revisão); modelos de raciocínio não aceitam temperatura 0, então a reprodutibilidade fica a cargo do cache local de respostas (D-25); tokens de raciocínio aumentam latência e custo.

### D-27 — Três ferramentas, sem argumentos de valor
- **Contexto:** o requisito 3 do enunciado pede validação com tool calling, e o princípio é "o LLM extrai, o código decide". O primeiro desenho tinha 6 ferramentas, que recebiam os valores como argumentos.
- **Opções:** (A) 6 ferramentas, uma por grupo de regras, recebendo os valores; (B) 3 ferramentas sem argumentos de valor (o código injeta os valores conferidos), com R-REQ no código.
- **Decisão:** B: `validar_identificacao` (R-ID + R-IDF), `validar_datas` (R-DAT) e `validar_valores_e_proporcao` (R-VAL ou R-PRO, conforme a classe). R-GRD, R-REQ, R-CLS e R-CNF rodam no código. O código chama as ferramentas que o modelo não chamou e registra isso no trace.
- **Por quê / custo:** um modelo repassando valores pode alterá-los no argumento, e essa alucinação escaparia do grounding; a R-REQ pediria ao modelo que repetisse quais campos ele mesmo extraiu, informação que o código já tem; fundir R-ID com R-IDF (mesmos campos) e R-VAL com R-PRO (a regra já sabe qual grupo vale para a classe) tira do modelo escolhas que ele poderia errar. Custo: a parte agêntica fica fina (o modelo orquestra, o código garante dados e cobertura), o que é intencional.

### D-28 — Agente sem framework
- **Contexto:** o agente é um laço de tool calling com 3 ferramentas, no máximo 3 rodadas, e cobertura imposta pelo código.
- **Opções:** (A) LangChain ou LangGraph; (B) PydanticAI; (C) o SDK oficial da OpenAI (pacote `openai`, a biblioteca cliente que faz as chamadas HTTP à API, compatível com o OpenRouter), com o laço escrito no código.
- **Decisão:** C.
- **Por quê / custo:** o laço tem cerca de 40 linhas, e cada uma é explicável e depurável ao vivo. O LangGraph brilha em grafos com estado, desvios e checkpoints, que o pipeline linear não tem; o LangChain acrescenta camadas e dependências; o PydanticAI seria a alternativa mais leve, mas é mais uma API para defender. O enunciado pede um agente "code-first". Custo: retry, cache e rastreamento são escritos à mão (poucas linhas cada).

### D-29 — Teste de estocasticidade: 50 execuções por documento, zero falhas
- **Contexto:** o modelo de raciocínio não aceita temperatura 0 (D-26), então duas execuções podem dar resultados diferentes. O cache local esconderia essa variação.
- **Opções:** (A) uma execução por documento, com cache; (B) N execuções por documento, sem o cache local, com critério de falha.
- **Decisão:** B, com N = 50 (decisão do usuário; era 100, reduzido por tempo; configurável com `EXECUCOES`). Cada documento é lido uma vez (a leitura é determinística) e processado N vezes; a primeira execução vai em série (para o cache do provider) e as demais em paralelo, com 20 workers. A extração vai sem o cache local; o agente usa um cache temporário, fora do repositório, porque não muda o resultado (D-27): se a extração variar, os valores mudam e o agente é chamado de novo. `-k` escolhe os documentos. O teste de cada documento passa só se nenhuma execução falhar em alguma métrica com meta do `contrato.md`, seção 9: erro não roteado, valor inventado, classificação, roteamento, motivo ou acurácia por campo. Fica fora da suíte padrão (`pytest -m estocastico`). Na suíte padrão, `tests/evals/test_lote.py` roda cada documento uma vez, pelo cache.
- **Por quê / custo:** zero falhas em 50 execuções limita a taxa real de falha a cerca de 6%, com 95% de confiança (regra de três: 3/n), um argumento que uma execução só não dá. Custo: o limite da conta é de 20 requisições por minuto (medido: de 60 chamadas simultâneas, 20 passaram e 40 tiveram 429), então uma rodada completa leva uns 42 minutos com o agente ao vivo e uns 21 com o agente pelo cache, por menos de US$ 1. O cache do agente deixa de medir falhas técnicas na chamada do agente; elas são cobertas pelo retry (D-13) e não ocorreram nas duas rodadas com o agente ao vivo.
- **Resultado (04/10/2026, N = 50, agente ao vivo, 400 execuções):** 397 sem falha; meta atingida em 6 dos 8 documentos. As 3 falhas foram para revisão humana, então nenhum erro passou sem revisão:
  - 2 no doc 01: o modelo leu como alíquota os 10% de IR por beneficiário; a R-REQ-03 mandou o documento para revisão sem necessidade (eram 6 em 50 antes do ajuste na descrição da alíquota);
  - 1 no doc 08: a classe veio vazia, e a R-REQ-01 acrescentou um motivo ao documento, que já ia para revisão. O trace não guarda a resposta do modelo, então a causa não foi confirmada.

  Zero erros de processamento e zero 429 (com o limitador); o retry resolveu 36 alucinações e 7 timeouts (o computador entrou em repouso no meio da rodada). A correção (descrição da alíquota e mensagem do retry) fica como próximo passo: mudar o prompt na última hora arriscaria o eval 8/8 e invalidaria o cache.

### D-30 — Rastreamento por documento
- **Contexto:** é preciso reconstruir o caminho de um documento (o que foi lido, o que o modelo respondeu, cada retry, cada ferramenta, o que decidiu o roteamento) sem misturar isso no JSON do operador.
- **Opções:** (A) log de texto; (B) trace JSONL por documento; (C) OpenTelemetry; (D) serviço externo (Langfuse, LangSmith, Logfire).
- **Decisão:** B: `saida/traces/<documento>.jsonl`, uma linha por etapa (`trace_id`, etapa, início, duração, tentativa, modelo e prompt de sistema de cada chamada, cache, `cached_tokens`, ferramenta e quem a chamou, resumo de entrada e saída, erro), gravada por um gerenciador de contexto. O `trace_id` vai também no JSON do operador.
- **Por quê / custo:** estruturado (dá para filtrar e somar tempos por etapa), sem dependência e sem dados saindo do ambiente. O OpenTelemetry seria o padrão de mercado, mas é configuração demais para 8 documentos; os serviços externos exigem conta e enviam os dados para fora. Custo: o formato é próprio; migrar para OpenTelemetry depois é trocar o gerenciador de contexto.

### D-31 — Saída num único JSON do lote, com o relatório de exceções como campo
- **Contexto:** o enunciado pede "um JSON por documento + um relatório de exceções curto", e o relatório é por lote.
- **Opções:** (A) um arquivo por documento + um arquivo de relatório; (B) um único `saida/lote.json`, com o campo `relatorio_excecoes` e um objeto por documento em `documentos`; (C) as duas formas.
- **Decisão:** B (decisão do usuário). O relatório traz os totais e só os documentos com exceção; o registro completo de cada documento fica em `documentos`.
- **Por quê / custo:** cada documento continua sendo um objeto JSON completo, e o enunciado não proíbe o relatório dentro do mesmo JSON; um arquivo só é mais fácil de consumir e de versionar, com menos código de escrita. Custo: uma leitura literal de "um JSON por documento" esperaria um arquivo por documento; a resposta está aqui e no README.

---

## Notas para as próximas fases

Lembretes que nasceram numa fase e só são usados numa fase seguinte. Sai daqui quando for consumido.

- **Fase 3 (arquitetura):** a ferramenta de OCR precisa devolver a confiança e a posição de cada palavra, para o código achar as palavras do valor dentro da citação e calcular a confiança do campo (D-08, R-CNF-01). Atendida pelo Tesseract (D-23).
- **Fase 3 (arquitetura):** arquivo de rótulos e sinônimos por campo, alimentado pela coluna "Como aparece nos dados" do glossário de `dominio.md`; o prompt pede a menor citação (D-20).
- **Fase 4 (eval):** o eval traduz os nomes do JSON para as colunas do gabarito: `status` → `revisao_humana` (`REVISAO_HUMANA` e `ERRO` → sim, D-18); campos dentro de `emissor` e `ativo` → colunas de mesmo nome, com `emissor.razao_social` → `emissor` e `ativo.classe` → `classe_acao`; `data_credito` da bonificação → `data_pagamento` (D-09); moeda de `valor_bruto` ou `custo_atribuido` → `moeda`; regras dos `motivos` dos campos → `motivo_revisao`.
- **Fase 4 (eval):** risco de sinônimo ausente na lista de rótulos: medir quantos campos caíram para MÉDIA por falta de rótulo e completar a lista (D-20).
