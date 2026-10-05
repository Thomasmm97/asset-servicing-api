"""Escrita em disco: o JSON do lote, com o relatório de exceções e um objeto por documento (D-31), o relatório em Markdown (D-32)
e o trace (D-30)."""

import json
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

from . import config
from .modelos import Registro, Status

_trace_atual: ContextVar["Trace | None"] = ContextVar("trace_atual", default=None)

ORDEM_TOPO = ["documento", "trace_id", "tipo_pdf", "status", "erro", "regras_aprovadas", "tipo_evento", "campos"]
ORDEM_CAMPO = ["valor", "moeda", "citacao", "citacoes", "confianca", "base_referencia", "revisao_humana", "motivos", "alertas"]


class Trace:
    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        pasta = Path(config.PASTA_TRACES)
        pasta.mkdir(parents=True, exist_ok=True)
        self.arquivo = pasta / f"{trace_id}.jsonl"

    def escrever(self, evento: dict):
        linha = {"trace_id": self.trace_id, "momento": datetime.now().isoformat(timespec="milliseconds"), **evento}
        with open(self.arquivo, "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")


def iniciar_trace(trace_id: str) -> Trace:
    trace = Trace(trace_id)
    _trace_atual.set(trace)
    return trace


def registrar(evento: str, **dados):
    """Registra um evento no trace do documento em processamento nesta thread (se houver)."""
    if trace := _trace_atual.get():
        trace.escrever({"evento": evento, **dados})


@contextmanager
def etapa(nome: str, **dados):
    """Registra uma etapa do pipeline: duração, dados que a etapa acrescentar e erro, se houver."""
    inicio, info = time.perf_counter(), dict(dados)
    try:
        yield info
    except Exception as e:
        info["erro"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        registrar("etapa", etapa=nome, duracao_ms=round((time.perf_counter() - inicio) * 1000), **info)


def para_dict(registro: Registro) -> dict:
    """O registro como o operador o vê: só as chaves preenchidas (D-17), em ordem legível."""
    return _ordenar(registro.model_dump(mode="json", exclude_unset=True))


def gravar_lote(registros: list[Registro], pasta: Path) -> Path:
    """saida/lote.json: o relatório de exceções em tópicos e um objeto por documento; os mesmos tópicos em
    saida/relatorio_excecoes.md (contrato.md, seção 8)."""
    ordenados = sorted(registros, key=lambda r: r.documento)
    topicos = relatorio_em_topicos(relatorio(ordenados))
    dados = {"relatorio_excecoes": topicos, "documentos": [para_dict(r) for r in ordenados]}
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "relatorio_excecoes.md").write_text(relatorio_em_texto(topicos), encoding="utf-8")
    arquivo = pasta / "lote.json"
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return arquivo


def relatorio(registros: list[Registro]) -> dict:
    """Totais do lote e só os documentos com exceção (motivo, alerta ou erro); o registro completo fica em `documentos`."""
    resumos = [_resumo(r) for r in registros]
    return {
        "totais": {
            "processados": len(resumos),
            "aprovados": sum(d["status"] == Status.APROVADO.value for d in resumos),
            "revisao_humana": sum(d["status"] == Status.REVISAO_HUMANA.value for d in resumos),
            "erro": sum(d["status"] == Status.ERRO.value for d in resumos),
            "com_alerta": sum(bool(d["alertas"]) for d in resumos),
        },
        "excecoes": [d for d in resumos if d["motivos"] or d["alertas"] or d["erro"]],
    }


def relatorio_em_topicos(relatorio: dict) -> list[str]:
    """O relatório em tópicos: os totais e uma linha por apontamento, completa em si mesma (D-32)."""
    t = relatorio["totais"]
    topicos = [f"Processados: {t['processados']} · aprovados: {t['aprovados']} · em revisão humana: {t['revisao_humana']} · "
               f"com erro: {t['erro']} · com alerta: {t['com_alerta']}."]
    for d in relatorio["excecoes"]:
        apontamentos = [(d["erro"]["codigo"], [], d["erro"]["mensagem"])] if d["erro"] else []
        apontamentos += [(a["regra"], a["campos"], a["mensagem"]) for a in d["motivos"]]
        apontamentos += [(f"alerta {a['regra']}", a["campos"], a["mensagem"]) for a in d["alertas"]]
        for regra, campos, mensagem in apontamentos:
            onde = f" em {', '.join(campos)}" if campos else ""
            topicos.append(f"{d['documento']} [{d['status']}] {regra}{onde}: {mensagem}".replace("\n", " "))
    return topicos if relatorio["excecoes"] else topicos + ["Nenhuma exceção."]


def relatorio_em_texto(topicos: list[str]) -> str:
    """O relatório em Markdown, para saida/relatorio_excecoes.md: título, totais e os tópicos (D-32)."""
    linhas = ["# Relatório de exceções", "", topicos[0], "", *(f"- {t}" for t in topicos[1:]), "",
              "O registro completo de cada documento está em `documentos`, no `saida/lote.json`; "
              "o rastro técnico, em `saida/traces/<trace_id>.jsonl`."]
    return "\n".join(linhas) + "\n"


def _resumo(registro: Registro) -> dict:
    return {
        "documento": registro.documento,
        "trace_id": registro.trace_id,
        "tipo_evento": registro.tipo_evento.valor.value if registro.tipo_evento else None,
        "status": registro.status.value,
        "erro": registro.erro.model_dump(mode="json") if registro.erro else None,
        "motivos": _agrupar(registro, "motivos"),
        "alertas": _agrupar(registro, "alertas"),
    }


def _agrupar(registro: Registro, tipo: str) -> list[dict]:
    """Um item por apontamento, com todos os campos que ele aponta (ex.: R-ID-01 nos 5 campos de emissor e ativo)."""
    if registro.erro:
        return []
    campos = {"tipo_evento": registro.tipo_evento} | registro.campos.todos()
    agrupados: dict[tuple, list[str]] = {}
    for nome, campo in campos.items():
        for a in getattr(campo, tipo):
            agrupados.setdefault((a.regra, a.mensagem), []).append(nome)
    return [{"regra": regra, "campos": nomes, "mensagem": mensagem} for (regra, mensagem), nomes in agrupados.items()]


def _ordenar(obj):
    if isinstance(obj, list):
        return [_ordenar(x) for x in obj]
    if not isinstance(obj, dict):
        return obj
    ordem = ORDEM_TOPO if "trace_id" in obj else ORDEM_CAMPO if "valor" in obj else []
    chaves = [k for k in ordem if k in obj] + [k for k in obj if k not in ordem]
    return {k: _ordenar(obj[k]) for k in chaves}
