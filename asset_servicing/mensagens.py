"""Catálogo único dos textos ao operador (D-15), copiado de docs/regras.md, seção "Mensagens".

Descrição curta: aparece em `regras_aprovadas`. Mensagem: aparece em `motivos` ou `alertas` do campo.
"""

REGRAS = {
    'R-GRD-01': ('Trecho citado existe no documento.',
                 'Valor de {campo} ({valor}) sem respaldo no documento: o trecho citado não foi encontrado no texto.'),
    'R-GRD-02': ('Valor está no trecho citado.',
                 'Valor de {campo} ({valor}) não está no trecho citado: "{trecho}".'),
    'R-GRD-03': ('Valor em formato reconhecido.',
                 'Valor de {campo} ("{valor}") em formato não reconhecido; confira no documento.'),
    'R-ID-01': ('Emissor encontrado na base de referência.',
                 'Emissor não encontrado na base de referência (ISIN {isin}, CNPJ {cnpj}).'),
    'R-ID-02': ('CNPJ, ISIN, ticker e classe conferem com a base.',
                 '{campo} diverge da base de referência: aviso {valor_aviso}, base {valor_base}.'),
    'R-ID-03': ('Nome do emissor confere com a base.',
                 'Nome do emissor diverge da base: aviso "{nome_aviso}", base "{nome_base}".'),
    'R-ID-04': ('Emissor com status ativo na base.',
                 'Emissor com status "{status}" na base de referência; só emissores ativos seguem automaticamente.'),
    'R-IDF-01': ('ISIN no formato BR + 9 caracteres + dígito.',
                 'ISIN "{isin}" fora do formato (BR + 9 caracteres + dígito).'),
    'R-IDF-02': ('Dígito verificador do ISIN confere.',
                 'Dígito verificador do ISIN {isin} não confere.'),
    'R-IDF-03': ('Dígitos verificadores do CNPJ conferem.',
                 'Dígitos verificadores do CNPJ {cnpj} não conferem.'),
    'R-IDF-04': ('Ticker no formato 4 caracteres + sufixo de classe.',
                 'Ticker "{ticker}" fora do formato (4 caracteres + sufixo de classe).'),
    'R-IDF-05': ('Classe coerente entre ticker, ISIN e aviso.',
                 'Classe da ação incoerente: ticker {ticker} indica {classe_ticker}, ISIN indica {classe_isin}, aviso informa {classe_aviso}.'),
    'R-IDF-06': ('Raiz do ticker igual ao código do emissor no ISIN.',
                 'Raiz do ticker ({raiz}) difere do código do emissor no ISIN ({codigo}).'),
    'R-DAT-01': ('Aprovação ≤ data com < data ex.',
                 'Ordem das datas inválida: aprovação {aprovacao}, data com {data_com}, data ex {data_ex} (esperado: aprovação ≤ data com < data ex).'),
    'R-DAT-02': ('Data de pagamento ou de crédito posterior à data com.',
                 '{papel_pagamento} ({pagamento}) não é posterior à data com ({data_com}).'),
    'R-DAT-03': ('Data ex é o pregão seguinte à data com.',
                 'Data ex ({data_ex}) não é o pregão seguinte à data com ({data_com}); esperado {data_ex_esperada}.'),
    'R-DAT-04': ('Datas de mercado em dia de pregão.',
                 '{papel} ({data}) cai em dia sem pregão ({motivo_sem_pregao}).'),
    'R-VAL-01': ('Valor bruto por ação positivo.',
                 'Valor bruto por ação ({valor_bruto}) não é positivo.'),
    'R-VAL-02': ('Líquido = bruto × (1 − alíquota).',
                 'Valor líquido ({valor_liquido}) não confere com bruto × (1 − alíquota) = {liquido_esperado}.'),
    'R-VAL-03': ('Alíquota de IRRF igual à vigente na data com.',
                 'Alíquota de IRRF informada ({aliquota}) difere da vigente em {data_com} ({aliquota_vigente}).'),
    'R-VAL-04': ('Valores monetários em BRL.',
                 'Moeda de {campo} não é BRL ({moeda}); valores em outra moeda ou sem moeda identificada não têm tratamento automático nesta entrega.'),
    'R-PRO-01': ('Proporção no formato antes:depois.',
                 'Proporção "{proporcao}" fora do formato antes:depois com inteiros positivos.'),
    'R-PRO-02': ('Direção da proporção coerente com a classe.',
                 'Proporção {proporcao} incoerente com {tipo_evento}: a quantidade de ações deveria {aumentar_ou_diminuir}.'),
    'R-PRO-03': ('Custo atribuído positivo.',
                 'Custo atribuído ({custo_atribuido}) não é positivo.'),
    'R-REQ-01': ('Campos obrigatórios da classe encontrados.',
                 '{campo} é obrigatório para {tipo_evento} e não foi encontrado no aviso.'),
    'R-REQ-02': ('Nenhum campo obrigatório adiado pelo emissor.',
                 '{campo} adiado pelo emissor ("{trecho}"); aguardar aviso complementar.'),
    'R-REQ-03': ('Nenhum campo de outra classe preenchido.',
                 '{campo} não se aplica a {tipo_evento}, mas veio preenchido ({valor}).'),
    'R-CLS-01': ('Título coerente com a natureza do evento.',
                 'Título do aviso ("{titulo}") diverge da natureza identificada ({tipo_evento}).'),
    'R-CLS-02': ('Evento classificado na taxonomia.',
                 'Não foi possível classificar o evento ({motivo}): {justificativa}.'),
    'R-CNF-01': ('Confiança do OCR acima do limite.',
                 'Leitura incerta de {campo} ({valor}): confiança do OCR ({confianca_ocr}) abaixo do limite ({limite}).'),
    'R-CNF-02': ('Confiança do modelo acima do limite.',
                 'Extração incerta de {campo} ({valor}): probabilidade do modelo ({confianca_modelo}) abaixo do limite ({limite}).'),
}

ERROS = {
    'FALHA_MODELO': 'Falha na chamada ao modelo depois de 2 tentativas ({detalhe}).',
    'PDF_ILEGIVEL': 'Não foi possível abrir o PDF ({detalhe}).',
    'FALHA_OCR': 'Falha no OCR do documento escaneado ({detalhe}).',
    'ERRO_INTERNO': 'Erro interno ao processar o documento; detalhes no log técnico.',
}

# Nome de cada campo nas mensagens
NOMES_CAMPOS = {
    "razao_social": "Razão social", "cnpj": "CNPJ", "isin": "ISIN", "ticker": "Ticker", "classe": "Classe",
    "data_aprovacao": "Data de aprovação", "data_com": "Data com", "data_ex": "Data ex",
    "data_pagamento": "Data de pagamento", "data_credito": "Crédito das ações", "valor_bruto": "Valor bruto",
    "aliquota_irrf": "Alíquota de IRRF", "valor_liquido": "Valor líquido", "proporcao": "Proporção",
    "custo_atribuido": "Custo atribuído", "moeda": "Moeda", "tipo_evento": "Tipo de evento",
}


def descricao(regra: str) -> str:
    return REGRAS[regra][0]


def mensagem(regra: str, **valores) -> str:
    return REGRAS[regra][1].format(**valores)


def mensagem_erro(codigo: str, **valores) -> str:
    return ERROS[codigo].format(**valores)
