# Relatório de exceções

Processados: 8 · aprovados: 4 · em revisão humana: 4 · com erro: 0 · com alerta: 0.

- 03_siderurgica_paranaense_proventos.pdf [REVISAO_HUMANA] R-CLS-01 em tipo_evento: Título do aviso ("AVISO AOS ACIONISTAS — Distribuição de Dividendos") diverge da natureza identificada (JCP).
- 04_rede_varejo_jcp_sem_data.pdf [REVISAO_HUMANA] R-REQ-02 em data_pagamento: Data de pagamento adiado pelo emissor ("Data de pagamento A definir (vide aviso complementar)"); aguardar aviso complementar.
- 05_aurora_saneamento_dividendo_datas.pdf [REVISAO_HUMANA] R-DAT-02 em data_com, data_pagamento: Data de pagamento (10/07/2026) não é posterior à data com (15/07/2026).
- 08_construtora_horizonte_bonificacao.pdf [REVISAO_HUMANA] R-ID-01 em razao_social, cnpj, isin, ticker, classe: Emissor não encontrado na base de referência (ISIN BRCNHZACNOR5, CNPJ 09.888.999/0001-21).

O registro completo de cada documento está em `documentos`, no `saida/lote.json`; o rastro técnico, em `saida/traces/<trace_id>.jsonl`.
