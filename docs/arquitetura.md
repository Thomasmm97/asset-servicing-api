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

## 7. Assinaturas das funções principais

```python
# leitura.py
def ler_documento(caminho: Path) -> Leitura

# llm.py
def chamar_modelo(mensagens: list[dict], schema: type[BaseModel] | None = None,
                  ferramentas: list[dict] | None = None, usar_cache: bool = True) -> RespostaModelo
def extrair(leitura: Leitura, problemas: list[str] | None = None, usar_cache: bool = True) -> Extracao
def validar(valores: dict[str, object], tipo_evento: TipoEvento, usar_cache: bool = True) -> list[Resultado]
ESQUEMAS_FERRAMENTAS: list[dict]

# evidencias.py
def verificar_evidencias(extracao: Extracao, leitura: Leitura) -> tuple[list[Ocorrencia], dict[str, Span]]
def rotulo_confere(campo: str, trecho: str, span_valor: Span) -> bool
def normalizar_extracao(extracao: Extracao) -> tuple[dict[str, object], list[Ocorrencia]]   # R-GRD-03

# regras.py — cada função é um grupo de regras e devolve Resultado
def validar_identificacao(valores: dict) -> Resultado          # R-ID + R-IDF (usa a base de referência)
def validar_datas(valores: dict) -> Resultado                  # R-DAT (usa o calendário B3)
def validar_valores_e_proporcao(valores: dict) -> Resultado    # R-VAL ou R-PRO, conforme a classe
def validar_campos_da_classe(extracao: Extracao) -> Resultado  # R-REQ
def verificar_classificacao(classificacao: Classificacao) -> Resultado  # R-CLS
def eh_pregao(dia: date) -> bool
def proximo_pregao(dia: date) -> date
FERRAMENTAS: dict[str, Callable[[dict], Resultado]]            # nome da ferramenta → função

# montagem.py
def calcular_confianca(campo: str, extraido: CampoExtraido, span: Span | None, leitura: Leitura,
                       confirmacoes: list[str]) -> tuple[Confianca | None, list[Ocorrencia]]   # R-CNF-01
def montar_registro(leitura: Leitura, extracao: Extracao, valores: dict[str, object],
                    resultados: list[Resultado], spans: dict[str, Span], trace_id: str) -> Registro
def registro_de_erro(documento: str, trace_id: str, tipo_pdf: TipoPdf | None, codigo: CodigoErro, detalhe: str) -> Registro

# saida.py
def gravar_registro(registro: Registro, pasta: Path) -> Path
def gerar_relatorio(registros: list[Registro], pasta: Path) -> Path
@contextmanager
def etapa(trace: Trace, nome: str, **dados) -> Iterator[dict]   # registra início, duração, dados e erro de cada etapa

# pipeline.py
def processar_documento(caminho: Path, leitura: Leitura | None = None, usar_cache: bool = True) -> Registro
def processar_lote(pasta: Path, saida: Path, workers: int = config.WORKERS) -> list[Registro]
```

## 8. Rastreamento (D-30)

Um arquivo JSONL por documento em `saida/traces/<documento>.jsonl`, uma linha por etapa, gravada pelo gerenciador de contexto `etapa`: `trace_id`, etapa, início, duração, tentativa, cache local (acerto ou falha), `cached_tokens`, ferramenta chamada (pelo modelo ou imposta pelo código), resumo da entrada e da saída, erro. O mesmo `trace_id` vai no JSON do operador, ligando o registro ao rastro técnico. O JSON do operador mostra só o resultado (D-13).

## 9. Eval e teste de estocasticidade (D-29)

- **`evals/avaliar.py`:** compara `saida/` com o gabarito e imprime as métricas do `contrato.md` (seção 9). Usa o cache local: roda sem chave de API.
- **`tests/test_estocasticidade.py`** (`pytest -m estocastico`, fora da suíte padrão): um teste por documento, parametrizado. Cada documento é lido uma vez (a leitura é determinística) e processado N vezes (padrão 100) **sem o cache local**; a primeira execução vai em série, para gravar o prefixo no cache do provider, e as demais vão em paralelo com 20 workers. O teste do documento passa só se **nenhuma** execução falhar em alguma métrica com meta: erro não roteado, valor inventado, classificação, roteamento, motivo ou acurácia por campo.
- **Estimativa:** 800 execuções de cerca de 3 chamadas (12 a 15 s cada) ÷ 20 workers ≈ 8 a 12 minutos; custo de US$ 3 a 5.

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
