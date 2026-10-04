# Arquitetura — Fase 3

> O menor desenho que cumpre `regras.md` e `contrato.md`. Decisões de origem: D-22 a D-26. Nada é implementado antes da aprovação de módulos, classes, atributos, funções e nomes.

---

## 1. Caso de uso → pipeline

**Caso de uso:** processar o lote de avisos em `documents/` e gerar, para cada documento, um JSON auditável em `saida/`, mais o relatório de exceções.

**Fluxo principal** (por documento):

| # | Etapa | Função | Tipo | Regras | Se der errado |
|---|---|---|---|---|---|
| 1 | Ler o PDF (nativo: camada de texto; escaneado: OCR com confiança e posição por palavra) | `ler_documento` | código | — | `ERRO` (`PDF_ILEGIVEL`, `FALHA_OCR`) |
| 2 | Extrair e classificar numa única chamada estruturada: campos (valor literal + trecho), tipo de evento, sinais de natureza e título | `extrair` | LLM | — | backoff, 2 tentativas → `ERRO` (`FALHA_MODELO`) |
| 3 | Conferir evidências: trecho no documento, valor no trecho, rótulo mais próximo | `verificar_evidencias` | código | R-GRD-01, R-GRD-02 | retry de alucinação (máx. 2) com o problema informado → valor descartado + motivo |
| 4 | Normalizar os literais para o formato do contrato (D-24) | `normalizar_extracao` | código | — | literal não reconhecido → motivo no campo |
| 5 | Validar com tools: o modelo escolhe as ferramentas; o código injeta os valores e impõe a cobertura | `validar` | LLM + código | R-ID, R-IDF, R-DAT, R-VAL, R-PRO | ferramenta não chamada → o código chama; falha na chamada → `FALHA_MODELO` |
| 6 | Campos da classe, classificação e confiança | `validar_campos_da_classe`, `verificar_classificacao`, `calcular_confianca` | código | R-REQ, R-CLS-01/02, R-CNF-01 | — |
| 7 | Montar o registro com as chaves da classe e derivar o status | `montar_registro` | código | D-21 | — |
| 8 | Gravar o JSON; no fim do lote, o relatório de exceções | `gravar_registro`, `gerar_relatorio` | código | — | — |

**Fluxos alternativos:** PDF que não abre → JSON com `ERRO` (etapa 1); escaneado → OCR (etapa 1); valor sem respaldo → retry e, se persistir, descarte com motivo (etapa 3); `INDETERMINADO` → chaves comuns + campos extraídos, revisão pela R-CLS-02 (etapa 7).

**Lote (D-25):** o primeiro documento é processado sozinho, para gravar a parte fixa do prompt no cache do provider; os demais vão em paralelo (`ThreadPoolExecutor`, 20 workers no `config.py`; 20 chamadas simultâneas testadas sem erro de limite, latência de 2,6 a 4,3 s). Dentro de um documento, as etapas são em série. A saída é ordenada pelo nome do documento.

```
documents/*.pdf ── 1º documento em série, demais em paralelo
   │
   ▼
[1 ler_documento] ──► Leitura (texto + palavras com confiança e posição)
   ▼
[2 extrair] ── LLM, saída estruturada, valores literais ──► Extracao (plana)
   ▼
[3 verificar_evidencias] ── falhou? ──► retry com o problema (máx. 2)
   ▼
[4 normalizar_extracao] ──► valores no formato do contrato
   ▼
[5 validar] ── LLM chama tools ⇄ regras (código); o código completa a cobertura
   ▼
[6 classificação + confiança] → [7 montar_registro + status] → [8 saida/*.json + relatório]
```

## 2. Quanto de agente

| Opção | Como funciona | Por que não / por que sim |
|---|---|---|
| A. Pipeline fixo, o código chama tudo | Sem tool calling pelo modelo | Não atende o requisito 3 do enunciado ("usando tool / function calling") |
| **B. Agente na validação, cobertura imposta pelo código** (escolhida) | O modelo recebe os valores e chama as ferramentas que julgar aplicáveis (no máximo 3 rodadas); as ferramentas são as regras determinísticas; ao fim, o código chama as aplicáveis que faltaram e registra isso no log | Atende o requisito e mantém "o LLM extrai, o código decide": os resultados vêm das regras, não da opinião do modelo |
| C. Agente livre (o modelo decide também o roteamento) | — | Contraria "o código decide" e não é auditável |

A extração (etapa 2) é uma única resposta estruturada, sem tools: o grounding precisa da extração completa antes de qualquer validação.

**A classificação acontece na mesma chamada da extração**, e não numa ferramenta nem num agente anterior. Ferramenta é para regra determinística, e classificar é interpretação, que é trabalho do modelo. Um agente de classificação antes da extração custaria uma chamada a mais por documento, as duas chamadas poderiam discordar e, se a extração passasse a pedir só os campos da classe, perderia a prova de uma classificação errada (D-17).

**Prompts:** diretos, com o mínimo necessário: o que extrair, a regra de classificação pela natureza, copiar o valor literal, citar a linha com o rótulo. A parte fixa vem primeiro (cache do provider, D-25).

## 3. Ferramentas (function calling)

Três ferramentas, todas aplicáveis a qualquer classe (D-27). **Nenhuma recebe valores como argumento:** o código injeta os valores já conferidos e normalizados, e o modelo decide só quais validações rodar. Uma alucinação no argumento de uma ferramenta não tem por onde entrar.

| Ferramenta | Regras |
|---|---|
| `validar_identificacao` | R-ID-01 a R-ID-04 (base de referência) + R-IDF-01 a R-IDF-06 (formato e coerência) |
| `validar_datas` | R-DAT-01 a R-DAT-04 |
| `validar_valores_e_proporcao` | R-VAL (DIVIDENDO, JCP, BONIFICACAO) ou R-PRO (BONIFICACAO, DESDOBRAMENTO, GRUPAMENTO), conforme a classe |

R-GRD, R-REQ, R-CLS e R-CNF rodam no código, fora do agente: dependem do texto do documento, do OCR ou de quais campos a extração trouxe, informações que o código já tem e que pedir ao modelo só abriria espaço para erro.

## 4. Stack

| Item | Escolha | Por quê |
|---|---|---|
| Linguagem | Python 3.14 | Versão estável mais recente; sintaxe moderna (`X \| None`, `list[...]`) |
| Provider / modelo | OpenRouter, pelo SDK oficial da OpenAI (pacote `openai`), com `openai/gpt-5.6-luna` | D-26; trocar de modelo é uma linha do `config.py` |
| Agente | Sem framework: laço de tool calling escrito com o SDK, no máximo 3 rodadas | D-28 |
| PDF nativo | PyMuPDF | D-22 (testado contra pdfplumber e pypdf) |
| OCR | Tesseract 5 via `pytesseract`, página a 300 dpi | D-23 (testado contra o Docling); limite de 0,70 |
| Schema | Pydantic v2 | Valida a saída do modelo e gera o JSON; o mesmo modelo é o schema da saída estruturada |
| Calendário B3 | Feriados da B3 (2025–2026) no `config.py`, com a fonte citada e um teste | Explícito, sem dependência (D-12) |
| Cache local | Respostas do modelo em `cache/`, chave = hash(modelo + mensagens + ferramentas); gravação atômica | Reprodutibilidade (o modelo de raciocínio não aceita temperatura 0) e clone limpo sem chave de API; **commitado** |
| Cache do provider | Parte fixa do prompt primeiro, documento por último; `cached_tokens` no log | D-25 |
| Testes | pytest | Um teste por caso "Dado → Então" de `regras.md`; teste de estocasticidade com `pytest -m estocastico` (D-29) |
| Rastreamento | Trace JSONL por documento em `saida/traces/`, com `trace_id` também no JSON do operador | D-30 |

## 5. Camadas e arquivos

As camadas são uma regra de dependência, não pastas: **o domínio nunca importa a camada do modelo**. As regras são testáveis sem chamada de API, e trocar o provider mexe só em `llm.py`.

| Camada | Arquivos |
|---|---|
| Orquestração | `__main__.py`, `pipeline.py` |
| Leitura | `leitura.py` |
| Modelo (LLM) | `llm.py` |
| Domínio (determinístico) | `evidencias.py`, `regras.py`, `montagem.py` |
| Saída | `saida.py` |
| Dados e configuração | `modelos.py`, `config.py`, `mensagens.py` |

```
asset_servicing/
  __main__.py     # CLI: python -m asset_servicing [documents/] [--saida saida/]
  config.py       # modelo, workers, tentativas, limite do OCR, IRRF com vigência, dígitos verificadores, feriados B3, chaves por classe, rótulos e sinônimos
  mensagens.py    # descrição curta + mensagem por regra; mensagens dos erros (D-15)
  modelos.py      # classes Pydantic e enums
  leitura.py      # PDF nativo (PyMuPDF) e escaneado (Tesseract)
  llm.py          # cliente (cache local, backoff, cached_tokens), extração, agente e schemas das ferramentas
  evidencias.py   # grounding (R-GRD), rótulo mais próximo e normalização dos literais (D-24)
  regras.py       # regras de coerência (R-ID, R-IDF, R-DAT, R-VAL, R-PRO, R-REQ, R-CLS), calendário B3 e base de referência
  montagem.py     # confiança (R-CNF), registro com as chaves da classe e status
  saida.py        # JSON, relatório de exceções e trace
  pipeline.py     # um documento; o lote (1º em série, demais em paralelo)
evals/avaliar.py  # métricas contra evals/gabarito.csv
tests/            # test_regras.py, test_evidencias.py, test_montagem.py, test_estocasticidade.py
```

Abaixo disso (uns 5 arquivos), cada arquivo passaria de 500 linhas e ficaria difícil de navegar ao vivo.

## 6. Classes e atributos

**Enums:** `TipoPdf` (NATIVO, ESCANEADO), `Status` (APROVADO, REVISAO_HUMANA, ERRO), `TipoEvento` (6 classes), `MotivoIndeterminado` (FORA_DA_TAXONOMIA, SINAIS_CONFLITANTES, EVIDENCIA_INSUFICIENTE), `NivelConfianca` (ALTA, MEDIA, BAIXA), `BaseReferencia` (CONFERE, DIVERGE, NAO_ENCONTRADO), `Comportamento` (REVISAO_HUMANA, ALERTA), `CodigoErro` (FALHA_MODELO, PDF_ILEGIVEL, FALHA_OCR, ERRO_INTERNO).

**Internas** (não vão para o JSON):
- `Palavra`: `texto`, `pagina`, `inicio`, `fim` (posição no texto), `confianca: float | None` (OCR, 0–1; `None` em nativo).
- `Leitura`: `documento`, `tipo_pdf`, `texto`, `palavras: list[Palavra]`.
- `CampoExtraido`: `valor: str | None` (literal do documento, D-24), `trecho: str | None`, `pagina: int | None`, `adiado: bool`.
- `Indeterminacao`: `motivo: MotivoIndeterminado`, `classes_candidatas: list[TipoEvento]`, `justificativa: str` (D-03; usada na mensagem da R-CLS-02).
- `Classificacao`: `valor: TipoEvento`, `sinais: list[Citacao]`, `titulo: str`, `indeterminacao: Indeterminacao | None`.
- `Extracao`: `tipo_evento: Classificacao` + um `CampoExtraido` por campo, plano: `razao_social`, `cnpj`, `isin`, `ticker`, `classe`, `data_aprovacao`, `data_com`, `data_ex`, `data_pagamento`, `valor_bruto`, `aliquota_irrf`, `valor_liquido`, `proporcao`, `custo_atribuido`, `moeda`. É também o schema da saída estruturada.
- `Ocorrencia`: `regra`, `comportamento`, `campos: list[str]`, `mensagem`.
- `Resultado`: `aprovadas: list[str]`, `ocorrencias: list[Ocorrencia]`.
- `RespostaModelo` (dataclass): `conteudo: str | None`, `chamadas: list[ChamadaFerramenta]`, `cached_tokens: int`. `ChamadaFerramenta`: `id`, `nome`.

**Saída** (o contrato):
- `Citacao`: `pagina`, `trecho`. `Apontamento`: `regra`, `mensagem`.
- `Confianca`: `nivel`, `ocr: float | None` (0–1), `modelo: float | None` (sempre `None`, D-26), `justificativa`.
- `Campo`: `valor`, `moeda` (só em valores monetários), `citacao`, `confianca`, `base_referencia` (só em emissor e ativo), `motivos`, `alertas`; **`revisao_humana` calculado** (`@computed_field`: há motivo?).
- `CampoTipoEvento`: `valor`, `citacoes`, `confianca`, `motivos`, `alertas`; `revisao_humana` calculado.
- `Emissor`: `razao_social`, `cnpj`. `Ativo`: `isin`, `ticker`, `classe` (todos `Campo`).
- `Campos`: `emissor`, `ativo`, `data_aprovacao`, `data_com`, `data_ex` e, opcionais, `data_pagamento`, `data_credito`, `valor_bruto`, `aliquota_irrf`, `valor_liquido`, `proporcao`, `custo_atribuido`.
- `RegraAprovada`: `regra`, `descricao`. `Erro`: `codigo`, `mensagem`.
- `Registro`: `documento`, `trace_id`, `tipo_pdf`, `erro`, `regras_aprovadas`, `tipo_evento`, `campos`; **`status` calculado** (`ERRO` se há erro; senão `REVISAO_HUMANA` se algum campo está em revisão; senão `APROVADO`, D-21).

`revisao_humana` e `status` calculados garantem a consistência pela construção: não existe registro com motivo e `revisao_humana: false`.

**Chaves por classe sem uma classe por evento:** `config.CHAVES_POR_CLASSE` diz quais chaves cada `TipoEvento` tem; a montagem só preenche essas, e o JSON sai com `model_dump(exclude_unset=True)`. Chave não preenchida não aparece; um campo preenchido com valor `null` aparece.

**O que o Pydantic valida:** o formato do contrato (tipos, obrigatórios, enums, aninhamento, faixas como `ocr` de 0 a 1) e a resposta do modelo (JSON fora do schema → retry → `FALHA_MODELO`). As regras de negócio ficam em `regras.py` de propósito: um erro de validação do Pydantic é uma exceção do tipo tudo ou nada, e uma regra precisa virar ocorrência com ID, mensagem e roteamento.

## 7. Assinaturas

As assinaturas reais estão na seção 11, junto com o papel de cada função.

## 8. Rastreamento (D-30)

Um arquivo JSONL por execução em `saida/traces/<trace_id>.jsonl` (o `trace_id` tem o documento e a data e hora, então execuções paralelas do mesmo documento não se misturam), uma linha por etapa ou evento, gravada pelo gerenciador de contexto `etapa` e pela função `registrar`: `trace_id`, etapa, início, duração, tentativa, cache local (acerto ou falha), `cached_tokens`, ferramenta chamada (pelo modelo ou imposta pelo código), resumo da entrada e da saída, erro. O mesmo `trace_id` vai no JSON do operador, ligando o registro ao rastro técnico. O JSON do operador mostra só o resultado (D-13).

## 9. Eval e teste de estocasticidade (D-29)

- **`evals/avaliar.py`:** compara `saida/` com o gabarito e imprime as métricas do `contrato.md` (seção 9). Usa o cache local: roda sem chave de API.
- **`tests/test_estocasticidade.py`** (`pytest -m estocastico`, fora da suíte padrão): um teste por documento, parametrizado. Cada documento é lido uma vez (a leitura é determinística) e processado N vezes (padrão 50) **sem o cache local**; a primeira execução vai em série, para gravar o prefixo no cache do provider, e as demais vão em paralelo com 20 workers. O teste do documento passa só se **nenhuma** execução falhar em alguma métrica com meta: erro não roteado, valor inventado, classificação, roteamento, motivo ou acurácia por campo.
- **Limite do provider:** o OpenRouter limita contas novas a 20 requisições por minuto neste modelo (erro 429 "new-account-rpm", descoberto na primeira rodada do lote). O cliente tem um limitador de ritmo (`LIMITE_RPM` no `config.py`), e o agente encerra assim que as 3 ferramentas foram chamadas, então cada execução faz 2 chamadas.
- **Estimativa:** N = 50 (decisão do usuário, para reduzir tempo e custo): 8 documentos × 50 × 2 chamadas = 800 chamadas a 20 por minuto ≈ 32 a 40 minutos. Com o limite da conta liberado, os 20 workers derrubam isso para poucos minutos.

## 10. Revisão de projeto: SOLID e simplicidade

| Princípio | Como o desenho atende |
|---|---|
| **S** — responsabilidade única | Cada arquivo tem uma responsabilidade: ler, falar com o modelo, conferir evidência, aplicar regras, montar, gravar. A regra (`regras.py`) fica separada da forma como o modelo a chama (`ESQUEMAS_FERRAMENTAS` em `llm.py`). |
| **O** — aberto para extensão | Nova regra: uma função em `regras.py` + uma linha em `mensagens.py`. Nova classe de evento: uma linha em `CHAVES_POR_CLASSE`. Novo sinônimo: `config.py`. Novo provider: só `llm.py`. |
| **L** — substituição | Quase sem herança, então não há subclasse que quebre o contrato. |
| **I** — interfaces enxutas | As ferramentas não recebem argumentos; o modelo não vê nem altera valores. |
| **D** — inversão de dependência | O domínio não importa a camada do modelo, e o provider tem uma única porta (`chamar_modelo`). Os testes de regras rodam sem API. |

**O que a revisão cortou (excesso de engenharia):**
- uma classe Pydantic por tipo de evento;
- `CampoBase` e `CampoMonetario`;
- o atributo `base` do resultado;
- o mapeamento de logprobs;
- 3 das 6 ferramentas;
- 8 dos 19 arquivos;
- interfaces abstratas, injeção de dependência e framework de agente.

## 11. Camadas e funções: por que cada uma existe

### Camadas

| Camada | Por que existe | O que quebraria sem ela |
|---|---|---|
| **Dados e configuração** (`modelos`, `config`, `mensagens`) | Um lugar para o contrato (classes Pydantic), para os parâmetros que mudam (alíquota, limites, feriados, chaves por classe) e para os textos ao operador | O contrato ficaria espalhado; mudar a alíquota ou uma mensagem exigiria mexer em regra |
| **Leitura** (`leitura`) | Transforma PDF em texto com a posição e a confiança de cada palavra, igual para nativo e escaneado | O resto do sistema teria que saber se o PDF é escaneado; a confiança do OCR por campo (D-08) não teria de onde vir |
| **Modelo** (`llm`) | Único lugar que fala com o provider: cache, retry, limitador de ritmo, extração e agente | Trocar de provider ou depurar uma chamada exigiria procurar em vários arquivos; testar regras exigiria API |
| **Domínio** (`evidencias`, `regras`, `montagem`) | As decisões determinísticas: o valor está no documento? É coerente? Que confiança tem? Vai para revisão? | "O LLM extrai, o código decide" deixaria de valer; as regras não seriam testáveis sem API |
| **Saída** (`saida`) | Escreve o que o operador e o avaliador leem: JSON, relatório de exceções e trace | A montagem misturaria lógica com escrita em disco; o trace não teria dono |
| **Orquestração** (`pipeline`, `__main__`) | Encadeia as etapas, faz o retry de alucinação e o paralelismo do lote | Cada etapa teria que chamar a seguinte, e o fluxo não seria legível num lugar só |

A regra entre elas: **o domínio nunca importa a camada do modelo.** Por isso as 52 regras e os testes de evidência rodam em 0,05 s, sem chave de API.

### Funções

**`config.py`**: só constantes. `CHAVES_POR_CLASSE` define as chaves de cada classe (uma classe nova é uma linha); `ROTULOS` são os sinônimos da checagem de rótulo; `IRRF_JCP` tem vigência; `LIMITE_RPM` e `WORKERS` controlam o ritmo.

**`mensagens.py`**: catálogo copiado de `regras.md` (D-15).
- `descricao(regra)`: texto curto de `regras_aprovadas`.
- `mensagem(regra, **valores)`: mensagem do motivo ou alerta, com os valores do registro.
- `mensagem_erro(codigo, **valores)`: mensagem do `erro` (D-18).

**`modelos.py`**: classes de dados.
- Internas: `Palavra`, `Leitura`, `CampoExtraido`, `Classificacao`, `Indeterminacao`, `Extracao` (também é o schema da saída estruturada do modelo), `Ocorrencia`, `Resultado`, `RespostaModelo`.
- Saída: `Campo`, `CampoTipoEvento`, `Emissor`, `Ativo`, `Campos`, `Registro`. `revisao_humana` e `status` são calculados, então nunca contradizem os motivos.
- `ErroProcessamento`: exceção que vira `status: ERRO`.

**`leitura.py`**
- `ler_documento(caminho) -> Leitura`: abre o PDF, usa a camada de texto ou, sem ela, o OCR. Falha → `PDF_ILEGIVEL` ou `FALHA_OCR`.
- `_linhas_nativas`, `_linhas_ocr`: palavras na ordem de leitura, com a linha a que pertencem (o OCR traz a confiança).
- `_montar_texto`: junta as palavras num texto e guarda a posição de cada uma, para depois achar as palavras de um valor.

**`llm.py`**
- `chamar_modelo(mensagens, schema=None, ferramentas=None, usar_cache=True) -> RespostaModelo`: a única porta para o provider. Cache local por hash da requisição, até 2 retries com backoff (D-13), limitador de ritmo.
- `extrair(leitura, problemas=None, usar_cache=True) -> Extracao`: extração e classificação numa chamada estruturada; `problemas` é o retorno do grounding no retry de alucinação.
- `validar(valores, tipo_evento, usar_cache=True) -> list[Resultado]`: o agente. O modelo escolhe as ferramentas, o código injeta os valores, chama as que faltarem e encerra quando as 3 rodaram (D-27).
- `_respeitar_limite`: no máximo `LIMITE_RPM` chamadas por minuto, somando todas as threads.
- `_gravar_cache`: gravação atômica, porque várias threads escrevem ao mesmo tempo.

**`evidencias.py`**
- `verificar_evidencias(extracao, leitura) -> (ocorrências, posições)`: R-GRD-01 (o trecho existe) e R-GRD-02 (o valor está no trecho), e devolve onde cada valor está no texto.
- `normalizar_texto(s) -> (texto, mapa)`: minúsculas, sem acento, sem pontilhado do OCR, aspas padronizadas; o mapa volta para a posição original.
- `rotulo_confere(campo, trecho, span) -> bool`: o rótulo mais próximo do valor é o do campo (D-20).
- `span_no_trecho`: posição do valor dentro da citação, para a checagem de rótulo.
- `normalizar_extracao(extracao) -> (valores, ocorrências)`: literal → formato do contrato (D-24); literal desconhecido → R-GRD-03.
- `para_data`, `para_decimal`, `para_fracao`: os normalizadores (data numérica ou por extenso; decimal com todas as casas; percentual → fração).

**`regras.py`**
- Ferramentas do agente: `validar_identificacao` (R-ID + R-IDF), `validar_datas` (R-DAT), `validar_valores_e_proporcao` (R-VAL ou R-PRO). `FERRAMENTAS` liga o nome da ferramenta à função.
- No código: `validar_campos_da_classe(extracao, descartados)` (R-REQ; um campo descartado pelo grounding não repete a R-REQ-01) e `verificar_classificacao(classificacao)` (R-CLS).
- Apoio: `eh_pregao`, `proximo_pregao` (calendário B3); `carregar_base`, `buscar` (base de referência, ISIN e depois CNPJ); `aliquota_vigente`; `isin_valido`, `cnpj_valido` (dígitos verificadores, desligados por configuração); `classe_do_titulo` (para a R-CLS-01); `campos_extraidos_da_classe`, `nome_na_saida` (a data de pagamento extraída vira `data_credito` na bonificação).

**`montagem.py`**
- `calcular_confianca(campo, extraido, span, leitura, confirmacoes) -> (Confianca, ocorrências)`: OCR abaixo de 0,70 → BAIXA e R-CNF-01; com confirmação → ALTA; senão MEDIA (D-20).
- `montar_registro(...) -> Registro`: monta só as chaves da classe, com motivos e alertas em cada campo e a base de referência derivada das ocorrências de R-ID.
- `registro_de_erro(...)`: o registro de uma falha de processamento.

**`saida.py`**
- `para_dict(registro)`: o JSON como o operador vê (só as chaves preenchidas, em ordem legível).
- `gravar_registro(registro, pasta)`, `gerar_relatorio(registros, pasta)`: JSON por documento e relatório de exceções.
- `iniciar_trace(trace_id)`, `registrar(evento, **dados)`, `etapa(nome, **dados)`: o trace da execução, por thread.

**`pipeline.py`**
- `processar_documento(caminho, leitura=None, usar_cache=True) -> Registro`: as etapas em série, com o retry de alucinação; qualquer falha vira registro de erro, nunca derruba o lote.
- `processar_lote(pasta, saida, workers) -> list[Registro]`: 1º documento em série, demais em paralelo; grava os JSON e o relatório.

**`evals/avaliar.py`**
- `carregar_gabarito()`, `achatar(registro)` (JSON → colunas do gabarito, contrato.md, seção 10) e `falhas(registro, esperado)` (métricas com meta não cumpridas; lista vazia = execução aprovada). O teste de estocasticidade usa a mesma função.

### Diferenças em relação ao desenho aprovado

- `validar_campos_da_classe` ganhou o parâmetro opcional `descartados`, para cumprir a nota da R-GRD em `regras.md` (o campo descartado pelo grounding não repete a R-REQ-01).
- O trace é guardado por thread (`contextvars`), então `etapa` não recebe o trace como parâmetro, e o arquivo é por execução (`<trace_id>.jsonl`), não por documento.
- Entraram o limitador de ritmo e o encerramento antecipado do agente, por causa do limite de 20 requisições por minuto.
- `para_data`, `para_decimal`, `para_fracao` e `span_no_trecho` ficaram públicas porque os testes as usam.
