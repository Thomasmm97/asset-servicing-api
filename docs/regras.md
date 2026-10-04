# Regras de coerência

> Regras de negócio que todo registro precisa cumprir, escritas no vocabulário de `dominio.md` e independentes de código.
> Cada regra tem um caso de teste, que vira teste automatizado na Fase 4.
> Uma regra só avalia campos presentes; a ausência de um campo é tratada pelas regras de campos por classe (seção 7).

---

## Comportamentos

| Comportamento | Efeito |
|---|---|
| **REVISÃO HUMANA** | O documento não segue automaticamente para os processos seguintes (cálculo de provento, custódia, conciliação) até um operador confirmar ou corrigir. O motivo vai com o ID da regra e a mensagem descritiva da seção "Mensagens". |
| **ALERTA** | O ID e a mensagem ficam registrados no JSON e no relatório de exceções; sozinho, não manda para revisão. |

## Retry

O retry é uma etapa do processamento, separada do comportamento das regras: só depois dele as regras são aplicadas ao resultado final.

| Tipo | Quando dispara | Como funciona | Se persistir depois de 2 tentativas |
|---|---|---|---|
| **Alucinação** | R-GRD-01 ou R-GRD-02 (valor sem respaldo no documento) | Nova chamada que informa ao modelo o problema encontrado e pede que ele releia o documento e cite o trecho de cada valor. (Com temperatura 0, repetir a mesma chamada daria a mesma resposta.) | A regra violada aplica o seu comportamento. No caso de R-GRD, o valor sem respaldo é descartado (o campo fica como não encontrado) e aparece só na mensagem; o motivo da revisão é a R-GRD, sem repetir o mesmo campo na R-REQ-01. |
| **Falha na chamada ao modelo** | Erro intermitente: tempo esgotado, limite de requisições, provedor indisponível | Repete a mesma chamada, com espera crescente entre as tentativas (backoff) | Revisão humana, com o motivo R-PRC-01. |

- Cada tipo tem o seu limite de 2 tentativas; um não consome o do outro.
- As demais regras não disparam retry. Com o grounding garantindo que cada valor está no documento, uma violação delas aponta para o próprio documento ou para a base, e um novo processamento não corrige.

## Configuração

| Parâmetro | Valor neste lote | Por quê |
|---|---|---|
| Máximo de tentativas de retry (por tipo) | 2 | Seção "Retry" (D-13) |
| Alíquota de IRRF sobre JCP | 15% até 2025-12-31; 17,5% a partir de 2026-01-01 | Alíquota é configuração com vigência, não taxonomia (`dominio.md`, critério 2) |
| Validar dígito verificador do ISIN | desligado | 11 dos 13 ISINs do lote (fictícios) falham no cálculo (D-11) |
| Validar dígitos verificadores do CNPJ | desligado | 11 dos 13 CNPJs do lote (fictícios) falham no cálculo (D-11) |
| Calendário de pregões | calendário da B3: dias úteis menos os feriados da bolsa | Datas de mercado só existem em dia de pregão (D-12). A fonte dos feriados é decidida na Fase 3. |

---

## 1. Evidência (grounding)

Aplica-se a todos os campos extraídos, em todas as classes. A verificação é dupla e segue esta ordem: primeiro, o trecho citado existe no documento (R-GRD-01); depois, o valor está no trecho citado (R-GRD-02). A ordem importa: se o trecho foi inventado, comparar o valor com ele não prova nada. Em documentos escaneados, o texto do documento é o resultado do OCR; a tolerância da comparação a ruído de leitura é definida na fase de OCR.

| ID | Regra | Comportamento | Caso de teste (Dado → Então) | No lote |
|---|---|---|---|---|
| R-GRD-01 | Todo valor extraído vem com o trecho do documento de onde saiu, e o trecho existe literalmente no texto do documento (desconsiderando espaços e quebras de linha). | REVISÃO HUMANA, com retry | Trecho "Valor bruto por ação R$ 0,4725", que não está no documento → retry → revisão humana | Todos passam, se a extração estiver certa |
| R-GRD-02 | O valor está no trecho citado. Valores literais (identificadores, datas, valores, alíquota): depois de normalizar o formato, o valor aparece no trecho. Valores derivados: o trecho contém os elementos de que o valor deriva. | REVISÃO HUMANA, com retry | Valor 2026-06-12 com trecho "Data-base (“data com”) 12/06/2026" → passa; valor 0.4257 com trecho "R$ 0,4275000000" → retry → revisão humana | Todos passam, se a extração estiver certa |

**Notas:**
- **O grounding é a defesa direta contra valor inventado**, o erro que o enunciado chama de prejuízo. O modelo pode citar um trecho que não existe (R-GRD-01) ou citar o trecho certo e transcrever o valor errado (R-GRD-02). As duas verificações são feitas pelo código, não pelo modelo (D-14).
- **Normalização (R-GRD-02):** datas em dd/mm/aaaa ou por extenso ("12 de junho de 2026"); decimais com vírgula e "R$"; percentuais ("17,5%" ↔ 0.175); identificadores comparados literalmente.
- **Valores derivados (R-GRD-02):** a proporção `20:21` deriva de "1 ação nova para cada 20", e o trecho precisa conter os números de que ela sai; a classe da ação deriva de "ON"/"ordinária" ou "PN"/"preferencial", ou do sufixo do ticker e do código de classe do ISIN citados (os docs 06 e 08 não escrevem a classe por extenso); a moeda deriva do símbolo ou do nome no trecho ("R$" → BRL, "US$" → USD); o tipo de evento deriva dos sinais de natureza (`dominio.md`), e o trecho citado precisa conter pelo menos um deles.
- **Limite:** o grounding confirma que o valor está no documento, não que pertence ao campo certo (ex.: a data ex citada como data de pagamento). Esse erro é pego, em parte, pelas regras de ordem das datas e de campos por classe.

## 2. Identificação e base de referência

Aplica-se a todas as classes.

| ID | Regra | Comportamento | Caso de teste (Dado → Então) | No lote |
|---|---|---|---|---|
| R-ID-01 | O emissor existe na base de referência: busca pelo ISIN; se não encontrar, pelo CNPJ. | REVISÃO HUMANA | ISIN e CNPJ ausentes da base → revisão humana | Doc 08 dispara |
| R-ID-02 | O registro encontrado bate com o extraído nas demais chaves: CNPJ, ISIN, ticker e classe. | REVISÃO HUMANA | ISIN da base com CNPJ diferente do extraído → revisão humana | 01–07 passam |
| R-ID-03 | O nome do emissor bate com a base depois de normalizar caixa, acentos, pontuação e abreviações societárias (Cia. = Companhia; S/A = S.A.). | REVISÃO HUMANA | "CIA. SIDERÚRGICA PARANAENSE S/A" × base "Companhia Siderúrgica Paranaense S.A." → passa; "Siderúrgica Paraná S.A." → revisão humana | 01–07 passam |
| R-ID-04 | O emissor está com status `ativo` na base. | REVISÃO HUMANA | Status `inativo` → revisão humana | Sem caso no lote |

**Notas:**
- **R-ID-01, ISIN antes do CNPJ:** o evento é de um ativo específico, e o ISIN identifica o ativo (emissor + classe). O CNPJ identifica só o emissor, que pode ter vários ativos na base (ON, PN, units), então a busca por ele pode trazer mais de um registro. O CNPJ fica como segunda tentativa: se o ISIN foi lido errado ou ainda não está na base, o emissor é encontrado mesmo assim, e a R-ID-02 aponta a divergência do ISIN com uma mensagem mais útil do que "emissor não encontrado". O ticker não serve de chave porque muda com renomeações; ele é conferido na R-ID-02. Se o CNPJ trouxer mais de um registro, usa-se o da classe extraída.
- **R-ID-03:** depois da normalização, um nome diferente indica que o registro pode ser de outro emissor, mesmo com o ISIN batendo. A normalização de abreviações evita mandar para revisão avisos válidos que escrevem "Cia." ou "S/A".
- **R-ID-04:** um provento de emissor ou ativo inativo (deslistado, com registro cancelado, ou uma classe de ação que foi convertida) indica que algo está errado. Ou o aviso é antigo, ou a base está desatualizada, ou o identificador aponta para um ativo que não é mais negociado. Se seguir automático, a custódia credita um direito sobre uma posição que pode não existir, e a conciliação quebra. Não há ação automática segura: só um humano sabe se o erro está na base ou no aviso. A regra é "diferente de `ativo`", e não uma lista de valores proibidos, porque a base só mostra o valor `ativo`.

## 3. Identificadores: formato e coerência interna

Aplica-se a todas as classes.

| ID | Regra | Comportamento | Caso de teste (Dado → Então) | No lote |
|---|---|---|---|---|
| R-IDF-01 | ISIN com 12 caracteres: `BR` + 9 alfanuméricos + 1 dígito. | REVISÃO HUMANA | "BRTIETACNOR" (11 caracteres) → revisão humana | Todos passam |
| R-IDF-02 | Dígito verificador do ISIN confere (Luhn sobre a conversão de letras em números). | REVISÃO HUMANA, quando ligado | BRPETRACNPR6 → passa; BRPETRACNPR7 → revisão humana | Desligado (ver configuração) |
| R-IDF-03 | Dígitos verificadores do CNPJ conferem. | REVISÃO HUMANA, quando ligado | 33.000.167/0001-01 → passa; 33.000.167/0001-02 → revisão humana | Desligado (ver configuração) |
| R-IDF-04 | Ticker com 4 caracteres alfanuméricos, o primeiro uma letra, + sufixo de classe (3 a 8, ou 11). | REVISÃO HUMANA | "TIET" → revisão humana; "B3SA3" → passa | Todos passam |
| R-IDF-05 | Classe coerente entre ticker, ISIN e linha do valor (quando informada): sufixo 3 ↔ `OR` ↔ ON; sufixo 4 ↔ `PR` ↔ PN. Os demais sufixos (preferenciais de classes A a D, units) não são verificados: estão fora do escopo do lote. | REVISÃO HUMANA | TIET3 com ISIN …ACNPR… → revisão humana | Todos passam |
| R-IDF-06 | Raiz do ticker igual ao código do emissor no ISIN (TIET3 ↔ BR**TIET**ACNOR3). | ALERTA | TIET3 com ISIN BRXXXXACNOR… → alerta | Todos passam |

**Notas:**
- **R-IDF-05 e R-IDF-06 importam sobretudo quando o emissor não está na base** (doc 08): aí a R-ID-02 não tem com o que comparar ticker e ISIN, e a coerência interna entre os dois é a única checagem disponível.
- **R-IDF-06:** no padrão brasileiro, o ISIN carrega a raiz do ticker (BR + **TIET** + ACN + OR + dígito). A regra confere esse padrão: uma divergência indica ticker e ISIN de ativos diferentes (ex.: o modelo pegou o ticker de uma linha e o ISIN de outra) ou erro de leitura. Só alerta porque o ISIN é atribuído ao ativo e pode não mudar quando o ticker muda (renomeação), então há exceções legítimas ao padrão.

## 4. Datas

**Papel das datas por classe** (D-09):

| Papel | `DIVIDENDO`, `JCP` | `BONIFICACAO` | `DESDOBRAMENTO`, `GRUPAMENTO` |
|---|---|---|---|
| Data com | data com | data com | data-base |
| Data ex | data ex | data ex | início da negociação desdobrada / grupada |
| Pagamento | data de pagamento | crédito das ações | não se aplica |

| ID | Regra | Classes | Comportamento | Caso de teste (Dado → Então) | No lote |
|---|---|---|---|---|---|
| R-DAT-01 | Aprovação ≤ data com < data ex. | Todas | REVISÃO HUMANA | Data com 15/06 e data ex 12/06 → revisão humana | Todos passam |
| R-DAT-02 | Pagamento posterior à data com. | `DIVIDENDO`, `JCP`, `BONIFICACAO` | REVISÃO HUMANA | Pagamento 10/07 e data com 15/07 → revisão humana | Doc 05 dispara |
| R-DAT-03 | Data ex = pregão seguinte à data com, pelo calendário da B3. | Todas | REVISÃO HUMANA | Data com sexta 12/06 e data ex quarta 17/06 → revisão humana | Todos passam |
| R-DAT-04 | Datas de mercado (com, ex, pagamento) caem em dia de pregão, pelo calendário da B3. A data de aprovação fica de fora. | Todas | REVISÃO HUMANA | Data com num sábado ou num feriado → revisão humana | Todos passam; as aprovações dos docs 06 e 07 caem num sábado e não disparam |

**Notas:**
- **Por que as datas importam:** a data com define quem recebe o provento. Um dia de erro muda o conjunto de acionistas com direito: vira pagamento a quem não deveria receber, falta de pagamento a quem deveria, e reclamação entre as partes. A data ex e o pagamento dependem dela.
- **Por que o calendário de pregões:** como a data ex é sempre o pregão seguinte à data com, uma confere a leitura da outra, como um dígito verificador. E datas de mercado só existem em dia de pregão. São checagens baratas que pegam o erro mais comum de OCR e de LLM em datas: um dígito ou um dia trocado. Com os feriados da B3 no calendário, nenhuma das duas regras gera alarme falso (D-12).
- **R-DAT-01:** a ordem faz parte da definição das datas: o direito só existe depois da aprovação, e a data ex é, por definição, posterior à data com. Uma violação é erro de leitura ou erro do documento; nos dois casos, o cálculo do direito usaria uma data errada.
- **R-DAT-02:** pagar antes de saber quem tem direito é impossível (doc 05). A regra exige só "posterior à data com", e não "a partir da data ex": como a data ex é o pregão seguinte à data com, entre as duas só há dias sem pregão, e um pagamento num desses dias já é pego pela R-DAT-04. Na prática, as duas versões dão o mesmo resultado.
- **R-DAT-03:** com o calendário da B3, uma data ex que não é o pregão seguinte à data com é inconsistência real, não alarme falso.
- **R-DAT-04:** uma data de mercado num dia sem pregão (fim de semana ou feriado) é erro de leitura (ex.: o OCR lê 21/06, um domingo, em vez de 22/06) ou erro do documento. A data de aprovação fica de fora porque conselho e assembleia podem se reunir em qualquer dia; as aprovações dos docs 06 e 07 caem num sábado.
- **No lote:** nenhuma data de mercado cai em dia sem pregão. O único feriado no período, Corpus Christi (04/06/2026), coincide só com a data de aprovação do doc 08, que essas regras não avaliam.

## 5. Valores (provento em dinheiro)

| ID | Regra | Classes | Comportamento | Caso de teste (Dado → Então) | No lote |
|---|---|---|---|---|---|
| R-VAL-01 | Valor bruto por ação > 0. | `DIVIDENDO`, `JCP` | REVISÃO HUMANA | Bruto 0 → revisão humana | Todos passam |
| R-VAL-02 | Líquido = bruto × (1 − alíquota), com tolerância de uma unidade na última casa decimal do líquido informado. | `JCP` | REVISÃO HUMANA | Bruto 0,2050, alíquota 17,5%, líquido 0,1700 → revisão humana | 02, 03, 04 e 07 passam (conta exata) |
| R-VAL-03 | Alíquota extraída = alíquota configurada vigente na data com. | `JCP` | REVISÃO HUMANA | Alíquota 15% com data com em 2026 → revisão humana | 02, 03, 04 e 07 passam |
| R-VAL-04 | Moeda identificada (código ISO 4217, a partir do símbolo ou do nome no documento) e igual a BRL. | `DIVIDENDO`, `JCP`, `BONIFICACAO` (custo atribuído) | REVISÃO HUMANA | "US$ 0,25" → moeda USD → revisão humana | Todos passam ("R$" → BRL) |

**Notas:**
- **R-VAL-03, por que importa:** no JCP, o imposto é retido na fonte, e o líquido creditado a cada acionista é bruto × (1 − alíquota). Alíquota errada significa pagamento errado para toda a base de acionistas e imposto recolhido errado pela fonte pagadora: erro financeiro e fiscal ao mesmo tempo, o tipo de erro que o enunciado destaca.
- **R-VAL-03, o que pega:** (1) erro de leitura da alíquota, como o OCR lendo "17,5%" como "1,75%" ou o modelo pegando os 10% da regra de dividendo do doc 01; na maioria desses casos, a R-VAL-02 também dispara. (2) Um aviso coerente por dentro, mas com a alíquota errada: um aviso de 2026 que aplica os 15% antigos e calcula o líquido com 15%. A conta fecha e a R-VAL-02 passa, mas o acionista receberia o valor errado. Só a R-VAL-03 pega esse caso.
- **R-VAL-03, por que a alíquota é configuração com vigência:** ela muda por lei (passou de 15% para 17,5% em 2026, segundo os avisos do lote). Com vigência, cada aviso é conferido pela alíquota da sua época (um aviso de 2025 com 15% passa), e uma nova mudança é uma linha de configuração, não código. Isenções e imunidades são aplicadas por acionista nos processos seguintes; a regra confere a alíquota geral informada no aviso.
- **R-VAL-04, identificar e mandar para revisão:** a moeda é sempre identificada (campo obrigatório, com grounding a partir do símbolo ou do nome no documento), e o operador vê qual é. Se não for BRL, o documento vai para revisão: um provento em outra moeda exige tratamento de câmbio (taxa e data de conversão) que esta entrega não define. Só identificar e seguir automático pressuporia que os processos seguintes tratam moeda estrangeira.
- **R-VAL-03, por que a data com como referência da vigência:** a retenção acontece no pagamento ou no crédito, o que vier primeiro (como diz o doc 03), e o crédito costuma ocorrer junto com a declaração. Um aviso cuja data com e cujo pagamento atravessam uma mudança de alíquota é caso de borda.

## 6. Proporção (evento em ações)

| ID | Regra | Classes | Comportamento | Caso de teste (Dado → Então) | No lote |
|---|---|---|---|---|---|
| R-PRO-01 | Proporção no formato `antes:depois`, com inteiros positivos. | `BONIFICACAO`, `DESDOBRAMENTO`, `GRUPAMENTO` | REVISÃO HUMANA | "10:0" → revisão humana | 06 e 08 passam |
| R-PRO-02 | Direção coerente com a classe: depois > antes em `BONIFICACAO` e `DESDOBRAMENTO`; depois < antes em `GRUPAMENTO`. | `BONIFICACAO`, `DESDOBRAMENTO`, `GRUPAMENTO` | REVISÃO HUMANA | `GRUPAMENTO` com 1:10 → revisão humana | 06 (10:1) e 08 (20:21) passam |
| R-PRO-03 | Custo atribuído > 0. | `BONIFICACAO` | REVISÃO HUMANA | Custo atribuído 0 → revisão humana | 08 passa |

## 7. Campos por classe

**Obrigatórios em todas as classes** (exceto `INDETERMINADO`): emissor, CNPJ, ISIN, ticker, classe da ação, tipo de evento, data de aprovação, data com, data ex.

| Classe | Obrigatórios além dos comuns | Não se aplica |
|---|---|---|
| `DIVIDENDO` | valor bruto, moeda, pagamento | alíquota, valor líquido, proporção, custo atribuído |
| `JCP` | valor bruto, alíquota, valor líquido, moeda, pagamento | proporção, custo atribuído |
| `BONIFICACAO` | proporção, custo atribuído, moeda, pagamento (crédito das ações) | valor bruto, alíquota, valor líquido |
| `DESDOBRAMENTO` | proporção | valor bruto, alíquota, valor líquido, custo atribuído, moeda, pagamento |
| `GRUPAMENTO` | proporção | valor bruto, alíquota, valor líquido, custo atribuído, moeda, pagamento |

| ID | Regra | Comportamento | Caso de teste (Dado → Então) | No lote |
|---|---|---|---|---|
| R-REQ-01 | Campo obrigatório não encontrado. | REVISÃO HUMANA; ALERTA para a data de aprovação | `JCP` sem valor líquido → revisão humana; qualquer classe sem data de aprovação → alerta | Nenhum caso no lote |
| R-REQ-02 | Campo obrigatório adiado pelo emissor ("a definir"). | REVISÃO HUMANA (D-07) | Pagamento "a definir" → revisão humana | Doc 04 dispara |
| R-REQ-03 | Campo que não se aplica à classe veio preenchido. | REVISÃO HUMANA | `DIVIDENDO` com valor líquido → revisão humana; `GRUPAMENTO` com valor em R$ → revisão humana | Nenhum caso, se a extração estiver certa. Pega dois erros prováveis: a alíquota de 10% por beneficiário do doc 01 lida como alíquota por ação, e o custo atribuído do doc 08 lido como valor bruto. |

**Notas:**
- **Critério:** um campo ausente manda para revisão quando os processos seguintes (cálculo de provento, custódia, conciliação) não conseguem agir corretamente sem ele.
- **R-REQ-01, data de aprovação como alerta:** a data de aprovação não entra em cálculo, pagamento nem conciliação. O registro pode seguir sem ela, e o alerta deixa a ausência visível para o operador.
- **R-REQ-02:** com o pagamento "a definir", o registro está correto, mas incompleto, e nada garante que os processos seguintes aceitem um evento sem data de pagamento (D-07). A mensagem diz ao operador que o caso é de aguardar o aviso complementar, não de corrigir a extração.
- **R-REQ-03 sem retry:** o valor fora do lugar normalmente está no documento (passou no grounding), então não é alucinação: ou o modelo pôs um valor real no campo errado, ou a classe está errada. Um retry poderia apagar a prova da classe errada: no doc 03, um JCP classificado como `DIVIDENDO` pelo título perderia o valor líquido e a alíquota e seguiria aprovado com a tributação errada. Indo direto para revisão, o pior caso é o operador corrigir um campo trocado. Valor inventado já é coberto pelo retry do grounding (D-13).

## 8. Classificação

| ID | Regra | Comportamento | Caso de teste (Dado → Então) | No lote |
|---|---|---|---|---|
| R-CLS-01 | O título diverge da natureza do evento. | ALERTA (D-06) | Título "Distribuição de Dividendos" e natureza JCP → alerta | Doc 03 dispara |
| R-CLS-02 | Classe `INDETERMINADO`. | REVISÃO HUMANA (D-03) | `INDETERMINADO` → revisão humana | Nenhum caso no lote |

---

## Mensagens

Catálogo único das mensagens ao operador (D-15). Para revisar ou acrescentar uma mensagem, edite só esta tabela; no código, as mensagens ficam num único arquivo, com o ID da regra como chave. `{campo}` é preenchido com o valor do registro; datas aparecem como dd/mm/aaaa.

| ID | Mensagem |
|---|---|
| R-GRD-01 | "Valor de {campo} ({valor}) sem respaldo no documento: o trecho citado não foi encontrado no texto." |
| R-GRD-02 | "Valor de {campo} ({valor}) não está no trecho citado: \"{trecho}\"." |
| R-ID-01 | "Emissor não encontrado na base de referência (ISIN {isin}, CNPJ {cnpj})." |
| R-ID-02 | "{campo} diverge da base de referência: aviso {valor_aviso}, base {valor_base}." |
| R-ID-03 | "Nome do emissor diverge da base: aviso \"{nome_aviso}\", base \"{nome_base}\"." |
| R-ID-04 | "Emissor com status \"{status}\" na base de referência; só emissores ativos seguem automaticamente." |
| R-IDF-01 | "ISIN \"{isin}\" fora do formato (BR + 9 caracteres + dígito)." |
| R-IDF-02 | "Dígito verificador do ISIN {isin} não confere." |
| R-IDF-03 | "Dígitos verificadores do CNPJ {cnpj} não conferem." |
| R-IDF-04 | "Ticker \"{ticker}\" fora do formato (4 caracteres + sufixo de classe)." |
| R-IDF-05 | "Classe da ação incoerente: ticker {ticker} indica {classe_ticker}, ISIN indica {classe_isin}, aviso informa {classe_aviso}." |
| R-IDF-06 | "Raiz do ticker ({raiz}) difere do código do emissor no ISIN ({codigo})." |
| R-DAT-01 | "Ordem das datas inválida: aprovação {aprovacao}, data com {data_com}, data ex {data_ex} (esperado: aprovação ≤ data com < data ex)." |
| R-DAT-02 | "{papel_pagamento} ({pagamento}) não é posterior à data com ({data_com})." |
| R-DAT-03 | "Data ex ({data_ex}) não é o pregão seguinte à data com ({data_com}); esperado {data_ex_esperada}." |
| R-DAT-04 | "{papel} ({data}) cai em dia sem pregão ({motivo_sem_pregao})." |
| R-VAL-01 | "Valor bruto por ação ({valor_bruto}) não é positivo." |
| R-VAL-02 | "Valor líquido ({valor_liquido}) não confere com bruto × (1 − alíquota) = {liquido_esperado}." |
| R-VAL-03 | "Alíquota de IRRF informada ({aliquota}) difere da vigente em {data_com} ({aliquota_vigente})." |
| R-VAL-04 | "Moeda {moeda} diferente de BRL; proventos em outra moeda não têm tratamento automático nesta entrega." |
| R-PRO-01 | "Proporção \"{proporcao}\" fora do formato antes:depois com inteiros positivos." |
| R-PRO-02 | "Proporção {proporcao} incoerente com {tipo_evento}: a quantidade de ações deveria {aumentar_ou_diminuir}." |
| R-PRO-03 | "Custo atribuído ({custo_atribuido}) não é positivo." |
| R-REQ-01 | "{campo} é obrigatório para {tipo_evento} e não foi encontrado no aviso." |
| R-REQ-02 | "{campo} adiado pelo emissor (\"{trecho}\"); aguardar aviso complementar." |
| R-REQ-03 | "{campo} não se aplica a {tipo_evento}, mas veio preenchido ({valor})." |
| R-CLS-01 | "Título do aviso (\"{titulo}\") diverge da natureza identificada ({tipo_evento})." |
| R-CLS-02 | "Não foi possível classificar o evento ({motivo}): {justificativa}." |
| R-PRC-01 | "Falha técnica ao processar o documento ({erro}) depois de 2 tentativas." |

---

## Matriz regra × classe

| Regras | `DIVIDENDO` | `JCP` | `BONIFICACAO` | `DESDOBRAMENTO` | `GRUPAMENTO` |
|---|---|---|---|---|---|
| R-GRD, R-ID, R-IDF, R-DAT-01, R-DAT-03, R-DAT-04, R-REQ, R-CLS | ✓ | ✓ | ✓ | ✓ | ✓ |
| R-DAT-02 | ✓ | ✓ | ✓ | — | — |
| R-VAL-01 | ✓ | ✓ | — | — | — |
| R-VAL-02, R-VAL-03 | — | ✓ | — | — | — |
| R-VAL-04 | ✓ | ✓ | ✓ | — | — |
| R-PRO-01, R-PRO-02 | — | — | ✓ | ✓ | ✓ |
| R-PRO-03 | — | — | ✓ | — | — |

---

## Verificação contra o gabarito

Aplicando as regras aos valores de `evals/gabarito.csv` (mensagens já preenchidas, como o operador as veria):

| Doc | Revisão humana | Alertas | Mensagem ao operador | Revisão no gabarito |
|---|---|---|---|---|
| 01 | — | — | — | não |
| 02 | — | — | — | não |
| 03 | — | R-CLS-01 | Alerta: "Título do aviso (\"Distribuição de Dividendos\") diverge da natureza identificada (JCP)." | não |
| 04 | R-REQ-02 | — | "Data de pagamento adiada pelo emissor (\"A definir (vide aviso complementar)\"); aguardar aviso complementar." | sim |
| 05 | R-DAT-02 | — | "Data de pagamento (10/07/2026) não é posterior à data com (15/07/2026)." | sim |
| 06 | — | — | — | não |
| 07 | — | — | — | não (política para escaneados pendente, D-08) |
| 08 | R-ID-01 | — | "Emissor não encontrado na base de referência (ISIN BRCNHZACNOR5, CNPJ 09.888.999/0001-21)." | sim |

As regras reproduzem a coluna de revisão do gabarito nos 8 documentos. No doc 08, as regras R-ID-02 a R-ID-04 não chegam a ser avaliadas, porque não há registro na base. Com a extração certa, nenhum documento dispara retry: as três revisões vêm de regras que apontam o documento (04 e 05) ou a base (08).
