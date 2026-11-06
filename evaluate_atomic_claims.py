from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.atomic_evaluation import (
    blinded_atomic_review_package,
    build_atomic_consensus,
    compare_atomic_annotations,
    judge_existing_claims,
    judge_results,
    read_jsonl,
    render_atomic_consensus_report,
    render_atomic_report,
    summarize_atomic_consensus,
    summarize_atomic_judgments,
    retry_failed_secondary_claims,
    write_atomic_disagreements_csv,
    write_atomic_review_csv,
    write_jsonl,
)


DEFAULT_JUDGE_MODEL = "gpt-5.5-2026-04-23"
DEFAULT_SECONDARY_JUDGE_MODEL = "gpt-5.4-mini-2026-03-17"


def _write(path: Path, content: str, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite {path}; pass --overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _subject_run_id(record: dict) -> str:
    return str((record.get("subject") or {}).get("run_id") or "")


def _result_run_id(record: dict) -> str:
    return str(record.get("run_id") or "")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Source-only atomic-claim evaluation for synthesis results"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    judge = subparsers.add_parser(
        "judge",
        help="Judge every completed response and create a blinded validation sample",
    )
    judge.add_argument("--results", required=True)
    judge.add_argument("--output-dir")
    judge.add_argument("--judge-provider", default="openai")
    judge.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    judge.add_argument("--reasoning-effort", default="none")
    judge.add_argument("--max-output-tokens", type=int, default=2400)
    judge.add_argument(
        "--max-attempts",
        type=int,
        default=2,
        help="Maximum judge attempts per response after API or parse failures",
    )
    judge.add_argument(
        "--retry-delay-seconds",
        type=float,
        default=1.0,
        help="Delay between judge attempts (default: 1.0)",
    )
    judge.add_argument("--review-seed", type=int, default=20260922)
    judge.add_argument("--overwrite", action="store_true")

    consensus = subparsers.add_parser(
        "consensus",
        help=(
            "Run two automated judges over a shared claim inventory and preserve "
            "disagreements as uncertain"
        ),
    )
    consensus.add_argument("--results", required=True)
    consensus.add_argument("--output-dir")
    consensus.add_argument("--primary-judge-provider", default="openai")
    consensus.add_argument("--primary-judge-model", default=DEFAULT_JUDGE_MODEL)
    consensus.add_argument("--secondary-judge-provider", default="openai")
    consensus.add_argument(
        "--secondary-judge-model", default=DEFAULT_SECONDARY_JUDGE_MODEL
    )
    consensus.add_argument("--primary-reasoning-effort", default="none")
    consensus.add_argument("--secondary-reasoning-effort", default="none")
    consensus.add_argument("--max-output-tokens", type=int, default=2400)
    consensus.add_argument("--max-attempts", type=int, default=2)
    consensus.add_argument("--retry-delay-seconds", type=float, default=1.0)
    consensus_write_mode = consensus.add_mutually_exclusive_group()
    consensus_write_mode.add_argument("--overwrite", action="store_true")
    consensus_write_mode.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Continue from parsed primary and secondary judgment checkpoints; "
            "failed or missing judgments are retried"
        ),
    )

    repair = subparsers.add_parser(
        "repair-consensus",
        help=(
            "Retry only failed or missing secondary judgments, preserve successful "
            "work, and rebuild consensus reports"
        ),
    )
    repair.add_argument("--consensus-dir", required=True)
    repair.add_argument("--output-dir")
    repair.add_argument("--secondary-judge-provider", default="openai")
    repair.add_argument(
        "--secondary-judge-model", default=DEFAULT_SECONDARY_JUDGE_MODEL
    )
    repair.add_argument("--secondary-reasoning-effort", default="none")
    repair.add_argument("--max-output-tokens", type=int, default=2400)
    repair.add_argument("--max-attempts", type=int, default=3)
    repair.add_argument("--retry-delay-seconds", type=float, default=1.0)
    repair.add_argument("--overwrite", action="store_true")

    summarize = subparsers.add_parser(
        "summarize",
        help="Rebuild reports from saved judgments without model API calls",
    )
    summarize.add_argument("--judgments", required=True)
    summarize.add_argument("--annotations")
    summarize.add_argument("--review-map")
    summarize.add_argument("--output-dir")
    summarize.add_argument("--overwrite", action="store_true")
    return parser


def _write_summary(
    judgments,
    output_dir: Path,
    *,
    annotations=None,
    overwrite: bool,
) -> None:
    summary = summarize_atomic_judgments(judgments)
    combined = {
        "automatic_atomic_judgments": summary,
        "review_validation": annotations,
    }
    _write(
        output_dir / "atomic_evaluation_summary.json",
        json.dumps(combined, ensure_ascii=False, indent=2) + "\n",
        overwrite,
    )
    report = render_atomic_report(summary)
    if annotations:
        fmt = lambda value: "n/a" if value is None else f"{100 * value:.1f}%"
        report += (
            "\n## Blinded review validation\n\n"
            f"- Completed claims: {annotations['completed_claims']}\n"
            f"- Exact support-label agreement: {fmt(annotations['support_label_exact_agreement'])} "
            f"({annotations['support_label_exact_agreement_count']}/{annotations['completed_claims']})\n"
            f"- Binary unsupported-claim agreement: {fmt(annotations['binary_unsupported_agreement'])} "
            f"({annotations['binary_unsupported_agreement_count']}/{annotations['completed_claims']})\n"
            f"- Exact citation-label agreement: {fmt(annotations['citation_label_exact_agreement'])} "
            f"({annotations['citation_label_exact_agreement_count']}/{annotations['completed_claims']})\n"
            f"- Claims with any exact-label disagreement: "
            f"{annotations['claims_with_any_exact_label_disagreement']}\n\n"
            f"{annotations['interpretation_note']}\n"
        )
    _write(output_dir / "atomic_evaluation_report.md", report, overwrite)


def _write_consensus_summary(
    consensus_records,
    primary_records,
    secondary_records,
    output_dir: Path,
    *,
    overwrite: bool,
) -> None:
    summary = summarize_atomic_consensus(
        consensus_records,
        primary_records=primary_records,
        secondary_records=secondary_records,
    )
    _write(
        output_dir / "atomic_consensus_summary.json",
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        overwrite,
    )
    _write(
        output_dir / "atomic_consensus_report.md",
        render_atomic_consensus_report(summary),
        overwrite,
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "repair-consensus":
        if args.max_output_tokens < 1:
            parser.error("--max-output-tokens must be at least 1")
        if args.max_attempts < 1:
            parser.error("--max-attempts must be at least 1")
        if args.retry_delay_seconds < 0:
            parser.error("--retry-delay-seconds cannot be negative")

        source_dir = Path(args.consensus_dir)
        output_dir = (
            Path(args.output_dir)
            if args.output_dir
            else source_dir.with_name(f"{source_dir.name}_repaired")
        )
        names = [
            "atomic_primary_judgments.jsonl",
            "atomic_primary_prompts.jsonl",
            "atomic_secondary_judgments.jsonl",
            "atomic_secondary_prompts.jsonl",
            "atomic_consensus.jsonl",
            "atomic_consensus_summary.json",
            "atomic_consensus_report.md",
        ]
        source_paths = [source_dir / name for name in names]
        required = source_paths[:4]
        missing = [path for path in required if not path.exists()]
        if missing:
            formatted = "\n".join(f"  - {path}" for path in missing)
            raise FileNotFoundError(
                "Cannot repair consensus because required artifacts are missing:\n"
                f"{formatted}"
            )
        output_paths = [output_dir / name for name in names]
        existing = [path for path in output_paths if path.exists()]
        if existing and not args.overwrite:
            formatted = "\n".join(f"  - {path}" for path in existing)
            raise FileExistsError(
                "Repaired consensus artifacts already exist. Pass --overwrite:\n"
                f"{formatted}"
            )

        try:
            from dotenv import load_dotenv
        except ImportError as exc:
            raise RuntimeError(
                "python-dotenv is required for consensus repair; install "
                "requirements.txt"
            ) from exc
        load_dotenv()

        primary_records = read_jsonl(source_paths[0])
        primary_prompts = read_jsonl(source_paths[1])
        secondary_records = read_jsonl(source_paths[2])
        secondary_prompts = read_jsonl(source_paths[3])
        repaired_secondary, repair_prompts, retried_run_ids = (
            retry_failed_secondary_claims(
                primary_records,
                secondary_records,
                judge_provider=args.secondary_judge_provider,
                judge_model=args.secondary_judge_model,
                max_output_tokens=args.max_output_tokens,
                settings={"reasoning_effort": args.secondary_reasoning_effort},
                max_attempts=args.max_attempts,
                retry_delay_seconds=args.retry_delay_seconds,
            )
        )
        consensus_records = build_atomic_consensus(
            primary_records,
            repaired_secondary,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(output_paths[0], primary_records)
        write_jsonl(output_paths[1], primary_prompts)
        write_jsonl(output_paths[2], repaired_secondary)
        write_jsonl(output_paths[3], secondary_prompts + repair_prompts)
        write_jsonl(output_paths[4], consensus_records)
        _write_consensus_summary(
            consensus_records,
            primary_records,
            repaired_secondary,
            output_dir,
            overwrite=True,
        )
        completed = sum(
            record.get("status") == "consensus_computed"
            for record in consensus_records
        )
        print(
            f"Retried {len(retried_run_ids)} failed or missing secondary "
            f"judgment(s): {', '.join(retried_run_ids) or 'none'}."
        )
        print(
            f"Repaired consensus complete: {completed}/{len(consensus_records)} "
            "responses have two parsed judgments."
        )
        print(f"Difficulty-stratified report written to {output_paths[6]}")
        if completed != len(consensus_records):
            raise RuntimeError(
                "Some consensus rows remain incomplete after repair; inspect "
                f"{output_paths[2]} before retrying."
            )
        return

    if args.command == "consensus":
        if args.max_output_tokens < 1:
            parser.error("--max-output-tokens must be at least 1")
        if args.max_attempts < 1:
            parser.error("--max-attempts must be at least 1")
        if args.retry_delay_seconds < 0:
            parser.error("--retry-delay-seconds cannot be negative")
        results_path = Path(args.results)
        output_dir = Path(args.output_dir) if args.output_dir else results_path.with_name(
            f"{results_path.stem}.atomic_consensus"
        )
        artifact_paths = [
            output_dir / "atomic_primary_judgments.jsonl",
            output_dir / "atomic_primary_prompts.jsonl",
            output_dir / "atomic_secondary_judgments.jsonl",
            output_dir / "atomic_secondary_prompts.jsonl",
            output_dir / "atomic_consensus.jsonl",
            output_dir / "atomic_consensus_summary.json",
            output_dir / "atomic_consensus_report.md",
        ]
        existing = [path for path in artifact_paths if path.exists()]
        if existing and not args.overwrite and not args.resume:
            formatted = "\n".join(f"  - {path}" for path in existing)
            raise FileExistsError(
                "Atomic consensus artifacts already exist. Pass --overwrite or "
                "--resume:\n"
                f"{formatted}"
            )
        if args.overwrite:
            for path in existing:
                path.unlink()
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            from dotenv import load_dotenv
        except ImportError as exc:
            raise RuntimeError(
                "python-dotenv is required for consensus judge runs; install "
                "requirements.txt"
            ) from exc
        load_dotenv()

        results = [
            row for row in read_jsonl(results_path) if row.get("status") == "completed"
        ]
        result_run_ids = [_result_run_id(row) for row in results]
        if not results or any(not run_id for run_id in result_run_ids):
            raise ValueError("Consensus judging requires completed results with run_id values")
        if len(set(result_run_ids)) != len(result_run_ids):
            raise ValueError("Consensus judging requires unique result run_id values")
        result_run_id_set = set(result_run_ids)

        primary_path, primary_prompt_path = artifact_paths[:2]
        existing_primary = read_jsonl(primary_path) if args.resume and primary_path.exists() else []
        primary_by_run = {
            _subject_run_id(record): record
            for record in existing_primary
            if record.get("status") == "parsed"
            and _subject_run_id(record) in result_run_id_set
        }
        retained_primary = [
            primary_by_run[run_id]
            for run_id in result_run_ids
            if run_id in primary_by_run
        ]
        existing_primary_prompts = (
            read_jsonl(primary_prompt_path)
            if args.resume and primary_prompt_path.exists()
            else []
        )
        retained_primary_run_ids = set(primary_by_run)
        retained_primary_prompts = [
            record
            for record in existing_primary_prompts
            if str(record.get("subject_run_id") or "") in retained_primary_run_ids
        ]
        write_jsonl(primary_path, retained_primary)
        write_jsonl(primary_prompt_path, retained_primary_prompts)
        missing_primary_results = [
            row for row in results if _result_run_id(row) not in primary_by_run
        ]
        new_primary, _ = judge_results(
            missing_primary_results,
            judge_provider=args.primary_judge_provider,
            judge_model=args.primary_judge_model,
            max_output_tokens=args.max_output_tokens,
            settings={"reasoning_effort": args.primary_reasoning_effort},
            max_attempts=args.max_attempts,
            retry_delay_seconds=args.retry_delay_seconds,
            on_judgment=lambda record: _append_jsonl(primary_path, record),
            on_prompt=lambda record: _append_jsonl(primary_prompt_path, record),
        )
        primary_by_run.update(
            {_subject_run_id(record): record for record in new_primary}
        )
        primary_records = [
            primary_by_run[run_id]
            for run_id in result_run_ids
            if run_id in primary_by_run
        ]
        write_jsonl(primary_path, primary_records)

        secondary_path, secondary_prompt_path = artifact_paths[2:4]
        parsed_primary_run_ids = {
            _subject_run_id(record)
            for record in primary_records
            if record.get("status") == "parsed"
        }
        existing_secondary = (
            read_jsonl(secondary_path)
            if args.resume and secondary_path.exists()
            else []
        )
        secondary_by_run = {
            _subject_run_id(record): record
            for record in existing_secondary
            if record.get("status") == "parsed"
            and _subject_run_id(record) in parsed_primary_run_ids
        }
        retained_secondary = [
            secondary_by_run[run_id]
            for run_id in result_run_ids
            if run_id in secondary_by_run
        ]
        existing_secondary_prompts = (
            read_jsonl(secondary_prompt_path)
            if args.resume and secondary_prompt_path.exists()
            else []
        )
        retained_secondary_run_ids = set(secondary_by_run)
        retained_secondary_prompts = [
            record
            for record in existing_secondary_prompts
            if str(record.get("subject_run_id") or "") in retained_secondary_run_ids
        ]
        write_jsonl(secondary_path, retained_secondary)
        write_jsonl(secondary_prompt_path, retained_secondary_prompts)
        missing_secondary_primary = [
            record
            for record in primary_records
            if record.get("status") == "parsed"
            and _subject_run_id(record) not in secondary_by_run
        ]
        new_secondary, _ = judge_existing_claims(
            missing_secondary_primary,
            judge_provider=args.secondary_judge_provider,
            judge_model=args.secondary_judge_model,
            max_output_tokens=args.max_output_tokens,
            settings={"reasoning_effort": args.secondary_reasoning_effort},
            max_attempts=args.max_attempts,
            retry_delay_seconds=args.retry_delay_seconds,
            on_judgment=lambda record: _append_jsonl(secondary_path, record),
            on_prompt=lambda record: _append_jsonl(secondary_prompt_path, record),
        )
        secondary_by_run.update(
            {_subject_run_id(record): record for record in new_secondary}
        )
        secondary_records = [
            secondary_by_run[run_id]
            for run_id in result_run_ids
            if run_id in secondary_by_run
        ]
        write_jsonl(secondary_path, secondary_records)
        consensus_records = build_atomic_consensus(
            primary_records, secondary_records
        )
        write_jsonl(artifact_paths[4], consensus_records)
        _write_consensus_summary(
            consensus_records,
            primary_records,
            secondary_records,
            output_dir,
            overwrite=True,
        )
        primary_parsed = sum(
            record.get("status") == "parsed" for record in primary_records
        )
        secondary_parsed = sum(
            record.get("status") == "parsed" for record in secondary_records
        )
        consensus_completed = sum(
            record.get("status") == "consensus_computed"
            for record in consensus_records
        )
        print(
            "Automated consensus evaluation complete: "
            f"primary {primary_parsed}/{len(primary_records)}, "
            f"secondary {secondary_parsed}/{len(secondary_records)}, "
            f"consensus {consensus_completed}/{len(consensus_records)}."
        )
        print(f"Report written to {artifact_paths[6]}")
        if consensus_completed != len(results):
            raise RuntimeError(
                "Some responses do not yet have two parsed judgments. Inspect the "
                "checkpoint files, then rerun this command with --resume."
            )
        return

    if args.command == "judge":
        if args.max_output_tokens < 1:
            parser.error("--max-output-tokens must be at least 1")
        if args.max_attempts < 1:
            parser.error("--max-attempts must be at least 1")
        if args.retry_delay_seconds < 0:
            parser.error("--retry-delay-seconds cannot be negative")
        results_path = Path(args.results)
        output_dir = Path(args.output_dir) if args.output_dir else results_path.with_name(
            f"{results_path.stem}.atomic_evaluation"
        )
        artifact_paths = [
            output_dir / "atomic_judgments.jsonl",
            output_dir / "atomic_judge_prompts.jsonl",
            output_dir / "atomic_evaluation_summary.json",
            output_dir / "atomic_evaluation_report.md",
            output_dir / "atomic_review.blinded.csv",
            output_dir / "atomic_review.mapping.json",
        ]
        existing = [path for path in artifact_paths if path.exists()]
        if existing and not args.overwrite:
            formatted = "\n".join(f"  - {path}" for path in existing)
            raise FileExistsError(
                "Atomic evaluation artifacts already exist. Pass --overwrite:\n"
                f"{formatted}"
            )
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            from dotenv import load_dotenv
        except ImportError as exc:
            raise RuntimeError(
                "python-dotenv is required for atomic judge runs; install requirements.txt"
            ) from exc
        load_dotenv()

        results = read_jsonl(results_path)
        judgments, prompts = judge_results(
            results,
            judge_provider=args.judge_provider,
            judge_model=args.judge_model,
            max_output_tokens=args.max_output_tokens,
            settings={"reasoning_effort": args.reasoning_effort},
            max_attempts=args.max_attempts,
            retry_delay_seconds=args.retry_delay_seconds,
        )
        write_jsonl(artifact_paths[0], judgments)
        write_jsonl(artifact_paths[1], prompts)
        _write_summary(judgments, output_dir, overwrite=True)
        review_rows, mapping = blinded_atomic_review_package(
            judgments, args.review_seed
        )
        write_atomic_review_csv(artifact_paths[4], review_rows)
        _write(
            artifact_paths[5],
            json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
            True,
        )
        parsed = sum(record.get("status") == "parsed" for record in judgments)
        print(
            f"Atomic evaluation complete: {parsed}/{len(judgments)} responses parsed."
        )
        print(f"Report written to {artifact_paths[3]}")
        print(f"Blinded validation sample written to {artifact_paths[4]}")
        return

    if bool(args.annotations) != bool(args.review_map):
        parser.error("--annotations and --review-map must be supplied together")
    judgments_path = Path(args.judgments)
    output_dir = Path(args.output_dir) if args.output_dir else judgments_path.parent
    annotations = None
    disagreements = None
    if args.annotations:
        try:
            annotations, disagreements = compare_atomic_annotations(
                args.annotations,
                args.review_map,
            )
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
    disagreement_path = output_dir / "review_disagreements.csv"
    if disagreements is not None and disagreement_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"Refusing to overwrite {disagreement_path}; pass --overwrite"
        )
    _write_summary(
        read_jsonl(judgments_path),
        output_dir,
        annotations=annotations,
        overwrite=args.overwrite,
    )
    if disagreements is not None:
        write_atomic_disagreements_csv(disagreement_path, disagreements)
    print(f"Atomic evaluation report rebuilt in {output_dir}")
    if disagreements is not None:
        print(
            f"Review disagreements written to {disagreement_path} "
            f"({len(disagreements)} claims)"
        )


if __name__ == "__main__":
    main()
