"""CLI: python -m asset_servicing [entrada/documentos/] [--saida saida/]"""

import argparse
from pathlib import Path

from . import config
from .pipeline import processar_lote


def main():
    parser = argparse.ArgumentParser(description="Processa o lote de avisos de eventos corporativos.")
    parser.add_argument("pasta", nargs="?", default=config.PASTA_DOCUMENTOS, type=Path)
    parser.add_argument("--saida", default=config.RAIZ / "saida", type=Path)
    parser.add_argument("--workers", default=config.WORKERS, type=int)
    args = parser.parse_args()
    for r in processar_lote(args.pasta, args.saida, args.workers):
        print(f"{r.status.value:15s} {r.documento}")
    print(f"Saída em {args.saida}/lote.json (relatório de exceções + um objeto por documento)")


if __name__ == "__main__":
    main()
