"""Escrita em disco: JSON do operador, relatório de exceções e trace por documento (D-30)."""

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


def gravar_registro(registro: Registro, pasta: Path) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"{Path(registro.documento).stem}.json"
    arquivo.write_text(json.dumps(para_dict(registro), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return arquivo


def gerar_relatorio(registros: list[Registro], pasta: Path) -> Path:
    """Relatório de exceções (contrato.md, seção 8)."""
    contagem = {s: sum(r.status == s for r in registros) for s in Status}
    com_alerta = [r for r in registros if _apontamentos(r, "alertas")]
    linhas = ["# Relatório de exceções", "",
              f"Processados: {len(registros)} · Aprovados: {contagem[Status.APROVADO]} · "
              f"Revisão humana: {contagem[Status.REVISAO_HUMANA]} · Erro: {contagem[Status.ERRO]} · "
              f"Com alerta: {len(com_alerta)}", "",
              "| Documento | Tipo de evento | Status | Motivos | Alertas |", "|---|---|---|---|---|"]
    limpos = []
    for r in sorted(registros, key=lambda r: r.documento):
        motivos, alertas = _apontamentos(r, "motivos"), _apontamentos(r, "alertas")
        if r.erro:
            motivos = [f"{r.erro.codigo.value}: {r.erro.mensagem}"]
        if not motivos and not alertas:
            limpos.append(Path(r.documento).stem)
            continue
        tipo = r.tipo_evento.valor.value if r.tipo_evento else "—"
        linhas.append(f"| {Path(r.documento).stem} | {tipo} | {r.status.value} | "
                      f"{'<br>'.join(motivos) or '—'} | {'<br>'.join(alertas) or '—'} |")
    linhas += ["", "Aprovados sem exceção: " + (", ".join(limpos) or "nenhum") + "."]
    arquivo = pasta / "relatorio_excecoes.md"
    arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return arquivo


def _apontamentos(registro: Registro, tipo: str) -> list[str]:
    """'R-ID-01 (razao_social, cnpj): mensagem', juntando os campos que têm o mesmo apontamento."""
    if registro.erro:
        return []
    campos = {"tipo_evento": registro.tipo_evento} | registro.campos.todos()
    agrupados: dict[tuple, list[str]] = {}
    for nome, campo in campos.items():
        for a in getattr(campo, tipo):
            agrupados.setdefault((a.regra, a.mensagem), []).append(nome)
    return [f"{regra} ({', '.join(nomes)}): {mensagem}" for (regra, mensagem), nomes in agrupados.items()]


def _ordenar(obj):
    if isinstance(obj, list):
        return [_ordenar(x) for x in obj]
    if not isinstance(obj, dict):
        return obj
    ordem = ORDEM_TOPO if "trace_id" in obj else ORDEM_CAMPO if "valor" in obj else []
    chaves = [k for k in ordem if k in obj] + [k for k in obj if k not in ordem]
    return {k: _ordenar(obj[k]) for k in chaves}
