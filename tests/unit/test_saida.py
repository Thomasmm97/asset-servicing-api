"""Contrato da saída (D-31): saida/lote.json com o relatório de exceções e um objeto por documento."""

import json
from pathlib import Path

import pytest

from asset_servicing.modelos import CodigoErro
from asset_servicing.montagem import registro_de_erro
from asset_servicing.saida import gravar_lote

LOTE = Path(__file__).resolve().parents[2] / "saida" / "lote.json"


def _documento(nome: str) -> dict:
    return next(d for d in json.loads(LOTE.read_text(encoding="utf-8"))["documentos"] if d["documento"].startswith(nome))


@pytest.mark.skipif(not LOTE.exists(), reason="rode o lote antes")
def test_dividendo_nao_tem_chaves_de_jcp_nem_de_acoes():
    d = _documento("01_")
    assert set(d["campos"]) == {"emissor", "ativo", "data_aprovacao", "data_com", "data_ex", "data_pagamento", "valor_bruto"}
    assert d["campos"]["valor_bruto"]["moeda"] == "BRL" and "moeda" not in d["campos"]["data_com"]
    assert d["campos"]["emissor"]["cnpj"]["base_referencia"] == "CONFERE"


@pytest.mark.skipif(not LOTE.exists(), reason="rode o lote antes")
def test_status_e_revisao_coerentes_com_os_motivos():
    d = _documento("08_")
    assert d["status"] == "REVISAO_HUMANA" and "data_credito" in d["campos"]
    for campo in d["campos"]["ativo"].values():
        assert campo["revisao_humana"] == bool(campo["motivos"])


def test_lote_tem_relatorio_e_um_objeto_por_documento(tmp_path):
    registros = [registro_de_erro("b.pdf", "b-1", None, CodigoErro.PDF_ILEGIVEL, "corrompido"),
                 registro_de_erro("a.pdf", "a-1", None, CodigoErro.FALHA_OCR, "sem texto")]
    dados = json.loads(gravar_lote(registros, tmp_path).read_text(encoding="utf-8"))
    assert list(dados) == ["relatorio_excecoes", "documentos"]
    assert dados["relatorio_excecoes"]["totais"] == {"processados": 2, "aprovados": 0, "revisao_humana": 0, "erro": 2, "com_alerta": 0}
    assert [d["documento"] for d in dados["documentos"]] == ["a.pdf", "b.pdf"]
    assert dados["relatorio_excecoes"]["excecoes"][0]["erro"]["codigo"] == "FALHA_OCR"
