"""Compara a saída com evals/gabarito.csv e imprime as métricas do contrato (docs/contrato.md, seção 9).

Uso: python -m evals.avaliar [saida/]
"""

import csv
import json
import sys
from pathlib import Path

from asset_servicing.regras import _nome

RAIZ = Path(__file__).resolve().parent.parent
AUSENTE = object()  # chave que não existe na classe (gabarito: n/a)
COLUNAS = ["emissor", "cnpj", "isin", "ticker", "classe_acao", "tipo_evento", "data_aprovacao", "data_com", "data_ex",
           "data_pagamento", "valor_bruto", "aliquota_irrf", "valor_liquido", "proporcao", "custo_atribuido", "moeda"]


def carregar_gabarito(caminho: Path = RAIZ / "evals" / "gabarito.csv") -> dict[str, dict]:
    with open(caminho, encoding="utf-8") as f:
        return {linha["doc"]: linha for linha in csv.DictReader(f)}


def achatar(registro: dict) -> dict[str, tuple]:
    """Coluna do gabarito → (valor obtido, revisão humana do campo) (contrato.md, seção 10)."""
    c, t = registro["campos"], registro["tipo_evento"]

    def de(campo):
        return (campo["valor"], campo["revisao_humana"]) if campo else (AUSENTE, False)

    monetario = c.get("valor_bruto") or c.get("custo_atribuido")
    return {
        "emissor": de(c["emissor"]["razao_social"]), "cnpj": de(c["emissor"]["cnpj"]),
        "isin": de(c["ativo"]["isin"]), "ticker": de(c["ativo"]["ticker"]), "classe_acao": de(c["ativo"]["classe"]),
        "tipo_evento": (t["valor"], t["revisao_humana"]),
        **{k: de(c.get(k)) for k in ("data_aprovacao", "data_com", "data_ex", "valor_bruto", "aliquota_irrf",
                                     "valor_liquido", "proporcao", "custo_atribuido")},
        "data_pagamento": de(c.get("data_pagamento") or c.get("data_credito")),
        "moeda": (monetario["moeda"], monetario["revisao_humana"]) if monetario else (AUSENTE, False),
    }


def falhas(registro: dict, esperado: dict) -> list[str]:
    """Métricas com meta que esta execução não cumpriu; lista vazia = execução aprovada."""
    if registro["status"] == "ERRO":
        return [f"erro de processamento: {registro['erro']['mensagem'][:120]}"]
    obtido, saida = achatar(registro), []
    errados = [col for col in COLUNAS if not _igual(col, obtido[col][0], esperado[col])]
    if errados:
        saida.append("acurácia por campo: " + ", ".join(f"{c}={_mostrar(obtido[c][0])} (esperado {esperado[c] or 'vazio'})" for c in errados))
    if nao_roteados := [c for c in errados if not obtido[c][1]]:
        saida.append("erro não roteado: " + ", ".join(nao_roteados))
    inventados = [c for c in COLUNAS if esperado[c] in ("", "n/a") and obtido[c][0] not in (None, AUSENTE)]
    inventados += [m["mensagem"] for m in registro["tipo_evento"]["motivos"] if m["regra"] == "R-REQ-03"]
    if inventados:
        saida.append("valor inventado: " + "; ".join(inventados))
    if obtido["tipo_evento"][0] != esperado["tipo_evento"]:
        saida.append(f"classificação: {obtido['tipo_evento'][0]} (esperado {esperado['tipo_evento']})")
    if (registro["status"] != "APROVADO") != (esperado["revisao_humana"] == "sim"):
        saida.append(f"roteamento: {registro['status']} (esperado revisão = {esperado['revisao_humana']})")
    motivos = _regras_dos_motivos(registro)
    esperados = {m for m in esperado["motivo_revisao"].split(";") if m}
    if motivos != esperados:
        saida.append(f"motivo: {sorted(motivos)} (esperado {sorted(esperados)})")
    return saida


def _regras_dos_motivos(registro: dict) -> set[str]:
    campos = [registro["tipo_evento"]]
    for chave, campo in registro["campos"].items():
        campos += list(campo.values()) if chave in ("emissor", "ativo") else [campo]
    return {m["regra"] for c in campos for m in c["motivos"]}


def _igual(coluna: str, obtido, esperado: str) -> bool:
    if esperado == "n/a":
        return obtido is AUSENTE
    if esperado == "":
        return obtido is None
    if obtido in (None, AUSENTE):
        return False
    return _nome(obtido) == _nome(esperado) if coluna == "emissor" else str(obtido) == esperado


def _mostrar(valor) -> str:
    return "ausente" if valor is AUSENTE else str(valor)


def main(pasta: Path = RAIZ / "saida"):
    gabarito = carregar_gabarito()
    totais = {"aprovados na meta": 0}
    for arquivo in sorted(pasta.glob("*.json")):
        registro = json.loads(arquivo.read_text(encoding="utf-8"))
        problemas = falhas(registro, gabarito[arquivo.stem])
        totais["aprovados na meta"] += not problemas
        print(f"{'OK   ' if not problemas else 'FALHA'} {arquivo.stem} [{registro['status']}]")
        for p in problemas:
            print(f"      - {p}")
    print(f"\n{totais['aprovados na meta']}/{len(gabarito)} documentos dentro de todas as metas")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "saida")
