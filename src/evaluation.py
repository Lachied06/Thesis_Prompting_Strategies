from __future__ import annotations

import csv
import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from src.parsing import parse_response
from src.schemas import Task


REVIEW_FIELDS = (
    "faithfulness_score",
    "unsupported_claim",
    "source_misrepresentation",
    "fabricated_citation",
    "excessive_abstention",
    "ambiguous_task",
    "reviewer_notes",
)
YES_NO_FIELDS = REVIEW_FIELDS[1:6]
BLINDED_REVIEW_FIELDS = (
    "review_id",
    "task_prompt",
    "source_context",
    "explanation",
    *REVIEW_FIELDS,
)
REVIEW_MAPPING_SCHEMA_VERSION = "1.0.0"


def read_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
    return rows


def _strategy_identity(row: Dict[str, Any]) -> tuple[str, str, str]:
    strategy = row.get("strategy") or {}
    name = str(strategy.get("name") or "unknown")
    version = strategy.get("version")
    if not version:
        templates = strategy.get("templates") or []
        version = templates[0].get("template_version") if templates else "unknown"
    version = str(version)
    return name, version, f"{name}@{version}"


def _model_identity(row: Dict[str, Any]) -> tuple[str, str]:
    model = row.get("model") or {}
    return (
        str(model.get("provider") or "unknown"),
        str(model.get("name") or "unknown"),
    )


def _condition_identity(
    row: Dict[str, Any], *, include_model: bool
) -> tuple[str, str, str]:
    name, version, strategy_condition = _strategy_identity(row)
    if not include_model:
        return name, version, strategy_condition
    provider, model = _model_identity(row)
    return name, version, f"{provider}:{model} | {strategy_condition}"


def _rate(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator / denominator, 4) if denominator else None


def _mean(values: List[float]) -> Optional[float]:
    return round(statistics.mean(values), 4) if values else None


def _median(values: List[float]) -> Optional[float]:
    return round(statistics.median(values), 4) if values else None


def _initial_label(row: Dict[str, Any]) -> Optional[str]:
    trace = row.get("trace") or []
    if not trace:
        return None
    raw = ((trace[0].get("response") or {}).get("text")) or ""
    task = Task(
        task_id="evaluation",
        dataset=str((row.get("dataset") or {}).get("name", "unknown")),
        prompt="",
        metadata={"task_type": "scientific_claim_verification"},
    )
    return parse_response(raw, task).parsed_label


def summarize_results(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    materialized = list(rows)
    include_model = len({_model_identity(row) for row in materialized}) > 1
    buckets: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "runs": 0,
            "statuses": Counter(),
            "parse_statuses": Counter(),
            "task_types": Counter(),
            "correct": 0,
            "scored": 0,
            "labelled_predictions": 0,
            "abstentions": 0,
            "decisive_truth_tasks": 0,
            "false_no_evidence_predictions": 0,
            "no_evidence_truth_tasks": 0,
            "correct_no_evidence_predictions": 0,
            "predicted": Counter(),
            "truth": Counter(),
            "confusion": Counter(),
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "latencies": [],
            "cov_changes": Counter(),
            "citation_applicable": 0,
            "citation_parse_statuses": Counter(),
            "responses_with_citations": 0,
            "responses_with_invalid_citations": 0,
            "cited_documents": 0,
            "invalid_citations": 0,
            "word_counts": [],
            "word_count_applicable": 0,
            "word_count_compliant": 0,
        }
    )

    for row in materialized:
        name, version, condition = _condition_identity(
            row, include_model=include_model
        )
        bucket = buckets[condition]
        bucket["name"] = name
        bucket["version"] = version
        provider, model = _model_identity(row)
        bucket["provider"] = provider
        bucket["model"] = model
        bucket["runs"] += 1
        status = str(row.get("status") or "unknown")
        bucket["statuses"][status] += 1
        task_type = str(
            ((row.get("task") or {}).get("metadata") or {}).get("task_type")
            or "unknown"
        )
        bucket["task_types"][task_type] += 1
        trace = row.get("trace") or []
        bucket["calls"] += len(trace)

        metrics = row.get("metrics") or {}
        bucket["input_tokens"] += int(metrics.get("input_tokens") or 0)
        bucket["output_tokens"] += int(metrics.get("output_tokens") or 0)
        bucket["reasoning_tokens"] += int(metrics.get("reasoning_tokens") or 0)
        if metrics.get("latency_seconds") is not None:
            bucket["latencies"].append(float(metrics["latency_seconds"]))

        response = row.get("response") or {}
        parse_status = str(response.get("parse_status") or "missing")
        bucket["parse_statuses"][parse_status] += 1
        predicted = response.get("parsed_label")
        truth = (row.get("ground_truth") or {}).get("label")
        if predicted:
            bucket["labelled_predictions"] += 1
            bucket["predicted"][predicted] += 1
            bucket["abstentions"] += int(predicted == "NO_EVIDENCE")
        if truth:
            bucket["truth"][truth] += 1
        if predicted and truth:
            bucket["scored"] += 1
            bucket["correct"] += int(predicted == truth)
            bucket["confusion"][(truth, predicted)] += 1
            if truth == "NO_EVIDENCE":
                bucket["no_evidence_truth_tasks"] += 1
                bucket["correct_no_evidence_predictions"] += int(
                    predicted == "NO_EVIDENCE"
                )
            else:
                bucket["decisive_truth_tasks"] += 1
                bucket["false_no_evidence_predictions"] += int(
                    predicted == "NO_EVIDENCE"
                )

        if task_type == "academic_evidence_synthesis":
            bucket["citation_applicable"] += 1
            cited_document_ids = response.get("cited_document_ids") or []
            invalid_document_ids = response.get("invalid_cited_document_ids") or []
            citation_parse_status = str(
                response.get("citation_parse_status") or "missing"
            )
            bucket["citation_parse_statuses"][citation_parse_status] += 1
            bucket["responses_with_citations"] += int(bool(cited_document_ids))
            bucket["responses_with_invalid_citations"] += int(
                bool(invalid_document_ids)
            )
            bucket["cited_documents"] += len(cited_document_ids)
            bucket["invalid_citations"] += len(invalid_document_ids)
            if metrics.get("response_word_count") is not None:
                bucket["word_counts"].append(
                    float(metrics["response_word_count"])
                )
            if metrics.get("word_count_within_range") is not None:
                bucket["word_count_applicable"] += 1
                bucket["word_count_compliant"] += int(
                    bool(metrics["word_count_within_range"])
                )

        if name == "chain_of_verification" and predicted and truth:
            initial = _initial_label(row)
            if initial and initial != predicted:
                if initial != truth and predicted == truth:
                    bucket["cov_changes"]["beneficial"] += 1
                elif initial == truth and predicted != truth:
                    bucket["cov_changes"]["harmful"] += 1
                else:
                    bucket["cov_changes"]["changed_other"] += 1
            elif initial == predicted:
                bucket["cov_changes"]["unchanged"] += 1

    conditions: Dict[str, Any] = {}
    for condition, bucket in sorted(buckets.items()):
        completed = bucket["statuses"].get("completed", 0)
        parsed = sum(
            count
            for status, count in bucket["parse_statuses"].items()
            if status in {"parsed_strict", "parsed_fallback"}
        )
        conditions[condition] = {
            "provider": bucket["provider"],
            "model": bucket["model"],
            "strategy": bucket["name"],
            "version": bucket["version"],
            "runs": bucket["runs"],
            "statuses": dict(bucket["statuses"]),
            "task_types": dict(bucket["task_types"]),
            "parse_statuses": dict(bucket["parse_statuses"]),
            "parse_rate": _rate(parsed, completed),
            "label_coverage": _rate(bucket["labelled_predictions"], completed),
            "accuracy": _rate(bucket["correct"], bucket["scored"]),
            "correct": bucket["correct"],
            "scored": bucket["scored"],
            "abstention_rate": _rate(
                bucket["abstentions"], bucket["labelled_predictions"]
            ),
            "false_no_evidence_rate_on_decisive_tasks": _rate(
                bucket["false_no_evidence_predictions"],
                bucket["decisive_truth_tasks"],
            ),
            "no_evidence_recall": _rate(
                bucket["correct_no_evidence_predictions"],
                bucket["no_evidence_truth_tasks"],
            ),
            "decisive_truth_tasks": bucket["decisive_truth_tasks"],
            "no_evidence_truth_tasks": bucket["no_evidence_truth_tasks"],
            "predicted_labels": dict(bucket["predicted"]),
            "ground_truth_labels": dict(bucket["truth"]),
            "confusion_matrix": {
                f"{truth}->{prediction}": count
                for (truth, prediction), count in sorted(bucket["confusion"].items())
            },
            "api_calls": bucket["calls"],
            "tokens": {
                "input": bucket["input_tokens"],
                "output": bucket["output_tokens"],
                "reasoning": bucket["reasoning_tokens"],
                "total": bucket["input_tokens"] + bucket["output_tokens"],
                "mean_total_per_run": _rate(
                    bucket["input_tokens"] + bucket["output_tokens"],
                    bucket["runs"],
                ),
            },
            "latency_seconds": {
                "mean": _mean(bucket["latencies"]),
                "median": _median(bucket["latencies"]),
            },
            "verification_label_changes": dict(bucket["cov_changes"]),
            "citation_metrics": {
                "applicable_responses": bucket["citation_applicable"],
                "citation_parse_statuses": dict(
                    bucket["citation_parse_statuses"]
                ),
                "responses_with_citations": bucket["responses_with_citations"],
                "citation_response_rate": _rate(
                    bucket["responses_with_citations"],
                    bucket["citation_applicable"],
                ),
                "cited_documents": bucket["cited_documents"],
                "invalid_citations": bucket["invalid_citations"],
                "invalid_citation_rate": _rate(
                    bucket["invalid_citations"], bucket["cited_documents"]
                ),
                "responses_with_invalid_citations": bucket[
                    "responses_with_invalid_citations"
                ],
                "invalid_citation_response_rate": _rate(
                    bucket["responses_with_invalid_citations"],
                    bucket["citation_applicable"],
                ),
                "mean_response_word_count": _mean(bucket["word_counts"]),
                "word_count_compliance_rate": _rate(
                    bucket["word_count_compliant"],
                    bucket["word_count_applicable"],
                ),
            },
        }

    return {
        "evaluation_schema_version": "1.3.0",
        "result_rows": len(materialized),
        "conditions": conditions,
        "interpretation_note": (
            "Accuracy and parsing are objective harness metrics. Explanation "
            "faithfulness requires completed reviewer annotations and is not inferred here."
        ),
    }


def manual_review_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    materialized = list(rows)
    include_model = len({_model_identity(row) for row in materialized}) > 1
    review_rows: List[Dict[str, Any]] = []
    for row in materialized:
        name, version, condition = _condition_identity(
            row, include_model=include_model
        )
        response = row.get("response") or {}
        task = row.get("task") or {}
        task_type = str((task.get("metadata") or {}).get("task_type") or "")
        dataset = row.get("dataset") or {}
        model = row.get("model") or {}
        metrics = row.get("metrics") or {}
        review_rows.append(
            {
                "run_id": row.get("run_id", ""),
                "experiment_id": row.get("experiment_id", ""),
                "dataset": dataset.get("name", ""),
                "task_id": dataset.get("task_id", ""),
                "provider": model.get("provider", ""),
                "model": model.get("name", ""),
                "strategy": name,
                "strategy_version": version,
                "condition": condition,
                "task_type": task_type,
                "ground_truth_label": (row.get("ground_truth") or {}).get("label", ""),
                "predicted_label": response.get("parsed_label", ""),
                "classification_correct": metrics.get("classification_correct", ""),
                "task_prompt": task.get("prompt", ""),
                "source_context": task.get("source_context", ""),
                "explanation": (
                    response.get("raw", "")
                    if task_type == "academic_evidence_synthesis"
                    else response.get("explanation", "")
                ),
                **{field: "" for field in REVIEW_FIELDS},
            }
        )
    return review_rows


def blinded_review_package(
    rows: Iterable[Dict[str, Any]], seed: int = 0
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    full_rows = manual_review_rows(rows)
    random.Random(seed).shuffle(full_rows)

    blinded_rows: List[Dict[str, Any]] = []
    mapping_entries: List[Dict[str, Any]] = []
    seen_run_ids: set[str] = set()
    for index, row in enumerate(full_rows, start=1):
        run_id = str(row.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("Every result row must have a run_id for blinded review")
        if run_id in seen_run_ids:
            raise ValueError(f"Duplicate run_id in blinded review input: {run_id}")
        seen_run_ids.add(run_id)

        review_id = f"review_{index:06d}"
        blinded_rows.append(
            {
                "review_id": review_id,
                "task_prompt": row["task_prompt"],
                "source_context": row["source_context"],
                "explanation": row["explanation"],
                **{field: "" for field in REVIEW_FIELDS},
            }
        )
        mapping_entries.append(
            {
                "review_id": review_id,
                "run_id": run_id,
                "experiment_id": row["experiment_id"],
                "dataset": row["dataset"],
                "task_id": row["task_id"],
                "provider": row["provider"],
                "model": row["model"],
                "strategy": row["strategy"],
                "strategy_version": row["strategy_version"],
                "condition": row["condition"],
                "task_type": row["task_type"],
                "ground_truth_label": row["ground_truth_label"],
                "predicted_label": row["predicted_label"],
                "classification_correct": row["classification_correct"],
            }
        )

    mapping = {
        "review_mapping_schema_version": REVIEW_MAPPING_SCHEMA_VERSION,
        "seed": seed,
        "review_rows": len(blinded_rows),
        "entries": mapping_entries,
    }
    return blinded_rows, mapping


def review_condition_lookup(mapping: Mapping[str, Any]) -> Dict[str, str]:
    schema_version = mapping.get("review_mapping_schema_version")
    if schema_version != REVIEW_MAPPING_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported review mapping schema version: "
            f"{schema_version!r}"
        )

    entries = mapping.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Review mapping contains no entries")

    lookup: Dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Every review mapping entry must be an object")
        review_id = str(entry.get("review_id") or "").strip()
        condition = str(entry.get("condition") or "").strip()
        if not review_id or not condition:
            raise ValueError("Every review mapping entry needs review_id and condition")
        if review_id in lookup:
            raise ValueError(f"Duplicate review_id in review mapping: {review_id}")
        lookup[review_id] = condition

    declared_rows = mapping.get("review_rows")
    if declared_rows != len(lookup):
        raise ValueError(
            "Review mapping row count does not match its entries: "
            f"declared {declared_rows!r}, found {len(lookup)}"
        )
    return lookup


def read_review_condition_lookup(path: str | Path) -> Dict[str, str]:
    with Path(path).open("r", encoding="utf-8") as handle:
        try:
            mapping = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid review mapping JSON: {exc}") from exc
    if not isinstance(mapping, dict):
        raise ValueError("Review mapping must be a JSON object")
    return review_condition_lookup(mapping)


def write_review_csv(path: str | Path, rows: Iterable[Dict[str, Any]]) -> int:
    materialized = list(rows)
    if not materialized:
        raise ValueError("No result rows were available for manual review")
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(materialized[0].keys())
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(materialized)
    return len(materialized)


def summarize_annotations(
    path: str | Path,
    condition_lookup: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    buckets: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"rows": 0, "scores": [], **{field: 0 for field in YES_NO_FIELDS}}
    )
    annotated = 0
    seen_review_ids: set[str] = set()
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        required_fields = set(REVIEW_FIELDS[:-1])
        required_fields.add("review_id" if condition_lookup is not None else "condition")
        missing_fields = sorted(required_fields - fieldnames)
        if missing_fields:
            raise ValueError(
                "Annotation file is missing required columns: "
                + ", ".join(missing_fields)
            )

        for line_number, row in enumerate(reader, start=2):
            review_id = ""
            if condition_lookup is not None:
                review_id = str(row.get("review_id") or "").strip()
                if not review_id:
                    raise ValueError(f"Line {line_number}: review_id is required")
                if review_id in seen_review_ids:
                    raise ValueError(
                        f"Line {line_number}: duplicate review_id {review_id}"
                    )
                seen_review_ids.add(review_id)
                if review_id not in condition_lookup:
                    raise ValueError(
                        f"Line {line_number}: review_id {review_id} is not in the review mapping"
                    )

            score_raw = str(row.get("faithfulness_score", "")).strip()
            values = {field: str(row.get(field, "")).strip().lower() for field in YES_NO_FIELDS}
            if not score_raw and not any(values.values()):
                continue
            if score_raw not in {"0", "1", "2"}:
                raise ValueError(
                    f"Line {line_number}: faithfulness_score must be 0, 1, or 2"
                )
            for field, value in values.items():
                if value not in {"yes", "no"}:
                    raise ValueError(
                        f"Line {line_number}: {field} must be yes or no"
                    )
            condition = (
                str(condition_lookup[review_id])
                if condition_lookup is not None
                else str(row.get("condition") or "").strip()
            )
            if not condition:
                raise ValueError(f"Line {line_number}: condition is required")
            bucket = buckets[condition]
            bucket["rows"] += 1
            bucket["scores"].append(int(score_raw))
            for field, value in values.items():
                bucket[field] += int(value == "yes")
            annotated += 1

    if annotated == 0:
        raise ValueError(
            "Annotation file contains zero completed rows. Enter a faithfulness_score "
            "and yes/no values for each reviewed row before using --annotations."
        )

    return {
        "annotation_schema_version": "1.0.0",
        "annotated_rows": annotated,
        "conditions": {
            condition: {
                "annotated_rows": bucket["rows"],
                "mean_faithfulness_score_0_to_2": _mean(bucket["scores"]),
                **{
                    f"{field}_rate": _rate(bucket[field], bucket["rows"])
                    for field in YES_NO_FIELDS
                },
            }
            for condition, bucket in sorted(buckets.items())
        },
    }


def render_report(summary: Dict[str, Any], annotations: Optional[Dict[str, Any]] = None) -> str:
    lines = [
        "# Experiment evaluation",
        "",
        "## Objective metrics",
        "",
        "| Condition | Runs | Accuracy | Label coverage | Parse rate | NO_EVIDENCE prediction | False NO_EVIDENCE on decisive tasks | NO_EVIDENCE recall | API calls | Tokens | Mean latency (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for condition, values in summary["conditions"].items():
        percent = lambda value: "—" if value is None else f"{100 * value:.1f}%"
        lines.append(
            f"| {condition} | {values['runs']} | {percent(values['accuracy'])} | "
            f"{percent(values['label_coverage'])} | {percent(values['parse_rate'])} | "
            f"{percent(values['abstention_rate'])} | "
            f"{percent(values['false_no_evidence_rate_on_decisive_tasks'])} | "
            f"{percent(values['no_evidence_recall'])} | "
            f"{values['api_calls']} | {values['tokens']['total']} | "
            f"{values['latency_seconds']['mean'] if values['latency_seconds']['mean'] is not None else '—'} |"
        )

    citation_conditions = {
        condition: values
        for condition, values in summary["conditions"].items()
        if values["citation_metrics"]["applicable_responses"]
    }
    if citation_conditions:
        lines.extend(
            [
                "",
                "## Automated citation checks",
                "",
                "| Condition | Applicable | Responses citing sources | Cited documents | Invalid identifiers | Responses with invalid identifiers | Word-count compliance |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for condition, values in citation_conditions.items():
            citation = values["citation_metrics"]
            percent = lambda value: "—" if value is None else f"{100 * value:.1f}%"
            lines.append(
                f"| {condition} | {citation['applicable_responses']} | "
                f"{percent(citation['citation_response_rate'])} | "
                f"{citation['cited_documents']} | {citation['invalid_citations']} | "
                f"{percent(citation['invalid_citation_response_rate'])} | "
                f"{percent(citation['word_count_compliance_rate'])} |"
            )
        lines.extend(
            [
                "",
                "An invalid identifier is a cited document ID that was not supplied to the model. "
                "This automated check does not determine whether a valid supplied document "
                "actually supports the attached claim.",
            ]
        )

    lines.extend([
        "",
        "Accuracy is calculated only for responses with a parsed label. Label coverage "
        "shows the share of completed responses included in that calculation. Accuracy "
        "measures label agreement, not explanation faithfulness.",
        "",
        "## Reviewer faithfulness review",
        "",
    ])
    if not annotations or annotations.get("annotated_rows", 0) == 0:
        lines.append(
            "No completed annotations were supplied. Fill in the generated manual-review CSV, "
            "then rerun this command with `--annotations`."
        )
    else:
        lines.extend([
            "| Condition | Reviewed | Mean faithfulness (0–2) | Unsupported claim | Source misrepresentation | Fabricated citation | Excessive abstention |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ])
        for condition, values in annotations["conditions"].items():
            percent = lambda value: "—" if value is None else f"{100 * value:.1f}%"
            lines.append(
                f"| {condition} | {values['annotated_rows']} | "
                f"{values['mean_faithfulness_score_0_to_2']} | "
                f"{percent(values['unsupported_claim_rate'])} | "
                f"{percent(values['source_misrepresentation_rate'])} | "
                f"{percent(values['fabricated_citation_rate'])} | "
                f"{percent(values['excessive_abstention_rate'])} |"
            )
    lines.extend([
        "",
        "## Interpretation limits",
        "",
        "The subjective fields require a documented annotation protocol and calibrated reviewer judgment. "
        "Automated citation checks detect identifiers outside the supplied source set; reviewers must "
        "still judge whether the cited source supports the associated statement.",
        "",
    ])
    return "\n".join(lines)
