from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config_halueval_synthesis.json"
DATA = ROOT / "data/approved/halueval_synthesis_pilot_14.jsonl"
OUTPUT_DIR = ROOT / "outputs/halueval_synthesis_v3_1_pilot"
RESULTS = OUTPUT_DIR / "results.jsonl"
PREVIEW_RESULTS = ROOT / "outputs/halueval_synthesis_v3_1_preview/results.jsonl"
SMOKE_DIR = ROOT / "outputs/halueval_synthesis_v3_1_smoke"
SMOKE_DATA = SMOKE_DIR / "smoke_input.jsonl"
SMOKE_RESULTS = SMOKE_DIR / "results.jsonl"
OBJECTIVE_DIR = OUTPUT_DIR / "evaluation_blinded"
ATOMIC_DIR = OUTPUT_DIR / "atomic_consensus_v3_8"
PRIMARY_JUDGE_MODEL = "gpt-5.5-2026-04-23"
SECONDARY_JUDGE_MODEL = "gpt-5.4-mini-2026-03-17"
EXPECTED_TASKS = 14
EXPECTED_RESULTS = 56


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
    output = PREVIEW_RESULTS if preview else RESULTS
    args = [
        "run_experiment.py",
        "--config",
        str(CONFIG.relative_to(ROOT)),
        "--data",
        str(DATA.relative_to(ROOT)),
        "--output",
        str(output.relative_to(ROOT)),
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
        "--blind-review",
        "--review-seed",
        "20260922",
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


def _require_complete_results() -> None:
    completed, errors = _result_counts(RESULTS)
    if completed != EXPECTED_RESULTS or errors:
        raise RuntimeError(
            f"Expected {EXPECTED_RESULTS} completed result rows and no errors before "
            f"evaluation; found {completed} completed and {errors} errors."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview, smoke-test, run, and evaluate the fixed HaluEval pilot"
    )
    parser.add_argument(
        "action",
        choices=("preview", "smoke", "run", "judge", "all"),
        help=(
            "preview costs nothing; smoke tests one task in four responses; run "
            "creates 56 responses and blinded objective-review artifacts; judge "
            "evaluates saved responses with two automated atomic judges (112 "
            "requests); all performs run and judge"
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
        if completed != 4 or errors:
            raise RuntimeError(
                "Expected four completed smoke rows and no errors; "
                f"found {completed} completed and {errors} errors."
            )
        print("\nHaluEval smoke run passed for all four strategies.")
        return

    if args.action in {"run", "all"}:
        _run(*_experiment_args(preview=False, overwrite=args.overwrite))
        _require_complete_results()
        _run(*_objective_args(overwrite=args.overwrite))

    if args.action in {"judge", "all"}:
        _require_complete_results()
        _run(*_atomic_args(overwrite=args.overwrite))

    print("\nHaluEval pilot workflow completed successfully.")


if __name__ == "__main__":
    main()
