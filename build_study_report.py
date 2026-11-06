from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from src.atomic_evaluation import (
    read_jsonl as read_atomic_jsonl,
    summarize_atomic_consensus,
)
from src.evaluation import summarize_results


def _write(path: Path, content: str, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite {path}; pass --overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fmt_percent(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}%"


def _fmt_number(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def _fmt_effect(value: Any, interval: Any) -> str:
    if value is None:
        return "n/a"
    if not interval:
        return f"{float(value):+.3f}"
    return (
        f"{float(value):+.3f} "
        f"[{float(interval[0]):+.3f}, {float(interval[1]):+.3f}]"
    )


def combined_condition_rows(
    objective: Dict[str, Any],
    atomic: Dict[str, Any],
) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    objective_conditions = objective.get("conditions", {})
    atomic_conditions = atomic.get("conditions", {})
    for condition in sorted(set(objective_conditions) | set(atomic_conditions)):
        objective_values = objective_conditions.get(condition, {})
        atomic_values = atomic_conditions.get(condition, {})
        citation = objective_values.get("citation_metrics", {})
        tokens = objective_values.get("tokens", {})
        latency = objective_values.get("latency_seconds", {})
        rows.append(
            {
                "condition": condition,
                "provider": objective_values.get("provider"),
                "model": objective_values.get("model"),
                "strategy": objective_values.get("strategy"),
                "strategy_version": objective_values.get("version"),
                "responses": atomic_values.get("consensus_responses"),
                "verdict_accuracy": objective_values.get("accuracy"),
                "abstention_rate": objective_values.get("abstention_rate"),
                "false_no_evidence_rate_on_decisive_tasks": objective_values.get(
                    "false_no_evidence_rate_on_decisive_tasks"
                ),
                "no_evidence_recall": objective_values.get("no_evidence_recall"),
                "mean_factual_claims_per_response": atomic_values.get(
                    "mean_evaluable_claims_per_response"
                ),
                "mean_supported_claims_per_response": atomic_values.get(
                    "mean_consensus_supported_claims_per_response"
                ),
                "consensus_supported_claim_rate": atomic_values.get(
                    "consensus_supported_claim_rate"
                ),
                "mean_response_consensus_unsupported_claim_rate": atomic_values.get(
                    "mean_response_consensus_unsupported_claim_rate"
                ),
                "mean_response_possible_unsupported_claim_rate": atomic_values.get(
                    "mean_response_possible_unsupported_claim_rate"
                ),
                "consensus_response_hallucination_rate": atomic_values.get(
                    "consensus_response_hallucination_rate"
                ),
                "possible_response_hallucination_rate": atomic_values.get(
                    "possible_response_hallucination_rate"
                ),
                "uncertain_claim_rate": atomic_values.get("uncertain_claim_rate"),
                "claim_citation_coverage": atomic_values.get(
                    "consensus_claim_citation_coverage"
                ),
                "citation_support_rate": atomic_values.get(
                    "consensus_citation_support_rate"
                ),
                "invalid_identifier_response_rate": citation.get(
                    "invalid_citation_response_rate"
                ),
                "mean_response_word_count": citation.get("mean_response_word_count"),
                "api_calls": objective_values.get("api_calls"),
                "mean_generation_tokens_per_response": tokens.get(
                    "mean_total_per_run"
                ),
                "mean_generation_latency_seconds": latency.get("mean"),
                "support_binary_agreement": atomic_values.get(
                    "support_binary_agreement"
                ),
                "hallucination_type_counts": atomic_values.get(
                    "consensus_hallucination_type_counts", {}
                ),
            }
        )
    return rows


def render_study_report(
    objective: Dict[str, Any],
    atomic: Dict[str, Any],
    rows: Iterable[Dict[str, Any]],
) -> str:
    materialized = list(rows)
    lines = [
        "# Confirmatory strategy analysis",
        "",
        "## Overall strategy outcomes",
        "",
        "| Condition | Responses | Verdict accuracy | Mean supported claims | Mean consensus unsupported | Mean possible unsupported | Any consensus unsupported | Any possible unsupported | Citation support | Mean tokens | Mean latency (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in materialized:
        lines.append(
            f"| {row['condition']} | {row['responses'] or 0} | "
            f"{_fmt_percent(row['verdict_accuracy'])} | "
            f"{_fmt_number(row['mean_supported_claims_per_response'])} | "
            f"{_fmt_percent(row['mean_response_consensus_unsupported_claim_rate'])} | "
            f"{_fmt_percent(row['mean_response_possible_unsupported_claim_rate'])} | "
            f"{_fmt_percent(row['consensus_response_hallucination_rate'])} | "
            f"{_fmt_percent(row['possible_response_hallucination_rate'])} | "
            f"{_fmt_percent(row['citation_support_rate'])} | "
            f"{_fmt_number(row['mean_generation_tokens_per_response'])} | "
            f"{_fmt_number(row['mean_generation_latency_seconds'])} |"
        )

    lines.extend(
        [
            "",
            "## Content, abstention, and measurement checks",
            "",
            "| Condition | Mean factual claims | Supported-claim rate | NO_EVIDENCE prediction | False NO_EVIDENCE on decisive tasks | NO_EVIDENCE recall | Citation coverage | Invalid-ID responses | Mean words | Judge binary agreement |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in materialized:
        lines.append(
            f"| {row['condition']} | "
            f"{_fmt_number(row['mean_factual_claims_per_response'])} | "
            f"{_fmt_percent(row['consensus_supported_claim_rate'])} | "
            f"{_fmt_percent(row['abstention_rate'])} | "
            f"{_fmt_percent(row['false_no_evidence_rate_on_decisive_tasks'])} | "
            f"{_fmt_percent(row['no_evidence_recall'])} | "
            f"{_fmt_percent(row['claim_citation_coverage'])} | "
            f"{_fmt_percent(row['invalid_identifier_response_rate'])} | "
            f"{_fmt_number(row['mean_response_word_count'])} | "
            f"{_fmt_percent(row['support_binary_agreement'])} |"
        )

    lines.extend(
        [
            "",
            "## Consensus hallucination types",
            "",
            "| Condition | Unsupported addition | Source contradiction | Evidence overstatement | Entity/context confusion | Other | Uncertain type |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in materialized:
        counts = row.get("hallucination_type_counts") or {}
        lines.append(
            f"| {row['condition']} | {counts.get('UNSUPPORTED_ADDITION', 0)} | "
            f"{counts.get('SOURCE_CONTRADICTION', 0)} | "
            f"{counts.get('EVIDENCE_OVERSTATEMENT', 0)} | "
            f"{counts.get('ENTITY_CONTEXT_CONFUSION', 0)} | "
            f"{counts.get('OTHER', 0)} | {counts.get('UNCERTAIN_TYPE', 0)} |"
        )

    paired = atomic.get("paired_strategy_effects_vs_baseline", {})
    if paired:
        lines.extend(
            [
                "",
                "## Paired effects versus baseline",
                "",
                "Negative hallucination-rate differences favour the named strategy. "
                "Positive supported-claim differences indicate more source-supported content.",
                "",
                "| Model | Strategy | Paired tasks | Consensus-rate difference | Possible-rate difference | Supported-claim difference | Factual-claim difference |",
                "|---|---|---:|---:|---:|---:|---:|",
            ]
        )
        for model, strategies in paired.items():
            for strategy, values in strategies.items():
                lines.append(
                    f"| {model} | {strategy} | {values['paired_responses']} | "
                    f"{_fmt_effect(values.get('mean_paired_consensus_unsupported_claim_rate_difference'), values.get('paired_consensus_unsupported_claim_rate_difference_95ci'))} | "
                    f"{_fmt_effect(values.get('mean_paired_possible_unsupported_claim_rate_difference'), values.get('paired_possible_unsupported_claim_rate_difference_95ci'))} | "
                    f"{_fmt_effect(values.get('mean_paired_consensus_supported_claim_count_difference'), values.get('paired_consensus_supported_claim_count_difference_95ci'))} | "
                    f"{_fmt_number(values.get('mean_paired_evaluable_claim_count_difference'), 3)} |"
                )

    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- The primary endpoint is the paired mean per-response consensus "
            "unsupported-claim proportion; the either-judge measure is a sensitivity endpoint.",
            "- The judges are automated and the labels are not human-validated ground truth.",
            "- Bracketed intervals are deterministic paired cluster-bootstrap 95% "
            "intervals, clustered by original SciFact source item when available. "
            "They quantify source-task sampling uncertainty conditional on the "
            "automated labels, not judge validity.",
            "- Strategy effects refer to complete prompt packages. Chain of Verification "
            "also uses additional requests and computation.",
            "- Citation measures concern supplied document identifiers and semantic "
            "claim-source support, not unconstrained bibliographic-reference fabrication.",
            "- Accuracy, supported-claim yield, abstention, and cost must be interpreted "
            "beside hallucination rates; a strategy is not better merely because it says less.",
            "",
        ]
    )
    return "\n".join(lines)


def write_condition_csv(path: Path, rows: Iterable[Dict[str, Any]], overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite {path}; pass --overwrite")
    materialized = list(rows)
    if not materialized:
        raise ValueError("No conditions were available for the study report")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        key for key in materialized[0] if key != "hallucination_type_counts"
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(
            {
                key: value
                for key, value in row.items()
                if key != "hallucination_type_counts"
            }
            for row in materialized
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Combine objective and dual-judge metrics into one study report"
    )
    parser.add_argument("--results", required=True, help="Harness results JSONL")
    parser.add_argument(
        "--consensus", required=True, help="Atomic consensus JSONL from both judges"
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    results = read_atomic_jsonl(args.results)
    consensus_records = read_atomic_jsonl(args.consensus)
    if not results or not consensus_records:
        raise ValueError("Results and consensus files must both contain records")

    objective = summarize_results(results)
    atomic = summarize_atomic_consensus(consensus_records)
    rows = combined_condition_rows(objective, atomic)
    output_dir = Path(args.output_dir)
    combined = {
        "study_report_schema_version": "1.0.0",
        "objective": objective,
        "atomic_consensus": atomic,
        "combined_conditions": rows,
    }
    _write(
        output_dir / "study_summary.json",
        json.dumps(combined, ensure_ascii=False, indent=2) + "\n",
        args.overwrite,
    )
    _write(
        output_dir / "study_report.md",
        render_study_report(objective, atomic, rows),
        args.overwrite,
    )
    write_condition_csv(
        output_dir / "strategy_results.csv",
        rows,
        args.overwrite,
    )
    print(f"Study summary written to {output_dir / 'study_summary.json'}")
    print(f"Study report written to {output_dir / 'study_report.md'}")
    print(f"Strategy table written to {output_dir / 'strategy_results.csv'}")


if __name__ == "__main__":
    main()
