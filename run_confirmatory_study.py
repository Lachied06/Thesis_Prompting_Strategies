from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config_scifact_confirmatory.json"
DATA = ROOT / "data/approved/scifact_confirmatory_100.jsonl"
OUTPUT_DIR = ROOT / "outputs/scifact_confirmatory_v3_2"
RESULTS = OUTPUT_DIR / "results.jsonl"
PREVIEW_RESULTS = ROOT / "outputs/scifact_confirmatory_v3_2_preview/results.jsonl"
SMOKE_DIR = ROOT / "outputs/scifact_confirmatory_v3_2_smoke"
SMOKE_DATA = SMOKE_DIR / "smoke_input.jsonl"
SMOKE_RESULTS = SMOKE_DIR / "results.jsonl"
OBJECTIVE_DIR = OUTPUT_DIR / "objective_evaluation"
ATOMIC_DIR = OUTPUT_DIR / "atomic_consensus_v3_9"
REPAIRED_ATOMIC_DIR = OUTPUT_DIR / "atomic_consensus_v3_9_repaired"
STUDY_ANALYSIS_DIR = OUTPUT_DIR / "study_analysis"
REPAIRED_STUDY_ANALYSIS_DIR = OUTPUT_DIR / "study_analysis_repaired"
PRIMARY_JUDGE_MODEL = "gpt-5.5-2026-04-23"
SECONDARY_JUDGE_MODEL = "gpt-5.4-mini-2026-03-17"
EXPECTED_TASKS = 100
EXPECTED_CATEGORIES = {
    "direct_control": 25,
    "near_match_distractors": 25,
    "evidence_omission": 25,
    "conflicting_or_partial_evidence": 25,
}


def _run(*args: str) -> None:
    command = [sys.executable, *args]
    print("\n$ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Confirmatory dataset does not exist at {path}. Freeze and approve "
            "the 100-task dataset before running the final study."
        )
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {path}") from exc
    return rows


def _config() -> dict:
    with CONFIG.open(encoding="utf-8") as handle:
        return json.load(handle)


def _expected_results(task_count: int) -> int:
    config = _config()
    return (
        task_count
        * len(config.get("models") or [])
        * len(config.get("strategies") or [])
        * int(config.get("repetitions") or 1)
    )


def _validate_frozen_dataset() -> None:
    rows = _read_jsonl(DATA)
    if len(rows) != EXPECTED_TASKS:
        raise RuntimeError(
            f"Expected {EXPECTED_TASKS} confirmatory tasks; found {len(rows)} in {DATA}."
        )
    category_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    labels_by_category: dict[str, Counter[str]] = defaultdict(Counter)
    source_ids_by_category: dict[str, set[str]] = defaultdict(set)
    task_ids: set[str] = set()
    dataset_names: set[str] = set()
    for row in rows:
        task_id = str(row.get("task_id") or "")
        if not task_id or task_id in task_ids:
            raise RuntimeError(f"Missing or duplicate confirmatory task_id: {task_id!r}")
        task_ids.add(task_id)
        metadata = row.get("metadata") or {}
        category = str(metadata.get("difficulty_category") or "")
        label = str(row.get("reference_answer") or "")
        source_item_id = str(metadata.get("source_item_id") or "")
        category_counts[category] += 1
        label_counts[label] += 1
        labels_by_category[category][label] += 1
        source_ids_by_category[category].add(source_item_id)
        dataset_names.add(str(row.get("dataset") or ""))
        if metadata.get("word_range") != [180, 250]:
            raise RuntimeError(f"Task {task_id} does not use the frozen 180–250 word range.")
        if not metadata.get("allowed_document_ids"):
            raise RuntimeError(f"Task {task_id} has no allowed document identifiers.")
    if dict(category_counts) != EXPECTED_CATEGORIES:
        raise RuntimeError(
            "Confirmatory difficulty counts are not frozen at 25 per category: "
            f"{category_counts}"
        )
    if label_counts != Counter({"SUPPORT": 25, "CONTRADICT": 25, "NO_EVIDENCE": 50}):
        raise RuntimeError(f"Unexpected confirmatory label balance: {dict(label_counts)}")
    if set(labels_by_category["direct_control"]) != {"SUPPORT", "CONTRADICT"}:
        raise RuntimeError("Direct controls must contain SUPPORT and CONTRADICT tasks.")
    if set(labels_by_category["near_match_distractors"]) != {
        "SUPPORT",
        "CONTRADICT",
    }:
        raise RuntimeError(
            "Near-match distractors must contain SUPPORT and CONTRADICT tasks."
        )
    for category in ("evidence_omission", "conflicting_or_partial_evidence"):
        if labels_by_category[category] != Counter({"NO_EVIDENCE": 25}):
            raise RuntimeError(f"{category} must contain 25 NO_EVIDENCE tasks.")
    if source_ids_by_category["direct_control"] != source_ids_by_category[
        "evidence_omission"
    ]:
        raise RuntimeError(
            "Evidence-omission tasks must be paired to the same source items as "
            "the direct controls."
        )
    non_omission_source_ids = set().union(
        source_ids_by_category["direct_control"],
        source_ids_by_category["near_match_distractors"],
        source_ids_by_category["conflicting_or_partial_evidence"],
    )
    if len(non_omission_source_ids) != 75:
        raise RuntimeError(
            "Expected 75 unique source items outside the paired omission transform; "
            f"found {len(non_omission_source_ids)}."
        )
    if dataset_names != {"SciFact_Confirmatory"}:
        raise RuntimeError(f"Unexpected confirmatory dataset names: {dataset_names}")
    config = _config()
    if len(config.get("models") or []) != 2 or len(config.get("strategies") or []) != 4:
        raise RuntimeError("Confirmatory config must contain two models and four strategies.")


def _result_counts(path: Path) -> tuple[int, int]:
    if not path.exists():
        raise FileNotFoundError(
            f"Results do not exist at {path}. Run the corresponding action first."
        )
    completed = errors = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            status = json.loads(line).get("status")
            completed += int(status == "completed")
            errors += int(status == "error")
    return completed, errors


def _prepare_smoke_input() -> None:
    rows = _read_jsonl(DATA)
    rendered = json.dumps(rows[0], ensure_ascii=False) + "\n"
    SMOKE_DATA.parent.mkdir(parents=True, exist_ok=True)
    if SMOKE_DATA.exists():
        if SMOKE_DATA.read_text(encoding="utf-8") != rendered:
            raise RuntimeError(
                f"Existing smoke input does not match the approved dataset: {SMOKE_DATA}"
            )
        return
    SMOKE_DATA.write_text(rendered, encoding="utf-8")


def _experiment_args(*, preview: bool, overwrite: bool, resume: bool = False) -> list[str]:
    selected_output = PREVIEW_RESULTS if preview else RESULTS
    args = [
        "run_experiment.py",
        "--config",
        str(CONFIG.relative_to(ROOT)),
        "--data",
        str(DATA.relative_to(ROOT)),
        "--output",
        str(selected_output.relative_to(ROOT)),
    ]
    if preview:
        args.append("--preview-prompts")
    if overwrite:
        args.append("--overwrite")
    if resume:
        args.append("--resume")
    return args


def _smoke_args(*, overwrite: bool, resume: bool = False) -> list[str]:
    args = [
        "run_experiment.py",
        "--config",
        str(CONFIG.relative_to(ROOT)),
        "--data",
        str(SMOKE_DATA.relative_to(ROOT)),
        "--output",
        str(SMOKE_RESULTS.relative_to(ROOT)),
    ]
    if overwrite:
        args.append("--overwrite")
    if resume:
        args.append("--resume")
    return args


def _objective_args(*, overwrite: bool) -> list[str]:
    args = [
        "evaluate_results.py",
        "--results",
        str(RESULTS.relative_to(ROOT)),
        "--output-dir",
        str(OBJECTIVE_DIR.relative_to(ROOT)),
    ]
    if overwrite:
        args.append("--overwrite")
    return args


def _atomic_args(*, overwrite: bool, resume: bool = False) -> list[str]:
    args = [
        "evaluate_atomic_claims.py",
        "consensus",
        "--results",
        str(RESULTS.relative_to(ROOT)),
        "--output-dir",
        str(ATOMIC_DIR.relative_to(ROOT)),
        "--primary-judge-provider",
        "openai",
        "--primary-judge-model",
        PRIMARY_JUDGE_MODEL,
        "--secondary-judge-provider",
        "openai",
        "--secondary-judge-model",
        SECONDARY_JUDGE_MODEL,
        "--max-attempts",
        "2",
    ]
    if overwrite:
        args.append("--overwrite")
    if resume:
        args.append("--resume")
    return args


def _repair_args(*, overwrite: bool) -> list[str]:
    args = [
        "evaluate_atomic_claims.py",
        "repair-consensus",
        "--consensus-dir",
        str(ATOMIC_DIR.relative_to(ROOT)),
        "--output-dir",
        str(REPAIRED_ATOMIC_DIR.relative_to(ROOT)),
        "--secondary-judge-provider",
        "openai",
        "--secondary-judge-model",
        SECONDARY_JUDGE_MODEL,
        "--max-attempts",
        "3",
    ]
    if overwrite:
        args.append("--overwrite")
    return args


def _study_report_args(
    *,
    consensus_dir: Path,
    output_dir: Path,
    overwrite: bool,
) -> list[str]:
    args = [
        "build_study_report.py",
        "--results",
        str(RESULTS.relative_to(ROOT)),
        "--consensus",
        str((consensus_dir / "atomic_consensus.jsonl").relative_to(ROOT)),
        "--output-dir",
        str(output_dir.relative_to(ROOT)),
    ]
    if overwrite:
        args.append("--overwrite")
    return args


def _require_complete_results() -> None:
    expected = _expected_results(EXPECTED_TASKS)
    completed, errors = _result_counts(RESULTS)
    if completed != expected or errors:
        raise RuntimeError(
            f"Expected {expected} completed result rows and no errors before "
            f"evaluation; found {completed} completed and {errors} errors."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview, run, and evaluate the frozen 100-task SciFact study"
    )
    parser.add_argument(
        "action",
        choices=("validate", "preview", "smoke", "run", "judge", "repair", "all"),
        help=(
            "validate checks the frozen design; preview costs nothing; smoke tests "
            "one task; run creates 800 responses and objective metrics; judge runs "
            "two automated source-only judges; repair retries only failed secondary "
            "judgments; all performs run and judge"
        ),
    )
    write_mode = parser.add_mutually_exclusive_group()
    write_mode.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace artifacts for the selected action",
    )
    write_mode.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Continue interrupted run or judge checkpoints without repeating "
            "completed API calls"
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.resume and args.action in {"validate", "preview", "repair"}:
        raise ValueError(f"--resume is not supported for the {args.action} action")
    _validate_frozen_dataset()

    if args.action == "validate":
        print("Confirmatory dataset and config passed the design-freeze checks.")
        return
    if args.action == "preview":
        _run(*_experiment_args(preview=True, overwrite=args.overwrite))
        return
    if args.action == "smoke":
        _prepare_smoke_input()
        _run(*_smoke_args(overwrite=args.overwrite, resume=args.resume))
        completed, errors = _result_counts(SMOKE_RESULTS)
        expected = _expected_results(1)
        if completed != expected or errors:
            raise RuntimeError(
                f"Expected {expected} completed smoke rows and no errors; "
                f"found {completed} completed and {errors} errors."
            )
        print("\nSmoke run passed for both models and all strategies.")
        return
    if args.action in {"run", "all"}:
        _run(
            *_experiment_args(
                preview=False,
                overwrite=args.overwrite,
                resume=args.resume,
            )
        )
        _require_complete_results()
        _run(*_objective_args(overwrite=args.overwrite or args.resume))
    if args.action in {"judge", "all"}:
        _require_complete_results()
        _run(*_atomic_args(overwrite=args.overwrite, resume=args.resume))
        _run(
            *_study_report_args(
                consensus_dir=ATOMIC_DIR,
                output_dir=STUDY_ANALYSIS_DIR,
                overwrite=args.overwrite or args.resume,
            )
        )
    if args.action == "repair":
        _require_complete_results()
        _run(*_repair_args(overwrite=args.overwrite))
        _run(
            *_study_report_args(
                consensus_dir=REPAIRED_ATOMIC_DIR,
                output_dir=REPAIRED_STUDY_ANALYSIS_DIR,
                overwrite=args.overwrite,
            )
        )

    print("\nConfirmatory SciFact workflow completed successfully.")


if __name__ == "__main__":
    main()
