# asset-servicing-api

Agente code-first que lê avisos de eventos corporativos (PDF nativo ou escaneado) e produz, para cada documento, um **JSON auditável** (de onde veio cada valor, quão confiável ele é, o resultado da validação contra a base de referência e o que precisa de revisão humana e por quê) e um **relatório de exceções**.

O princípio que guia o desenho: **o LLM extrai, o código decide.** O modelo lê, classifica e escolhe as validações; a conferência das evidências, as regras, a confiança e o roteamento são código determinístico e testado.

---

## Como rodar

**Pré-requisitos:** Python 3.14 e Tesseract com o idioma português.

```bash
brew install python@3.14 tesseract tesseract-lang
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**Rodar o lote:**

```bash
python -m asset_servicing             # lê documents/ e escreve em saida/ (JSON por documento + relatorio_excecoes.json)
python -m tests.evals.avaliar               # compara saida/ com tests/evals/gabarito.csv
pytest                                # 52 testes unitários (tests/unit/): regras, evidências, montagem, saída; sem API
```

**Não precisa de chave de API para reproduzir a entrega:** as respostas do modelo estão no cache local versionado (`cache/`), e o lote roda inteiro a partir dele. Para chamar o modelo de novo (outro documento, prompt alterado), crie um `.env` com `OPENROUTER_API_KEY=...`.

**Teste de estocasticidade** (`tests/evals/test_estocasticidade.py`; chama a API e ignora o cache local; ~35 min com o limite da conta):

```bash
pytest -m estocastico                 # 50 execuções por documento
EXECUCOES=5 pytest -m estocastico     # versão rápida
```

## O que sai

| Arquivo | Para quem | Para quê |
|---|---|---|
| `saida/<documento>.json` | Operador e processos seguintes (cálculo de provento, custódia, conciliação) | O registro do documento, exigido pelo enunciado: cada valor com origem, confiança, validação e motivo de revisão, auditável sem reabrir o PDF ([contrato](docs/contrato.md); exemplos em [docs/exemplos/](docs/exemplos/)) |
| `saida/relatorio_excecoes.json` | Operador e sistemas (fila de revisão, painel) | O relatório de exceções do lote num único JSON: totais e, para todos os documentos, status, tipo de evento, erro, motivos e alertas, cada um com os campos que aponta e a mensagem |
| `saida/traces/<trace_id>.jsonl` | Engenharia e auditoria | O caminho técnico de cada execução: etapas e durações, cada chamada ao modelo (do cache ou não, `cached_tokens`), cada retry e o motivo, cada ferramenta e quem a chamou (o modelo ou o código), erros. Serve para depurar ("por que o doc 03 foi para revisão?"), para reconstruir uma decisão numa auditoria e para medir desempenho. Fica fora do JSON do operador, que mostra só o resultado (D-13, D-30); o `trace_id` liga os dois |
| `cache/<hash>.json` | Quem roda o projeto | As respostas do modelo usadas nesta entrega, uma por arquivo, indexadas pelo hash da requisição (modelo, mensagens, schema, ferramentas). Garante a reprodutibilidade (o modelo de raciocínio não aceita temperatura 0), permite rodar o clone limpo sem chave de API e evita pagar de novo por chamadas iguais durante o desenvolvimento. Qualquer mudança no prompt, no schema, no modelo ou no texto do documento muda o hash e gera uma chamada nova. Não confundir com o cache de prompt do provider (D-25), que fica do lado da OpenAI. O teste de estocasticidade não usa este cache |

Cada JSON responde, sem reabrir o PDF:
- **o que foi extraído e de onde:** valor normalizado e citação literal (página e trecho);
- **quão confiável é cada campo:** nível ALTA, MÉDIA ou BAIXA, com justificativa;
- **o resultado da validação:** `base_referencia` em cada campo de emissor e ativo, e a lista de `regras_aprovadas` com descrição;
- **o que vai para revisão e por quê:** `motivos` em cada campo (regra + mensagem) e `status` do documento.

## Arquitetura

```
documents/*.pdf ── 1º documento em série, demais em paralelo (20 workers)
   ▼
[1 leitura]      PyMuPDF (nativo) ou Tesseract (escaneado), com posição e confiança por palavra
[2 extração]     uma chamada estruturada ao modelo: valores literais, citações, tipo de evento
[3 evidências]   o trecho existe? o valor está no trecho? → senão, retry com o problema (máx. 2)
[4 normalização] literal → formato do contrato (datas ISO, decimais com todas as casas)
[5 validação]    agente: o modelo escolhe entre 3 ferramentas; o código injeta os valores e completa a cobertura
[6 confiança]    OCR, rótulo do campo na citação, base de referência, regras cruzadas
[7 montagem]     só as chaves da classe; status calculado
   ▼
saida/*.json + relatorio_excecoes.json + traces/
```

Detalhes em [docs/arquitetura.md](docs/arquitetura.md): caso de uso, camadas, por que cada arquivo e cada função existem, testes das bibliotecas.

| Arquivo | Responsabilidade |
|---|---|
| `leitura.py` | PDF → texto com posição e confiança de cada palavra |
| `llm.py` | Única porta para o provider: cache, retry, limite de ritmo, extração e agente |
| `evidencias.py` | Grounding, rótulo mais próximo, normalização dos literais |
| `regras.py` | As regras de coerência de [docs/regras.md](docs/regras.md), calendário B3, base de referência |
| `montagem.py` | Confiança e registro de saída |
| `saida.py` | JSON, relatório e trace |
| `pipeline.py` | Encadeamento, retry de alucinação, paralelismo |

## Decisões e trade-offs

Todas registradas, com opções e custo, em [docs/decisoes.md](docs/decisoes.md). As principais:

| Decisão | Por quê | Custo |
|---|---|---|
| Classificar pela natureza, não pelo título; divergência vai para revisão com a classe já preenchida (D-01, D-06) | O doc 03 se chama "Distribuição de Dividendos" e é JCP: errar muda a tributação | Um documento a mais na fila |
| Grounding verificado pelo código (D-14) e valor copiado literalmente, normalizado pelo código (D-24) | Valor inventado é o erro mais caro; o código não compartilha os pontos cegos do modelo | Um normalizador por tipo de campo |
| Confiança calculada por sinais verificáveis: OCR por palavra, rótulo do campo na citação, base, regras cruzadas (D-20) | Cada nível tem causa e justificativa legível | Limites decididos por critério, com 8 documentos |
| Agente com 3 ferramentas sem argumentos de valor (D-27) | Atende o tool calling sem deixar o modelo alterar valores no argumento | A parte agêntica é fina, de propósito |
| Documento é a unidade de roteamento; `status` com 3 estados, inspirado no JSend (D-18, D-21) | Não existe provento aprovado em parte; uma chave diz se segue e o que fazer | O operador abre o documento inteiro |
| Modelo de raciocínio `gpt-5.6-luna` sem logprobs (D-26, revisão da D-20) | O logprob só acrescenta onde o modelo interpreta, e lá o modelo forte acerta com probabilidade 1,0 (testado) | Sem medida de hesitação; reprodutibilidade pelo cache |
| PyMuPDF e Tesseract, escolhidos por teste (D-22, D-23) | Posição e confiança por palavra; o Docling só dá confiança por página e leu a tabela por colunas | Licença AGPL do PyMuPDF; Tesseract a instalar |
| Sem framework de agente (D-28) | Um laço de ~40 linhas, explicável e depurável ao vivo | Retry, cache e trace escritos à mão |

**O que decidimos não fazer, e por quê:**
- **API, interface do operador e banco de dados:** fora do escopo desta entrega; a saída em arquivo atende o enunciado.
- **Logprobs como sinal de confiança:** avaliado e desligado (D-20, revisão); a R-CNF-02 fica documentada para um modelo que devolva logprobs.
- **Citações múltiplas com regra "valor da tabela = valor do corpo":** um aviso que se contradiz entre tabela e corpo passa sem ser notado em proporção, custo atribuído e data de aprovação (D-20).
- **Dígitos verificadores de ISIN e CNPJ ligados:** implementados, mas desligados, porque 11 dos 13 identificadores sintéticos falham (D-11).
- **Códigos ISO 20022:** a taxonomia está no mesmo nível de tipo de evento, sem adotar os códigos (D-16).
- **Tratamento de câmbio:** valor em moeda diferente de BRL vai para revisão (R-VAL-04).
- **Docling, OCR em nuvem e LangChain/LangGraph:** testados ou avaliados e descartados (D-23, D-28).

## Premissas

- O lote é sintético: os identificadores não passam nos dígitos verificadores, e os nomes não são de empresas reais.
- A alíquota de IRRF sobre JCP é de 15% até 2025 e de 17,5% desde 2026, conforme os avisos do lote; ela é configuração com vigência, conferida pela data com.
- O calendário de pregões usa os feriados nacionais da B3 de 2025 e 2026, mais 24/12 e 31/12; fechamentos extraordinários não entram.
- O gabarito foi feito antes do código ([tests/evals/gabarito.csv](tests/evals/gabarito.csv)) e assume leitura correta do escaneado (doc 07).
- Um aviso traz um único evento.

## Resultados

| Verificação | Resultado |
|---|---|
| Testes (`pytest`) | 52 passam, sem API, em 0,05 s |
| Eval contra o gabarito (`python -m tests.evals.avaliar`) | 8/8 documentos dentro de todas as metas: zero erros não roteados, zero valores inventados, classificação 8/8, roteamento 8/8, motivo certo 4/4, acurácia por campo 100% |
| Estocasticidade (`pytest -m estocastico`, 50 execuções por documento) | Ver [tests/evals/resultado_estocasticidade.txt](tests/evals/resultado_estocasticidade.txt) |

Revisões humanas no lote, todas esperadas pelo gabarito:

| Doc | Motivo |
|---|---|
| 03 | R-CLS-01: o título diz dividendos e a natureza é JCP |
| 04 | R-REQ-02: data de pagamento "a definir" |
| 05 | R-DAT-02: pagamento antes da data com |
| 08 | R-ID-01: emissor fora da base de referência |

**O que os ciclos de melhoria mostraram:**
- o modelo pegou os 10% de IR sobre dividendos acima de R$ 50 mil por beneficiário como alíquota do doc 01 (a R-REQ-03 mandou para revisão, sem erro silencioso);
- devolveu a proporção como literal no doc 08;
- não reconheceu "data-base" como data com no grupamento do doc 06.

Os três foram corrigidos no prompt ou no schema, e a variação entre execuções é o que o teste de estocasticidade mede.

## Por que o risco de campo errado é reduzido, não eliminado

O grounding prova que o valor está no documento, mas não que ele pertence ao campo certo. O erro típico: o modelo usa a data ex (15/06) como data de pagamento; a data existe no texto, então o grounding passa. Duas defesas reduzem esse risco:

**O rótulo na citação (D-20).** O código confere que o rótulo mais próximo do valor, dentro da citação, é o do campo. Ele não elimina o risco porque:
- **a falha só rebaixa a confiança para MÉDIA, que não vai para revisão.** Tem de ser assim: a lista de sinônimos é incompleta (um aviso pode escrever "Crédito em" em vez de "Data de pagamento"), e um rótulo não reconhecido mandaria valores corretos para a fila;
- **a citação é escolhida pelo próprio modelo.** Se a extração de texto juntar a linha de um campo com o valor do vizinho (por exemplo, num layout em duas colunas), a citação traz o rótulo certo com o valor errado, e a checagem passa;
- **em texto corrido, o rótulo pode estar longe do valor, ou depois dele,** e a checagem fica sem conclusão.

**As regras cruzadas (R-DAT-01 a R-DAT-03, R-VAL-02).** Uma data trocada ou um valor trocado costuma quebrar uma conta ou uma ordem. Elas não eliminam o risco porque:
- **só cobrem alguns campos:** data com e data ex se conferem uma à outra (R-DAT-03), e bruto, alíquota e líquido do JCP fecham uma conta (R-VAL-02). Data de aprovação, valor bruto do dividendo, proporção e custo atribuído não têm conferência cruzada;
- **um valor errado que continua coerente passa:** se a troca resultar em datas ainda na ordem certa, a R-DAT-01 e a R-DAT-02 não percebem.

O risco que sobra é medido, não suposto: o eval conta os erros não roteados (meta zero), e o teste de estocasticidade repete cada documento 50 vezes.

## Limitações conhecidas

- Os limites de confiança (OCR 0,70) foram calibrados com um único escaneado.
- O grounding prova que o valor está no documento, não que pertence ao campo certo; o rótulo na citação e as regras cruzadas reduzem esse risco sem eliminá-lo.
- Uma leitura errada do OCR com confiança acima de 0,70 só é pega pelas regras cruzadas (R-DAT-03, R-VAL-02).
- A conta do OpenRouter usada tem limite de 20 requisições por minuto neste modelo; o cliente respeita esse ritmo (`LIMITE_RPM`), o que alonga o teste de estocasticidade.
- O cache local é indexado pelo texto lido do PDF. Com outra versão do Tesseract (a entrega usou a 5.5.3) ou do PyMuPDF, o texto do doc 07 pode mudar e exigir uma chamada nova ao modelo, com chave de API. As versões das bibliotecas Python estão fixadas em `requirements.txt`.

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/metodologia.md](docs/metodologia.md) | Fases do projeto, gates e princípios |
| [docs/inventario.md](docs/inventario.md) | O lote: formato, campos, problemas de cada documento |
| [docs/dominio.md](docs/dominio.md) | Taxonomia, glossário e princípios de classificação |
| [docs/regras.md](docs/regras.md) | Regras de coerência, com caso de teste, comportamento e mensagem |
| [docs/contrato.md](docs/contrato.md) | Schema da saída, confiança, roteamento e métricas |
| [docs/arquitetura.md](docs/arquitetura.md) | Pipeline, agente, ferramentas, stack, camadas e funções |
| [docs/decisoes.md](docs/decisoes.md) | D-01 a D-30: contexto, opções, decisão e custo |
