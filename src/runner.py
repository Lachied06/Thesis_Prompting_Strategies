from __future__ import annotations

import json
import random
import time
import uuid
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from src.parsing import normalize_label, parse_response
from src.prompting import build_prompt_plan, parse_strategy_spec, strategy_label
from src.schemas import (
    GenerationRequest,
    ParsedResponse,
    Prompt,
    RunResult,
    Task,
    TraceStep,
)


RESULT_SCHEMA_VERSION = "3.1.0"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_jsonl_if_exists(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: invalid JSON on line {line_number}") from exc
    return rows


def _rewrite_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(path)


def _result_job_key(row: Dict[str, Any]) -> tuple[Any, ...]:
    dataset = row.get("dataset") or {}
    model = row.get("model") or {}
    strategy = row.get("strategy") or {}
    return (
        int(row.get("repetition") or 1),
        str(dataset.get("task_id") or ""),
        str(model.get("provider") or ""),
        str(model.get("name") or ""),
        str(strategy.get("name") or ""),
        str(strategy.get("version") or ""),
    )


def _planned_job_key(job: Dict[str, Any]) -> tuple[Any, ...]:
    strategy_name, strategy_version = parse_strategy_spec(job["strategy"])
    model_cfg = job["model_cfg"]
    task: Task = job["task"]
    return (
        int(job["repetition"]),
        task.task_id,
        str(model_cfg["provider"]),
        str(model_cfg["model"]),
        strategy_name,
        strategy_version,
    )


def _prepare_resume_artifacts(
    output: Path,
    prompt_log: Optional[Path],
) -> tuple[Dict[tuple[Any, ...], Dict[str, Any]], int]:
    existing_rows = _read_jsonl_if_exists(output)
    retained: Dict[tuple[Any, ...], Dict[str, Any]] = {}
    error_keys = set()
    for row in existing_rows:
        key = _result_job_key(row)
        if row.get("status") in {"completed", "skipped"}:
            retained[key] = row
        elif row.get("status") == "error":
            error_keys.add(key)

    retained_rows = list(retained.values())
    _rewrite_jsonl(output, retained_rows)
    if prompt_log is not None:
        retained_run_ids = {
            str(row.get("run_id") or "") for row in retained_rows
        }
        retained_prompts = [
            row
            for row in _read_jsonl_if_exists(prompt_log)
            if str(row.get("run_id") or "") in retained_run_ids
        ]
        _rewrite_jsonl(prompt_log, retained_prompts)
    return retained, len(error_keys - set(retained))


def _default_provider_builder(provider: str, model: str):
    # Delayed import keeps prompt preview completely independent of provider
    # SDKs, API keys, and network access.
    from src.providers.factory import build_provider

    return build_provider(provider, model)


def build_jobs(config: Dict[str, Any], tasks: Iterable[Task]) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    for repetition in range(1, int(config["repetitions"]) + 1):
        for task in tasks:
            for model_cfg in config["models"]:
                for strategy in config["strategies"]:
                    jobs.append(
                        {
                            "repetition": repetition,
                            "task": task,
                            "model_cfg": model_cfg,
                            "strategy": strategy,
                        }
                    )

    if config.get("shuffle_run_order", True):
        rng = random.Random(int(config.get("random_seed", 42)))
        rng.shuffle(jobs)
    return jobs


def _prompt_log_record(
    *,
    experiment_id: str,
    experiment_name: str,
    run_id: str,
    repetition: int,
    task: Task,
    provider: str,
    model: str,
    prompt: Prompt,
    request: GenerationRequest,
) -> Dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "experiment_name": experiment_name,
        "run_id": run_id,
        "repetition": repetition,
        "dataset": task.dataset,
        "task_id": task.task_id,
        "provider": provider,
        "model": model,
        "strategy": prompt.strategy,
        "strategy_version": prompt.template_version,
        "step": prompt.step,
        "logged_at_utc": utc_now_iso(),
        "prompt": prompt.to_dict(),
        "request": asdict(request),
    }


def write_prompt_preview(
    config: Dict[str, Any],
    tasks: List[Task],
    output_path: str | Path,
    task_limit: Optional[int] = None,
) -> Dict[str, int]:
    selected_tasks = tasks[:task_limit] if task_limit is not None else tasks
    rendered = 0
    skipped = 0
    lines = [
        f"# Prompt preview: {config['experiment_name']}",
        "",
        "This file is generated without calling any model API.",
        "For chain-of-verification, generated material is represented by",
        "placeholders. Live runs save every fully realised prompt.",
        "",
    ]

    for task in selected_tasks:
        for strategy in config["strategies"]:
            display_strategy = strategy_label(strategy)
            lines.extend(
                [
                    f"## Task `{task.task_id}` — `{display_strategy}`",
                    "",
                    f"- Dataset: `{task.dataset}`",
                    "",
                ]
            )
            try:
                plan = build_prompt_plan(strategy, task)
            except ValueError as exc:
                skipped += 1
                lines.extend([f"- Status: skipped — {exc}", ""])
                continue

            for prompt in plan.preview_prompts():
                rendered += 1
                components = ", ".join(
                    next(
                        template["components"]
                        for template in plan.strategy_metadata["templates"]
                        if template["template_id"] == prompt.template_id
                    )
                )
                lines.extend(
                    [
                        f"### {prompt.step}",
                        "",
                        f"- Template: `{prompt.template_id}`",
                        f"- Version: `{prompt.template_version}`",
                        f"- Components: {components}",
                        f"- Prompt hash: `{prompt.prompt_hash}`",
                        "",
                    ]
                )
                if prompt.system_prompt:
                    lines.extend(
                        ["#### System", "", "```text", prompt.system_prompt, "```", ""]
                    )
                else:
                    lines.extend(["#### System", "", "_No system prompt._", ""])
                lines.extend(
                    ["#### User", "", "```text", prompt.user_prompt, "```", ""]
                )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "tasks": len(selected_tasks),
        "rendered_prompts": rendered,
        "skipped_conditions": skipped,
    }


def run_experiment(
    config: Dict[str, Any],
    tasks: List[Task],
    output_path: str,
    *,
    prompt_log_path: Optional[str] = None,
    experiment_id: Optional[str] = None,
    provider_builder: Callable[[str, str], Any] = _default_provider_builder,
    resume: bool = False,
) -> Dict[str, int]:
    output = Path(output_path)
    prompt_log = Path(prompt_log_path) if prompt_log_path else None
    experiment_id = experiment_id or str(uuid.uuid4())
    jobs = build_jobs(config, tasks)
    providers: Dict[tuple[str, str], Any] = {}
    statuses: Counter[str] = Counter()
    retained: Dict[tuple[Any, ...], Dict[str, Any]] = {}
    retried_errors = 0
    if resume:
        retained, retried_errors = _prepare_resume_artifacts(output, prompt_log)
        statuses.update(str(row.get("status")) for row in retained.values())

    for index, job in enumerate(jobs, start=1):
        job_key = _planned_job_key(job)
        if job_key in retained:
            print(f"[{index}/{len(jobs)}] already complete; skipping")
            continue
        task: Task = job["task"]
        model_cfg = job["model_cfg"]
        strategy_spec = job["strategy"]
        strategy_base_name, strategy_version = parse_strategy_spec(strategy_spec)
        strategy_display = strategy_label(strategy_spec)
        repetition = int(job["repetition"])

        provider_name = str(model_cfg["provider"])
        model_name = str(model_cfg["model"])
        settings = dict(model_cfg.get("settings", {}))
        max_output_tokens = int(config["max_output_tokens"])

        run_id = str(uuid.uuid4())
        started_at = utc_now_iso()
        overall_start = time.perf_counter()
        trace: List[TraceStep] = []
        status = "completed"
        parsed_response: Optional[ParsedResponse] = None
        error = None
        strategy_metadata: Dict[str, Any] = {
            "name": strategy_base_name,
            "version": strategy_version,
            "registry_version": None,
            "templates": [],
        }

        print(
            f"[{index}/{len(jobs)}] "
            f"{task.task_id} | {provider_name}:{model_name} | {strategy_display}"
        )

        try:
            # Build and validate the treatment before touching provider keys.
            plan = build_prompt_plan(strategy_spec, task)
            strategy_metadata = plan.strategy_metadata

            provider_key = (provider_name, model_name)
            if provider_key not in providers:
                providers[provider_key] = provider_builder(provider_name, model_name)
            provider = providers[provider_key]

            first_prompt = plan.first_prompt
            first_request = GenerationRequest(
                system_prompt=first_prompt.system_prompt,
                user_prompt=first_prompt.user_prompt,
                max_output_tokens=max_output_tokens,
                settings=settings,
            )
            if prompt_log:
                append_jsonl(
                    prompt_log,
                    _prompt_log_record(
                        experiment_id=experiment_id,
                        experiment_name=config["experiment_name"],
                        run_id=run_id,
                        repetition=repetition,
                        task=task,
                        provider=provider_name,
                        model=model_name,
                        prompt=first_prompt,
                        request=first_request,
                    ),
                )

            t0 = time.perf_counter()
            first_response = provider.generate(first_request)
            first_latency = time.perf_counter() - t0
            trace.append(
                TraceStep(
                    label="initial_generation",
                    prompt=first_prompt,
                    request=first_request,
                    response=first_response,
                    latency_seconds=first_latency,
                )
            )
            final_text = first_response.text

            verification_prompt = plan.render_verification(first_response.text)
            if verification_prompt:
                verification_request = GenerationRequest(
                    system_prompt=verification_prompt.system_prompt,
                    user_prompt=verification_prompt.user_prompt,
                    max_output_tokens=max_output_tokens,
                    settings=settings,
                )
                if prompt_log:
                    append_jsonl(
                        prompt_log,
                        _prompt_log_record(
                            experiment_id=experiment_id,
                            experiment_name=config["experiment_name"],
                            run_id=run_id,
                            repetition=repetition,
                            task=task,
                            provider=provider_name,
                            model=model_name,
                            prompt=verification_prompt,
                            request=verification_request,
                        ),
                    )

                t1 = time.perf_counter()
                verification_response = provider.generate(verification_request)
                verification_latency = time.perf_counter() - t1
                trace.append(
                    TraceStep(
                        label="verification_generation",
                        prompt=verification_prompt,
                        request=verification_request,
                        response=verification_response,
                        latency_seconds=verification_latency,
                    )
                )
                final_text = verification_response.text

                revision_prompt = plan.render_revision(
                    first_response.text,
                    verification_response.text,
                )
                if revision_prompt:
                    revision_request = GenerationRequest(
                        system_prompt=revision_prompt.system_prompt,
                        user_prompt=revision_prompt.user_prompt,
                        max_output_tokens=max_output_tokens,
                        settings=settings,
                    )
                    if prompt_log:
                        append_jsonl(
                            prompt_log,
                            _prompt_log_record(
                                experiment_id=experiment_id,
                                experiment_name=config["experiment_name"],
                                run_id=run_id,
                                repetition=repetition,
                                task=task,
                                provider=provider_name,
                                model=model_name,
                                prompt=revision_prompt,
                                request=revision_request,
                            ),
                        )

                    t2 = time.perf_counter()
                    revision_response = provider.generate(revision_request)
                    revision_latency = time.perf_counter() - t2
                    trace.append(
                        TraceStep(
                            label="revision_generation",
                            prompt=revision_prompt,
                            request=revision_request,
                            response=revision_response,
                            latency_seconds=revision_latency,
                        )
                    )
                    final_text = revision_response.text

            parsed_response = parse_response(final_text, task)

        except ValueError as exc:
            status = "skipped"
            error = str(exc)
        except Exception as exc:
            status = "error"
            error = f"{type(exc).__name__}: {exc}"

        finished_at = utc_now_iso()
        total_latency = time.perf_counter() - overall_start
        result = RunResult(
            schema_version=RESULT_SCHEMA_VERSION,
            experiment_id=experiment_id,
            run_id=run_id,
            experiment_name=config["experiment_name"],
            repetition=repetition,
            task=task,
            provider=provider_name,
            model=model_name,
            strategy=strategy_metadata,
            max_output_tokens=max_output_tokens,
            status=status,
            started_at_utc=started_at,
            finished_at_utc=finished_at,
            latency_seconds=total_latency,
            parsed_response=parsed_response,
            trace=trace,
            model_settings=settings,
            ground_truth_label=normalize_label(task.reference_answer),
            error=error,
        )
        append_jsonl(output, result.to_dict())
        statuses[status] += 1

    return {
        "total": len(jobs),
        "completed": statuses["completed"],
        "skipped": statuses["skipped"],
        "errors": statuses["error"],
        "resumed_existing": len(retained),
        "retried_errors": retried_errors,
    }
