"""Montagem do registro de saída: confiança por campo (D-20, R-CNF-01), chaves da classe (D-17) e erro (D-18)."""

from datetime import date

from . import config, mensagens
from .evidencias import Span, normalizar_texto, rotulo_confere, span_no_trecho
from .modelos import (Apontamento, Ativo, BaseReferencia, Campo, CampoExtraido, CampoTipoEvento, Campos, Citacao,
                      CodigoErro, Comportamento, Confianca, Emissor, Erro, Extracao, Leitura, NivelConfianca, Ocorrencia,
                      RegraAprovada, Registro, Resultado, TipoPdf)
from .regras import IDENTIFICADORES, nome_na_saida

OPCIONAIS = ["data_pagamento", "valor_bruto", "aliquota_irrf", "valor_liquido", "proporcao", "custo_atribuido"]


def calcular_confianca(campo: str, extraido: CampoExtraido, span: Span | None, leitura: Leitura,
                       confirmacoes: list[str]) -> tuple[Confianca | None, list[Ocorrencia]]:
    """Nível de confiança do campo (D-20) e, se o OCR ficou abaixo do limite, a ocorrência R-CNF-01."""
    if extraido.valor is None:
        return None, []
    ocr = None
    if leitura.tipo_pdf == TipoPdf.ESCANEADO and span:
        confiancas = [p.confianca for p in leitura.palavras  # pontilhados e símbolos soltos não são o valor
                      if p.confianca is not None and p.inicio < span[1] and p.fim > span[0] and any(ch.isalnum() for ch in p.texto)]
        ocr = round(min(confiancas), 2) if confiancas else None
    if ocr is not None and ocr < config.LIMITE_OCR:
        ocorrencia = Ocorrencia(regra="R-CNF-01", comportamento=Comportamento.REVISAO_HUMANA, campos=[campo],
                                mensagem=mensagens.mensagem("R-CNF-01", campo=mensagens.NOMES_CAMPOS[campo], valor=extraido.valor,
                                                            confianca_ocr=_num(ocr), limite=_num(config.LIMITE_OCR)))
        return Confianca(nivel=NivelConfianca.BAIXA, ocr=ocr, modelo=None,
                         justificativa=f"OCR {_num(ocr)}, abaixo do limite de {_num(config.LIMITE_OCR)}."), [ocorrencia]
    prefixo = f"OCR {_num(ocr)}; " if ocr is not None else ""
    if confirmacoes:
        return Confianca(nivel=NivelConfianca.ALTA, ocr=ocr, modelo=None,
                         justificativa=_frase(prefixo + "confirmado por " + ", ".join(confirmacoes) + ".")), []
    return Confianca(nivel=NivelConfianca.MEDIA, ocr=ocr, modelo=None,
                     justificativa=_frase(prefixo + "sem confirmação independente: sem rótulo do campo na citação, "
                                          "base de referência ou regra cruzada.")), []


def montar_registro(leitura: Leitura, extracao: Extracao, valores: dict[str, object],
                    resultados: list[Resultado], spans: dict[str, Span], trace_id: str) -> Registro:
    tipo = extracao.tipo_evento.valor.value
    ocorrencias = [o for r in resultados for o in r.ocorrencias]
    aprovadas = {a for r in resultados for a in r.aprovadas}
    base = _base_por_campo(ocorrencias)

    def campo(nome: str) -> Campo:
        saida = nome_na_saida(nome, tipo)
        extraido = getattr(extracao, nome)
        confianca, cnf = calcular_confianca(saida, extraido, spans.get(nome), leitura,
                                            _confirmacoes(nome, extraido, base, aprovadas))
        ocorrencias.extend(cnf)
        dados = dict(valor=_texto(valores.get(nome)),
                     citacao=Citacao(pagina=extraido.pagina or 1, trecho=extraido.trecho) if extraido.trecho else None,
                     confianca=confianca,
                     motivos=_apontamentos(ocorrencias, saida, Comportamento.REVISAO_HUMANA),
                     alertas=_apontamentos(ocorrencias, saida, Comportamento.ALERTA))
        if nome in config.CAMPOS_MONETARIOS:
            dados["moeda"] = valores.get("moeda")
        if nome in IDENTIFICADORES:
            dados["base_referencia"] = base[nome]
        return Campo(**dados)

    chaves = {"emissor": Emissor(razao_social=campo("razao_social"), cnpj=campo("cnpj")),
              "ativo": Ativo(isin=campo("isin"), ticker=campo("ticker"), classe=campo("classe"))}
    for chave in config.CHAVES_POR_CLASSE[tipo]:
        if chave not in chaves:
            chaves[chave] = campo("data_pagamento" if chave == "data_credito" else chave)
    if tipo == "INDETERMINADO":
        chaves |= {k: campo(k) for k in OPCIONAIS if getattr(extracao, k).valor is not None}

    sinais = extracao.tipo_evento.sinais
    nivel = NivelConfianca.ALTA if len(sinais) >= 2 and tipo != "INDETERMINADO" else NivelConfianca.MEDIA
    tipo_evento = CampoTipoEvento(
        valor=extracao.tipo_evento.valor, citacoes=sinais,
        confianca=Confianca(nivel=nivel, ocr=None, modelo=None,
                            justificativa=f"{len(sinais)} sinal(is) de natureza citado(s)."),
        motivos=_apontamentos(ocorrencias, "tipo_evento", Comportamento.REVISAO_HUMANA),
        alertas=_apontamentos(ocorrencias, "tipo_evento", Comportamento.ALERTA))

    if leitura.tipo_pdf == TipoPdf.ESCANEADO and not any(o.regra == "R-CNF-01" for o in ocorrencias):
        aprovadas.add("R-CNF-01")
    falhas = {o.regra for o in ocorrencias}
    regras_aprovadas = [RegraAprovada(regra=r, descricao=mensagens.descricao(r))
                        for r in mensagens.REGRAS if r in aprovadas and r not in falhas]
    return Registro(documento=leitura.documento, trace_id=trace_id, tipo_pdf=leitura.tipo_pdf, erro=None,
                    regras_aprovadas=regras_aprovadas, tipo_evento=tipo_evento, campos=Campos(**chaves))


def registro_de_erro(documento: str, trace_id: str, tipo_pdf: TipoPdf | None, codigo: CodigoErro, detalhe: str) -> Registro:
    return Registro(documento=documento, trace_id=trace_id, tipo_pdf=tipo_pdf,
                    erro=Erro(codigo=codigo, mensagem=mensagens.mensagem_erro(codigo.value, detalhe=detalhe)),
                    regras_aprovadas=[], tipo_evento=None, campos=None)


def _base_por_campo(ocorrencias: list[Ocorrencia]) -> dict[str, BaseReferencia]:
    """CONFERE, DIVERGE ou NAO_ENCONTRADO por campo, derivado das ocorrências de R-ID."""
    if any(o.regra == "R-ID-01" for o in ocorrencias):
        return {k: BaseReferencia.NAO_ENCONTRADO for k in IDENTIFICADORES}
    divergentes = {k for o in ocorrencias if o.regra in ("R-ID-02", "R-ID-03") for k in o.campos}
    return {k: BaseReferencia.DIVERGE if k in divergentes else BaseReferencia.CONFERE for k in IDENTIFICADORES}


def _confirmacoes(nome: str, extraido: CampoExtraido, base: dict, aprovadas: set[str]) -> list[str]:
    confirmacoes = []
    if extraido.valor and extraido.trecho:
        span = span_no_trecho(nome, extraido.valor, extraido.trecho)
        if span and rotulo_confere(nome, normalizar_texto(extraido.trecho)[0], span):
            confirmacoes.append("rótulo do campo na citação")
    if base.get(nome) == BaseReferencia.CONFERE:
        confirmacoes.append("base de referência")
    if nome in ("data_com", "data_ex") and "R-DAT-03" in aprovadas:
        confirmacoes.append("R-DAT-03")
    if nome in ("valor_bruto", "aliquota_irrf", "valor_liquido") and "R-VAL-02" in aprovadas:
        confirmacoes.append("R-VAL-02")
    return confirmacoes


def _apontamentos(ocorrencias: list[Ocorrencia], campo: str, comportamento: Comportamento) -> list[Apontamento]:
    vistos, saida = set(), []
    for o in ocorrencias:
        if campo in o.campos and o.comportamento == comportamento and (o.regra, o.mensagem) not in vistos:
            vistos.add((o.regra, o.mensagem))
            saida.append(Apontamento(regra=o.regra, mensagem=o.mensagem))
    return saida


def _texto(valor: object) -> str | None:
    if valor is None:
        return None
    return valor.isoformat() if isinstance(valor, date) else str(valor)


def _num(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def _frase(s: str) -> str:
    return s[0].upper() + s[1:]
