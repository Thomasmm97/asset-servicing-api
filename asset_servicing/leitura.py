"""Leitura do PDF: camada de texto (PyMuPDF, D-22) ou OCR (Tesseract, D-23), com a posição de cada palavra no texto."""

import io
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image

from . import config
from .modelos import CodigoErro, ErroProcessamento, Leitura, Palavra, TipoPdf


def ler_documento(caminho: Path) -> Leitura:
    try:
        pdf = pymupdf.open(caminho)
    except Exception as e:
        raise ErroProcessamento(CodigoErro.PDF_ILEGIVEL, str(e))
    with pdf:
        linhas = _linhas_nativas(pdf)
        tipo = TipoPdf.NATIVO
        if sum(len(t) for _, _, t, _ in linhas) < config.MIN_CARACTERES_NATIVO:
            tipo = TipoPdf.ESCANEADO
            try:
                linhas = _linhas_ocr(pdf)
            except Exception as e:
                raise ErroProcessamento(CodigoErro.FALHA_OCR, str(e))
            if not linhas:
                raise ErroProcessamento(CodigoErro.FALHA_OCR, "o OCR não devolveu texto")
    texto, palavras = _montar_texto(linhas)
    return Leitura(documento=Path(caminho).name, tipo_pdf=tipo, texto=texto, palavras=palavras)


def _linhas_nativas(pdf) -> list[tuple]:
    """(página, chave da linha, palavra, confiança) na ordem de leitura."""
    saida = []
    for num, pagina in enumerate(pdf, start=1):
        for x0, y0, x1, y1, palavra, bloco, linha, _ in pagina.get_text("words", sort=False):
            saida.append((num, (bloco, linha), palavra, None))
    return saida


def _linhas_ocr(pdf) -> list[tuple]:
    saida = []
    for num, pagina in enumerate(pdf, start=1):
        imagem = Image.open(io.BytesIO(pagina.get_pixmap(dpi=config.DPI_OCR).tobytes("png")))
        dados = pytesseract.image_to_data(imagem, lang=config.IDIOMA_OCR, output_type=pytesseract.Output.DICT)
        for i, palavra in enumerate(dados["text"]):
            if palavra.strip():
                chave = (dados["block_num"][i], dados["par_num"][i], dados["line_num"][i])
                saida.append((num, chave, palavra, float(dados["conf"][i]) / 100))
    return saida


def _montar_texto(linhas: list[tuple]) -> tuple[str, list[Palavra]]:
    partes, palavras, pos, anterior = [], [], 0, None
    for pagina, chave, texto, confianca in linhas:
        if anterior is not None:
            separador = " " if (pagina, chave) == anterior else "\n"
            partes.append(separador)
            pos += 1
        palavras.append(Palavra(texto=texto, pagina=pagina, inicio=pos, fim=pos + len(texto), confianca=confianca))
        partes.append(texto)
        pos += len(texto)
        anterior = (pagina, chave)
    return "".join(partes), palavras
