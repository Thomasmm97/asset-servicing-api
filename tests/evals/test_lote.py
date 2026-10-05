"""Regressão do lote: cada documento passa uma vez pelo pipeline inteiro, pelo cache local (sem API), e é comparado com o gabarito.
Uma mudança de prompt, schema ou documento invalida o cache: aí o teste chama a API (precisa da chave)."""

import pytest

from asset_servicing import config
from asset_servicing.pipeline import processar_documento
from asset_servicing.saida import para_dict
from tests.evals.avaliar import carregar_gabarito, falhas

DOCUMENTOS = sorted(config.PASTA_DOCUMENTOS.glob("*.pdf"))


@pytest.mark.parametrize("pdf", DOCUMENTOS, ids=lambda p: p.stem)
def test_documento_dentro_das_metas(pdf, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PASTA_TRACES", tmp_path)  # não mistura com saida/traces
    registro = para_dict(processar_documento(pdf))
    assert not falhas(registro, carregar_gabarito()[pdf.stem])
