"""Contrato da saída: só as chaves da classe, status e revisão calculados, a partir de um JSON gerado pelo lote."""

import json
from pathlib import Path

import pytest

SAIDA = Path(__file__).resolve().parents[2] / "saida"


@pytest.mark.skipif(not (SAIDA / "01_energetica_vale_tiete_dividendo.json").exists(), reason="rode o lote antes")
def test_dividendo_nao_tem_chaves_de_jcp_nem_de_acoes():
    d = json.loads((SAIDA / "01_energetica_vale_tiete_dividendo.json").read_text(encoding="utf-8"))
    assert set(d["campos"]) == {"emissor", "ativo", "data_aprovacao", "data_com", "data_ex", "data_pagamento", "valor_bruto"}
    assert d["campos"]["valor_bruto"]["moeda"] == "BRL" and "moeda" not in d["campos"]["data_com"]
    assert d["campos"]["emissor"]["cnpj"]["base_referencia"] == "CONFERE"


@pytest.mark.skipif(not (SAIDA / "08_construtora_horizonte_bonificacao.json").exists(), reason="rode o lote antes")
def test_status_e_revisao_coerentes_com_os_motivos():
    d = json.loads((SAIDA / "08_construtora_horizonte_bonificacao.json").read_text(encoding="utf-8"))
    assert d["status"] == "REVISAO_HUMANA" and "data_credito" in d["campos"]
    for campo in d["campos"]["ativo"].values():
        assert campo["revisao_humana"] == bool(campo["motivos"])


def test_relatorio_json_tem_todos_os_documentos_e_os_totais(tmp_path):
    from asset_servicing.modelos import CodigoErro
    from asset_servicing.montagem import registro_de_erro
    from asset_servicing.saida import gerar_relatorio
    registros = [registro_de_erro("b.pdf", "b-1", None, CodigoErro.PDF_ILEGIVEL, "corrompido"),
                 registro_de_erro("a.pdf", "a-1", None, CodigoErro.FALHA_OCR, "sem texto")]
    dados = json.loads(gerar_relatorio(registros, tmp_path).read_text(encoding="utf-8"))
    assert dados["totais"] == {"processados": 2, "aprovados": 0, "revisao_humana": 0, "erro": 2, "com_alerta": 0}
    assert [d["documento"] for d in dados["documentos"]] == ["a.pdf", "b.pdf"]
    assert dados["documentos"][0]["erro"]["codigo"] == "FALHA_OCR"
