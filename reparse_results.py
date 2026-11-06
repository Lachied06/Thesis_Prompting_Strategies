from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.evaluation import read_jsonl
from src.reprocessing import RESPONSE_PARSER_VERSION, reparse_result_row


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reparse stored model responses and rebuild response-derived metrics "
            "without calling a model API"
        )
    )
    parser.add_argument("--results", required=True, help="Existing results JSONL")
    parser.add_argument(
        "--output",
        help="Defaults beside the input as <stem>.reparsed.jsonl",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    input_path = Path(args.results)
    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name(f"{input_path.stem}.reparsed.jsonl")
    )
    if input_path.resolve() == output_path.resolve():
        parser.error("--output must differ from --results; the source file is preserved")
    if output_path.exists() and not args.overwrite:
        raise FileExistsError(f"Refusing to overwrite {output_path}; pass --overwrite")

    rows = read_jsonl(input_path)
    if not rows:
        raise ValueError("Results file contains no records")

    reparsed_rows = []
    reparsed_count = 0
    for line_number, row in enumerate(rows, start=1):
        try:
            reparsed, changed = reparse_result_row(row)
        except ValueError as exc:
            raise ValueError(f"Line {line_number}: {exc}") from exc
        reparsed_rows.append(reparsed)
        reparsed_count += int(changed)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False) + "\n" for row in reparsed_rows
        ),
        encoding="utf-8",
    )
    print(f"Reparsed results written to {output_path}")
    print(f"Parser version: {RESPONSE_PARSER_VERSION}")
    print(
        f"Rows: {len(reparsed_rows)} total, {reparsed_count} reparsed, "
        f"{len(reparsed_rows) - reparsed_count} unchanged"
    )


if __name__ == "__main__":
    main()
