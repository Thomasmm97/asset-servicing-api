"""Casos "Dado → Então" de docs/regras.md."""

from datetime import date

import pytest

from asset_servicing import config
from asset_servicing.modelos import CampoExtraido, Citacao, Classificacao, Comportamento, Extracao, CAMPOS_EXTRAIDOS
from asset_servicing.regras import (cnpj_valido, isin_valido, validar_campos_da_classe, validar_datas, validar_identificacao,
                                    validar_valores_e_proporcao, verificar_classificacao)

DOC01 = {"tipo_evento": "DIVIDENDO", "razao_social": "Energética Vale do Tietê S.A.", "cnpj": "12.345.678/0001-90",
         "isin": "BRTIETACNOR3", "ticker": "TIET3", "classe": "ON", "data_aprovacao": date(2026, 5, 28),
         "data_com": date(2026, 6, 12), "data_ex": date(2026, 6, 15), "data_pagamento": date(2026, 7, 3),
         "valor_bruto": "0.4275000000", "moeda": "BRL"}
JCP = {**DOC01, "tipo_evento": "JCP", "valor_bruto": "0.2050000000", "aliquota_irrf": "0.175", "valor_liquido": "0.1691250000"}


def regras(resultado, comportamento=Comportamento.REVISAO_HUMANA):
    return {o.regra for o in resultado.ocorrencias if o.comportamento == comportamento}


def test_doc01_passa_em_tudo():
    for funcao in (validar_identificacao, validar_datas, validar_valores_e_proporcao):
        assert not funcao(DOC01).ocorrencias


@pytest.mark.parametrize("mudanca, regra", [
    ({"isin": "BRXXXXACNOR1", "cnpj": "99.999.999/0001-99"}, "R-ID-01"),
    ({"cnpj": "60.111.222/0001-55"}, "R-ID-02"),
    ({"razao_social": "Siderúrgica Paraná S.A."}, "R-ID-03"),
    ({"isin": "BRTIETACNOR"}, "R-IDF-01"),
    ({"ticker": "TIET"}, "R-IDF-04"),
])
def test_identificacao_reprova(mudanca, regra):
    assert regra in regras(validar_identificacao({**DOC01, **mudanca}))


def test_r_id_01_vai_nos_cinco_campos():
    r = validar_identificacao({**DOC01, "isin": "BRXXXXACNOR1", "cnpj": "99.999.999/0001-99"})
    assert r.ocorrencias[0].campos == ["razao_social", "cnpj", "isin", "ticker", "classe"]


def test_r_id_03_normaliza_abreviacoes():
    valores = {**DOC01, "isin": "BRCSPRACNOR1", "cnpj": "76.543.210/0001-12", "ticker": "CSPR3",
               "razao_social": "CIA. SIDERÚRGICA PARANAENSE S/A"}
    assert "R-ID-03" not in regras(validar_identificacao(valores))


def test_r_idf_04_aceita_digito_na_raiz():
    assert "R-IDF-04" not in regras(validar_identificacao({**DOC01, "ticker": "B3SA3"}))


def test_r_idf_05_classe_incoerente():
    assert "R-IDF-05" in regras(validar_identificacao({**DOC01, "isin": "BRTIETACNPR3"}))


def test_r_idf_06_e_alerta():
    r = validar_identificacao({**DOC01, "isin": "BRXXXXACNOR3"})
    assert "R-IDF-06" in regras(r, Comportamento.ALERTA)


def test_digitos_verificadores_com_identificadores_reais():
    assert isin_valido("BRPETRACNPR6") and not isin_valido("BRPETRACNPR7")
    assert cnpj_valido("33.000.167/0001-01") and not cnpj_valido("33.000.167/0001-02")


@pytest.mark.parametrize("mudanca, regra", [
    ({"data_com": date(2026, 6, 15), "data_ex": date(2026, 6, 12)}, "R-DAT-01"),
    ({"data_com": date(2026, 7, 15), "data_ex": date(2026, 7, 16), "data_pagamento": date(2026, 7, 10)}, "R-DAT-02"),
    ({"data_ex": date(2026, 6, 17)}, "R-DAT-03"),
    ({"data_com": date(2026, 6, 13), "data_ex": date(2026, 6, 15)}, "R-DAT-04"),   # sábado
    ({"data_pagamento": date(2026, 6, 4)}, "R-DAT-04"),                            # Corpus Christi
])
def test_datas_reprova(mudanca, regra):
    assert regra in regras(validar_datas({**DOC01, **mudanca}))


def test_r_dat_04_ignora_aprovacao_em_feriado():
    assert not validar_datas({**DOC01, "data_aprovacao": date(2026, 6, 4), "data_com": date(2026, 6, 12)}).ocorrencias


@pytest.mark.parametrize("valores, regra", [
    ({**DOC01, "valor_bruto": "0"}, "R-VAL-01"),
    ({**JCP, "valor_liquido": "0.1700"}, "R-VAL-02"),
    ({**JCP, "aliquota_irrf": "0.15", "valor_liquido": "0.1742500000"}, "R-VAL-03"),
    ({**DOC01, "moeda": "USD"}, "R-VAL-04"),
    ({**DOC01, "moeda": None}, "R-VAL-04"),
])
def test_valores_reprova(valores, regra):
    assert regra in regras(validar_valores_e_proporcao(valores))


def test_jcp_com_conta_exata_passa():
    assert not validar_valores_e_proporcao(JCP).ocorrencias


def test_r_val_03_usa_a_aliquota_da_epoca():
    jcp_2025 = {**JCP, "data_com": date(2025, 6, 12), "aliquota_irrf": "0.15", "valor_liquido": "0.1742500000"}
    assert "R-VAL-03" not in regras(validar_valores_e_proporcao(jcp_2025))


@pytest.mark.parametrize("tipo, proporcao, custo, regra", [
    ("GRUPAMENTO", "10:0", None, "R-PRO-01"),
    ("GRUPAMENTO", "1:10", None, "R-PRO-02"),
    ("BONIFICACAO", "20:21", "0", "R-PRO-03"),
])
def test_proporcao_reprova(tipo, proporcao, custo, regra):
    valores = {**DOC01, "tipo_evento": tipo, "proporcao": proporcao, "custo_atribuido": custo, "valor_bruto": None}
    assert regra in regras(validar_valores_e_proporcao(valores))


def extracao(tipo="DIVIDENDO", titulo="Pagamento de Dividendos", **campos) -> Extracao:
    vazio = {"valor": None, "trecho": None, "pagina": None, "adiado": False}
    preenchidos = {k: {"valor": "x", "trecho": "x", "pagina": 1, "adiado": False}
                   for k in ("razao_social", "cnpj", "isin", "ticker", "classe", "data_aprovacao", "data_com", "data_ex",
                             "data_pagamento", "valor_bruto")}
    dados = {k: CampoExtraido(**{**vazio, **preenchidos.get(k, {}), **campos.get(k, {})}) for k in CAMPOS_EXTRAIDOS}
    return Extracao(tipo_evento=Classificacao(valor=tipo, sinais=[Citacao(pagina=1, trecho="x")], titulo=titulo,
                                              indeterminacao=None), **dados)


def test_r_req_01_obrigatorio_ausente_e_alerta_na_aprovacao():
    r = validar_campos_da_classe(extracao(valor_bruto={"valor": None}, data_aprovacao={"valor": None}))
    assert "R-REQ-01" in regras(r) and "R-REQ-01" in regras(r, Comportamento.ALERTA)


def test_r_req_02_adiado():
    assert "R-REQ-02" in regras(validar_campos_da_classe(extracao(data_pagamento={"valor": None, "adiado": True})))


def test_r_req_03_campo_de_outra_classe():
    r = validar_campos_da_classe(extracao(valor_liquido={"valor": "0,07", "trecho": "x", "pagina": 1}))
    assert "R-REQ-03" in regras(r) and r.ocorrencias[0].campos == ["tipo_evento"]


def test_descartado_pelo_grounding_nao_repete_r_req_01():
    r = validar_campos_da_classe(extracao(valor_bruto={"valor": None}), descartados=frozenset({"valor_bruto"}))
    assert "R-REQ-01" not in regras(r)


def test_r_cls_01_titulo_diverge_da_natureza():
    assert "R-CLS-01" in regras(verificar_classificacao(extracao("JCP", "Distribuição de Dividendos").tipo_evento))


def test_r_cls_02_indeterminado():
    assert "R-CLS-02" in regras(verificar_classificacao(extracao("INDETERMINADO", "Aviso aos Acionistas").tipo_evento))


def test_digitos_verificadores_desligados_por_configuracao():
    assert not config.VALIDAR_DV_ISIN and not config.VALIDAR_DV_CNPJ
