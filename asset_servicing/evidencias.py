"""Evidência dos valores: grounding (R-GRD-01/02), rótulo mais próximo (D-20) e normalização dos literais (D-24, R-GRD-03)."""

import re
import unicodedata
from datetime import date
from decimal import Decimal

from . import config, mensagens
from .modelos import CAMPOS_EXTRAIDOS, Comportamento, Extracao, Leitura, Ocorrencia

Span = tuple[int, int]

_TROCAS = str.maketrans({"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "–": "-", "—": "-"})
_PONTILHADO = re.compile(r"[.,;:…_]{3,}")
_MESES = {m: i for i, m in enumerate(["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
                                      "agosto", "setembro", "outubro", "novembro", "dezembro"], start=1)}
DATAS = ["data_aprovacao", "data_com", "data_ex", "data_pagamento"]
DERIVADOS = ["classe", "proporcao", "moeda"]


def normalizar_texto(s: str) -> tuple[str, list[int]]:
    """Minúsculas, sem acento, aspas e travessões padronizados, sem pontilhados, espaços colapsados.
    Devolve também o mapa posição normalizada → posição original."""
    s = _PONTILHADO.sub(lambda m: " " * len(m.group()), s)
    saida, mapa = [], []
    for i, ch in enumerate(s):
        ch = "".join(c for c in unicodedata.normalize("NFD", ch.translate(_TROCAS).lower()) if not unicodedata.combining(c))
        if ch.isspace():
            if saida and saida[-1] != " ":
                saida.append(" ")
                mapa.append(i)
            continue
        for c in ch:
            saida.append(c)
            mapa.append(i)
    while saida and saida[-1] == " ":
        saida.pop()
        mapa.pop()
    return "".join(saida), mapa


def verificar_evidencias(extracao: Extracao, leitura: Leitura) -> tuple[list[Ocorrencia], dict[str, Span]]:
    """Confere, para cada valor, que o trecho existe no texto (R-GRD-01) e contém o valor (R-GRD-02).
    Devolve as ocorrências e a posição de cada valor no texto da leitura."""
    texto, mapa = normalizar_texto(leitura.texto)
    ocorrencias, spans = [], {}
    for campo in CAMPOS_EXTRAIDOS:
        extraido = getattr(extracao, campo)
        if extraido.valor is None:
            continue
        nome = mensagens.NOMES_CAMPOS[campo]
        trecho = normalizar_texto(extraido.trecho or "")[0]
        inicio = texto.find(trecho) if trecho else -1
        if inicio < 0:
            ocorrencias.append(_ocorrencia("R-GRD-01", [campo], campo=nome, valor=extraido.valor))
            continue
        relativo = _valor_no_trecho(campo, extraido.valor, trecho)
        if relativo is None:
            ocorrencias.append(_ocorrencia("R-GRD-02", [campo], campo=nome, valor=extraido.valor, trecho=extraido.trecho))
            continue
        a, b = relativo
        spans[campo] = (mapa[inicio + a], mapa[inicio + b - 1] + 1)
    sinais_ausentes = [s.trecho for s in extracao.tipo_evento.sinais if normalizar_texto(s.trecho)[0] not in texto]
    if sinais_ausentes or not extracao.tipo_evento.sinais:
        ocorrencias.append(_ocorrencia("R-GRD-01", ["tipo_evento"], campo="Tipo de evento",
                                       valor=extracao.tipo_evento.valor.value))
    return ocorrencias, spans


def rotulo_confere(campo: str, trecho: str, span_valor: Span) -> bool:
    """O rótulo mais próximo do valor, dentro da citação, é o do campo (D-20)."""
    proprios = config.ROTULOS.get(campo, [])
    if not proprios:
        return False
    a, b = span_valor
    melhor, distancia = None, None
    for rotulos in config.ROTULOS.values():
        for rotulo in rotulos:
            for m in re.finditer(re.escape(rotulo), trecho):
                d = max(a - m.end(), m.start() - b, 0)
                if distancia is None or d < distancia:
                    melhor, distancia = rotulo, d
    return melhor in proprios


def span_no_trecho(campo: str, valor: str, trecho: str) -> Span | None:
    """Posição do valor dentro do trecho já normalizado (para a checagem de rótulo)."""
    return _valor_no_trecho(campo, valor, normalizar_texto(trecho)[0])


def normalizar_extracao(extracao: Extracao) -> tuple[dict[str, object], list[Ocorrencia]]:
    """Literal do documento → formato do contrato (D-24). Literal não reconhecido → R-GRD-03."""
    valores: dict[str, object] = {"tipo_evento": extracao.tipo_evento.valor.value}
    ocorrencias = []
    for campo in CAMPOS_EXTRAIDOS:
        literal = getattr(extracao, campo).valor
        if literal is None:
            valores[campo] = None
            continue
        try:
            valores[campo] = _normalizar_valor(campo, literal)
        except ValueError:
            valores[campo] = None
            ocorrencias.append(_ocorrencia("R-GRD-03", [campo], campo=mensagens.NOMES_CAMPOS[campo], valor=literal))
    return valores, ocorrencias


def para_data(literal: str) -> date:
    t = normalizar_texto(literal)[0]
    if m := re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", t):
        return date(int(m[3]), int(m[2]), int(m[1]))
    if m := re.search(r"(\d{1,2})\s*(?:º|°|o)?\s+de\s+([a-z]+)\s+de\s+(\d{4})", t):
        if m[2] in _MESES:
            return date(int(m[3]), _MESES[m[2]], int(m[1]))
    raise ValueError(literal)


def para_decimal(literal: str) -> str:
    """'R$ 0,4275000000' → '0.4275000000', mantendo todas as casas do documento."""
    m = re.search(r"\d{1,3}(?:\.\d{3})+,\d+|\d+,\d+|\d+", literal)
    if not m:
        raise ValueError(literal)
    return m.group().replace(".", "").replace(",", ".")


def para_fracao(literal: str) -> str:
    """'17,5%' → '0.175'."""
    m = re.search(r"(\d+(?:,\d+)?)\s*%", literal)
    if not m:
        raise ValueError(literal)
    return str(Decimal(m[1].replace(",", ".")) / 100)


def _normalizar_valor(campo: str, literal: str) -> object:
    if campo in DATAS:
        return para_data(literal)
    if campo in config.CAMPOS_MONETARIOS:
        return para_decimal(literal)
    if campo == "aliquota_irrf":
        return para_fracao(literal)
    if campo == "proporcao":
        m = re.search(r"(\d+)\s*:\s*(\d+)", literal)
        if not m:
            raise ValueError(literal)
        return f"{m[1]}:{m[2]}"
    if campo in ("isin", "ticker", "classe", "moeda"):
        return literal.strip().upper()
    return literal.strip()


def _valor_no_trecho(campo: str, valor: str, trecho: str) -> Span | None:
    if campo not in DERIVADOS:
        v = normalizar_texto(valor)[0]
        i = trecho.find(v)
        return (i, i + len(v)) if i >= 0 and v else None
    if campo == "proporcao":
        m = re.search(r"(\d+)\s*:\s*(\d+)", valor)
        if not m:
            return None
        numeros = {n.group(): n.span() for n in re.finditer(r"\d+", trecho)}
        outro = m[2] if m[2] in numeros else str(abs(int(m[2]) - int(m[1])))
        if m[1] in numeros and outro in numeros:
            (a1, b1), (a2, b2) = numeros[m[1]], numeros[outro]
            return (min(a1, a2), max(b1, b2))
        return None
    sinais = {
        "ON": [r"\bon\b", r"\bordinarias?\b", r"\b[a-z0-9]{4}3\b", r"br[a-z0-9]{4}acnor\d"],
        "PN": [r"\bpn\b", r"\bpreferenciais?\b", r"\b[a-z0-9]{4}4\b", r"br[a-z0-9]{4}acnpr\d"],
        "BRL": [r"r\$", r"\breais\b"],
        "USD": [r"us\$", r"\bdolar"],
    }.get(valor.strip().upper(), [])
    achado = next((m for p in sinais if (m := re.search(p, trecho))), None)
    return achado.span() if achado else None


def _ocorrencia(regra: str, campos: list[str], **valores) -> Ocorrencia:
    return Ocorrencia(regra=regra, comportamento=Comportamento.REVISAO_HUMANA, campos=campos,
                      mensagem=mensagens.mensagem(regra, **valores))
