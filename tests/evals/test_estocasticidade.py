"""Estocasticidade (D-29): cada documento é processado N vezes; nenhuma execução pode falhar nas métricas.
A extração vai sem o cache local; o agente usa um cache temporário, porque não muda o resultado (D-27).

Uso: pytest -m estocastico                 (N = 50, os 8 documentos)
     EXECUCOES=10 pytest -m estocastico    (desenvolvimento)
     pytest -m estocastico -k 01           (só o doc 01)
A 1ª execução vai em série (grava a parte fixa do prompt no cache do provider); as demais em paralelo.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from asset_servicing import config, llm, pipeline
from asset_servicing.leitura import ler_documento
from asset_servicing.pipeline import processar_documento
from asset_servicing.saida import para_dict
from tests.evals.avaliar import carregar_gabarito, falhas

pytestmark = pytest.mark.estocastico
N = int(os.environ.get("EXECUCOES", "50"))
DOCUMENTOS = sorted((config.RAIZ / "documents").glob("*.pdf"))


@pytest.fixture(scope="module")
def execucoes(request, tmp_path_factory) -> dict[Path, list[dict]]:
    selecionados = {item.callspec.params.get("pdf") for item in request.session.items if hasattr(item, "callspec")}
    documentos = [p for p in DOCUMENTOS if p in selecionados]  # só os escolhidos com -k
    leituras = {p: ler_documento(p) for p in documentos}  # leitura determinística: uma vez por documento

    def rodar(pdf: Path) -> dict:
        return para_dict(processar_documento(pdf, leituras[pdf], usar_cache=False))

    tarefas = [pdf for _ in range(N) for pdf in documentos]
    resultados = {pdf: [] for pdf in documentos}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, "PASTA_TRACES", tmp_path_factory.mktemp("traces"))
        mp.setattr(config, "PASTA_CACHE", tmp_path_factory.mktemp("cache"))  # fora do repo
        mp.setattr(pipeline, "validar", lambda valores, tipo, _: llm.validar(valores, tipo, usar_cache=True))
        resultados[tarefas[0]].append(rodar(tarefas[0]))
        with ThreadPoolExecutor(max_workers=config.WORKERS) as executor:
            for pdf, registro in zip(tarefas[1:], executor.map(rodar, tarefas[1:])):
                resultados[pdf].append(registro)
    return resultados


@pytest.mark.parametrize("pdf", DOCUMENTOS, ids=lambda p: p.stem)
def test_nenhuma_execucao_falha(execucoes, pdf):
    gabarito = carregar_gabarito()[pdf.stem]
    com_falha = [f for registro in execucoes[pdf] if (f := falhas(registro, gabarito))]
    assert not com_falha, f"{len(com_falha)}/{N} execuções com falha; primeira: {com_falha[0]}"
