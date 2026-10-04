"""Regras de coerência (docs/regras.md): uma função por grupo, cada uma devolve um Resultado.
Também o calendário de pregões da B3 e a base de referência, que só as regras usam."""

import csv
import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from . import config, mensagens
from .modelos import CAMPOS_EXTRAIDOS, Classificacao, Comportamento, Extracao, Ocorrencia, Resultado

NOMES = mensagens.NOMES_CAMPOS
DINHEIRO = {"DIVIDENDO", "JCP"}
COM_PAGAMENTO = {"DIVIDENDO", "JCP", "BONIFICACAO"}
EM_ACOES = {"BONIFICACAO", "DESDOBRAMENTO", "GRUPAMENTO"}
IDENTIFICADORES = ["razao_social", "cnpj", "isin", "ticker", "classe"]


class _Coletor:
    def __init__(self):
        self.resultado = Resultado()

    def aprova(self, regra: str):
        self.resultado.aprovadas.append(regra)

    def falha(self, regra: str, campos: list[str], alerta: bool = False, **valores):
        comportamento = Comportamento.ALERTA if alerta else Comportamento.REVISAO_HUMANA
        self.resultado.ocorrencias.append(
            Ocorrencia(regra=regra, comportamento=comportamento, campos=campos, mensagem=mensagens.mensagem(regra, **valores)))

    def checa(self, regra: str, ok: bool, campos: list[str], alerta: bool = False, **valores):
        if ok:
            self.aprova(regra)
        else:
            self.falha(regra, campos, alerta, **valores)


# ---------- Calendário da B3 (D-12) ----------

def eh_pregao(dia: date) -> bool:
    return dia.weekday() < 5 and dia not in config.FERIADOS_B3


def proximo_pregao(dia: date) -> date:
    seguinte = dia + timedelta(days=1)
    while not eh_pregao(seguinte):
        seguinte += timedelta(days=1)
    return seguinte


# ---------- Base de referência ----------

@lru_cache
def carregar_base(caminho: Path = config.CAMINHO_BASE) -> tuple[dict, ...]:
    with open(caminho, encoding="utf-8") as f:
        return tuple(csv.DictReader(f))


def buscar(base, isin: str | None, cnpj: str | None, classe: str | None) -> tuple[dict | None, str]:
    """Busca pelo ISIN e, se não achar, pelo CNPJ (R-ID-01). Devolve o registro e a chave usada."""
    for registro in base:
        if isin and registro["isin"] == isin:
            return registro, "isin"
    candidatos = [r for r in base if cnpj and _digitos(r["cnpj"]) == _digitos(cnpj)]
    if candidatos:
        return next((r for r in candidatos if r["classe"] == classe), candidatos[0]), "cnpj"
    return None, ""


# ---------- Ferramentas do agente (D-27) ----------

def validar_identificacao(valores: dict) -> Resultado:
    """R-ID-01 a R-ID-04 (base de referência) e R-IDF-01 a R-IDF-06 (formato e coerência)."""
    c = _Coletor()
    isin, cnpj, ticker, classe, nome = (valores.get(k) for k in ("isin", "cnpj", "ticker", "classe", "razao_social"))
    registro, chave = buscar(carregar_base(), isin, cnpj, classe)
    if registro is None:
        c.falha("R-ID-01", IDENTIFICADORES, isin=isin or "—", cnpj=cnpj or "—")
    else:
        c.aprova("R-ID-01")
        divergentes = [k for k in ("cnpj", "isin", "ticker", "classe")
                       if valores.get(k) and _comparavel(k, valores[k]) != _comparavel(k, registro[k])]
        for k in divergentes:
            c.falha("R-ID-02", [k], campo=NOMES[k], valor_aviso=valores[k], valor_base=registro[k])
        if not divergentes:
            c.aprova("R-ID-02")
        if nome:
            c.checa("R-ID-03", _nome(nome) == _nome(registro["emissor"]), ["razao_social"],
                    nome_aviso=nome, nome_base=registro["emissor"])
        c.checa("R-ID-04", registro["status"] == "ativo", [chave], status=registro["status"])
    if isin:
        c.checa("R-IDF-01", bool(re.fullmatch(r"BR[A-Z0-9]{9}\d", isin)), ["isin"], isin=isin)
        if config.VALIDAR_DV_ISIN:
            c.checa("R-IDF-02", isin_valido(isin), ["isin"], isin=isin)
    if cnpj and config.VALIDAR_DV_CNPJ:
        c.checa("R-IDF-03", cnpj_valido(cnpj), ["cnpj"], cnpj=cnpj)
    if ticker:
        c.checa("R-IDF-04", bool(re.fullmatch(r"[A-Z][A-Z0-9]{3}(3|4|5|6|7|8|11)", ticker)), ["ticker"], ticker=ticker)
    if ticker and isin and len(isin) == 12:
        sufixo, codigo_classe = ticker[4:], isin[9:11]
        if sufixo in ("3", "4"):
            esperada = {"3": "ON", "4": "PN"}[sufixo]
            ok = codigo_classe == {"3": "OR", "4": "PR"}[sufixo] and classe in (None, esperada)
            c.checa("R-IDF-05", ok, ["ticker", "isin", "classe"], ticker=ticker, classe_ticker=esperada,
                    classe_isin={"OR": "ON", "PR": "PN"}.get(codigo_classe, codigo_classe), classe_aviso=classe or "—")
        c.checa("R-IDF-06", ticker[:4] == isin[2:6], ["ticker", "isin"], alerta=True, raiz=ticker[:4], codigo=isin[2:6])
    return c.resultado


def validar_datas(valores: dict) -> Resultado:
    """R-DAT-01 a R-DAT-04."""
    c = _Coletor()
    tipo = valores["tipo_evento"]
    aprovacao, com, ex, pagamento = (valores.get(k) for k in ("data_aprovacao", "data_com", "data_ex", "data_pagamento"))
    campo_pagamento = "data_credito" if tipo == "BONIFICACAO" else "data_pagamento"
    if com and ex:
        campos = ["data_aprovacao", "data_com", "data_ex"] if aprovacao else ["data_com", "data_ex"]
        c.checa("R-DAT-01", com < ex and (aprovacao is None or aprovacao <= com), campos,
                aprovacao=_br(aprovacao), data_com=_br(com), data_ex=_br(ex))
        c.checa("R-DAT-03", ex == proximo_pregao(com), ["data_com", "data_ex"],
                data_ex=_br(ex), data_com=_br(com), data_ex_esperada=_br(proximo_pregao(com)))
    mercado = [("data_com", com), ("data_ex", ex)]
    if tipo in COM_PAGAMENTO and pagamento:
        mercado.append((campo_pagamento, pagamento))
        if com:
            c.checa("R-DAT-02", pagamento > com, [campo_pagamento, "data_com"],
                    papel_pagamento=NOMES[campo_pagamento], pagamento=_br(pagamento), data_com=_br(com))
    sem_pregao = [(k, d) for k, d in mercado if d and not eh_pregao(d)]
    for k, d in sem_pregao:
        c.falha("R-DAT-04", [k], papel=NOMES[k], data=_br(d),
                motivo_sem_pregao="fim de semana" if d.weekday() >= 5 else "feriado da B3")
    if not sem_pregao and any(d for _, d in mercado):
        c.aprova("R-DAT-04")
    return c.resultado


def validar_valores_e_proporcao(valores: dict) -> Resultado:
    """R-VAL (provento em dinheiro e custo atribuído) ou R-PRO (evento em ações), conforme a classe."""
    c = _Coletor()
    tipo = valores["tipo_evento"]
    bruto, aliquota, liquido, com = (valores.get(k) for k in ("valor_bruto", "aliquota_irrf", "valor_liquido", "data_com"))
    if tipo in DINHEIRO and bruto:
        c.checa("R-VAL-01", Decimal(bruto) > 0, ["valor_bruto"], valor_bruto=bruto)
    if tipo == "JCP":
        if bruto and aliquota and liquido:
            casas = -Decimal(liquido).as_tuple().exponent
            esperado = Decimal(bruto) * (1 - Decimal(aliquota))
            ok = abs(Decimal(liquido) - esperado) <= Decimal(1).scaleb(-casas)
            c.checa("R-VAL-02", ok, ["valor_bruto", "aliquota_irrf", "valor_liquido"],
                    valor_liquido=liquido, liquido_esperado=f"{esperado:.{casas}f}")
        if aliquota and com:
            vigente = aliquota_vigente(com)
            c.checa("R-VAL-03", Decimal(aliquota) == vigente, ["aliquota_irrf"],
                    aliquota=aliquota, data_com=_br(com), aliquota_vigente=str(vigente))
    if tipo in COM_PAGAMENTO:
        monetarios = [k for k in config.CAMPOS_MONETARIOS if valores.get(k) and k in config.CHAVES_POR_CLASSE[tipo]]
        moeda = valores.get("moeda")
        for k in monetarios:
            if moeda != "BRL":
                c.falha("R-VAL-04", [k], campo=NOMES[k], moeda=moeda or "não identificada")
        if monetarios and moeda == "BRL":
            c.aprova("R-VAL-04")
    if tipo in EM_ACOES and (proporcao := valores.get("proporcao")):
        m = re.fullmatch(r"(\d+):(\d+)", proporcao)
        formato_ok = bool(m) and int(m[1]) > 0 and int(m[2]) > 0
        c.checa("R-PRO-01", formato_ok, ["proporcao"], proporcao=proporcao)
        if formato_ok:
            aumenta = tipo in ("BONIFICACAO", "DESDOBRAMENTO")
            c.checa("R-PRO-02", int(m[2]) > int(m[1]) if aumenta else int(m[2]) < int(m[1]), ["proporcao"],
                    proporcao=proporcao, tipo_evento=tipo, aumentar_ou_diminuir="aumentar" if aumenta else "diminuir")
    if tipo == "BONIFICACAO" and (custo := valores.get("custo_atribuido")):
        c.checa("R-PRO-03", Decimal(custo) > 0, ["custo_atribuido"], custo_atribuido=custo)
    return c.resultado


FERRAMENTAS = {
    "validar_identificacao": validar_identificacao,
    "validar_datas": validar_datas,
    "validar_valores_e_proporcao": validar_valores_e_proporcao,
}


# ---------- Regras que rodam no código, fora do agente ----------

def validar_campos_da_classe(extracao: Extracao, descartados: frozenset[str] = frozenset()) -> Resultado:
    """R-REQ-01 a R-REQ-03. Um campo descartado pelo grounding já tem motivo (R-GRD) e não repete a R-REQ-01."""
    c = _Coletor()
    tipo = extracao.tipo_evento.valor.value
    if tipo == "INDETERMINADO":
        return c.resultado
    obrigatorios = campos_extraidos_da_classe(tipo)
    ausentes, adiados = [], []
    for campo in obrigatorios:
        extraido = getattr(extracao, campo)
        saida = nome_na_saida(campo, tipo)
        if extraido.valor is None and extraido.adiado:
            adiados.append(campo)
            c.falha("R-REQ-02", [saida], campo=NOMES[saida], trecho=" ".join((extraido.trecho or "").split()))
        elif extraido.valor is None and campo not in descartados:
            ausentes.append(campo)
            c.falha("R-REQ-01", [saida], alerta=campo == "data_aprovacao", campo=NOMES[saida], tipo_evento=tipo)
    if not ausentes:
        c.aprova("R-REQ-01")
    if not adiados:
        c.aprova("R-REQ-02")
    fora = [k for k in CAMPOS_EXTRAIDOS if k not in obrigatorios and k != "moeda" and getattr(extracao, k).valor is not None]
    for k in fora:
        c.falha("R-REQ-03", ["tipo_evento"], campo=NOMES[k], tipo_evento=tipo, valor=getattr(extracao, k).valor)
    if not fora:
        c.aprova("R-REQ-03")
    return c.resultado


def verificar_classificacao(classificacao: Classificacao) -> Resultado:
    """R-CLS-01 (título diverge da natureza) e R-CLS-02 (INDETERMINADO)."""
    c = _Coletor()
    tipo = classificacao.valor.value
    if tipo == "INDETERMINADO":
        ind = classificacao.indeterminacao
        c.falha("R-CLS-02", ["tipo_evento"], motivo=ind.motivo.value if ind else "sem motivo",
                justificativa=ind.justificativa if ind else "")
    else:
        c.aprova("R-CLS-02")
    do_titulo = classe_do_titulo(classificacao.titulo)
    c.checa("R-CLS-01", do_titulo in (None, tipo), ["tipo_evento"], titulo=classificacao.titulo, tipo_evento=tipo)
    return c.resultado


# ---------- Apoio ----------

def campos_extraidos_da_classe(tipo: str) -> list[str]:
    """Campos da extração que a classe usa (emissor e ativo abertos; crédito das ações = data_pagamento extraída)."""
    abertos = {"emissor": ["razao_social", "cnpj"], "ativo": ["isin", "ticker", "classe"], "data_credito": ["data_pagamento"]}
    return [k for chave in config.CHAVES_POR_CLASSE[tipo] for k in abertos.get(chave, [chave])]


def nome_na_saida(campo: str, tipo: str) -> str:
    return "data_credito" if campo == "data_pagamento" and tipo == "BONIFICACAO" else campo


def classe_do_titulo(titulo: str) -> str | None:
    t = _sem_acento(titulo).lower()
    padroes = [("JCP", r"juros sobre (o )?capital proprio|\bjcp\b|remuneracao do capital"),
               ("BONIFICACAO", r"bonificacao"), ("DESDOBRAMENTO", r"desdobramento"),
               ("GRUPAMENTO", r"grupamento|inplit"), ("DIVIDENDO", r"dividendo")]
    return next((classe for classe, p in padroes if re.search(p, t)), None)


def aliquota_vigente(dia: date) -> Decimal:
    for inicio, fim, aliquota in config.IRRF_JCP:
        if (inicio is None or dia >= inicio) and (fim is None or dia <= fim):
            return aliquota
    raise ValueError(f"sem alíquota de IRRF configurada para {dia}")


def isin_valido(isin: str) -> bool:
    digitos = "".join(str(int(ch, 36)) for ch in isin[:-1])
    soma = 0
    for i, d in enumerate(reversed(digitos)):
        n = int(d) * (2 if i % 2 == 0 else 1)
        soma += n - 9 if n > 9 else n
    return (10 - soma % 10) % 10 == int(isin[-1])


def cnpj_valido(cnpj: str) -> bool:
    d = [int(x) for x in _digitos(cnpj)]
    if len(d) != 14:
        return False
    for tamanho in (12, 13):
        pesos = list(range(tamanho - 7, 1, -1)) + list(range(9, 1, -1))
        resto = sum(a * b for a, b in zip(d[:tamanho], pesos)) % 11
        if d[tamanho] != (0 if resto < 2 else 11 - resto):
            return False
    return True


def _br(dia: date | None) -> str:
    return dia.strftime("%d/%m/%Y") if dia else "—"


def _digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _comparavel(campo: str, valor: str) -> str:
    return _digitos(valor) if campo == "cnpj" else valor.strip().upper()


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def _nome(s: str) -> str:
    """Normaliza a razão social para a R-ID-03: caixa, acentos, pontuação, Cia. = Companhia, S/A = S.A."""
    s = _sem_acento(s).lower()
    s = re.sub(r"\bs\s*[./]\s*a\b\.?", " sa ", s)
    s = re.sub(r"\bcia\b", "companhia", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()
