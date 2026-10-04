# Domínio — Eventos corporativos

> Especificação do domínio: o que cada tipo de evento é, como distingui-los e o vocabulário dos avisos. Vale para qualquer aviso, não só para o lote.
> Consumida pelo prompt (sinais, pares, princípios), pelo schema (lista de classes) e pelas regras (tratamento por classe).

---

## 1. Taxonomia de eventos

### Critérios da taxonomia

1. **Uma classe = um tratamento.** Dois eventos só ficam na mesma classe se recebem o mesmo tratamento downstream. Sem subtipos: o termo literal do documento (ex.: "Dividendo intercalar") vai como evidência.
2. **Alíquota não é taxonomia.** A taxonomia diz *se* há retenção na fonte. A alíquota é extraída do documento e conferida contra um valor de configuração com vigência.

### Definição

| Classe | Nome | O acionista recebe | Origem | Retenção na fonte | Como o valor é expresso | Datas típicas |
|---|---|---|---|---|---|---|
| `DIVIDENDO` | Dividendo | Dinheiro | Lucro do exercício ou reservas de lucros (Lei 6.404/76) | Sem alíquota única por ação: a retenção vigente desde 2026 depende do beneficiário | R$ bruto por ação, por classe | aprovação, com, ex, pagamento |
| `JCP` | Juros sobre Capital Próprio | Dinheiro | Patrimônio líquido × TJLP pro rata die (Lei 9.249/95, art. 9º) | Alíquota única sobre o bruto, salvo imunes/isentos | R$ bruto, alíquota e R$ líquido por ação | aprovação, com, ex, pagamento |
| `BONIFICACAO` | Bonificação em ações | Ações novas, sem custo | Capitalização de reservas (o capital social aumenta) | Não; há custo atribuído para fins fiscais | Proporção + custo atribuído (R$/ação) | aprovação, com, ex, crédito das ações |
| `DESDOBRAMENTO` | Desdobramento (split) | Mais ações: cada ação vira N | Só divide as ações; capital social inalterado | Não | Proporção | aprovação, com, início da negociação desdobrada |
| `GRUPAMENTO` | Grupamento (inplit) | Menos ações: N ações viram 1 | Só agrupa as ações; capital social inalterado | Não | Proporção (+ tratamento de frações) | aprovação, data-base, início da negociação grupada, ajuste de frações |
| `INDETERMINADO` | Indeterminado | — | Não é uma natureza: é o resultado "não foi possível classificar com segurança" | — | — | — |

> Nomes em português, maiúsculos e sem acento, para uso seguro em código. `JCP` fica como sigla de mercado (D-04).

### Sinais fortes no texto

| Classe | Sinais |
|---|---|
| `DIVIDENDO` | "dividendos", "lucro do exercício", "reservas de lucros", "ex-dividendos" |
| `JCP` | "juros sobre o capital próprio", "remuneração do capital próprio", "Lei 9.249/95", "TJLP", "patrimônio líquido", alíquota única + valor líquido |
| `BONIFICACAO` | "bonificação", "capitalização de reservas", "ações novas", "custo atribuído" |
| `DESDOBRAMENTO` | "desdobramento", "split", "cada ação passará a ser representada por N" |
| `GRUPAMENTO` | "grupamento", "inplit", "N ações para 1" |

### Pares que se confundem

| Par | Critério decisivo | Não decide |
|---|---|---|
| `DIVIDENDO` × `JCP` | Base de cálculo e tributação. PL × TJLP, Lei 9.249, alíquota única com bruto e líquido → `JCP`. Lucro ou reservas de lucros, sem alíquota por ação → `DIVIDENDO`. | Título; "imputado ao dividendo obrigatório"; a palavra "provento" |
| `BONIFICACAO` × `DESDOBRAMENTO` | Ambos aumentam a quantidade de ações. Capitalização de reservas e custo atribuído → `BONIFICACAO`. Capital social inalterado, sem custo atribuído → `DESDOBRAMENTO`. | A proporção em si (os dois são "N para M") |
| `DESDOBRAMENTO` × `GRUPAMENTO` | Direção: a quantidade aumenta → `DESDOBRAMENTO`; diminui → `GRUPAMENTO`. | Notação "X:Y" sem indicar qual lado é o antigo |
| `BONIFICACAO` × `DIVIDENDO` | Bonificação é sempre em ações. Pagamento em dinheiro nunca é `BONIFICACAO` nesta taxonomia. | — |

### `INDETERMINADO`: quando usar

Existe para que o modelo nunca seja forçado a escolher uma classe errada. Usar **somente** quando:

| Motivo | Quando |
|---|---|
| `FORA_DA_TAXONOMIA` | O evento existe, mas não é nenhuma das 5 classes (ex.: subscrição, amortização, resgate, restituição de capital). |
| `SINAIS_CONFLITANTES` | Os sinais de **natureza** apontam para classes diferentes e nenhum critério da tabela de pares desempata. |
| `EVIDENCIA_INSUFICIENTE` | O documento não traz, ou não deixa ler, os trechos que permitem decidir a natureza. |

**Não usar** quando:
- só o título ou o rótulo diverge e a natureza converge → classifica pela natureza e manda para revisão humana com a classe preenchida (princípio 1, seção 3; R-CLS-01; caso do doc 03 no inventário);
- a classe é clara, mas um campo está ausente ou ilegível → é problema de campo, não de classe;
- a confiança é apenas moderada → classifica com a confiança correspondente; a revisão vem do roteamento, não da classe.

**Salvaguardas:**
- `motivo` obrigatório, junto com as classes candidatas consideradas e os trechos que conflitam.
- `INDETERMINADO` sempre vai para revisão humana.
- O eval mede o uso: se nenhum documento do gabarito for `INDETERMINADO`, qualquer `INDETERMINADO` na saída é excesso de cautela e aparece na métrica.

---

## 2. Glossário

| Termo | Definição | Como aparece no lote |
|---|---|---|
| Provento | Termo geral para qualquer distribuição ao acionista (dividendo, JCP, bonificação). **Não é classe.** | "provento", "Natureza do provento" |
| Data de aprovação | Data da deliberação do órgão competente: RCA (Reunião do Conselho de Administração) ou AGE/AGO (Assembleia Geral). | "Data de aprovação (RCA)", "em reunião realizada em…", "Assembleia Geral Extraordinária realizada em…" |
| Data com (data-base) | Último dia em que quem detém a ação tem direito ao evento. | "data com", "data-base", "posição acionária final do dia", "inscritos nos registros… ao final do dia", "ao final do pregão de" |
| Data ex | Primeiro pregão em que a ação é negociada sem o direito. | "ex-dividendos", "ex-JCP", "ex", "ex-bonificação"; no grupamento, "negociadas já grupadas a partir de" |
| Data de pagamento | Data do crédito em dinheiro. Na bonificação, o equivalente é o crédito das ações. | "Data de pagamento", "crédito aos acionistas", "Crédito das ações bonificadas", "A definir" |
| Valor bruto / líquido | Valor por ação antes / depois da retenção na fonte. "Líquido" só existe quando há alíquota única por ação (JCP). | "Valor bruto por ação ON/PN", "Valor líquido por ação" |
| IRRF | Imposto de Renda Retido na Fonte. A alíquota vem do documento; não fixar de memória. | JCP: 17,5%. Dividendo: 10% sobre o que exceder R$ 50 mil/mês por beneficiário (doc 01) |
| Imputação ao dividendo obrigatório | O JCP pode ser descontado do dividendo mínimo obrigatório. Não muda a natureza: continua JCP. | "imputado aos dividendos obrigatórios", "imputado ao dividendo mínimo obrigatório" |
| Dividendo intercalar / intermediário | Dividendo declarado antes do fim do exercício ou à conta de reservas. Mesmo tratamento de qualquer `DIVIDENDO`. | "Dividendos Intercalares", "Dividendo intercalar" |
| Remuneração do capital próprio | Expressão legal do JCP (art. 9º da Lei 9.249/95). | "a título de remuneração do capital próprio" |
| TJLP | Taxa de Juros de Longo Prazo; limita o cálculo do JCP. Sinal forte de `JCP`. | "variação pro rata die da Taxa de Juros de Longo Prazo" |
| Proporção | Razão entre a quantidade de ações antes e depois do evento. A notação varia; precisa de representação canônica. | "10:1 (dez para uma)", "1 ação nova para cada 20 ações (5%)" |
| Custo atribuído | Valor fiscal de cada ação bonificada (base de custo para IR). | "Custo atribuído (base fiscal)" |
| Frações | Sobras não inteiras após bonificação ou grupamento; vendidas em leilão na B3 e o produto é rateado. | "frações… alienadas em leilão na B3" |
| Inplit / split | Inplit = grupamento. Split = desdobramento. | "Grupamento de Ações (Inplit)" |
| Classe (ON / PN) | Ação ordinária / preferencial. O valor do provento é informado por classe. | "por ação ordinária (ON)", "por ação preferencial (PN)" |
| Ticker | Código de negociação: 4 caracteres (em geral letras; ex.: B3SA3) + sufixo de classe (3 = ON, 4 = PN; 5 a 8 = preferenciais de classes A a D; 11 = unit). | "TIET3", "BMRD4" |
| ISIN | 12 caracteres. Padrão brasileiro: BR + emissor (4) + tipo de ativo (ACN = ação) + classe (OR = ON, PR = PN) + dígito verificador. | "BRTIETACNOR3", "BRBMRDACNPR7" |

---

## 3. Princípios de classificação

> Derivados da análise do lote (`inventario.md`). Orientam o prompt e o modelo de confiança.

1. **Natureza, não título.** Hierarquia de evidência: natureza (origem, base legal, forma de cálculo, tributação) > rótulo da tabela ("Tipo de evento") > título. Quando os níveis divergem mas a natureza converge, classifica-se pela natureza e o documento vai para revisão humana, com a classe já preenchida para o operador confirmar (D-06). *Origem: doc 03.*
2. **Fase não é tipo.** "Distribuição", "pagamento" e "crédito" descrevem o andamento do evento, não a sua natureza. *Origem: títulos "Pagamento de Dividendos" e "Distribuição de Dividendos".*
