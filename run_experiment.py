from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.data import load_jsonl_tasks
from src.experiment import (
    artifact_paths,
    build_manifest,
    new_experiment_id,
    sha256_file,
    validate_config,
    write_json,
)
from src.runner import run_experiment, utc_now_iso, write_prompt_preview


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Controlled multi-LLM hallucination experiment runner"
    )
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--data", default="data/sample_tasks.jsonl")
    parser.add_argument(
        "--output",
        help=(
            "Results JSONL path. Defaults to "
            "outputs/<experiment_name>/results.jsonl."
        ),
    )
    parser.add_argument("--prompt-log", help="Override the prompt JSONL path")
    parser.add_argument("--preview-output", help="Override prompt preview path")
    parser.add_argument("--manifest-output", help="Override manifest path")
    parser.add_argument(
        "--preview-prompts",
        action="store_true",
        help="Render prompts and exit without API keys or model calls",
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        help="Only include the first N tasks in the Markdown preview",
    )
    write_mode = parser.add_mutually_exclusive_group()
    write_mode.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing experiment artifacts at the selected paths",
    )
    write_mode.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Continue an interrupted live run, retaining completed jobs and "
            "retrying missing or failed jobs"
        ),
    )
    return parser


def _prepare_paths(
    paths: dict[str, Path],
    *,
    preview_only: bool,
    overwrite: bool,
    resume: bool,
):
    if preview_only and resume:
        raise ValueError("--resume cannot be combined with --preview-prompts")
    selected_names = ["preview", "manifest"] if preview_only else list(paths)
    selected = [paths[name] for name in selected_names]
    existing = [path for path in selected if path.exists() and path.stat().st_size > 0]
    if existing and not overwrite and not resume:
        formatted = "\n".join(f"  - {path}" for path in existing)
        raise FileExistsError(
            "Experiment artifacts already exist. Choose a new --output path or "
            f"pass --overwrite:\n{formatted}"
        )
    if overwrite:
        for path in selected:
            if path.exists():
                path.unlink()
    for path in selected:
        path.parent.mkdir(parents=True, exist_ok=True)


def _resume_manifest(
    path: Path,
    *,
    config_path: str,
    data_path: str,
) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Cannot resume without the existing manifest: {path}"
        )
    with path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("mode") != "live_experiment":
        raise RuntimeError(
            "Refusing to resume because the manifest is not from a live experiment"
        )
    inputs = manifest.get("inputs") or {}
    expected = {
        "config_sha256": sha256_file(config_path),
        "data_sha256": sha256_file(data_path),
    }
    mismatches = [
        name for name, value in expected.items() if inputs.get(name) != value
    ]
    if mismatches:
        raise RuntimeError(
            "Refusing to resume because the frozen inputs changed: "
            + ", ".join(mismatches)
        )
    if not manifest.get("experiment_id"):
        raise ValueError(f"Resume manifest has no experiment_id: {path}")
    return manifest


def main() -> None:
    args = build_parser().parse_args()

    with Path(args.config).open("r", encoding="utf-8") as f:
        config = json.load(f)
    validate_config(config)
    tasks = load_jsonl_tasks(args.data)
    if not tasks:
        raise ValueError("The data file contains no tasks")
    if args.preview_limit is not None and args.preview_limit < 1:
        raise ValueError("--preview-limit must be at least 1")

    output = args.output or str(
        Path("outputs") / str(config["experiment_name"]) / "results.jsonl"
    )
    paths = artifact_paths(
        output,
        prompt_log_path=args.prompt_log,
        preview_path=args.preview_output,
        manifest_path=args.manifest_output,
    )
    _prepare_paths(
        paths,
        preview_only=args.preview_prompts,
        overwrite=args.overwrite,
        resume=args.resume,
    )

    if args.resume:
        manifest = _resume_manifest(
            paths["manifest"],
            config_path=args.config,
            data_path=args.data,
        )
        experiment_id = str(manifest["experiment_id"])
        manifest["mode"] = "live_experiment"
        manifest["status"] = "resuming"
        manifest["completed_at_utc"] = None
        manifest["resumed_at_utc"] = utc_now_iso()
    else:
        experiment_id = new_experiment_id(str(config["experiment_name"]))
        mode = "preview_only" if args.preview_prompts else "live_experiment"
        manifest = build_manifest(
            experiment_id=experiment_id,
            config=config,
            tasks=tasks,
            config_path=args.config,
            data_path=args.data,
            paths=paths,
            mode=mode,
        )

    preview_summary = write_prompt_preview(
        config,
        tasks,
        paths["preview"],
        task_limit=args.preview_limit,
    )

    print(f"Loaded {len(tasks)} tasks.")
    print(f"Planned runs: {manifest['planned_runs']}")
    print(f"Prompt preview written to {paths['preview']}")

    if args.preview_prompts:
        manifest["status"] = "preview_completed"
        manifest["completed_at_utc"] = utc_now_iso()
        manifest["summary"] = {"preview": preview_summary}
        write_json(paths["manifest"], manifest)
        print("Preview complete. No model APIs were called.")
        return

    # Persist the prepared state before live calls so interrupted experiments
    # still retain their frozen configuration and input hashes.
    write_json(paths["manifest"], manifest)

    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError(
            "python-dotenv is required for live runs; install requirements.txt"
        ) from exc
    load_dotenv()

    summary = run_experiment(
        config,
        tasks,
        str(paths["results"]),
        prompt_log_path=str(paths["prompts"]),
        experiment_id=experiment_id,
        resume=args.resume,
    )
    manifest["status"] = "completed" if summary["errors"] == 0 else "completed_with_errors"
    manifest["completed_at_utc"] = utc_now_iso()
    manifest["summary"] = {
        "preview": preview_summary,
        "runs": summary,
    }
    write_json(paths["manifest"], manifest)

    print(f"Finished. Results written to {paths['results']}")
    print(f"Exact prompts written to {paths['prompts']}")
    print(f"Manifest written to {paths['manifest']}")
    print(
        "Run summary: "
        f"{summary['completed']} completed, "
        f"{summary['skipped']} skipped, {summary['errors']} errors, "
        f"{summary['resumed_existing']} retained from checkpoint"
    )


if __name__ == "__main__":
    main()
