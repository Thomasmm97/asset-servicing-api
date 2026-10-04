"""Grounding (R-GRD-01/02/03), rótulo mais próximo e normalização dos literais (D-24)."""

from datetime import date

import pytest

from asset_servicing.evidencias import (normalizar_texto, para_data, para_decimal, para_fracao, rotulo_confere,
                                        span_no_trecho, verificar_evidencias)
from asset_servicing.modelos import Leitura, TipoPdf
from tests.unit.test_regras import extracao

TEXTO = "Valor bruto por ação ordinária\n(ON)\nR$ 0,4275000000\nData-base (“data com”)\n12/06/2026"


@pytest.mark.parametrize("literal, esperado", [
    ("12/06/2026", date(2026, 6, 12)), ("12 de junho de 2026", date(2026, 6, 12)), ("1º de janeiro de 2026", date(2026, 1, 1))])
def test_para_data(literal, esperado):
    assert para_data(literal) == esperado


def test_para_decimal_mantem_todas_as_casas():
    assert para_decimal("R$ 0,4275000000") == "0.4275000000"
    assert para_decimal("R$ 50.000,00") == "50000.00"


def test_para_fracao():
    assert para_fracao("17,5%") == "0.175"


def test_literal_nao_reconhecido():
    with pytest.raises(ValueError):
        para_data("meados de junho de 2026")


def test_normalizacao_ignora_aspas_pontilhado_e_espacos():
    assert normalizar_texto("Data-base (data com) ............ 22/06/2026")[0] == "data-base (data com) 22/06/2026"
    assert normalizar_texto("“data com”")[0] == '"data com"'


def _leitura(texto=TEXTO):
    return Leitura(documento="x.pdf", tipo_pdf=TipoPdf.NATIVO, texto=texto, palavras=[])


def test_grounding_passa_com_quebra_de_linha_no_trecho():
    e = extracao(**{k: {"valor": None} for k in ("razao_social", "cnpj", "isin", "ticker", "classe", "data_aprovacao",
                                                  "data_ex", "data_pagamento")},
                 valor_bruto={"valor": "R$ 0,4275000000", "trecho": "Valor bruto por ação ordinária (ON) R$ 0,4275000000"},
                 data_com={"valor": "12/06/2026", "trecho": 'Data-base ("data com") 12/06/2026'})
    e.tipo_evento.sinais[0].trecho = "Valor bruto"
    falhas, spans = verificar_evidencias(e, _leitura())
    assert not falhas and TEXTO[slice(*spans["data_com"])] == "12/06/2026"


@pytest.mark.parametrize("campo, trecho, regra", [
    ("valor_bruto", "Valor bruto por ação R$ 0,4725", "R-GRD-01"),                 # trecho que não existe
    ("valor_bruto", "Valor bruto por ação ordinária (ON) R$ 0,4275000000", "R-GRD-02"),  # valor fora do trecho
])
def test_grounding_reprova(campo, trecho, regra):
    e = extracao(**{k: {"valor": None} for k in ("razao_social", "cnpj", "isin", "ticker", "classe", "data_aprovacao",
                                                  "data_com", "data_ex", "data_pagamento")},
                 valor_bruto={"valor": "0,4257", "trecho": trecho})
    e.tipo_evento.sinais[0].trecho = "Valor bruto"
    falhas, _ = verificar_evidencias(e, _leitura())
    assert [f.regra for f in falhas] == [regra]


def test_rotulo_mais_proximo():
    trecho = normalizar_texto("Código de negociação TIET3 (ISIN BRTIETACNOR3)")[0]
    assert rotulo_confere("ticker", trecho, span_no_trecho("ticker", "TIET3", trecho))
    assert not rotulo_confere("data_pagamento", "data ex 15/06/2026", (8, 18))
