from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.data import load_jsonl_tasks
from src.parsing import CANONICAL_LABELS, normalize_label


AUDIT_REVIEW_FIELDS = (
    "claim_clear",
    "evidence_addresses_claim",
    "gold_label_supported",
    "include",
    "exclusion_reason",
    "reviewer_notes",
)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_audit_rows(data_path: str | Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for task in load_jsonl_tasks(str(data_path)):
        evidence_ids = task.metadata.get("evidence_sentence_ids", {})
        label = normalize_label(task.reference_answer)
        rows.append(
            {
                "task_id": task.task_id,
                "dataset": task.dataset,
                "task_prompt": task.prompt,
                "reference_label": task.reference_answer or "",
                "source_context": task.source_context or "",
                "difficulty_category": task.metadata.get("difficulty_category", ""),
                "document_mode": task.metadata.get("document_mode", ""),
                "base_task_id": task.metadata.get("base_task_id", ""),
                "evidence_sentence_ids": json.dumps(evidence_ids, ensure_ascii=False, sort_keys=True),
                "automatic_evidence_present": "yes" if task.source_context else "no",
                "automatic_reference_label_valid": "yes" if label in CANONICAL_LABELS else "no",
                **{field: "" for field in AUDIT_REVIEW_FIELDS},
            }
        )
    return rows


def write_audit_csv(path: str | Path, rows: Iterable[Dict[str, Any]], *, overwrite: bool) -> int:
    materialized = list(rows)
    if not materialized:
        raise ValueError("Dataset contains no tasks")
    output = Path(path)
    if output.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite {output}; pass --overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(materialized[0].keys()))
        writer.writeheader()
        writer.writerows(materialized)
    return len(materialized)


def _read_audit(path: str | Path) -> Dict[str, Dict[str, str]]:
    rows: Dict[str, Dict[str, str]] = {}
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        for line_number, row in enumerate(csv.DictReader(handle), start=2):
            task_id = str(row.get("task_id", "")).strip()
            if not task_id:
                raise ValueError(f"Line {line_number}: task_id is required")
            if task_id in rows:
                raise ValueError(f"Line {line_number}: duplicate task_id {task_id}")
            for field in AUDIT_REVIEW_FIELDS[:4]:
                value = str(row.get(field, "")).strip().lower()
                if value not in {"yes", "no"}:
                    raise ValueError(f"Line {line_number}: {field} must be yes or no")
                row[field] = value
            expected_include = "yes" if all(
                row[field] == "yes" for field in AUDIT_REVIEW_FIELDS[:3]
            ) else "no"
            if row["include"] != expected_include:
                raise ValueError(
                    f"Line {line_number}: include must be {expected_include} under the "
                    "predefined rule (all three quality checks must be yes)"
                )
            if row["include"] == "no" and not str(row.get("exclusion_reason", "")).strip():
                raise ValueError(
                    f"Line {line_number}: exclusion_reason is required when include=no"
                )
            rows[task_id] = row
    return rows


def apply_audit(
    data_path: str | Path,
    audit_path: str | Path,
    output_path: str | Path,
    *,
    overwrite: bool,
) -> Dict[str, Any]:
    input_path = Path(data_path)
    output = Path(output_path)
    manifest_path = output.with_name(f"{output.stem}.audit_manifest.json")
    for path in (output, manifest_path):
        if path.exists() and not overwrite:
            raise FileExistsError(f"Refusing to overwrite {path}; pass --overwrite")

    audit = _read_audit(audit_path)
    source_rows: List[Dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if "task_id" not in row:
                raise ValueError(f"Source line {line_number}: task_id is required")
            source_rows.append(row)

    source_ids = [str(row["task_id"]) for row in source_rows]
    missing = sorted(set(source_ids) - set(audit))
    extra = sorted(set(audit) - set(source_ids))
    if missing or extra:
        raise ValueError(
            "Audit/task mismatch. "
            f"Missing audit rows: {missing or 'none'}; extra audit rows: {extra or 'none'}"
        )

    included = [row for row in source_rows if audit[str(row["task_id"])]["include"] == "yes"]
    excluded_reasons = Counter(
        str(audit[task_id].get("exclusion_reason", "")).strip()
        for task_id in source_ids
        if audit[task_id]["include"] == "no"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in included),
        encoding="utf-8",
    )
    manifest = {
        "audit_schema_version": "1.0.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_data": str(input_path),
        "source_data_sha256": sha256_file(input_path),
        "audit_csv": str(Path(audit_path)),
        "audit_csv_sha256": sha256_file(audit_path),
        "output_data": str(output),
        "output_data_sha256": sha256_file(output),
        "total_tasks": len(source_rows),
        "included_tasks": len(included),
        "excluded_tasks": len(source_rows) - len(included),
        "exclusion_reasons": dict(excluded_reasons),
        "selection_note": (
            "Tasks were selected from pre-run benchmark audit decisions only. "
            "No model responses are present in the audit template."
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
