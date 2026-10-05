# Contrato de saída

> O que o sistema entrega para cada documento e por quê. Decisões de origem: D-17 (formato), D-18 (status e erro), D-19 e D-20 (confiança), D-21 (roteamento).
> Exemplos preenchidos à mão: `docs/exemplos/01_energetica_vale_tiete_dividendo.json` (aprovado) e `docs/exemplos/08_construtora_horizonte_bonificacao.json` (revisão humana).

A saída fica em `saida/lote.json`: o relatório de exceções do lote e um objeto por documento (seção 8, D-31).

---

## 1. Topo do JSON

| Chave | Valores | Finalidade |
|---|---|---|
| `documento` | nome do arquivo | Liga o registro ao PDF de origem. |
| `trace_id` | `<documento>-<data e hora da execução>` | Liga o registro ao rastro técnico em `saida/traces/` (D-30). |
| `tipo_pdf` | `NATIVO`, `ESCANEADO` ou `null` | Diz ao operador se os valores vieram de OCR, caso em que um dígito mal lido é um risco. `null` quando o PDF não abre. Um PDF misto conta como `ESCANEADO`. |
| `status` | `APROVADO`, `REVISAO_HUMANA`, `ERRO` | Responde, numa chave só, se o registro pode seguir para os processos seguintes (só `APROVADO` segue) e o que fazer: revisar ou reprocessar (D-18). Calculado a partir do erro e dos campos (seção 6), nunca preenchido à mão. |
| `erro` | `null` ou `{codigo, mensagem}` | Explica uma falha de processamento (seção 7). Com erro, `tipo_evento` e `campos` saem `null`. |
| `regras_aprovadas` | lista de `{regra, descricao}` | Mostra as checagens que o registro passou. As que falharam aparecem nos `motivos` e `alertas` dos campos. Sem esta lista, um documento aprovado não traria sinal de que foi validado. A descrição vem do catálogo de `regras.md`. |
| `tipo_evento` | campo (seção 2) com `citacoes` | Fica no topo porque define quais chaves existem em `campos`. As citações são os sinais de natureza que sustentam a classificação (R-GRD-02). |
| `campos` | objeto | Os campos da classe (seção 3). |

## 2. Estrutura de um campo

| Chave | Presente em | Finalidade |
|---|---|---|
| `valor` | todos | O valor normalizado (seção 4); `null` quando não encontrado ou adiado. |
| `moeda` | `valor_bruto`, `valor_liquido`, `custo_atribuido` | Código ISO 4217 do valor, derivado do símbolo ou do nome na citação. Um valor monetário sem moeda é incompleto (R-VAL-04). |
| `citacao` | todos, exceto `tipo_evento` | `{pagina, trecho}`: de onde veio o valor. O trecho existe no documento (R-GRD-01) e contém o valor (R-GRD-02). Uma citação por campo: a linha da tabela com o rótulo do campo ou, se não houver, a menor frase com rótulo e valor. |
| `citacoes` | só `tipo_evento` | Lista de `{pagina, trecho}`, um por sinal de natureza. |
| `confianca` | todos | `{nivel, ocr, modelo, justificativa}` (seção 5); `null` quando o valor é `null`. |
| `base_referencia` | campos de `emissor` e `ativo` | `CONFERE`, `DIVERGE` ou `NAO_ENCONTRADO`: o resultado da validação contra `entrada/golden_records.csv`, campo a campo. O detalhe de uma divergência vai na mensagem do motivo. |
| `revisao_humana` | todos | `true` se algum motivo aponta este campo. |
| `motivos` | todos | Lista de `{regra, mensagem}`: por que o campo vai para revisão humana. |
| `alertas` | todos | Lista de `{regra, mensagem}`: o que o operador deve saber, sem ir para revisão. |

Não há status por campo (D-17): uma chave que não se aplica à classe não existe; "não encontrado" e "adiado" são explicados pelo motivo (R-REQ-01, R-REQ-02). Todo valor `null` tem motivo no campo, exceto a data de aprovação, cuja ausência é só alerta.

## 3. Chaves de `campos` por classe

| Classe | Chaves |
|---|---|
| Todas | `emissor` (`razao_social`, `cnpj`), `ativo` (`isin`, `ticker`, `classe`), `data_aprovacao`, `data_com`, `data_ex` |
| `DIVIDENDO` | comuns + `data_pagamento`, `valor_bruto` |
| `JCP` | comuns + `data_pagamento`, `valor_bruto`, `aliquota_irrf`, `valor_liquido` |
| `BONIFICACAO` | comuns + `data_credito`, `proporcao`, `custo_atribuido` |
| `DESDOBRAMENTO`, `GRUPAMENTO` | comuns + `proporcao` |
| `INDETERMINADO` | comuns + todo campo extraído com valor |

`emissor` agrupa o que identifica a companhia; `ativo`, o que identifica o valor mobiliário (um emissor pode ter ON, PN e units, cada uma com ISIN e ticker próprios, R-ID-01). Na bonificação, a data é o crédito das ações, por isso `data_credito`. Em desdobramento e grupamento, `data_com` é a data-base e `data_ex` é o início da negociação com a nova quantidade (`regras.md`, seção 4).

## 4. Convenções de valor

Iguais às do gabarito (D-09): datas em ISO 8601; decimais como texto, com ponto e todas as casas do documento (`"0.4275000000"`), para não perder casas nem introduzir erro de ponto flutuante; alíquota como fração (`"0.175"`); proporção `antes:depois` (`"20:21"`); moeda em ISO 4217; CNPJ com a pontuação do documento.

## 5. Confiança

| Chave | Significado |
|---|---|
| `ocr` | Menor confiança do OCR entre as palavras do valor, de 0 a 1; `null` em PDF nativo. |
| `modelo` | Menor probabilidade entre os tokens do valor (logprob normalizado: e^logprob), de 0 a 1. `null` nesta entrega: o modelo escolhido não devolve logprobs (D-20, D-26). |
| `nivel` | `ALTA`, `MEDIA` ou `BAIXA`, pelas regras abaixo. |
| `justificativa` | Texto gerado a partir dos sinais: valores medidos e confirmações encontradas. |

| Nível | Quando | Efeito |
|---|---|---|
| `BAIXA` | `ocr` abaixo de 0,70 (D-23); `modelo` abaixo de 0,95 se o logprob for ligado | Revisão humana (R-CNF-01; R-CNF-02, desligada) |
| `ALTA` | Acima dos limites e pelo menos uma confirmação: rótulo do campo na citação (o rótulo mais próximo do valor é o do campo), base de referência, R-DAT-03 ou R-VAL-02; no `tipo_evento`, dois ou mais sinais de natureza | Segue |
| `MEDIA` | Acima dos limites, sem confirmação | Segue; é onde o risco residual se concentra |

A agregação pelo mínimo está justificada em D-19, e os níveis, as mitigações e os custos, em D-20. A confiança mede a leitura; a coerência é das regras: um campo pode ter `ALTA` e ir para revisão (doc 05, R-DAT-02).

## 6. Roteamento

**Status do documento** (D-21), derivado pelo código nesta ordem:
1. `ERRO`, se o processamento falhou;
2. `REVISAO_HUMANA`, se o `tipo_evento` ou algum campo tem `revisao_humana: true`;
3. `APROVADO`.

Alertas e o nível `MEDIA` não mudam o status.

**Em quais campos vai o motivo de cada regra.** Uma regra que avalia vários campos repete o motivo em cada um deles, porque o sistema não sabe qual está errado.

| Regra | Campos |
|---|---|
| R-GRD-01, R-GRD-02, R-GRD-03, R-CNF-01, R-CNF-02 | O campo avaliado |
| R-ID-01 | Os 5 campos de `emissor` e `ativo` |
| R-ID-02 | Cada campo divergente (`cnpj`, `isin`, `ticker`, `classe`) |
| R-ID-03 | `razao_social` |
| R-ID-04 | O campo usado como chave da busca (`isin`, ou `cnpj` quando a busca caiu nele) |
| R-IDF-01, R-IDF-02 | `isin` |
| R-IDF-03 | `cnpj` |
| R-IDF-04 | `ticker` |
| R-IDF-05 | `ticker`, `isin`, `classe` |
| R-IDF-06 (alerta) | `ticker`, `isin` |
| R-DAT-01 | `data_aprovacao`, `data_com`, `data_ex` |
| R-DAT-02 | `data_pagamento` ou `data_credito`, `data_com` |
| R-DAT-03 | `data_com`, `data_ex` |
| R-DAT-04 | A data que cai em dia sem pregão |
| R-VAL-01 | `valor_bruto` |
| R-VAL-02 | `valor_bruto`, `aliquota_irrf`, `valor_liquido` |
| R-VAL-03 | `aliquota_irrf` |
| R-VAL-04 | O valor monetário com moeda diferente de BRL ou não identificada |
| R-PRO-01, R-PRO-02 | `proporcao` |
| R-PRO-03 | `custo_atribuido` |
| R-REQ-01 | O campo não encontrado (alerta para `data_aprovacao`) |
| R-REQ-02 | O campo adiado; a citação mostra o trecho "a definir" |
| R-REQ-03, R-CLS-01, R-CLS-02 | `tipo_evento` (na R-REQ-03, o campo e o valor fora da classe vão na mensagem, porque não há chave para eles) |

## 7. Erros de processamento

`erro` = `{codigo, mensagem}`, com os códigos `FALHA_MODELO`, `PDF_ILEGIVEL`, `FALHA_OCR` e `ERRO_INTERNO`. As mensagens estão no catálogo de `regras.md` ("Erros de processamento"). Com erro: `status: ERRO`, `regras_aprovadas: []`, `tipo_evento: null`, `campos: null`.

## 8. Arquivo de saída e relatório de exceções (D-31)

Um único arquivo, `saida/lote.json`, com o relatório de exceções do lote e **um objeto por documento**:

```json
{
  "relatorio_excecoes": {
    "totais": { "processados": 8, "aprovados": 4, "revisao_humana": 4, "erro": 0, "com_alerta": 0 },
    "excecoes": [
      { "documento": "08_construtora_horizonte_bonificacao.pdf", "trace_id": "…", "tipo_evento": "BONIFICACAO",
        "status": "REVISAO_HUMANA", "erro": null,
        "motivos": [ { "regra": "R-ID-01", "campos": ["razao_social", "cnpj", "isin", "ticker", "classe"],
                       "mensagem": "Emissor não encontrado na base de referência (ISIN BRCNHZACNOR5, CNPJ 09.888.999/0001-21)." } ],
        "alertas": [] }
    ]
  },
  "documentos": [ { "documento": "01_energetica_vale_tiete_dividendo.pdf", "…": "registro completo (seções 1 a 7)" } ]
}
```

- `relatorio_excecoes`: os totais e só os documentos que pedem atenção (motivo, alerta ou erro); cada apontamento aparece uma vez, com todos os campos que aponta. É o relatório curto que o operador lê primeiro.
- `documentos`: o registro completo de cada documento, no formato das seções 1 a 7 (exemplos em `docs/exemplos/`), ordenados pelo nome do arquivo.

## 9. Métricas e metas (eval)

| Métrica | Definição | Meta |
|---|---|---|
| Erros não roteados | Campo com valor diferente do gabarito e `revisao_humana: false` | 0 |
| Valores inventados | Campo com valor onde o gabarito é vazio, ou R-REQ-03 em campo que o gabarito marca `n/a` | 0 |
| Classificação | `tipo_evento` igual ao gabarito | 8/8 |
| Roteamento | `status` traduzido igual à coluna `revisao_humana` | 8/8 |
| Motivo certo | Regras dos motivos iguais a `motivo_revisao` | 4/4 |
| Acurácia por campo | Valor igual ao gabarito, por campo e por classe | 100% |
| Sem rótulo (acompanhamento) | Campos em `MEDIA` por falta de rótulo na citação | Sem meta; serve para completar a lista de sinônimos |

**Estocasticidade (D-29):** as metas valem para cada uma das N execuções (padrão 100) de cada documento, sem o cache local; uma única execução fora da meta reprova o documento.

## 10. Correspondência com o gabarito

O eval traduz os nomes do JSON para as colunas de `tests/evals/gabarito.csv`:
- `status` → `revisao_humana` (`REVISAO_HUMANA` e `ERRO` → sim);
- campos de `emissor` e `ativo` → colunas de mesmo nome, com `emissor.razao_social` → `emissor` e `ativo.classe` → `classe_acao`;
- `data_credito` → `data_pagamento`;
- `moeda` de `valor_bruto` ou `custo_atribuido` → `moeda`;
- chave ausente na classe ↔ `n/a`;
- regras dos `motivos` → `motivo_revisao`.
