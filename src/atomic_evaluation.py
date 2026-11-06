from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from src.schemas import GenerationRequest


ATOMIC_EVALUATION_SCHEMA_VERSION = "1.4.0"
SUPPORT_LABELS = {
    "SUPPORTED",
    "CONTRADICTED",
    "NOT_IN_SOURCES",
    "NOT_FACTUAL",
}
CITATION_LABELS = {
    "SUPPORTED",
    "UNSUPPORTED",
    "NO_CITATION",
    "NOT_APPLICABLE",
}
UNSUPPORTED_LABELS = {"CONTRADICTED", "NOT_IN_SOURCES"}
HALLUCINATION_TYPES = {
    "NONE",
    "UNSUPPORTED_ADDITION",
    "SOURCE_CONTRADICTION",
    "EVIDENCE_OVERSTATEMENT",
    "ENTITY_CONTEXT_CONFUSION",
    "OTHER",
}


def _validated_hallucination_type(
    value: Any,
    support_status: str,
    *,
    claim_label: str,
) -> str:
    hallucination_type = str(value or "").strip().upper()
    if hallucination_type not in HALLUCINATION_TYPES:
        raise ValueError(
            f"{claim_label} has invalid hallucination_type: {hallucination_type}"
        )
    if support_status in {"SUPPORTED", "NOT_FACTUAL"} and hallucination_type != "NONE":
        raise ValueError(
            f"{claim_label}: supported or non-factual claims require "
            "hallucination_type NONE"
        )
    if support_status in UNSUPPORTED_LABELS and hallucination_type == "NONE":
        raise ValueError(
            f"{claim_label}: unsupported claims require a non-NONE hallucination_type"
        )
    return hallucination_type


def _default_provider_builder(provider: str, model: str):
    from src.providers.factory import build_provider

    return build_provider(provider, model)


def read_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Line {line_number}: invalid JSON") from exc
    return rows


def write_jsonl(path: str | Path, rows: Iterable[Dict[str, Any]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _response_text(row: Dict[str, Any]) -> str:
    response = row.get("response") or {}
    return str(response.get("raw") or response.get("explanation") or "").strip()


def build_atomic_judge_request(
    row: Dict[str, Any],
    *,
    max_output_tokens: int,
    settings: Optional[Dict[str, Any]] = None,
) -> GenerationRequest:
    task = row.get("task") or {}
    task_prompt = str(task.get("prompt") or "").strip()
    source_context = str(task.get("source_context") or "").strip()
    response_text = _response_text(row)
    if not task_prompt or not source_context or not response_text:
        raise ValueError("Atomic judging requires task prompt, sources, and response text")

    system_prompt = (
        "You are a strict evidence-attribution annotator. Extract only subject-matter "
        "factual propositions asserted in the model response, then evaluate whether "
        "each is established by the supplied source material. Do not use outside "
        "knowledge, name familiarity, aliases, abbreviation assumptions, or facts "
        "that merely sound plausible."
    )
    user_prompt = f"""TASK
----
{task_prompt}

SUPPLIED SOURCE MATERIAL
------------------------
{source_context}

MODEL RESPONSE
--------------
{response_text}

ANNOTATION PROCEDURE
--------------------
1. Extract only minimal, independently checkable SUBJECT-MATTER facts about
   people, organisations, objects, events, relationships, measurements, or outcomes.
2. EXCLUDE all of the following from the claims list:
   - the VERDICT label or restatements that the answer is supported/contradicted;
   - descriptions of the question, task, or proposed answer;
   - statements about what the source says, mentions, omits, or establishes;
   - evidential-sufficiency conclusions such as "there is no contradiction",
     "the evidence is sufficient", or "there is no basis to reject";
   - conclusions that the proposed answer is correct or incorrect;
   - citations by themselves, discourse markers, and statements of uncertainty.
3. Rewrite retained claims as subject-matter propositions without phrases such as
   "the source states". Do not add facts while rewriting.
4. Treat entity identity strictly. If a proposition depends on equating different
   names, aliases, abbreviations, or entities, the supplied source must explicitly
   establish that link. Name similarity or outside knowledge is insufficient.
5. Assign each extracted claim exactly one support_status:
   - SUPPORTED: directly established by the supplied source material.
   - CONTRADICTED: inconsistent with the supplied source material.
   - NOT_IN_SOURCES: neither established nor contradicted by the supplied sources.
   - NOT_FACTUAL: not an externally checkable factual proposition.
6. Assign one dominant hallucination_type:
   - NONE: required for SUPPORTED and NOT_FACTUAL claims.
   - UNSUPPORTED_ADDITION: a factual detail is introduced without source support.
   - SOURCE_CONTRADICTION: the proposition directly conflicts with the sources.
   - EVIDENCE_OVERSTATEMENT: the response strengthens scope, certainty, causality,
     population, or generality beyond what the sources establish.
   - ENTITY_CONTEXT_CONFUSION: the response confuses a paper, entity, population,
     intervention, outcome, setting, or closely related concept.
   - OTHER: unsupported or contradicted, but none of the preceding types fits.
   For an unsupported claim, choose the single type that best explains the error.
7. Record only document IDs actually attached to that claim in the response.
8. Assign citation_status exactly one value:
   - SUPPORTED: at least one attached supplied citation supports the claim.
   - UNSUPPORTED: attached citation IDs are supplied but do not support the claim.
   - NO_CITATION: a factual claim has no attached citation.
   - NOT_APPLICABLE: use only when support_status is NOT_FACTUAL.
9. A valid-looking document ID does not prove that the document supports the claim.

Return JSON only, with no Markdown fence or additional text:
{{
  "claims": [
    {{
      "claim": "minimal factual proposition",
      "support_status": "SUPPORTED | CONTRADICTED | NOT_IN_SOURCES | NOT_FACTUAL",
      "hallucination_type": "NONE | UNSUPPORTED_ADDITION | SOURCE_CONTRADICTION | EVIDENCE_OVERSTATEMENT | ENTITY_CONTEXT_CONFUSION | OTHER",
      "cited_document_ids": ["document_id"],
      "citation_status": "SUPPORTED | UNSUPPORTED | NO_CITATION | NOT_APPLICABLE",
      "rationale": "brief source-grounded reason"
    }}
  ]
}}"""
    return GenerationRequest(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_output_tokens=max_output_tokens,
        settings=dict(settings or {}),
    )


def _json_object_from_text(text: str) -> Dict[str, Any]:
    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Judge output does not contain a JSON object")
    payload = json.loads(stripped[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Judge output must be a JSON object")
    return payload


def parse_atomic_judgment(text: str, run_id: str) -> List[Dict[str, Any]]:
    payload = _json_object_from_text(text)
    raw_claims = payload.get("claims")
    if not isinstance(raw_claims, list) or not raw_claims:
        raise ValueError("Judge output must contain a non-empty claims list")

    claims: List[Dict[str, Any]] = []
    for index, raw_claim in enumerate(raw_claims, start=1):
        if not isinstance(raw_claim, dict):
            raise ValueError(f"Claim {index} must be an object")
        claim = str(raw_claim.get("claim") or "").strip()
        support_status = str(raw_claim.get("support_status") or "").strip().upper()
        citation_status = str(raw_claim.get("citation_status") or "").strip().upper()
        if support_status == "NOT_IN_EVIDENCE":
            support_status = "NOT_IN_SOURCES"
        if not claim:
            raise ValueError(f"Claim {index} is empty")
        if support_status not in SUPPORT_LABELS:
            raise ValueError(f"Claim {index} has invalid support_status: {support_status}")
        if citation_status not in CITATION_LABELS:
            raise ValueError(f"Claim {index} has invalid citation_status: {citation_status}")
        hallucination_type = _validated_hallucination_type(
            raw_claim.get("hallucination_type"),
            support_status,
            claim_label=f"Claim {index}",
        )
        if support_status == "NOT_FACTUAL" and citation_status != "NOT_APPLICABLE":
            raise ValueError(
                f"Claim {index}: NOT_FACTUAL requires citation_status NOT_APPLICABLE"
            )
        if support_status != "NOT_FACTUAL" and citation_status == "NOT_APPLICABLE":
            raise ValueError(
                f"Claim {index}: factual claims cannot use citation_status NOT_APPLICABLE"
            )
        cited = raw_claim.get("cited_document_ids") or []
        if not isinstance(cited, list):
            raise ValueError(f"Claim {index}: cited_document_ids must be a list")
        claims.append(
            {
                "claim_id": f"{run_id}:claim:{index:03d}",
                "claim": claim,
                "support_status": support_status,
                "hallucination_type": hallucination_type,
                "cited_document_ids": [str(value).strip() for value in cited if str(value).strip()],
                "citation_status": citation_status,
                "rationale": str(raw_claim.get("rationale") or "").strip(),
            }
        )
    return claims


def _prompt_hash(request: GenerationRequest) -> str:
    payload = json.dumps(
        {
            "system_prompt": request.system_prompt,
            "user_prompt": request.user_prompt,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _subject_metadata(row: Dict[str, Any]) -> Dict[str, Any]:
    task = row.get("task") or {}
    metadata = task.get("metadata") or {}
    return {
        "experiment_id": row.get("experiment_id"),
        "run_id": row.get("run_id"),
        "dataset": (row.get("dataset") or {}).get("name"),
        "task_id": (row.get("dataset") or {}).get("task_id"),
        "task_prompt": task.get("prompt"),
        "source_context": task.get("source_context"),
        "response_text": _response_text(row),
        "difficulty_category": metadata.get("difficulty_category", "unspecified"),
        "source_item_id": metadata.get("source_item_id"),
        "base_task_id": metadata.get("base_task_id"),
        "model": row.get("model") or {},
        "strategy": row.get("strategy") or {},
    }


def judge_results(
    rows: Iterable[Dict[str, Any]],
    *,
    judge_provider: str,
    judge_model: str,
    max_output_tokens: int = 2400,
    settings: Optional[Dict[str, Any]] = None,
    max_attempts: int = 2,
    retry_delay_seconds: float = 1.0,
    provider_builder: Callable[[str, str], Any] = _default_provider_builder,
    on_judgment: Optional[Callable[[Dict[str, Any]], None]] = None,
    on_prompt: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if retry_delay_seconds < 0:
        raise ValueError("retry_delay_seconds cannot be negative")
    materialized = [row for row in rows if row.get("status") == "completed"]
    if not materialized:
        return [], []
    provider = provider_builder(judge_provider, judge_model)
    judgments: List[Dict[str, Any]] = []
    prompts: List[Dict[str, Any]] = []

    for index, row in enumerate(materialized, start=1):
        subject = _subject_metadata(row)
        run_id = str(subject.get("run_id") or f"row-{index}")
        request = build_atomic_judge_request(
            row,
            max_output_tokens=max_output_tokens,
            settings=settings,
        )
        prompt_hash = _prompt_hash(request)
        print(
            f"[{index}/{len(materialized)}] atomic judge | "
            f"{subject['task_id']} | {subject['model'].get('name')} | "
            f"{subject['strategy'].get('name')}"
        )

        started = time.perf_counter()
        raw_output = ""
        claims: List[Dict[str, Any]] = []
        status = "error"
        error: Optional[str] = None
        attempts: List[Dict[str, Any]] = []

        for attempt_number in range(1, max_attempts + 1):
            prompt_record = {
                "schema_version": ATOMIC_EVALUATION_SCHEMA_VERSION,
                "subject_run_id": run_id,
                "attempt_number": attempt_number,
                "max_attempts": max_attempts,
                "judge": {
                    "provider": judge_provider,
                    "model": judge_model,
                    "settings": dict(settings or {}),
                },
                "prompt_hash": prompt_hash,
                "request": asdict(request),
            }
            prompts.append(prompt_record)
            if on_prompt:
                on_prompt(prompt_record)
            attempt_started = time.perf_counter()
            attempt_output = ""
            attempt_usage = {
                "input_tokens": None,
                "output_tokens": None,
                "reasoning_tokens": None,
            }
            try:
                response = provider.generate(request)
                attempt_output = response.text
                attempt_usage = {
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "reasoning_tokens": response.reasoning_tokens,
                }
                claims = parse_atomic_judgment(response.text, run_id)
                status = "parsed"
                error = None
            except Exception as exc:
                claims = []
                status = "error"
                error = f"{type(exc).__name__}: {exc}"

            raw_output = attempt_output
            attempts.append(
                {
                    "attempt_number": attempt_number,
                    "status": status,
                    "raw_judge_output": attempt_output,
                    "usage": attempt_usage,
                    "latency_seconds": round(
                        time.perf_counter() - attempt_started, 4
                    ),
                    "error": error,
                }
            )
            if status == "parsed":
                break
            if attempt_number < max_attempts:
                print(
                    f"  retrying atomic judge after attempt {attempt_number}: "
                    f"{error}"
                )
                if retry_delay_seconds:
                    time.sleep(retry_delay_seconds)

        usage = {}
        for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
            known = [
                attempt["usage"][key]
                for attempt in attempts
                if attempt["usage"][key] is not None
            ]
            usage[key] = sum(known) if known else None
        judgment_record = {
                "schema_version": ATOMIC_EVALUATION_SCHEMA_VERSION,
                "subject": subject,
                "judge": {
                    "provider": judge_provider,
                    "model": judge_model,
                    "settings": dict(settings or {}),
                },
                "status": status,
                "claims": claims,
                "prompt_hash": prompt_hash,
                "raw_judge_output": raw_output,
                "usage": usage,
                "attempt_count": len(attempts),
                "attempts": attempts,
                "latency_seconds": round(time.perf_counter() - started, 4),
                "error": error,
            }
        judgments.append(judgment_record)
        if on_judgment:
            on_judgment(judgment_record)
    return judgments, prompts


def build_atomic_secondary_request(
    primary_record: Dict[str, Any],
    *,
    max_output_tokens: int,
    settings: Optional[Dict[str, Any]] = None,
) -> GenerationRequest:
    if primary_record.get("status") != "parsed":
        raise ValueError("Secondary judging requires a parsed primary judgment")
    subject = primary_record.get("subject") or {}
    claims = primary_record.get("claims") or []
    if not claims:
        raise ValueError("Secondary judging requires at least one extracted claim")
    task_prompt = str(subject.get("task_prompt") or "").strip()
    source_context = str(subject.get("source_context") or "").strip()
    response_text = str(subject.get("response_text") or "").strip()
    if not task_prompt or not source_context or not response_text:
        raise ValueError("Secondary judging requires task, sources, and response text")

    shared_claims = [
        {
            "claim_id": claim["claim_id"],
            "claim": claim["claim"],
            "cited_document_ids": claim.get("cited_document_ids") or [],
        }
        for claim in claims
    ]
    system_prompt = (
        "You are the second of two independent source-only factuality judges. "
        "Evaluate the supplied fixed claim inventory without seeing or inferring the "
        "first judge's labels. Do not add, remove, merge, split, or rewrite claims."
    )
    user_prompt = f"""TASK
----
{task_prompt}

SUPPLIED SOURCE MATERIAL
------------------------
{source_context}

MODEL RESPONSE
--------------
{response_text}

FIXED CLAIM INVENTORY
---------------------
{json.dumps(shared_claims, ensure_ascii=False, indent=2)}

INDEPENDENT LABELING RULES
--------------------------
1. Judge every claim only against the supplied source material. Do not use
   outside knowledge, common name variants, aliases, abbreviations, or plausibility.
2. Entity identity is strict: different names or entities may be linked only when
   the supplied source explicitly establishes that link.
3. Assign support_status exactly one value:
   - SUPPORTED: directly established by the supplied source material.
   - CONTRADICTED: inconsistent with the supplied source material.
   - NOT_IN_SOURCES: neither established nor contradicted by the supplied sources.
   - NOT_FACTUAL: not an externally checkable subject-matter proposition.
4. Assign one dominant hallucination_type using the same source-only decision:
   - NONE: required for SUPPORTED and NOT_FACTUAL claims.
   - UNSUPPORTED_ADDITION: a factual detail is introduced without source support.
   - SOURCE_CONTRADICTION: the proposition directly conflicts with the sources.
   - EVIDENCE_OVERSTATEMENT: the response strengthens scope, certainty, causality,
     population, or generality beyond what the sources establish.
   - ENTITY_CONTEXT_CONFUSION: the response confuses a paper, entity, population,
     intervention, outcome, setting, or closely related concept.
   - OTHER: unsupported or contradicted, but none of the preceding types fits.
5. Judge citation_status from cited_document_ids already attached to each claim:
   - SUPPORTED: at least one attached supplied citation supports the claim.
   - UNSUPPORTED: attached supplied citation IDs do not support the claim.
   - NO_CITATION: a factual claim has no attached citation.
   - NOT_APPLICABLE: use only when support_status is NOT_FACTUAL.
6. A valid document identifier does not establish semantic support.

Return JSON only, preserving every claim_id exactly and in the supplied order:
{{
  "claims": [
    {{
      "claim_id": "existing claim ID",
      "support_status": "SUPPORTED | CONTRADICTED | NOT_IN_SOURCES | NOT_FACTUAL",
      "hallucination_type": "NONE | UNSUPPORTED_ADDITION | SOURCE_CONTRADICTION | EVIDENCE_OVERSTATEMENT | ENTITY_CONTEXT_CONFUSION | OTHER",
      "citation_status": "SUPPORTED | UNSUPPORTED | NO_CITATION | NOT_APPLICABLE",
      "rationale": "brief source-grounded reason"
    }}
  ]
}}"""
    return GenerationRequest(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_output_tokens=max_output_tokens,
        settings=dict(settings or {}),
    )


def parse_atomic_secondary_judgment(
    text: str,
    primary_claims: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    expected = list(primary_claims)
    expected_by_id = {str(claim["claim_id"]): claim for claim in expected}
    payload = _json_object_from_text(text)
    raw_claims = payload.get("claims")
    if not isinstance(raw_claims, list):
        raise ValueError("Secondary judge output must contain a claims list")

    parsed_by_id: Dict[str, Dict[str, Any]] = {}
    for index, raw_claim in enumerate(raw_claims, start=1):
        if not isinstance(raw_claim, dict):
            raise ValueError(f"Secondary claim {index} must be an object")
        claim_id = str(raw_claim.get("claim_id") or "").strip()
        if claim_id not in expected_by_id:
            raise ValueError(f"Secondary claim {index} has unknown claim_id: {claim_id}")
        if claim_id in parsed_by_id:
            raise ValueError(f"Secondary judge repeated claim_id: {claim_id}")
        support_status = str(raw_claim.get("support_status") or "").strip().upper()
        citation_status = str(raw_claim.get("citation_status") or "").strip().upper()
        if support_status == "NOT_IN_EVIDENCE":
            support_status = "NOT_IN_SOURCES"
        if support_status not in SUPPORT_LABELS:
            raise ValueError(
                f"Secondary claim {index} has invalid support_status: {support_status}"
            )
        if citation_status not in CITATION_LABELS:
            raise ValueError(
                f"Secondary claim {index} has invalid citation_status: {citation_status}"
            )
        hallucination_type = _validated_hallucination_type(
            raw_claim.get("hallucination_type"),
            support_status,
            claim_label=f"Secondary claim {index}",
        )
        if (support_status == "NOT_FACTUAL") != (
            citation_status == "NOT_APPLICABLE"
        ):
            raise ValueError(
                f"Secondary claim {index}: NOT_FACTUAL and NOT_APPLICABLE must match"
            )
        original = expected_by_id[claim_id]
        parsed_by_id[claim_id] = {
            "claim_id": claim_id,
            "claim": original["claim"],
            "cited_document_ids": list(original.get("cited_document_ids") or []),
            "support_status": support_status,
            "hallucination_type": hallucination_type,
            "citation_status": citation_status,
            "rationale": str(raw_claim.get("rationale") or "").strip(),
        }

    missing = [claim_id for claim_id in expected_by_id if claim_id not in parsed_by_id]
    if missing:
        raise ValueError(
            "Secondary judge omitted claim IDs: " + ", ".join(missing)
        )
    return [parsed_by_id[str(claim["claim_id"])] for claim in expected]


def judge_existing_claims(
    primary_records: Iterable[Dict[str, Any]],
    *,
    judge_provider: str,
    judge_model: str,
    max_output_tokens: int = 2400,
    settings: Optional[Dict[str, Any]] = None,
    max_attempts: int = 2,
    retry_delay_seconds: float = 1.0,
    provider_builder: Callable[[str, str], Any] = _default_provider_builder,
    on_judgment: Optional[Callable[[Dict[str, Any]], None]] = None,
    on_prompt: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if retry_delay_seconds < 0:
        raise ValueError("retry_delay_seconds cannot be negative")
    materialized = [
        record for record in primary_records if record.get("status") == "parsed"
    ]
    if not materialized:
        return [], []
    provider = provider_builder(judge_provider, judge_model)
    judgments: List[Dict[str, Any]] = []
    prompts: List[Dict[str, Any]] = []

    for index, primary in enumerate(materialized, start=1):
        subject = primary.get("subject") or {}
        run_id = str(subject.get("run_id") or f"row-{index}")
        request = build_atomic_secondary_request(
            primary,
            max_output_tokens=max_output_tokens,
            settings=settings,
        )
        prompt_hash = _prompt_hash(request)
        print(
            f"[{index}/{len(materialized)}] secondary atomic judge | "
            f"{subject.get('task_id')} | {(subject.get('model') or {}).get('name')} | "
            f"{(subject.get('strategy') or {}).get('name')}"
        )
        started = time.perf_counter()
        raw_output = ""
        claims: List[Dict[str, Any]] = []
        status = "error"
        error: Optional[str] = None
        attempts: List[Dict[str, Any]] = []

        for attempt_number in range(1, max_attempts + 1):
            prompt_record = {
                    "schema_version": ATOMIC_EVALUATION_SCHEMA_VERSION,
                    "judge_role": "secondary",
                    "subject_run_id": run_id,
                    "attempt_number": attempt_number,
                    "max_attempts": max_attempts,
                    "judge": {
                        "provider": judge_provider,
                        "model": judge_model,
                        "settings": dict(settings or {}),
                    },
                    "prompt_hash": prompt_hash,
                    "request": asdict(request),
                }
            prompts.append(prompt_record)
            if on_prompt:
                on_prompt(prompt_record)
            attempt_started = time.perf_counter()
            attempt_output = ""
            attempt_usage = {
                "input_tokens": None,
                "output_tokens": None,
                "reasoning_tokens": None,
            }
            try:
                response = provider.generate(request)
                attempt_output = response.text
                attempt_usage = {
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "reasoning_tokens": response.reasoning_tokens,
                }
                claims = parse_atomic_secondary_judgment(
                    response.text,
                    primary.get("claims") or [],
                )
                status = "parsed"
                error = None
            except Exception as exc:
                claims = []
                status = "error"
                error = f"{type(exc).__name__}: {exc}"

            raw_output = attempt_output
            attempts.append(
                {
                    "attempt_number": attempt_number,
                    "status": status,
                    "raw_judge_output": attempt_output,
                    "usage": attempt_usage,
                    "latency_seconds": round(
                        time.perf_counter() - attempt_started, 4
                    ),
                    "error": error,
                }
            )
            if status == "parsed":
                break
            if attempt_number < max_attempts:
                print(
                    f"  retrying secondary judge after attempt {attempt_number}: "
                    f"{error}"
                )
                if retry_delay_seconds:
                    time.sleep(retry_delay_seconds)

        usage: Dict[str, Optional[int]] = {}
        for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
            known = [
                attempt["usage"][key]
                for attempt in attempts
                if attempt["usage"][key] is not None
            ]
            usage[key] = sum(known) if known else None
        judgment_record = {
                "schema_version": ATOMIC_EVALUATION_SCHEMA_VERSION,
                "judge_role": "secondary",
                "subject": subject,
                "judge": {
                    "provider": judge_provider,
                    "model": judge_model,
                    "settings": dict(settings or {}),
                },
                "status": status,
                "claims": claims,
                "prompt_hash": prompt_hash,
                "raw_judge_output": raw_output,
                "usage": usage,
                "attempt_count": len(attempts),
                "attempts": attempts,
                "latency_seconds": round(time.perf_counter() - started, 4),
                "error": error,
            }
        judgments.append(judgment_record)
        if on_judgment:
            on_judgment(judgment_record)
    return judgments, prompts


def _combined_usage(
    existing: Dict[str, Any],
    retry: Dict[str, Any],
) -> Dict[str, Optional[int]]:
    combined: Dict[str, Optional[int]] = {}
    for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
        values = [
            record.get("usage", {}).get(key)
            for record in (existing, retry)
            if record.get("usage", {}).get(key) is not None
        ]
        combined[key] = sum(values) if values else None
    return combined


def _merge_secondary_retry(
    existing: Optional[Dict[str, Any]],
    retry: Dict[str, Any],
) -> Dict[str, Any]:
    if not existing:
        return {
            **retry,
            "schema_version": ATOMIC_EVALUATION_SCHEMA_VERSION,
            "repair": {
                "previous_status": "missing",
                "previous_attempt_count": 0,
                "retry_attempt_count": int(retry.get("attempt_count") or 0),
            },
        }

    previous_attempts = [dict(attempt) for attempt in existing.get("attempts", [])]
    previous_count = int(existing.get("attempt_count") or len(previous_attempts))
    retry_attempts: List[Dict[str, Any]] = []
    for local_number, attempt in enumerate(retry.get("attempts", []), start=1):
        retry_attempts.append(
            {
                **attempt,
                "repair_attempt_number": local_number,
                "attempt_number": previous_count + local_number,
            }
        )
    return {
        **retry,
        "schema_version": ATOMIC_EVALUATION_SCHEMA_VERSION,
        "usage": _combined_usage(existing, retry),
        "attempt_count": previous_count + len(retry_attempts),
        "attempts": previous_attempts + retry_attempts,
        "latency_seconds": round(
            float(existing.get("latency_seconds") or 0)
            + float(retry.get("latency_seconds") or 0),
            4,
        ),
        "repair": {
            "previous_status": existing.get("status"),
            "previous_attempt_count": previous_count,
            "retry_attempt_count": len(retry_attempts),
        },
    }


def retry_failed_secondary_claims(
    primary_records: Iterable[Dict[str, Any]],
    secondary_records: Iterable[Dict[str, Any]],
    *,
    judge_provider: str,
    judge_model: str,
    max_output_tokens: int = 2400,
    settings: Optional[Dict[str, Any]] = None,
    max_attempts: int = 3,
    retry_delay_seconds: float = 1.0,
    provider_builder: Callable[[str, str], Any] = _default_provider_builder,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    primary = list(primary_records)
    existing_secondary = list(secondary_records)
    existing_by_run = {
        str((record.get("subject") or {}).get("run_id")): record
        for record in existing_secondary
    }
    retry_primary: List[Dict[str, Any]] = []
    retried_run_ids: List[str] = []
    for record in primary:
        if record.get("status") != "parsed":
            continue
        run_id = str((record.get("subject") or {}).get("run_id") or "")
        previous = existing_by_run.get(run_id)
        if previous and previous.get("status") == "parsed":
            continue
        retry_primary.append(record)
        retried_run_ids.append(run_id)

    if not retry_primary:
        return existing_secondary, [], []

    retry_records, retry_prompts = judge_existing_claims(
        retry_primary,
        judge_provider=judge_provider,
        judge_model=judge_model,
        max_output_tokens=max_output_tokens,
        settings=settings,
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay_seconds,
        provider_builder=provider_builder,
    )
    retry_by_run = {
        str((record.get("subject") or {}).get("run_id")): record
        for record in retry_records
    }
    merged: List[Dict[str, Any]] = []
    primary_run_ids = set()
    for record in primary:
        if record.get("status") != "parsed":
            continue
        run_id = str((record.get("subject") or {}).get("run_id") or "")
        primary_run_ids.add(run_id)
        if run_id in retry_by_run:
            merged.append(
                _merge_secondary_retry(
                    existing_by_run.get(run_id),
                    retry_by_run[run_id],
                )
            )
        elif run_id in existing_by_run:
            merged.append(existing_by_run[run_id])

    merged.extend(
        record
        for record in existing_secondary
        if str((record.get("subject") or {}).get("run_id")) not in primary_run_ids
    )

    previous_attempts_by_run = {
        run_id: int((existing_by_run.get(run_id) or {}).get("attempt_count") or 0)
        for run_id in retried_run_ids
    }
    adjusted_prompts: List[Dict[str, Any]] = []
    for prompt in retry_prompts:
        run_id = str(prompt.get("subject_run_id") or "")
        local_number = int(prompt.get("attempt_number") or 0)
        adjusted_prompts.append(
            {
                **prompt,
                "repair_attempt_number": local_number,
                "attempt_number": previous_attempts_by_run.get(run_id, 0)
                + local_number,
            }
        )
    return merged, adjusted_prompts, retried_run_ids


def build_atomic_consensus(
    primary_records: Iterable[Dict[str, Any]],
    secondary_records: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    primary = list(primary_records)
    secondary_by_run = {
        str((record.get("subject") or {}).get("run_id")): record
        for record in secondary_records
    }
    output: List[Dict[str, Any]] = []
    for primary_record in primary:
        subject = primary_record.get("subject") or {}
        run_id = str(subject.get("run_id") or "")
        secondary_record = secondary_by_run.get(run_id)
        if primary_record.get("status") != "parsed" or not secondary_record:
            output.append(
                {
                    "schema_version": ATOMIC_EVALUATION_SCHEMA_VERSION,
                    "subject": subject,
                    "status": "error",
                    "claims": [],
                    "primary_judge": primary_record.get("judge") or {},
                    "secondary_judge": (
                        (secondary_record or {}).get("judge") or {}
                    ),
                    "error": "Both judges must parse successfully for consensus",
                }
            )
            continue
        if secondary_record.get("status") != "parsed":
            output.append(
                {
                    "schema_version": ATOMIC_EVALUATION_SCHEMA_VERSION,
                    "subject": subject,
                    "status": "error",
                    "claims": [],
                    "primary_judge": primary_record.get("judge") or {},
                    "secondary_judge": secondary_record.get("judge") or {},
                    "error": secondary_record.get("error")
                    or "Secondary judge did not parse",
                }
            )
            continue

        secondary_claims = {
            str(claim["claim_id"]): claim
            for claim in secondary_record.get("claims") or []
        }
        consensus_claims: List[Dict[str, Any]] = []
        missing: List[str] = []
        for primary_claim in primary_record.get("claims") or []:
            claim_id = str(primary_claim["claim_id"])
            secondary_claim = secondary_claims.get(claim_id)
            if not secondary_claim:
                missing.append(claim_id)
                continue
            primary_support = primary_claim["support_status"]
            secondary_support = secondary_claim["support_status"]
            primary_type = primary_claim["hallucination_type"]
            secondary_type = secondary_claim["hallucination_type"]
            primary_unsupported = primary_support in UNSUPPORTED_LABELS
            secondary_unsupported = secondary_support in UNSUPPORTED_LABELS
            if primary_support == secondary_support == "NOT_FACTUAL":
                support_consensus = "EXCLUDED_NOT_FACTUAL"
            elif primary_support == "NOT_FACTUAL" or secondary_support == "NOT_FACTUAL":
                support_consensus = "UNCERTAIN"
            elif primary_unsupported and secondary_unsupported:
                support_consensus = "CONSENSUS_UNSUPPORTED"
            elif primary_unsupported or secondary_unsupported:
                support_consensus = "UNCERTAIN"
            else:
                support_consensus = "CONSENSUS_SUPPORTED"

            primary_citation = primary_claim["citation_status"]
            secondary_citation = secondary_claim["citation_status"]
            citation_consensus = (
                primary_citation
                if primary_citation == secondary_citation
                else "UNCERTAIN"
            )
            if support_consensus == "CONSENSUS_UNSUPPORTED":
                hallucination_type_consensus = (
                    primary_type
                    if primary_type == secondary_type
                    else "UNCERTAIN_TYPE"
                )
            elif support_consensus == "UNCERTAIN" and (
                primary_unsupported or secondary_unsupported
            ):
                hallucination_type_consensus = "UNCERTAIN_TYPE"
            else:
                hallucination_type_consensus = "NOT_APPLICABLE"
            consensus_claims.append(
                {
                    "claim_id": claim_id,
                    "claim": primary_claim["claim"],
                    "cited_document_ids": list(
                        primary_claim.get("cited_document_ids") or []
                    ),
                    "primary_support_status": primary_support,
                    "secondary_support_status": secondary_support,
                    "support_exact_match": primary_support == secondary_support,
                    "support_binary_match": (
                        primary_unsupported == secondary_unsupported
                    ),
                    "support_consensus": support_consensus,
                    "possible_unsupported": (
                        primary_unsupported or secondary_unsupported
                    ),
                    "primary_hallucination_type": primary_type,
                    "secondary_hallucination_type": secondary_type,
                    "hallucination_type_exact_match": primary_type == secondary_type,
                    "hallucination_type_consensus": hallucination_type_consensus,
                    "possible_hallucination_types": sorted(
                        {
                            value
                            for value in (primary_type, secondary_type)
                            if value != "NONE"
                        }
                    ),
                    "primary_citation_status": primary_citation,
                    "secondary_citation_status": secondary_citation,
                    "citation_exact_match": primary_citation == secondary_citation,
                    "citation_consensus": citation_consensus,
                    "primary_rationale": primary_claim.get("rationale") or "",
                    "secondary_rationale": secondary_claim.get("rationale") or "",
                }
            )
        if missing:
            output.append(
                {
                    "schema_version": ATOMIC_EVALUATION_SCHEMA_VERSION,
                    "subject": subject,
                    "status": "error",
                    "claims": [],
                    "primary_judge": primary_record.get("judge") or {},
                    "secondary_judge": secondary_record.get("judge") or {},
                    "error": "Secondary judgment omitted claims: " + ", ".join(missing),
                }
            )
            continue
        output.append(
            {
                "schema_version": ATOMIC_EVALUATION_SCHEMA_VERSION,
                "subject": subject,
                "status": "consensus_computed",
                "claims": consensus_claims,
                "primary_judge": primary_record.get("judge") or {},
                "secondary_judge": secondary_record.get("judge") or {},
                "error": None,
            }
        )
    return output


def _safe_rate(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator / denominator, 4) if denominator else None


def _safe_mean(values: Iterable[float]) -> Optional[float]:
    materialized = list(values)
    return round(sum(materialized) / len(materialized), 4) if materialized else None


def _paired_bootstrap_mean_ci(
    values: Iterable[float],
    *,
    seed_material: str,
    cluster_ids: Optional[Iterable[str]] = None,
    samples: int = 2000,
) -> Optional[List[float]]:
    materialized = list(values)
    if not materialized:
        return None
    if len(materialized) == 1:
        value = round(float(materialized[0]), 4)
        return [value, value]
    seed = int.from_bytes(
        hashlib.sha256(seed_material.encode("utf-8")).digest()[:8],
        byteorder="big",
    )
    rng = random.Random(seed)
    materialized_cluster_ids = list(cluster_ids or [])
    if materialized_cluster_ids:
        if len(materialized_cluster_ids) != len(materialized):
            raise ValueError("Bootstrap cluster IDs must align with the paired values")
        grouped: Dict[str, List[float]] = defaultdict(list)
        for cluster_id, value in zip(materialized_cluster_ids, materialized):
            grouped[str(cluster_id)].append(value)
        cluster_names = sorted(grouped)
        cluster_count = len(cluster_names)
        means = []
        for _ in range(samples):
            sampled_values: List[float] = []
            for _ in range(cluster_count):
                sampled_values.extend(
                    grouped[cluster_names[rng.randrange(cluster_count)]]
                )
            means.append(sum(sampled_values) / len(sampled_values))
        means.sort()
    else:
        count = len(materialized)
        means = sorted(
            sum(materialized[rng.randrange(count)] for _ in range(count)) / count
            for _ in range(samples)
        )
    lower = means[int(0.025 * (samples - 1))]
    upper = means[int(0.975 * (samples - 1))]
    return [round(lower, 4), round(upper, 4)]


def _judge_usage_summary(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    materialized = list(records)
    usage_keys = ("input_tokens", "output_tokens", "reasoning_tokens")
    usage: Dict[str, Optional[int]] = {}
    for key in usage_keys:
        known = [
            record.get("usage", {}).get(key)
            for record in materialized
            if record.get("usage", {}).get(key) is not None
        ]
        usage[key] = sum(known) if known else None
    return {
        "responses": len(materialized),
        "parsed_responses": sum(
            record.get("status") == "parsed" for record in materialized
        ),
        "api_calls": sum(int(record.get("attempt_count") or 0) for record in materialized),
        "usage": usage,
        "latency_seconds_total": round(
            sum(float(record.get("latency_seconds") or 0) for record in materialized),
            4,
        ),
    }


def _consensus_bucket(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    materialized = list(records)
    completed = [
        record
        for record in materialized
        if record.get("status") == "consensus_computed"
    ]
    claims = [claim for record in completed for claim in record.get("claims", [])]
    evaluable = [
        claim
        for claim in claims
        if claim.get("support_consensus") != "EXCLUDED_NOT_FACTUAL"
    ]
    consensus_unsupported = [
        claim
        for claim in evaluable
        if claim.get("support_consensus") == "CONSENSUS_UNSUPPORTED"
    ]
    consensus_supported = [
        claim
        for claim in evaluable
        if claim.get("support_consensus") == "CONSENSUS_SUPPORTED"
    ]
    possible_unsupported = [
        claim for claim in evaluable if claim.get("possible_unsupported")
    ]
    uncertain = [
        claim
        for claim in evaluable
        if claim.get("support_consensus") == "UNCERTAIN"
    ]
    citation_evaluable = [
        claim
        for claim in evaluable
        if claim.get("citation_consensus") != "NOT_APPLICABLE"
    ]
    cited = [
        claim
        for claim in citation_evaluable
        if claim.get("citation_consensus") in {"SUPPORTED", "UNSUPPORTED"}
    ]
    response_consensus = sum(
        any(
            claim.get("support_consensus") == "CONSENSUS_UNSUPPORTED"
            for claim in record.get("claims", [])
        )
        for record in completed
    )
    response_possible = sum(
        any(claim.get("possible_unsupported") for claim in record.get("claims", []))
        for record in completed
    )
    response_uncertain = sum(
        any(
            claim.get("support_consensus") == "UNCERTAIN"
            for claim in record.get("claims", [])
        )
        for record in completed
    )
    response_evaluable_counts = [
        sum(
            claim.get("support_consensus") != "EXCLUDED_NOT_FACTUAL"
            for claim in record.get("claims", [])
        )
        for record in completed
    ]
    response_supported_counts = [
        sum(
            claim.get("support_consensus") == "CONSENSUS_SUPPORTED"
            for claim in record.get("claims", [])
        )
        for record in completed
    ]
    response_consensus_rates: List[float] = []
    response_possible_rates: List[float] = []
    for record in completed:
        metrics = _consensus_response_metrics(record)
        if metrics["consensus_unsupported_claim_rate"] is not None:
            response_consensus_rates.append(
                metrics["consensus_unsupported_claim_rate"]
            )
        if metrics["possible_unsupported_claim_rate"] is not None:
            response_possible_rates.append(metrics["possible_unsupported_claim_rate"])

    consensus_type_counts = Counter(
        str(claim.get("hallucination_type_consensus") or "UNCERTAIN_TYPE")
        for claim in consensus_unsupported
    )
    possible_type_counts = Counter(
        hallucination_type
        for claim in possible_unsupported
        for hallucination_type in claim.get("possible_hallucination_types", [])
    )
    return {
        "responses": len(materialized),
        "consensus_responses": len(completed),
        "consensus_parse_rate": _safe_rate(len(completed), len(materialized)),
        "extracted_claims": len(claims),
        "evaluable_claims": len(evaluable),
        "excluded_not_factual_claims": len(claims) - len(evaluable),
        "consensus_supported_claims": len(consensus_supported),
        "consensus_supported_claim_rate": _safe_rate(
            len(consensus_supported), len(evaluable)
        ),
        "mean_evaluable_claims_per_response": _safe_mean(response_evaluable_counts),
        "mean_consensus_supported_claims_per_response": _safe_mean(
            response_supported_counts
        ),
        "consensus_unsupported_claims": len(consensus_unsupported),
        "consensus_unsupported_claim_rate": _safe_rate(
            len(consensus_unsupported), len(evaluable)
        ),
        "possible_unsupported_claims": len(possible_unsupported),
        "possible_unsupported_claim_rate": _safe_rate(
            len(possible_unsupported), len(evaluable)
        ),
        "mean_response_consensus_unsupported_claim_rate": _safe_mean(
            response_consensus_rates
        ),
        "mean_response_possible_unsupported_claim_rate": _safe_mean(
            response_possible_rates
        ),
        "consensus_hallucination_type_counts": dict(
            sorted(consensus_type_counts.items())
        ),
        "possible_hallucination_type_counts": dict(
            sorted(possible_type_counts.items())
        ),
        "uncertain_claims": len(uncertain),
        "uncertain_claim_rate": _safe_rate(len(uncertain), len(evaluable)),
        "responses_with_consensus_unsupported_claim": response_consensus,
        "consensus_response_hallucination_rate": _safe_rate(
            response_consensus, len(completed)
        ),
        "responses_with_possible_unsupported_claim": response_possible,
        "possible_response_hallucination_rate": _safe_rate(
            response_possible, len(completed)
        ),
        "responses_with_uncertain_claim": response_uncertain,
        "uncertain_response_rate": _safe_rate(response_uncertain, len(completed)),
        "support_label_exact_agreement": _safe_rate(
            sum(bool(claim.get("support_exact_match")) for claim in claims),
            len(claims),
        ),
        "support_binary_agreement": _safe_rate(
            sum(bool(claim.get("support_binary_match")) for claim in claims),
            len(claims),
        ),
        "citation_label_exact_agreement": _safe_rate(
            sum(bool(claim.get("citation_exact_match")) for claim in claims),
            len(claims),
        ),
        "consensus_claim_citation_coverage": _safe_rate(
            len(cited), len(citation_evaluable)
        ),
        "consensus_citation_support_rate": _safe_rate(
            sum(claim.get("citation_consensus") == "SUPPORTED" for claim in cited),
            len(cited),
        ),
    }


def _consensus_response_metrics(
    record: Dict[str, Any],
) -> Dict[str, Any]:
    evaluable = [
        claim
        for claim in record.get("claims", [])
        if claim.get("support_consensus") != "EXCLUDED_NOT_FACTUAL"
    ]
    consensus_count = sum(
        claim.get("support_consensus") == "CONSENSUS_UNSUPPORTED"
        for claim in evaluable
    )
    possible_count = sum(
        bool(claim.get("possible_unsupported")) for claim in evaluable
    )
    supported_count = sum(
        claim.get("support_consensus") == "CONSENSUS_SUPPORTED"
        for claim in evaluable
    )
    return {
        "consensus_unsupported_claim_rate": _safe_rate(
            consensus_count, len(evaluable)
        ),
        "possible_unsupported_claim_rate": _safe_rate(
            possible_count, len(evaluable)
        ),
        "has_consensus_unsupported": int(consensus_count > 0),
        "has_possible_unsupported": int(possible_count > 0),
        "evaluable_claims": len(evaluable),
        "consensus_supported_claims": supported_count,
    }


def _consensus_baseline_contrasts(
    records: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    cells: Dict[Tuple[str, str], Dict[str, Dict[str, Any]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for record in records:
        if record.get("status") != "consensus_computed":
            continue
        subject = record.get("subject") or {}
        model = subject.get("model") or {}
        strategy = subject.get("strategy") or {}
        model_key = f"{model.get('provider')}:{model.get('name')}"
        strategy_key = f"{strategy.get('name')}@{strategy.get('version')}"
        task_id = str(subject.get("task_id") or subject.get("run_id"))
        cells[(model_key, strategy_key)][task_id] = record

    output: Dict[str, Any] = {}
    for model_key in sorted({key[0] for key in cells}):
        strategy_keys = sorted(key[1] for key in cells if key[0] == model_key)
        baseline_keys = [key for key in strategy_keys if key.startswith("baseline@")]
        if len(baseline_keys) != 1:
            continue
        baseline_key = baseline_keys[0]
        baseline = cells[(model_key, baseline_key)]
        contrasts: Dict[str, Any] = {}
        for strategy_key in strategy_keys:
            if strategy_key == baseline_key:
                continue
            treatment = cells[(model_key, strategy_key)]
            paired = sorted(set(baseline) & set(treatment))
            consensus_rate_deltas: List[float] = []
            possible_rate_deltas: List[float] = []
            consensus_response_deltas: List[int] = []
            possible_response_deltas: List[int] = []
            evaluable_claim_deltas: List[int] = []
            supported_claim_deltas: List[int] = []
            consensus_rate_clusters: List[str] = []
            possible_rate_clusters: List[str] = []
            supported_claim_clusters: List[str] = []
            for task_id in paired:
                base_metrics = _consensus_response_metrics(baseline[task_id])
                treatment_metrics = _consensus_response_metrics(treatment[task_id])
                subject = treatment[task_id].get("subject") or {}
                cluster_id = str(subject.get("source_item_id") or task_id)
                if (
                    base_metrics["consensus_unsupported_claim_rate"] is not None
                    and treatment_metrics["consensus_unsupported_claim_rate"] is not None
                ):
                    consensus_rate_deltas.append(
                        treatment_metrics["consensus_unsupported_claim_rate"]
                        - base_metrics["consensus_unsupported_claim_rate"]
                    )
                    consensus_rate_clusters.append(cluster_id)
                if (
                    base_metrics["possible_unsupported_claim_rate"] is not None
                    and treatment_metrics["possible_unsupported_claim_rate"] is not None
                ):
                    possible_rate_deltas.append(
                        treatment_metrics["possible_unsupported_claim_rate"]
                        - base_metrics["possible_unsupported_claim_rate"]
                    )
                    possible_rate_clusters.append(cluster_id)
                consensus_response_deltas.append(
                    treatment_metrics["has_consensus_unsupported"]
                    - base_metrics["has_consensus_unsupported"]
                )
                possible_response_deltas.append(
                    treatment_metrics["has_possible_unsupported"]
                    - base_metrics["has_possible_unsupported"]
                )
                evaluable_claim_deltas.append(
                    treatment_metrics["evaluable_claims"]
                    - base_metrics["evaluable_claims"]
                )
                supported_claim_deltas.append(
                    treatment_metrics["consensus_supported_claims"]
                    - base_metrics["consensus_supported_claims"]
                )
                supported_claim_clusters.append(cluster_id)
            contrasts[strategy_key] = {
                "reference": baseline_key,
                "paired_responses": len(paired),
                "mean_paired_consensus_unsupported_claim_rate_difference": _safe_mean(
                    consensus_rate_deltas
                ),
                "mean_paired_possible_unsupported_claim_rate_difference": _safe_mean(
                    possible_rate_deltas
                ),
                "mean_paired_consensus_response_hallucination_difference": _safe_mean(
                    consensus_response_deltas
                ),
                "mean_paired_possible_response_hallucination_difference": _safe_mean(
                    possible_response_deltas
                ),
                "mean_paired_evaluable_claim_count_difference": _safe_mean(
                    evaluable_claim_deltas
                ),
                "mean_paired_consensus_supported_claim_count_difference": _safe_mean(
                    supported_claim_deltas
                ),
                "paired_consensus_unsupported_claim_rate_difference_95ci": _paired_bootstrap_mean_ci(
                    consensus_rate_deltas,
                    seed_material=(
                        f"{model_key}|{strategy_key}|consensus_unsupported_rate"
                    ),
                    cluster_ids=consensus_rate_clusters,
                ),
                "paired_possible_unsupported_claim_rate_difference_95ci": _paired_bootstrap_mean_ci(
                    possible_rate_deltas,
                    seed_material=(
                        f"{model_key}|{strategy_key}|possible_unsupported_rate"
                    ),
                    cluster_ids=possible_rate_clusters,
                ),
                "paired_consensus_supported_claim_count_difference_95ci": _paired_bootstrap_mean_ci(
                    supported_claim_deltas,
                    seed_material=(
                        f"{model_key}|{strategy_key}|consensus_supported_count"
                    ),
                    cluster_ids=supported_claim_clusters,
                ),
                "bootstrap_cluster": "source_item_id_or_task_id",
                "direction_note": (
                    "Negative differences favour the named strategy over baseline."
                ),
            }
        output[model_key] = contrasts
    return output


def summarize_atomic_consensus(
    consensus_records: Iterable[Dict[str, Any]],
    *,
    primary_records: Optional[Iterable[Dict[str, Any]]] = None,
    secondary_records: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    materialized = list(consensus_records)
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    grouped_difficulty: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in materialized:
        condition = _condition_key(record)
        difficulty = str(
            (record.get("subject") or {}).get("difficulty_category") or "unspecified"
        )
        grouped[condition].append(record)
        grouped_difficulty[condition][difficulty].append(record)
    difficulty_names = sorted(
        {
            str((record.get("subject") or {}).get("difficulty_category") or "unspecified")
            for record in materialized
        }
    )
    return {
        "atomic_evaluation_schema_version": ATOMIC_EVALUATION_SCHEMA_VERSION,
        "evaluation_mode": "dual_judge_consensus",
        "responses": len(materialized),
        "interpretation_note": (
            "A primary model extracts and labels subject-matter claims. A secondary "
            "model independently labels the same fixed claims. Consensus unsupported "
            "means both judges flag a claim; possible unsupported means either judge "
            "flags it. Disagreements remain uncertain. This is automated, AI-assisted "
            "measurement and is not human-validated ground truth."
        ),
        "conditions": {
            condition: {
                **_consensus_bucket(records),
                "by_difficulty": {
                    difficulty: _consensus_bucket(difficulty_records)
                    for difficulty, difficulty_records in sorted(
                        grouped_difficulty[condition].items()
                    )
                },
            }
            for condition, records in sorted(grouped.items())
        },
        "paired_strategy_effects_vs_baseline": _consensus_baseline_contrasts(
            materialized
        ),
        "paired_strategy_effects_vs_baseline_by_difficulty": {
            difficulty: _consensus_baseline_contrasts(
                record
                for record in materialized
                if str(
                    (record.get("subject") or {}).get("difficulty_category")
                    or "unspecified"
                )
                == difficulty
            )
            for difficulty in difficulty_names
        },
        "primary_judge_usage": _judge_usage_summary(primary_records or []),
        "secondary_judge_usage": _judge_usage_summary(secondary_records or []),
    }


def render_atomic_consensus_report(summary: Dict[str, Any]) -> str:
    fmt = lambda value: "n/a" if value is None else f"{100 * value:.1f}%"
    lines = [
        "# Automated dual-judge atomic evaluation",
        "",
        "## Consensus results",
        "",
        "| Condition | Responses | Both parsed | Claims | Consensus unsupported | Possible unsupported | Uncertain | Consensus response rate | Possible response rate | Binary judge agreement |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for condition, values in summary.get("conditions", {}).items():
        lines.append(
            f"| {condition} | {values['responses']} | "
            f"{fmt(values['consensus_parse_rate'])} | {values['evaluable_claims']} | "
            f"{values['consensus_unsupported_claims']} "
            f"({fmt(values['consensus_unsupported_claim_rate'])}) | "
            f"{values['possible_unsupported_claims']} "
            f"({fmt(values['possible_unsupported_claim_rate'])}) | "
            f"{values['uncertain_claims']} ({fmt(values['uncertain_claim_rate'])}) | "
            f"{fmt(values['consensus_response_hallucination_rate'])} | "
            f"{fmt(values['possible_response_hallucination_rate'])} | "
            f"{fmt(values['support_binary_agreement'])} |"
        )
    lines.extend(
        [
            "",
            "## Supported-content yield and claim exposure",
            "",
            "| Condition | Mean factual claims/response | Mean consensus-supported claims/response | Consensus-supported claim rate | Mean per-response consensus unsupported rate | Mean per-response possible unsupported rate |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for condition, values in summary.get("conditions", {}).items():
        lines.append(
            f"| {condition} | {values['mean_evaluable_claims_per_response']} | "
            f"{values['mean_consensus_supported_claims_per_response']} | "
            f"{fmt(values['consensus_supported_claim_rate'])} | "
            f"{fmt(values['mean_response_consensus_unsupported_claim_rate'])} | "
            f"{fmt(values['mean_response_possible_unsupported_claim_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Consensus hallucination types",
            "",
            "Counts include only claims both judges marked unsupported. A type is "
            "reported as `UNCERTAIN_TYPE` when the judges agree that a claim is "
            "unsupported but disagree on the dominant error mechanism.",
            "",
            "| Condition | Unsupported addition | Source contradiction | Evidence overstatement | Entity/context confusion | Other | Uncertain type |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for condition, values in summary.get("conditions", {}).items():
        counts = values.get("consensus_hallucination_type_counts", {})
        lines.append(
            f"| {condition} | {counts.get('UNSUPPORTED_ADDITION', 0)} | "
            f"{counts.get('SOURCE_CONTRADICTION', 0)} | "
            f"{counts.get('EVIDENCE_OVERSTATEMENT', 0)} | "
            f"{counts.get('ENTITY_CONTEXT_CONFUSION', 0)} | "
            f"{counts.get('OTHER', 0)} | {counts.get('UNCERTAIN_TYPE', 0)} |"
        )
    lines.extend(
        [
            "",
            "## Consensus results by difficulty",
            "",
            "| Condition | Difficulty | Responses | Both parsed | Claims | Consensus unsupported | Possible unsupported | Uncertain | Consensus response rate | Possible response rate |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for condition, values in summary.get("conditions", {}).items():
        for difficulty, difficulty_values in values.get("by_difficulty", {}).items():
            lines.append(
                f"| {condition} | {difficulty} | {difficulty_values['responses']} | "
                f"{fmt(difficulty_values['consensus_parse_rate'])} | "
                f"{difficulty_values['evaluable_claims']} | "
                f"{difficulty_values['consensus_unsupported_claims']} "
                f"({fmt(difficulty_values['consensus_unsupported_claim_rate'])}) | "
                f"{difficulty_values['possible_unsupported_claims']} "
                f"({fmt(difficulty_values['possible_unsupported_claim_rate'])}) | "
                f"{difficulty_values['uncertain_claims']} "
                f"({fmt(difficulty_values['uncertain_claim_rate'])}) | "
                f"{fmt(difficulty_values['consensus_response_hallucination_rate'])} | "
                f"{fmt(difficulty_values['possible_response_hallucination_rate'])} |"
            )
    lines.extend(
        [
            "",
            "Consensus unsupported requires both judges to flag a claim. Possible "
            "unsupported includes every claim flagged by either judge. Claims on "
            "which the judges disagree remain uncertain.",
            "",
            "## Citation and exact-label agreement",
            "",
            "| Condition | Exact support agreement | Exact citation agreement | Claim citation coverage | Citation support among agreed citations |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for condition, values in summary.get("conditions", {}).items():
        lines.append(
            f"| {condition} | {fmt(values['support_label_exact_agreement'])} | "
            f"{fmt(values['citation_label_exact_agreement'])} | "
            f"{fmt(values['consensus_claim_citation_coverage'])} | "
            f"{fmt(values['consensus_citation_support_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Judge usage",
            "",
            "| Judge | Responses | Parsed | API calls | Input tokens | Output tokens | Reasoning tokens | Total latency (s) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label, key in (
        ("Primary", "primary_judge_usage"),
        ("Secondary", "secondary_judge_usage"),
    ):
        values = summary.get(key, {})
        usage = values.get("usage", {})
        lines.append(
            f"| {label} | {values.get('responses', 0)} | "
            f"{values.get('parsed_responses', 0)} | {values.get('api_calls', 0)} | "
            f"{usage.get('input_tokens') or 0} | {usage.get('output_tokens') or 0} | "
            f"{usage.get('reasoning_tokens') or 0} | "
            f"{values.get('latency_seconds_total', 0)} |"
        )
    contrasts = summary.get("paired_strategy_effects_vs_baseline", {})
    if contrasts:
        lines.extend(
            [
                "",
                "## Paired strategy effects versus baseline",
                "",
                "Negative values favour the named strategy.",
                "",
                "| Model | Strategy | Paired responses | Consensus claim-rate difference | Possible claim-rate difference | Consensus response difference | Possible response difference | Supported-claim difference | Factual-claim difference |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for model, model_contrasts in contrasts.items():
            for strategy, values in model_contrasts.items():
                def delta(name: str) -> str:
                    value = values.get(name)
                    return "n/a" if value is None else f"{value:+.3f}"

                def delta_ci(name: str, ci_name: str) -> str:
                    value = values.get(name)
                    interval = values.get(ci_name)
                    if value is None:
                        return "n/a"
                    if not interval:
                        return f"{value:+.3f}"
                    return (
                        f"{value:+.3f} "
                        f"[{interval[0]:+.3f}, {interval[1]:+.3f}]"
                    )

                lines.append(
                    f"| {model} | {strategy} | {values['paired_responses']} | "
                    f"{delta_ci('mean_paired_consensus_unsupported_claim_rate_difference', 'paired_consensus_unsupported_claim_rate_difference_95ci')} | "
                    f"{delta_ci('mean_paired_possible_unsupported_claim_rate_difference', 'paired_possible_unsupported_claim_rate_difference_95ci')} | "
                    f"{delta('mean_paired_consensus_response_hallucination_difference')} | "
                    f"{delta('mean_paired_possible_response_hallucination_difference')} | "
                    f"{delta('mean_paired_consensus_supported_claim_count_difference')} | "
                    f"{delta('mean_paired_evaluable_claim_count_difference')} |"
                )
    lines.extend(
        [
            "",
            "## Interpretation limit",
            "",
            summary.get("interpretation_note", ""),
            "",
        ]
    )
    return "\n".join(lines)


def _summary_bucket(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    materialized = list(records)
    parsed = [record for record in materialized if record.get("status") == "parsed"]
    claims = [claim for record in parsed for claim in record.get("claims", [])]
    factual = [claim for claim in claims if claim["support_status"] != "NOT_FACTUAL"]
    unsupported = [
        claim for claim in factual if claim["support_status"] in UNSUPPORTED_LABELS
    ]
    responses_with_unsupported = sum(
        any(
            claim["support_status"] in UNSUPPORTED_LABELS
            for claim in record.get("claims", [])
        )
        for record in parsed
    )
    citation_supported = sum(
        claim["citation_status"] == "SUPPORTED" for claim in factual
    )
    citation_unsupported = sum(
        claim["citation_status"] == "UNSUPPORTED" for claim in factual
    )
    no_citation = sum(claim["citation_status"] == "NO_CITATION" for claim in factual)
    return {
        "responses": len(materialized),
        "parsed_responses": len(parsed),
        "judge_parse_rate": _safe_rate(len(parsed), len(materialized)),
        "atomic_claims": len(claims),
        "factual_claims": len(factual),
        "support_statuses": dict(Counter(claim["support_status"] for claim in claims)),
        "unsupported_atomic_claims": len(unsupported),
        "unsupported_atomic_claim_rate": _safe_rate(len(unsupported), len(factual)),
        "responses_with_unsupported_claim": responses_with_unsupported,
        "response_hallucination_rate": _safe_rate(
            responses_with_unsupported, len(parsed)
        ),
        "citation_supported_claims": citation_supported,
        "citation_unsupported_claims": citation_unsupported,
        "claims_without_citation": no_citation,
        "citation_support_rate": _safe_rate(
            citation_supported, citation_supported + citation_unsupported
        ),
    }


def _condition_key(record: Dict[str, Any]) -> str:
    subject = record.get("subject") or {}
    model = subject.get("model") or {}
    strategy = subject.get("strategy") or {}
    return (
        f"{model.get('provider')}:{model.get('name')} | "
        f"{strategy.get('name')}@{strategy.get('version')}"
    )


def _response_unsupported_metrics(record: Dict[str, Any]) -> Tuple[Optional[float], int]:
    factual = [
        claim
        for claim in record.get("claims", [])
        if claim.get("support_status") != "NOT_FACTUAL"
    ]
    unsupported = sum(
        claim.get("support_status") in UNSUPPORTED_LABELS for claim in factual
    )
    return _safe_rate(unsupported, len(factual)), int(unsupported > 0)


def _baseline_contrasts(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    cells: Dict[Tuple[str, str], Dict[str, Dict[str, Any]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for record in records:
        if record.get("status") != "parsed":
            continue
        subject = record.get("subject") or {}
        model = subject.get("model") or {}
        strategy = subject.get("strategy") or {}
        model_key = f"{model.get('provider')}:{model.get('name')}"
        strategy_key = f"{strategy.get('name')}@{strategy.get('version')}"
        task_id = str(subject.get("task_id") or subject.get("run_id"))
        cells[(model_key, strategy_key)][task_id] = record

    output: Dict[str, Any] = {}
    model_keys = sorted({model_key for model_key, _ in cells})
    for model_key in model_keys:
        strategy_keys = sorted(
            strategy_key
            for candidate_model, strategy_key in cells
            if candidate_model == model_key
        )
        baseline_keys = [key for key in strategy_keys if key.startswith("baseline@")]
        if len(baseline_keys) != 1:
            continue
        baseline_key = baseline_keys[0]
        baseline = cells[(model_key, baseline_key)]
        contrasts: Dict[str, Any] = {}
        for strategy_key in strategy_keys:
            if strategy_key == baseline_key:
                continue
            treatment = cells[(model_key, strategy_key)]
            paired_task_ids = sorted(set(baseline) & set(treatment))
            rate_deltas: List[float] = []
            response_deltas: List[int] = []
            for task_id in paired_task_ids:
                baseline_rate, baseline_any = _response_unsupported_metrics(
                    baseline[task_id]
                )
                treatment_rate, treatment_any = _response_unsupported_metrics(
                    treatment[task_id]
                )
                if baseline_rate is not None and treatment_rate is not None:
                    rate_deltas.append(treatment_rate - baseline_rate)
                response_deltas.append(treatment_any - baseline_any)
            contrasts[strategy_key] = {
                "reference": baseline_key,
                "paired_responses": len(paired_task_ids),
                "mean_paired_unsupported_claim_rate_difference": _safe_mean(rate_deltas),
                "mean_paired_response_hallucination_difference": _safe_mean(
                    response_deltas
                ),
                "direction_note": (
                    "Negative differences favour the named strategy over baseline."
                ),
            }
        output[model_key] = contrasts
    return output


def summarize_atomic_judgments(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    materialized = list(records)
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    grouped_difficulty: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in materialized:
        condition = _condition_key(record)
        difficulty = str(
            (record.get("subject") or {}).get("difficulty_category") or "unspecified"
        )
        grouped[condition].append(record)
        grouped_difficulty[condition][difficulty].append(record)

    return {
        "atomic_evaluation_schema_version": ATOMIC_EVALUATION_SCHEMA_VERSION,
        "judged_responses": len(materialized),
        "interpretation_note": (
            "Atomic claim labels are produced by a source-only LLM judge. They are "
            "AI-assisted measurements and should be checked against the blinded "
            "review sample before final thesis reporting."
        ),
        "conditions": {
            condition: {
                **_summary_bucket(rows),
                "by_difficulty": {
                    difficulty: _summary_bucket(difficulty_rows)
                    for difficulty, difficulty_rows in sorted(
                        grouped_difficulty[condition].items()
                    )
                },
            }
            for condition, rows in sorted(grouped.items())
        },
        "paired_strategy_effects_vs_baseline": _baseline_contrasts(materialized),
    }


def render_atomic_report(summary: Dict[str, Any]) -> str:
    lines = [
        "# Atomic-claim factuality evaluation",
        "",
        "## Overall AI-assisted metrics",
        "",
        "| Condition | Responses | Judge parse rate | Factual claims | Unsupported claims | Unsupported claim rate | Responses with any unsupported claim | Citation support |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for condition, values in summary.get("conditions", {}).items():
        fmt = lambda value: "n/a" if value is None else f"{100 * value:.1f}%"
        lines.append(
            f"| {condition} | {values['responses']} | {fmt(values['judge_parse_rate'])} | "
            f"{values['factual_claims']} | {values['unsupported_atomic_claims']} | "
            f"{fmt(values['unsupported_atomic_claim_rate'])} | "
            f"{fmt(values['response_hallucination_rate'])} | "
            f"{fmt(values['citation_support_rate'])} |"
        )

    lines.extend(
        [
            "",
            "## Unsupported atomic-claim rate by difficulty",
            "",
            "| Condition | Difficulty | Responses | Factual claims | Unsupported claim rate |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for condition, values in summary.get("conditions", {}).items():
        for difficulty, difficulty_values in values.get("by_difficulty", {}).items():
            rate = difficulty_values["unsupported_atomic_claim_rate"]
            rendered_rate = "n/a" if rate is None else f"{100 * rate:.1f}%"
            lines.append(
                f"| {condition} | {difficulty} | {difficulty_values['responses']} | "
                f"{difficulty_values['factual_claims']} | {rendered_rate} |"
            )
    contrasts = summary.get("paired_strategy_effects_vs_baseline", {})
    if contrasts:
        lines.extend(
            [
                "",
                "## Paired strategy effects versus baseline",
                "",
                "Negative differences favour the named strategy. Each difference is "
                "calculated within the same model and task before averaging.",
                "",
                "| Model | Strategy | Paired responses | Unsupported-claim rate difference | Response-hallucination difference |",
                "|---|---|---:|---:|---:|",
            ]
        )
        for model, model_contrasts in contrasts.items():
            for strategy, values in model_contrasts.items():
                claim_delta = values[
                    "mean_paired_unsupported_claim_rate_difference"
                ]
                response_delta = values[
                    "mean_paired_response_hallucination_difference"
                ]
                claim_text = "n/a" if claim_delta is None else f"{claim_delta:+.3f}"
                response_text = (
                    "n/a" if response_delta is None else f"{response_delta:+.3f}"
                )
                lines.append(
                    f"| {model} | {strategy} | {values['paired_responses']} | "
                    f"{claim_text} | {response_text} |"
                )
    lines.extend(
        [
            "",
            "## Interpretation limit",
            "",
            summary.get("interpretation_note", ""),
            "",
        ]
    )
    return "\n".join(lines)


ATOMIC_REVIEW_FIELDS = [
    "review_id",
    "response_group_id",
    "task_prompt",
    "source_context",
    "response_text",
    "atomic_claim",
    "cited_document_ids",
    "reviewer_support_label",
    "reviewer_citation_label",
    "reviewer_notes",
]

ATOMIC_DISAGREEMENT_FIELDS = [
    "review_id",
    "response_group_id",
    "subject_run_id",
    "task_id",
    "difficulty_category",
    "model_provider",
    "model_name",
    "strategy_name",
    "strategy_version",
    "atomic_claim",
    "cited_document_ids",
    "automatic_support_label",
    "reviewer_support_label",
    "support_exact_match",
    "binary_unsupported_match",
    "automatic_citation_label",
    "reviewer_citation_label",
    "citation_exact_match",
    "task_prompt",
    "source_context",
    "response_text",
    "reviewer_notes",
]


def blinded_atomic_review_package(
    records: Iterable[Dict[str, Any]],
    seed: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    parsed = [record for record in records if record.get("status") == "parsed"]
    strata: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for record in parsed:
        subject = record.get("subject") or {}
        model = subject.get("model") or {}
        strategy = subject.get("strategy") or {}
        key = (
            f"{model.get('provider')}:{model.get('name')}",
            f"{strategy.get('name')}@{strategy.get('version')}",
            str(subject.get("difficulty_category") or "unspecified"),
        )
        strata[key].append(record)

    rng = random.Random(seed)
    selected: List[Dict[str, Any]] = []
    for key in sorted(strata):
        candidates = sorted(
            strata[key], key=lambda record: str((record.get("subject") or {}).get("run_id"))
        )
        selected.append(candidates[rng.randrange(len(candidates))])
    rng.shuffle(selected)

    rows: List[Dict[str, Any]] = []
    mapping_entries: Dict[str, Any] = {}
    review_index = 0
    for group_index, record in enumerate(selected, start=1):
        subject = record["subject"]
        response_group_id = f"review_response_{group_index:04d}"
        for claim in record.get("claims", []):
            review_index += 1
            review_id = f"atomic_review_{review_index:06d}"
            rows.append(
                {
                    "review_id": review_id,
                    "response_group_id": response_group_id,
                    "task_prompt": subject.get("task_prompt") or "",
                    "source_context": subject.get("source_context") or "",
                    "response_text": subject.get("response_text") or "",
                    "atomic_claim": claim.get("claim") or "",
                    "cited_document_ids": ", ".join(claim.get("cited_document_ids") or []),
                    "reviewer_support_label": "",
                    "reviewer_citation_label": "",
                    "reviewer_notes": "",
                }
            )
            mapping_entries[review_id] = {
                "subject_run_id": subject.get("run_id"),
                "task_id": subject.get("task_id"),
                "difficulty_category": subject.get("difficulty_category"),
                "model": subject.get("model"),
                "strategy": subject.get("strategy"),
                "automatic_support_label": claim.get("support_status"),
                "automatic_citation_label": claim.get("citation_status"),
            }

    mapping = {
        "atomic_review_mapping_schema_version": "1.0.0",
        "review_seed": seed,
        "sampling_method": "one_response_per_model_strategy_difficulty_cell",
        "selected_responses": len(selected),
        "review_claims": len(rows),
        "entries": mapping_entries,
    }
    return rows, mapping


def write_atomic_review_csv(path: str | Path, rows: Iterable[Dict[str, Any]]) -> None:
    materialized = list(rows)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ATOMIC_REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(materialized)


def _completed_atomic_annotations(
    annotations_path: str | Path,
    mapping_path: str | Path,
) -> List[Tuple[Dict[str, str], Dict[str, Any]]]:
    mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    if mapping.get("atomic_review_mapping_schema_version") != "1.0.0":
        raise ValueError("Unsupported atomic review mapping schema version")
    entries = mapping.get("entries") or {}
    if not isinstance(entries, dict) or not entries:
        raise ValueError("Atomic review mapping contains no entries")
    completed: List[Tuple[Dict[str, str], Dict[str, Any]]] = []
    seen_review_ids: set[str] = set()
    with Path(annotations_path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"review_id", "reviewer_support_label", "reviewer_citation_label"}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ValueError(
                "Atomic annotation file is missing columns: " + ", ".join(missing)
            )
        for line_number, row in enumerate(reader, start=2):
            review_id = str(row.get("review_id") or "").strip()
            support = str(row.get("reviewer_support_label") or "").strip().upper()
            citation = str(row.get("reviewer_citation_label") or "").strip().upper()
            if not support and not citation:
                continue
            if review_id in seen_review_ids:
                raise ValueError(f"Line {line_number}: duplicate review_id {review_id}")
            seen_review_ids.add(review_id)
            if review_id not in entries:
                raise ValueError(f"Line {line_number}: unknown review_id {review_id}")
            if support not in SUPPORT_LABELS:
                raise ValueError(f"Line {line_number}: invalid reviewer_support_label")
            if citation not in CITATION_LABELS:
                raise ValueError(f"Line {line_number}: invalid reviewer_citation_label")
            if (support == "NOT_FACTUAL") != (citation == "NOT_APPLICABLE"):
                raise ValueError(
                    f"Line {line_number}: NOT_APPLICABLE is required only for NOT_FACTUAL"
                )
            completed.append((row, entries[review_id]))
    if not completed:
        raise ValueError("Atomic annotation file contains zero completed rows")
    return completed


def compare_atomic_annotations(
    annotations_path: str | Path,
    mapping_path: str | Path,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    completed = _completed_atomic_annotations(annotations_path, mapping_path)

    exact_support = sum(
        row["reviewer_support_label"].strip().upper()
        == entry["automatic_support_label"]
        for row, entry in completed
    )
    exact_citation = sum(
        row["reviewer_citation_label"].strip().upper()
        == entry["automatic_citation_label"]
        for row, entry in completed
    )
    binary_unsupported = sum(
        (
            row["reviewer_support_label"].strip().upper() in UNSUPPORTED_LABELS
        )
        == (entry["automatic_support_label"] in UNSUPPORTED_LABELS)
        for row, entry in completed
    )
    binary_counts = Counter()
    support_confusion: Dict[str, Counter[str]] = defaultdict(Counter)
    citation_confusion: Dict[str, Counter[str]] = defaultdict(Counter)
    disagreements: List[Dict[str, Any]] = []

    for row, entry in completed:
        reviewer_support = row["reviewer_support_label"].strip().upper()
        reviewer_citation = row["reviewer_citation_label"].strip().upper()
        automatic_support = str(entry["automatic_support_label"]).upper()
        automatic_citation = str(entry["automatic_citation_label"]).upper()
        automatic_unsupported = automatic_support in UNSUPPORTED_LABELS
        reviewer_unsupported = reviewer_support in UNSUPPORTED_LABELS
        support_confusion[automatic_support][reviewer_support] += 1
        citation_confusion[automatic_citation][reviewer_citation] += 1
        if automatic_unsupported and reviewer_unsupported:
            binary_counts["true_positive"] += 1
        elif automatic_unsupported and not reviewer_unsupported:
            binary_counts["false_positive"] += 1
        elif not automatic_unsupported and reviewer_unsupported:
            binary_counts["false_negative"] += 1
        else:
            binary_counts["true_negative"] += 1

        support_match = automatic_support == reviewer_support
        citation_match = automatic_citation == reviewer_citation
        if support_match and citation_match:
            continue
        model = entry.get("model") or {}
        strategy = entry.get("strategy") or {}
        disagreements.append(
            {
                "review_id": str(row.get("review_id") or ""),
                "response_group_id": str(row.get("response_group_id") or ""),
                "subject_run_id": str(entry.get("subject_run_id") or ""),
                "task_id": str(entry.get("task_id") or ""),
                "difficulty_category": str(
                    entry.get("difficulty_category") or "unspecified"
                ),
                "model_provider": str(model.get("provider") or ""),
                "model_name": str(model.get("name") or ""),
                "strategy_name": str(strategy.get("name") or ""),
                "strategy_version": str(strategy.get("version") or ""),
                "atomic_claim": str(row.get("atomic_claim") or ""),
                "cited_document_ids": str(row.get("cited_document_ids") or ""),
                "automatic_support_label": automatic_support,
                "reviewer_support_label": reviewer_support,
                "support_exact_match": "yes" if support_match else "no",
                "binary_unsupported_match": (
                    "yes" if automatic_unsupported == reviewer_unsupported else "no"
                ),
                "automatic_citation_label": automatic_citation,
                "reviewer_citation_label": reviewer_citation,
                "citation_exact_match": "yes" if citation_match else "no",
                "task_prompt": str(row.get("task_prompt") or ""),
                "source_context": str(row.get("source_context") or ""),
                "response_text": str(row.get("response_text") or ""),
                "reviewer_notes": str(row.get("reviewer_notes") or ""),
            }
        )

    summary = {
        "annotation_schema_version": "1.0.0",
        "completed_claims": len(completed),
        "support_label_exact_agreement_count": exact_support,
        "support_label_exact_disagreement_count": len(completed) - exact_support,
        "support_label_exact_agreement": _safe_rate(exact_support, len(completed)),
        "binary_unsupported_agreement_count": binary_unsupported,
        "binary_unsupported_disagreement_count": len(completed) - binary_unsupported,
        "binary_unsupported_agreement": _safe_rate(
            binary_unsupported, len(completed)
        ),
        "citation_label_exact_agreement_count": exact_citation,
        "citation_label_exact_disagreement_count": len(completed) - exact_citation,
        "citation_label_exact_agreement": _safe_rate(exact_citation, len(completed)),
        "claims_with_any_exact_label_disagreement": len(disagreements),
        "binary_unsupported_confusion": {
            key: binary_counts.get(key, 0)
            for key in (
                "true_positive",
                "false_positive",
                "false_negative",
                "true_negative",
            )
        },
        "support_label_confusion": {
            automatic: dict(counts)
            for automatic, counts in sorted(support_confusion.items())
        },
        "citation_label_confusion": {
            automatic: dict(counts)
            for automatic, counts in sorted(citation_confusion.items())
        },
        "interpretation_note": (
            "Agreement checks validate the AI-assisted judge on a blinded, "
            "stratified response sample; they do not convert the remaining "
            "automatic labels into independent human annotations."
        ),
    }
    return summary, disagreements


def summarize_atomic_annotations(
    annotations_path: str | Path,
    mapping_path: str | Path,
) -> Dict[str, Any]:
    return compare_atomic_annotations(annotations_path, mapping_path)[0]


def write_atomic_disagreements_csv(
    path: str | Path,
    rows: Iterable[Dict[str, Any]],
) -> int:
    materialized = list(rows)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ATOMIC_DISAGREEMENT_FIELDS)
        writer.writeheader()
        writer.writerows(materialized)
    return len(materialized)
