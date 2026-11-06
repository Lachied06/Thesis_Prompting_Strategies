from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.evaluation import (
    blinded_review_package,
    manual_review_rows,
    read_jsonl,
    read_review_condition_lookup,
    render_report,
    summarize_annotations,
    summarize_results,
    write_review_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize objective metrics and prepare reviewer faithfulness review"
    )
    parser.add_argument("--results", required=True, help="Harness results JSONL")
    parser.add_argument("--output-dir", help="Defaults beside results in <stem>.evaluation/")
    parser.add_argument("--annotations", help="Completed manual_review.csv to aggregate")
    parser.add_argument(
        "--blind-review",
        action="store_true",
        help="Generate a randomized review CSV with treatment identities removed",
    )
    parser.add_argument(
        "--review-seed",
        type=int,
        default=0,
        help="Reproducible shuffle seed used with --blind-review (default: 0)",
    )
    parser.add_argument(
        "--review-map",
        help="Mapping JSON generated with --blind-review; required to aggregate a blinded CSV",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _write(path: Path, content: str, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite {path}; pass --overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.blind_review and args.annotations:
        parser.error("--blind-review cannot be combined with --annotations")
    if args.review_map and not args.annotations:
        parser.error("--review-map requires --annotations")
    results_path = Path(args.results)
    output_dir = Path(args.output_dir) if args.output_dir else results_path.with_name(
        f"{results_path.stem}.evaluation"
    )
    rows = read_jsonl(results_path)
    if not rows:
        raise ValueError("Results file contains no records")

    summary = summarize_results(rows)
    try:
        condition_lookup = (
            read_review_condition_lookup(args.review_map) if args.review_map else None
        )
        annotations = (
            summarize_annotations(args.annotations, condition_lookup)
            if args.annotations
            else None
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    combined = {"objective": summary, "reviewer_annotations": annotations}

    summary_path = output_dir / "evaluation_summary.json"
    report_path = output_dir / "evaluation_report.md"
    review_path = output_dir / "manual_review.csv"
    blinded_review_path = output_dir / "manual_review.blinded.csv"
    review_map_path = output_dir / "manual_review.mapping.json"
    _write(summary_path, json.dumps(combined, ensure_ascii=False, indent=2) + "\n", args.overwrite)
    _write(report_path, render_report(summary, annotations), args.overwrite)
    if not args.annotations:
        if args.blind_review:
            if blinded_review_path.exists() and not args.overwrite:
                raise FileExistsError(
                    f"Refusing to overwrite {blinded_review_path}; pass --overwrite"
                )
            blinded_rows, mapping = blinded_review_package(rows, args.review_seed)
            write_review_csv(blinded_review_path, blinded_rows)
            _write(
                review_map_path,
                json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
                args.overwrite,
            )
        else:
            if review_path.exists() and not args.overwrite:
                raise FileExistsError(
                    f"Refusing to overwrite {review_path}; pass --overwrite"
                )
            write_review_csv(review_path, manual_review_rows(rows))

    print(f"Evaluation summary written to {summary_path}")
    print(f"Markdown report written to {report_path}")
    if not args.annotations:
        if args.blind_review:
            print(f"Blinded manual review template written to {blinded_review_path}")
            print(f"Private review mapping written to {review_map_path}")
        else:
            print(f"Manual review template written to {review_path}")


if __name__ == "__main__":
    main()
