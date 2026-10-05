"""Orquestração: um documento passa pelas etapas em série; o lote vai com o 1º em série e os demais em paralelo (D-25)."""

import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from . import config
from .evidencias import normalizar_extracao, verificar_evidencias
from .leitura import ler_documento
from .llm import extrair, validar
from .modelos import CodigoErro, ErroProcessamento, Leitura, Registro, Resultado
from .montagem import montar_registro, registro_de_erro
from .regras import nome_na_saida, validar_campos_da_classe, verificar_classificacao
from .saida import etapa, gravar_lote, iniciar_trace, registrar

REGRAS_EVIDENCIA = ["R-GRD-01", "R-GRD-02", "R-GRD-03"]


def processar_documento(caminho: Path, leitura: Leitura | None = None, usar_cache: bool = True) -> Registro:
    caminho = Path(caminho)
    trace_id = f"{caminho.stem}-{datetime.now():%Y%m%dT%H%M%S%f}"
    iniciar_trace(trace_id)
    tipo_pdf = leitura.tipo_pdf if leitura else None
    try:
        if leitura is None:
            with etapa("leitura") as info:
                leitura = ler_documento(caminho)
                info.update(tipo_pdf=leitura.tipo_pdf.value, palavras=len(leitura.palavras))
        tipo_pdf = leitura.tipo_pdf

        problemas = None
        for tentativa in range(config.MAX_RETRIES + 1):  # retry de alucinação (D-13)
            with etapa("extracao", tentativa=tentativa) as info:
                extracao = extrair(leitura, problemas, usar_cache)
                info["tipo_evento"] = extracao.tipo_evento.valor.value
            with etapa("evidencias", tentativa=tentativa) as info:
                falhas, spans = verificar_evidencias(extracao, leitura)
                info["falhas"] = [o.mensagem for o in falhas]
            if not falhas:
                break
            problemas = [o.mensagem for o in falhas]
        tipo = extracao.tipo_evento.valor.value

        descartados = frozenset(c for o in falhas for c in o.campos if c != "tipo_evento")
        for campo in descartados:  # valor sem respaldo: descartado, fica só a mensagem
            getattr(extracao, campo).valor = None
            getattr(extracao, campo).trecho = None

        with etapa("normalizacao") as info:
            valores, falhas_formato = normalizar_extracao(extracao)
            info["falhas"] = [o.mensagem for o in falhas_formato]
        with etapa("validacao"):
            resultados = validar(valores, tipo, usar_cache)
        resultados.append(validar_campos_da_classe(extracao, descartados))
        resultados.append(verificar_classificacao(extracao.tipo_evento))

        evidencia = falhas + falhas_formato
        for o in evidencia:
            o.campos = [nome_na_saida(c, tipo) for c in o.campos]
        aprovadas = [r for r in REGRAS_EVIDENCIA if not any(o.regra == r for o in evidencia)]
        resultados.append(Resultado(aprovadas=aprovadas, ocorrencias=evidencia))

        with etapa("montagem") as info:
            registro = montar_registro(leitura, extracao, valores, resultados, spans, trace_id)
            info["status"] = registro.status.value
        return registro
    except ErroProcessamento as e:
        registrar("erro", codigo=e.codigo.value, detalhe=e.detalhe)
        return registro_de_erro(caminho.name, trace_id, tipo_pdf, e.codigo, e.detalhe)
    except Exception as e:
        registrar("erro", codigo=CodigoErro.ERRO_INTERNO.value, detalhe=traceback.format_exc())
        return registro_de_erro(caminho.name, trace_id, tipo_pdf, CodigoErro.ERRO_INTERNO, f"{type(e).__name__}: {e}")


def processar_lote(pasta: Path, saida: Path, workers: int = config.WORKERS) -> list[Registro]:
    pdfs = sorted(Path(pasta).glob("*.pdf"))
    if not pdfs:
        return []
    registros = [processar_documento(pdfs[0])]  # em série: grava a parte fixa do prompt no cache do provider
    with ThreadPoolExecutor(max_workers=workers) as executor:
        registros += list(executor.map(processar_documento, pdfs[1:]))
    gravar_lote(registros, saida)
    return registros
