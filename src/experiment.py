from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.prompting import build_prompt_plan, registry_manifest, resolve_strategy
from src.runner import RESULT_SCHEMA_VERSION, utc_now_iso
from src.schemas import Task


DEPENDENCIES = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google-genai": "google-genai",
    "mistralai": "mistralai",
    "python-dotenv": "python-dotenv",
}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_paths(
    output_path: str | Path,
    *,
    prompt_log_path: Optional[str] = None,
    preview_path: Optional[str] = None,
    manifest_path: Optional[str] = None,
) -> Dict[str, Path]:
    results = Path(output_path)
    stem = results.stem
    return {
        "results": results,
        "prompts": Path(prompt_log_path)
        if prompt_log_path
        else results.with_name(f"{stem}.prompts.jsonl"),
        "preview": Path(preview_path)
        if preview_path
        else results.with_name(f"{stem}.prompt_preview.md"),
        "manifest": Path(manifest_path)
        if manifest_path
        else results.with_name(f"{stem}.manifest.json"),
    }


def validate_config(config: Dict[str, Any]) -> None:
    required = {
        "experiment_name",
        "repetitions",
        "max_output_tokens",
        "models",
        "strategies",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"Config missing required fields: {', '.join(missing)}")
    if int(config["repetitions"]) < 1:
        raise ValueError("repetitions must be at least 1")
    if int(config["max_output_tokens"]) < 1:
        raise ValueError("max_output_tokens must be at least 1")
    if not config["models"]:
        raise ValueError("models must contain at least one model")
    if not config["strategies"]:
        raise ValueError("strategies must contain at least one strategy")

    for index, strategy in enumerate(config["strategies"]):
        try:
            resolve_strategy(strategy)
        except ValueError as exc:
            raise ValueError(f"strategies[{index}]: {exc}") from exc
    for index, model in enumerate(config["models"]):
        if "provider" not in model or "model" not in model:
            raise ValueError(
                f"models[{index}] must include both provider and model"
            )


def _dependency_versions() -> Dict[str, Optional[str]]:
    versions: Dict[str, Optional[str]] = {}
    for label, distribution in DEPENDENCIES.items():
        try:
            versions[label] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[label] = None
    return versions


def build_manifest(
    *,
    experiment_id: str,
    config: Dict[str, Any],
    tasks: List[Task],
    config_path: str,
    data_path: str,
    paths: Dict[str, Path],
    mode: str,
) -> Dict[str, Any]:
    dataset_counts: Dict[str, int] = {}
    for task in tasks:
        dataset_counts[task.dataset] = dataset_counts.get(task.dataset, 0) + 1

    requests_per_task = 0
    skipped_conditions_per_task = 0
    for task in tasks:
        for strategy in config["strategies"]:
            try:
                requests_per_task += build_prompt_plan(
                    strategy, task
                ).definition.request_count
            except ValueError:
                skipped_conditions_per_task += 1

    model_repetition_multiplier = len(config["models"]) * int(config["repetitions"])

    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "experiment_name": config["experiment_name"],
        "mode": mode,
        "status": "prepared",
        "created_at_utc": utc_now_iso(),
        "completed_at_utc": None,
        "config": config,
        "inputs": {
            "config_path": str(Path(config_path)),
            "config_sha256": sha256_file(config_path),
            "data_path": str(Path(data_path)),
            "data_sha256": sha256_file(data_path),
            "task_count": len(tasks),
            "dataset_counts": dataset_counts,
        },
        "planned_runs": (
            len(tasks)
            * len(config["models"])
            * len(config["strategies"])
            * int(config["repetitions"])
        ),
        "planned_api_requests": requests_per_task * model_repetition_multiplier,
        "planned_skipped_runs": (
            skipped_conditions_per_task * model_repetition_multiplier
        ),
        "prompt_registry": registry_manifest(),
        "runtime": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "dependency_versions": _dependency_versions(),
        },
        "artifacts": {name: str(path) for name, path in paths.items()},
        "summary": None,
    }


def new_experiment_id(experiment_name: str) -> str:
    safe_name = "".join(
        char if char.isalnum() or char in {"-", "_"} else "-"
        for char in experiment_name.strip()
    )
    return f"{safe_name}-{uuid.uuid4().hex[:12]}"


def write_json(path: str | Path, value: Dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
