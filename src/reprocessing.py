from __future__ import annotations

import copy
import re
from dataclasses import asdict
from typing import Any, Dict

from src.parsing import parse_response
from src.schemas import Task


RESPONSE_PARSER_VERSION = "1.3.0"


def _task_from_result(row: Dict[str, Any]) -> Task:
    dataset = row.get("dataset") or {}
    task_data = row.get("task") or {}
    metadata = task_data.get("metadata") or {}
    if not metadata.get("task_type"):
        run_id = row.get("run_id") or "unknown"
        raise ValueError(
            f"Result {run_id} has no task.metadata.task_type and cannot be reparsed"
        )
    return Task(
        task_id=str(dataset.get("task_id") or "unknown"),
        dataset=str(dataset.get("name") or "unknown"),
        prompt=str(task_data.get("prompt") or ""),
        reference_answer=task_data.get("reference_answer"),
        source_context=task_data.get("source_context"),
        metadata=dict(metadata),
    )


def _updated_metrics(
    row: Dict[str, Any], explanation: str | None, parsed_label: str | None,
    cited_document_ids: list[str], invalid_cited_document_ids: list[str], task: Task
) -> Dict[str, Any]:
    metrics = copy.deepcopy(row.get("metrics") or {})
    truth = (row.get("ground_truth") or {}).get("label")
    metrics["classification_correct"] = (
        parsed_label == truth if parsed_label is not None and truth is not None else None
    )
    metrics["cited_document_count"] = len(cited_document_ids)
    metrics["invalid_citation_count"] = len(invalid_cited_document_ids)
    metrics["has_invalid_citation"] = bool(invalid_cited_document_ids)

    word_count = len(re.findall(r"\b[\w’-]+\b", explanation)) if explanation else None
    metrics["response_word_count"] = word_count
    word_range = task.metadata.get("word_range")
    if (
        word_count is not None
        and isinstance(word_range, (list, tuple))
        and len(word_range) == 2
        and all(isinstance(value, int) for value in word_range)
    ):
        metrics["word_count_within_range"] = word_range[0] <= word_count <= word_range[1]
    else:
        metrics["word_count_within_range"] = None
    return metrics


def reparse_result_row(row: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    """Return a copy with response-derived fields rebuilt from the stored raw text."""
    updated = copy.deepcopy(row)
    response = updated.get("response")
    if updated.get("status") != "completed" or not isinstance(response, dict):
        return updated, False
    raw = response.get("raw")
    if not isinstance(raw, str):
        return updated, False

    task = _task_from_result(updated)
    parsed = parse_response(raw, task)
    updated["response"] = asdict(parsed)
    updated["metrics"] = _updated_metrics(
        updated,
        parsed.explanation,
        parsed.parsed_label,
        parsed.cited_document_ids,
        parsed.invalid_cited_document_ids,
        task,
    )
    updated["postprocessing"] = {
        **(updated.get("postprocessing") or {}),
        "response_parser_version": RESPONSE_PARSER_VERSION,
        "response_reparsed_from_stored_raw_text": True,
    }
    return updated, True
