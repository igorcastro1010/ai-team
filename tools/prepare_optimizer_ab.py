"""Offline only: prepare a pair from JSON, optionally analyze supplied receipts."""

import argparse
import json
from pathlib import Path

from ai_team.optimizer_ab_benchmark import analyze_receipts, prepare_pair


def read_json(path):
    # Bound reads before JSON parsing; never echo invalid or credential-bearing input.
    with path.open("rb") as handle:
        data = handle.read(500001)
    if len(data) > 500000:
        raise ValueError("Arquivo excede limite offline")
    return json.loads(data.decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Preparar A/B offline; nenhuma inferência")
    parser.add_argument("input", type=Path, help="JSON com argumentos de prepare_pair")
    parser.add_argument("--receipts", type=Path, help="JSON de dois recibos existentes")
    args = parser.parse_args()
    try:
        prepared = prepare_pair(**read_json(args.input))
        output = {"pair": prepared}
        if args.receipts:
            output["analysis"] = analyze_receipts(
                prepared, read_json(args.receipts)
            )
        print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
    except (OSError, ValueError, TypeError):
        parser.exit(2, "Entrada inválida; não inclua credenciais. Nenhuma chamada executada.\n")


if __name__ == "__main__":
    main()
