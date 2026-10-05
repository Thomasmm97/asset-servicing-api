"""Parâmetros do sistema. Mudar um comportamento configurável é mudar uma linha aqui (regras.md, "Configuração")."""

from datetime import date
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Modelo (D-26)
MODELO = "openai/gpt-5.6-luna"
URL_BASE = "https://openrouter.ai/api/v1"
VARIAVEL_CHAVE = "OPENROUTER_API_KEY"

# Execução (D-13, D-25, D-27)
WORKERS = 20
LIMITE_RPM = 20             # limite do OpenRouter para contas novas neste modelo (429 com 'new-account-rpm')
MAX_RETRIES = 2              # por tipo de retry: alucinação e falha na chamada
MAX_RODADAS_AGENTE = 3
PASTA_CACHE = RAIZ / "cache"
PASTA_TRACES = RAIZ / "saida" / "traces"
PASTA_DOCUMENTOS = RAIZ / "entrada" / "documentos"
CAMINHO_BASE = RAIZ / "entrada" / "golden_records.csv"

# Leitura (D-22, D-23)
MIN_CARACTERES_NATIVO = 20   # abaixo disso, o PDF não tem camada de texto: vai para o OCR
DPI_OCR = 300
IDIOMA_OCR = "por"
LIMITE_OCR = 0.70            # R-CNF-01, calibrado no doc 07

# Regras (regras.md, "Configuração")
IRRF_JCP = [  # (início, fim, alíquota); a vigência é conferida pela data com (R-VAL-03)
    (None, date(2025, 12, 31), Decimal("0.15")),
    (date(2026, 1, 1), None, Decimal("0.175")),
]
VALIDAR_DV_ISIN = False      # D-11: 11 dos 13 ISINs do lote (fictícios) falham
VALIDAR_DV_CNPJ = False      # D-11: 11 dos 13 CNPJs do lote (fictícios) falham

# Feriados nacionais em que a B3 não abre, mais 24/12 e 31/12 (calendário de negociação da B3; atualizar a cada ano, D-12)
FERIADOS_B3 = {
    date(2025, 1, 1), date(2025, 3, 3), date(2025, 3, 4), date(2025, 4, 18), date(2025, 4, 21),
    date(2025, 5, 1), date(2025, 6, 19), date(2025, 11, 20), date(2025, 12, 24), date(2025, 12, 25),
    date(2025, 12, 31),
    date(2026, 1, 1), date(2026, 2, 16), date(2026, 2, 17), date(2026, 4, 3), date(2026, 4, 21),
    date(2026, 5, 1), date(2026, 6, 4), date(2026, 9, 7), date(2026, 10, 12), date(2026, 11, 2),
    date(2026, 11, 20), date(2026, 12, 24), date(2026, 12, 25), date(2026, 12, 31),
}

# Chaves de `campos` por classe (contrato.md, seção 3). Nova classe de evento = nova linha.
COMUNS = ["emissor", "ativo", "data_aprovacao", "data_com", "data_ex"]
CHAVES_POR_CLASSE = {
    "DIVIDENDO": COMUNS + ["data_pagamento", "valor_bruto"],
    "JCP": COMUNS + ["data_pagamento", "valor_bruto", "aliquota_irrf", "valor_liquido"],
    "BONIFICACAO": COMUNS + ["data_credito", "proporcao", "custo_atribuido"],
    "DESDOBRAMENTO": COMUNS + ["proporcao"],
    "GRUPAMENTO": COMUNS + ["proporcao"],
    "INDETERMINADO": COMUNS,
}
CAMPOS_MONETARIOS = ["valor_bruto", "valor_liquido", "custo_atribuido"]

# Rótulos e sinônimos por campo, sem acento e em minúsculas (D-20). Fonte: dominio.md, glossário.
ROTULOS = {
    "razao_social": [],
    "cnpj": ["cnpj"],
    "isin": ["isin"],
    "ticker": ["codigo de negociacao", "ticker"],
    "classe": [],
    "data_aprovacao": ["data de aprovacao", "aprovacao", "aprovou", "reuniao", "assembleia", "rca", "age"],
    "data_com": ["data com", "data-base", "data base"],
    "data_ex": ["ex-dividendos", "ex-jcp", "ex-bonificacao", "ex-direito", "\"ex\"", "data ex", "negociadas ex",
                "negociacao grupada", "negociacao desdobrada", "ex "],
    "data_pagamento": ["data de pagamento", "pagamento", "credito das acoes", "credito"],
    "valor_bruto": ["valor bruto", "bruto"],
    "aliquota_irrf": ["imposto de renda", "irrf", "aliquota"],
    "valor_liquido": ["valor liquido", "liquido"],
    "proporcao": ["proporcao", "para cada", "grupamento", "desdobramento"],
    "custo_atribuido": ["custo atribuido", "custo unitario"],
}
