from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config_scifact_difficulty_pilot.json"
DATA = ROOT / "data/approved/scifact_difficulty_pilot_12.jsonl"
OUTPUT_DIR = ROOT / "outputs/scifact_difficulty_pilot_v3_2"
RESULTS = OUTPUT_DIR / "results.jsonl"
PREVIEW_RESULTS = ROOT / "outputs/scifact_difficulty_pilot_v3_2_preview/results.jsonl"
SMOKE_DIR = ROOT / "outputs/scifact_difficulty_pilot_v3_2_smoke"
SMOKE_DATA = SMOKE_DIR / "smoke_input.jsonl"
SMOKE_RESULTS = SMOKE_DIR / "results.jsonl"
OBJECTIVE_DIR = OUTPUT_DIR / "objective_evaluation"
ATOMIC_DIR = OUTPUT_DIR / "atomic_consensus_v3_8"
REPAIRED_ATOMIC_DIR = OUTPUT_DIR / "atomic_consensus_v3_8_repaired"
PRIMARY_JUDGE_MODEL = "gpt-5.5-2026-04-23"
SECONDARY_JUDGE_MODEL = "gpt-5.4-mini-2026-03-17"


def _run(*args: str) -> None:
    command = [sys.executable, *args]
    print("\n$ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


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
    with DATA.open(encoding="utf-8") as handle:
        first_task = next((line for line in handle if line.strip()), None)
    if first_task is None:
        raise ValueError(f"Approved dataset contains no tasks: {DATA}")
    SMOKE_DATA.parent.mkdir(parents=True, exist_ok=True)
    rendered = first_task.rstrip("\n") + "\n"
    if SMOKE_DATA.exists():
        if SMOKE_DATA.read_text(encoding="utf-8") != rendered:
            raise RuntimeError(
                f"Existing smoke input does not match the approved dataset: {SMOKE_DATA}"
            )
        return
    SMOKE_DATA.write_text(rendered, encoding="utf-8")


def _experiment_args(*, preview: bool, overwrite: bool) -> list[str]:
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
    return args


def _smoke_args(*, overwrite: bool) -> list[str]:
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


def _atomic_args(*, overwrite: bool) -> list[str]:
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


def _require_complete_results() -> None:
    completed, errors = _result_counts(RESULTS)
    if completed != 96 or errors:
        raise RuntimeError(
            "Expected 96 completed result rows and no errors before evaluation; "
            f"found {completed} completed and {errors} errors."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview, run, and evaluate the fixed SciFact difficulty pilot"
    )
    parser.add_argument(
        "action",
        choices=("preview", "smoke", "run", "judge", "repair", "all"),
        help=(
            "preview costs nothing; smoke tests one task in 12 requests; run creates "
            "96 responses and objective metrics; judge evaluates saved responses "
            "with two automated atomic judges (192 requests); repair retries only "
            "failed secondary judgments and adds difficulty tables; all performs "
            "run and judge"
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace artifacts for the selected action",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.action == "preview":
        _run(*_experiment_args(preview=True, overwrite=args.overwrite))
        return

    if args.action == "smoke":
        _prepare_smoke_input()
        _run(*_smoke_args(overwrite=args.overwrite))
        completed, errors = _result_counts(SMOKE_RESULTS)
        if completed != 8 or errors:
            raise RuntimeError(
                "Expected 8 completed smoke rows and no errors; "
                f"found {completed} completed and {errors} errors."
            )
        print("\nSmoke run passed for both models and all strategies.")
        return

    if args.action in {"run", "all"}:
        _run(*_experiment_args(preview=False, overwrite=args.overwrite))
        _require_complete_results()
        _run(*_objective_args(overwrite=args.overwrite))

    if args.action in {"judge", "all"}:
        _require_complete_results()
        _run(*_atomic_args(overwrite=args.overwrite))

    if args.action == "repair":
        _require_complete_results()
        _run(*_repair_args(overwrite=args.overwrite))

    print("\nDifficulty pilot workflow completed successfully.")


if __name__ == "__main__":
    main()
