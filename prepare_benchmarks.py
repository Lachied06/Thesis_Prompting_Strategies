#!/usr/bin/env python3
"""
Normalize selected hallucination/factuality benchmarks into the Task JSONL
format used by the thesis experiment harness.

This script does NOT call any LLM APIs and does NOT perform web retrieval.
Download/freeze the raw benchmark files first, then run this locally.

Supported adapters:
  - TruthfulQA generation data (CSV)
  - SciFact claims + corpus (JSONL)
  - SciFact academic synthesis with controlled document sets (JSONL)
  - HaluEval QA data (JSON)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


TOKEN_STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "has",
    "have",
    "not",
    "that",
    "the",
    "their",
    "this",
    "was",
    "were",
    "with",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def choose_rows(rows: List[Dict[str, Any]], limit: Optional[int], seed: int):
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")
    if limit is None or limit >= len(rows):
        return rows
    rng = random.Random(seed)
    indices = list(range(len(rows)))
    rng.shuffle(indices)
    selected = sorted(indices[:limit])
    return [rows[i] for i in selected]


def scifact_label(row: Dict[str, Any]) -> str:
    labels = {
        str(rationale.get("label", "")).strip().upper()
        for rationales in (row.get("evidence") or {}).values()
        for rationale in rationales
        if rationale.get("label")
    }
    if len(labels) == 1:
        label = next(iter(labels))
        if label in {"SUPPORT", "SUPPORTED"}:
            return "SUPPORT"
        if label in {"CONTRADICT", "CONTRADICTED"}:
            return "CONTRADICT"
        return label
    if not labels:
        return "NO_EVIDENCE"
    return "|".join(sorted(labels))


def choose_scifact_rows(
    rows: List[Dict[str, Any]],
    limit: Optional[int],
    seed: int,
    sampling: str,
) -> List[Dict[str, Any]]:
    if sampling == "random":
        return choose_rows(rows, limit, seed)
    if sampling != "stratified":
        raise ValueError("sampling must be random or stratified")
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")
    if limit is None or limit >= len(rows):
        return rows

    grouped: Dict[str, List[tuple[int, Dict[str, Any]]]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[scifact_label(row)].append((index, row))

    rng = random.Random(seed)
    for group in grouped.values():
        rng.shuffle(group)

    selected: List[tuple[int, Dict[str, Any]]] = []
    labels = sorted(grouped)
    while len(selected) < min(limit, len(rows)):
        made_progress = False
        for label in labels:
            if grouped[label] and len(selected) < limit:
                selected.append(grouped[label].pop())
                made_progress = True
        if not made_progress:
            break
    return [row for _, row in sorted(selected, key=lambda value: value[0])]


def _primary_scifact_document_ids(row: Dict[str, Any]) -> set[str]:
    evidence_ids = {str(value) for value in (row.get("evidence") or {})}
    cited_ids = {str(value) for value in row.get("cited_doc_ids", [])}
    return evidence_ids or cited_ids


def choose_scifact_rows_with_unique_primary_documents(
    rows: List[Dict[str, Any]],
    limit: Optional[int],
    seed: int,
    sampling: str,
) -> List[Dict[str, Any]]:
    """Select rows while preventing repeated gold/cited source documents."""
    if sampling not in {"random", "stratified"}:
        raise ValueError("sampling must be random or stratified")
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")

    grouped: Dict[str, List[tuple[int, Dict[str, Any]]]] = defaultdict(list)
    if sampling == "stratified":
        for index, row in enumerate(rows):
            grouped[scifact_label(row)].append((index, row))
    else:
        grouped["all"] = list(enumerate(rows))

    rng = random.Random(seed)
    for group in grouped.values():
        rng.shuffle(group)

    target = len(rows) if limit is None else min(limit, len(rows))
    labels = sorted(grouped)
    selected: List[tuple[int, Dict[str, Any]]] = []
    used_document_ids: set[str] = set()
    while len(selected) < target:
        made_progress = False
        for label in labels:
            while grouped[label] and len(selected) < target:
                candidate = grouped[label].pop()
                primary_ids = _primary_scifact_document_ids(candidate[1])
                if primary_ids & used_document_ids:
                    continue
                selected.append(candidate)
                used_document_ids.update(primary_ids)
                made_progress = True
                break
        if not made_progress:
            break
    return [row for _, row in sorted(selected, key=lambda value: value[0])]


def _unique(values: Iterable[str]) -> List[str]:
    seen = set()
    output = []
    for value in values:
        normalized = str(value)
        if normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def _abstract_text(doc: Dict[str, Any]) -> str:
    abstract = doc.get("abstract") or []
    if isinstance(abstract, list):
        return " ".join(str(sentence).strip() for sentence in abstract if str(sentence).strip())
    return str(abstract).strip()


def _format_source_context(doc_ids: Iterable[str], corpus: Dict[str, Dict[str, Any]]) -> str:
    sections = []
    for doc_id in doc_ids:
        doc = corpus.get(str(doc_id))
        if not doc:
            continue
        sections.append(
            f"[Document {doc_id}]\n"
            f"Title: {str(doc.get('title') or '').strip()}\n"
            f"Abstract: {_abstract_text(doc)}"
        )
    return "\n\n".join(sections)


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) >= 3 and token not in TOKEN_STOPWORDS
    }


def _supplementary_document_ids(
    claim: str,
    primary_doc_ids: Iterable[str],
    corpus: Dict[str, Dict[str, Any]],
    target_count: int,
    seed: int,
) -> List[str]:
    primary = _unique(str(doc_id) for doc_id in primary_doc_ids if str(doc_id) in corpus)
    if len(primary) >= target_count:
        return primary

    query_tokens = _tokens(claim)
    for doc_id in primary:
        doc = corpus[doc_id]
        query_tokens.update(_tokens(str(doc.get("title") or "")))

    excluded = set(primary)
    candidates = [doc_id for doc_id in corpus if doc_id not in excluded]
    random.Random(seed).shuffle(candidates)
    def relevance_score(doc_id: str) -> int:
        title_overlap = len(
            query_tokens & _tokens(str(corpus[doc_id].get("title") or ""))
        )
        abstract_overlap = len(query_tokens & _tokens(_abstract_text(corpus[doc_id])))
        return (3 * title_overlap) + abstract_overlap

    candidates.sort(key=relevance_score, reverse=True)
    return primary + candidates[: max(0, target_count - len(primary))]


def write_jsonl(rows: Iterable[Dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    print(f"Wrote {count} tasks -> {output}")


def truthfulness_target() -> str:
    return "unsupported_claim"


def prepare_truthfulqa(input_path: Path, output: Path, limit: Optional[int], seed: int):
    source_hash = sha256_file(input_path)

    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    rows = choose_rows(rows, limit, seed)
    tasks = []

    for i, row in enumerate(rows):
        question = (row.get("Question") or row.get("question") or "").strip()
        best_answer = (row.get("Best Answer") or row.get("best_answer") or "").strip()
        if not question:
            continue

        source_item_id = row.get("Question ID") or row.get("id") or str(i)

        tasks.append({
            "task_id": f"truthfulqa_{source_item_id}",
            "dataset": "TruthfulQA",
            "prompt": question,
            "reference_answer": best_answer or None,
            "source_context": None,
            "metadata": {
                "task_type": "truthfulness_qa",
                "hallucination_target": truthfulness_target(),
                "source_dataset": "TruthfulQA",
                "source_item_id": str(source_item_id),
                "category": row.get("Category"),
                "type": row.get("Type"),
                "best_incorrect_answer": row.get("Best Incorrect Answer"),
                "source_file_sha256": source_hash,
                "supported_strategies": [
                    "baseline",
                    "structured",
                    "chain_of_verification"
                ],
                "adaptation_note": (
                    "Uses TruthfulQA's generation question/reference answer. "
                    "No source context is supplied, so source_grounded is excluded."
                )
            }
        })

    write_jsonl(tasks, output)


def prepare_scifact_confirmatory_study(
    base_tasks_path: Path,
    design_output: Path,
    dataset_output: Path,
    seed: int,
) -> None:
    """Create the frozen 100-task confirmatory design without model outputs.

    The base pool must contain at least 25 tasks for each SciFact reference
    label. Evidence-backed SUPPORT and CONTRADICT tasks are divided between
    direct and distractor conditions. The same 25 direct items are transformed
    into paired evidence-omission tasks. Original NO_EVIDENCE items form the
    partial/insufficient-evidence condition.
    """
    base_rows = load_jsonl(base_tasks_path)
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in base_rows:
        grouped[str(row.get("reference_answer") or "")].append(row)

    required = {"SUPPORT": 25, "CONTRADICT": 25, "NO_EVIDENCE": 25}
    missing = {
        label: needed - len(grouped.get(label, []))
        for label, needed in required.items()
        if len(grouped.get(label, [])) < needed
    }
    if missing:
        raise ValueError(
            "Confirmatory base pool does not contain the required balanced labels: "
            f"{missing}"
        )

    rng = random.Random(seed)
    for label in required:
        rng.shuffle(grouped[label])

    support = grouped["SUPPORT"][:25]
    contradict = grouped["CONTRADICT"][:25]
    no_evidence = grouped["NO_EVIDENCE"][:25]
    direct = support[:13] + contradict[:12]
    near_match = support[13:] + contradict[12:]
    rng.shuffle(direct)
    rng.shuffle(near_match)
    rng.shuffle(no_evidence)

    def source_id(row: Dict[str, Any]) -> str:
        value = str((row.get("metadata") or {}).get("source_item_id") or "").strip()
        if not value:
            raise ValueError("Every confirmatory base task needs source_item_id")
        return value

    entries: List[Dict[str, Any]] = []
    for row in direct:
        entries.append(
            {
                "source_item_id": source_id(row),
                "difficulty_category": "direct_control",
                "document_mode": "gold_only",
                "difficulty_description": (
                    "Decisive gold evidence only; establishes basic synthesis and "
                    "verdict competence."
                ),
            }
        )
    for row in near_match:
        entries.append(
            {
                "source_item_id": source_id(row),
                "difficulty_category": "near_match_distractors",
                "document_mode": "full_distractor_first",
                "difficulty_description": (
                    "Four lexically related documents precede the decisive source, "
                    "testing source selection and attribution."
                ),
            }
        )
    for row in direct:
        entries.append(
            {
                "source_item_id": source_id(row),
                "difficulty_category": "evidence_omission",
                "document_mode": "omit_gold",
                "difficulty_description": (
                    "Decisive evidence is withheld while related documents remain; "
                    "the correct verdict becomes NO_EVIDENCE."
                ),
            }
        )
    for row in no_evidence:
        entries.append(
            {
                "source_item_id": source_id(row),
                "difficulty_category": "conflicting_or_partial_evidence",
                "document_mode": "full_distractor_first",
                "difficulty_description": (
                    "The source packet is topically relevant but does not establish "
                    "the full claim, testing qualification and overstatement."
                ),
            }
        )

    design = {
        "design_version": "1.0.0",
        "dataset_name": "SciFact_Confirmatory",
        "design_seed": seed,
        "design_note": (
            "One hundred-task confirmatory design selected before final model "
            "generation. Selection uses only SciFact labels, source identities, and "
            "predeclared evidence transformations; no model output is consulted."
        ),
        "expected_categories": {
            "direct_control": 25,
            "near_match_distractors": 25,
            "evidence_omission": 25,
            "conflicting_or_partial_evidence": 25,
        },
        "tasks": entries,
    }
    design_output.parent.mkdir(parents=True, exist_ok=True)
    design_output.write_text(
        json.dumps(design, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    prepare_scifact_difficulty_pilot(
        base_tasks_path,
        design_output,
        dataset_output,
    )


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_json_or_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load either a JSON array/wrapper or newline-delimited JSON records."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        rows = payload.get("data", payload.get("examples", []))
        if isinstance(rows, list):
            return rows
    raise ValueError(f"Unsupported JSON structure in {path}")


def scifact_source_ids_from_task_files(paths: Iterable[Path]) -> set[str]:
    """Collect original SciFact claim IDs from previously prepared task files."""
    source_ids: set[str] = set()
    for path in paths:
        for row in load_jsonl(path):
            metadata = row.get("metadata") or {}
            source_id = metadata.get("source_item_id")
            if source_id is None:
                task_id = str(row.get("task_id") or "")
                source_id = re.sub(r"^scifact(?:_synthesis)?_", "", task_id)
            normalized = str(source_id).strip()
            if normalized:
                source_ids.add(normalized)
    return source_ids


def prepare_scifact(
    claims_path: Path,
    corpus_path: Path,
    output: Path,
    limit: Optional[int],
    seed: int,
    sampling: str = "random",
):
    claims_hash = sha256_file(claims_path)
    corpus_hash = sha256_file(corpus_path)

    corpus_rows = load_jsonl(corpus_path)
    corpus = {str(row["doc_id"]): row for row in corpus_rows}
    claims = choose_scifact_rows(load_jsonl(claims_path), limit, seed, sampling)

    tasks = []

    for row in claims:
        claim_id = str(row["id"])
        claim = row["claim"].strip()
        evidence = row.get("evidence") or {}
        cited_doc_ids = [str(x) for x in row.get("cited_doc_ids", [])]

        evidence_doc_ids = []
        evidence_sentence_ids: Dict[str, List[int]] = {}

        for doc_id, rationales in evidence.items():
            doc_id = str(doc_id)
            evidence_doc_ids.append(doc_id)
            sentence_ids = []
            for rationale in rationales:
                sentence_ids.extend(rationale.get("sentences", []))
            evidence_sentence_ids[doc_id] = sorted(set(sentence_ids))

        reference_label = scifact_label(row)

        # Prefer gold evidence documents. If a row has no annotated evidence,
        # fall back to cited documents so that available citation context can
        # still be retained for analysis.
        context_doc_ids = evidence_doc_ids or cited_doc_ids
        context_doc_ids = _unique(context_doc_ids)
        source_context = _format_source_context(context_doc_ids, corpus) or None

        prompt = (
            "Assess the following scientific claim. State whether it is supported, "
            "contradicted, or cannot be determined, and briefly explain your answer.\n\n"
            f"Claim: {claim}"
        )

        tasks.append({
            "task_id": f"scifact_{claim_id}",
            "dataset": "SciFact",
            "prompt": prompt,
            "reference_answer": reference_label,
            "source_context": source_context,
            "metadata": {
                "task_type": "scientific_claim_verification",
                "hallucination_target": "source_misrepresentation",
                "source_dataset": "SciFact",
                "source_item_id": claim_id,
                "gold_label": reference_label,
                "evidence_doc_ids": evidence_doc_ids,
                "cited_doc_ids": cited_doc_ids,
                "evidence_sentence_ids": evidence_sentence_ids,
                "context_doc_ids": context_doc_ids,
                "claims_file_sha256": claims_hash,
                "corpus_file_sha256": corpus_hash,
                "sampling_method": sampling,
                "sampling_seed": seed,
                "supported_strategies": [
                    "baseline",
                    "structured",
                    "source_grounded",
                    "chain_of_verification"
                ],
                "adaptation_note": (
                    "Scientific claim verification adapted into short-form generation. "
                    "Evidence-controlled v2 conditions all receive the associated "
                    "evidence abstract(s). Legacy v1 treatments differ in evidence access."
                )
            }
        })

    write_jsonl(tasks, output)


def prepare_scifact_synthesis(
    claims_path: Path,
    corpus_path: Path,
    output: Path,
    limit: Optional[int],
    seed: int,
    documents_per_task: int,
    sampling: str = "stratified",
    exclude_task_files: Optional[List[Path]] = None,
    unique_primary_documents: bool = False,
):
    if documents_per_task < 1:
        raise ValueError("documents_per_task must be at least 1")

    claims_hash = sha256_file(claims_path)
    corpus_hash = sha256_file(corpus_path)
    corpus = {str(row["doc_id"]): row for row in load_jsonl(corpus_path)}
    exclusion_paths = list(exclude_task_files or [])
    excluded_source_ids = scifact_source_ids_from_task_files(exclusion_paths)
    eligible_claims = [
        row
        for row in load_jsonl(claims_path)
        if str(row.get("id")) not in excluded_source_ids
        and _primary_scifact_document_ids(row)
        and _primary_scifact_document_ids(row).issubset(corpus)
    ]
    if unique_primary_documents:
        claims = choose_scifact_rows_with_unique_primary_documents(
            eligible_claims, limit, seed, sampling
        )
    else:
        claims = choose_scifact_rows(eligible_claims, limit, seed, sampling)
    exclusion_manifest = [
        {"path": str(path), "sha256": sha256_file(path)}
        for path in exclusion_paths
    ]
    tasks = []

    for row in claims:
        claim_id = str(row["id"])
        claim = str(row["claim"]).strip()
        evidence = row.get("evidence") or {}
        evidence_doc_ids = _unique(str(doc_id) for doc_id in evidence)
        cited_doc_ids = _unique(str(doc_id) for doc_id in row.get("cited_doc_ids", []))
        primary_doc_ids = evidence_doc_ids or cited_doc_ids
        context_doc_ids = _supplementary_document_ids(
            claim,
            primary_doc_ids,
            corpus,
            documents_per_task,
            seed + int(claim_id) if claim_id.isdigit() else seed,
        )
        source_context = _format_source_context(context_doc_ids, corpus) or None
        reference_label = scifact_label(row)

        prompt = (
            "Write a 120–180 word academic synthesis evaluating the following "
            "scientific claim against the supplied source material. Explain the "
            "extent to which the sources support, contradict, or fail to establish "
            "the claim.\n\n"
            f"CLAIM: {claim}"
        )

        tasks.append(
            {
                "task_id": f"scifact_synthesis_{claim_id}",
                "dataset": "SciFact_Synthesis",
                "prompt": prompt,
                "reference_answer": reference_label,
                "source_context": source_context,
                "metadata": {
                    "task_type": "academic_evidence_synthesis",
                    "hallucination_target": [
                        "unsupported_claim",
                        "source_misrepresentation",
                        "fabricated_citation",
                    ],
                    "source_dataset": "SciFact",
                    "source_item_id": claim_id,
                    "gold_label": reference_label,
                    "evidence_doc_ids": evidence_doc_ids,
                    "cited_doc_ids": cited_doc_ids,
                    "allowed_document_ids": context_doc_ids,
                    "context_doc_ids": context_doc_ids,
                    "supplementary_doc_ids": [
                        doc_id for doc_id in context_doc_ids if doc_id not in primary_doc_ids
                    ],
                    "claims_file_sha256": claims_hash,
                    "corpus_file_sha256": corpus_hash,
                    "sampling_method": sampling,
                    "sampling_seed": seed,
                    "excluded_source_item_count": len(excluded_source_ids),
                    "exclusion_task_files": exclusion_manifest,
                    "unique_primary_documents": unique_primary_documents,
                    "documents_per_task": documents_per_task,
                    "word_range": [120, 180],
                    "supported_strategies": [
                        "baseline",
                        "structured",
                        "source_grounded",
                        "chain_of_verification",
                    ],
                    "adaptation_note": (
                        "SciFact claim verification adapted into evidence-controlled "
                        "academic synthesis. Every condition receives the same source "
                        "set and may cite only its supplied document identifiers."
                    ),
                },
            }
        )

    write_jsonl(tasks, output)


def _document_sections(source_context: str) -> Dict[str, str]:
    """Split a rendered source packet while preserving each document verbatim."""
    sections: Dict[str, str] = {}
    for part in re.split(r"(?=^\[Document [^\]]+\]\s*$)", source_context, flags=re.MULTILINE):
        rendered = part.strip()
        if not rendered:
            continue
        match = re.match(r"\[Document ([^\]]+)\]", rendered)
        if not match:
            raise ValueError("Source context contains text outside a [Document ID] section")
        document_id = match.group(1).strip()
        if document_id in sections:
            raise ValueError(f"Duplicate document section: {document_id}")
        sections[document_id] = rendered
    return sections


def _claim_from_synthesis_prompt(prompt: str) -> str:
    marker = "CLAIM:"
    if marker not in prompt:
        raise ValueError("Base synthesis task does not contain a CLAIM field")
    claim = prompt.split(marker, 1)[1].strip()
    if not claim:
        raise ValueError("Base synthesis task contains an empty claim")
    return claim


def prepare_scifact_difficulty_pilot(
    base_tasks_path: Path,
    design_path: Path,
    output: Path,
) -> None:
    """Build a frozen, paired stress pilot from pre-audited SciFact tasks.

    The design file selects source items and declares how their evidence packet
    is transformed. No model output is consulted during construction.
    """
    base_rows = load_jsonl(base_tasks_path)
    by_source_id = {
        str((row.get("metadata") or {}).get("source_item_id")): row
        for row in base_rows
    }
    design = json.loads(design_path.read_text(encoding="utf-8"))
    dataset_name = str(
        design.get("dataset_name") or "SciFact_Difficulty_Pilot"
    ).strip()
    if not dataset_name:
        raise ValueError("Difficulty design dataset_name cannot be empty")
    entries = design.get("tasks")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Difficulty design must contain a non-empty tasks list")

    expected_categories = design.get("expected_categories") or {}
    category_counts = Counter(str(entry.get("difficulty_category")) for entry in entries)
    if expected_categories and category_counts != Counter(expected_categories):
        raise ValueError(
            "Difficulty design category counts do not match expected_categories: "
            f"actual={dict(category_counts)}, expected={expected_categories}"
        )

    tasks: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for entry in entries:
        source_item_id = str(entry.get("source_item_id", "")).strip()
        category = str(entry.get("difficulty_category", "")).strip()
        mode = str(entry.get("document_mode", "")).strip()
        if not source_item_id or not category or not mode:
            raise ValueError(
                "Each difficulty task needs source_item_id, difficulty_category, "
                "and document_mode"
            )
        if source_item_id not in by_source_id:
            raise ValueError(f"Unknown base SciFact source item: {source_item_id}")

        base = by_source_id[source_item_id]
        metadata = dict(base.get("metadata") or {})
        sections = _document_sections(str(base.get("source_context") or ""))
        evidence_ids = _unique(metadata.get("evidence_doc_ids") or [])
        cited_ids = _unique(metadata.get("cited_doc_ids") or [])
        primary_ids = evidence_ids or cited_ids
        context_ids = _unique(metadata.get("context_doc_ids") or sections.keys())
        supplementary_ids = _unique(metadata.get("supplementary_doc_ids") or [])

        if mode == "gold_only":
            if not evidence_ids:
                raise ValueError(f"gold_only requires gold evidence for {source_item_id}")
            selected_ids = evidence_ids
            reference_label = str(base.get("reference_answer") or "")
        elif mode == "full_distractor_first":
            selected_ids = supplementary_ids + [
                doc_id for doc_id in primary_ids if doc_id not in supplementary_ids
            ]
            reference_label = str(base.get("reference_answer") or "")
        elif mode == "omit_gold":
            if not evidence_ids:
                raise ValueError(f"omit_gold requires gold evidence for {source_item_id}")
            selected_ids = [
                doc_id
                for doc_id in context_ids
                if doc_id not in evidence_ids
            ]
            reference_label = "NO_EVIDENCE"
        else:
            raise ValueError(f"Unknown document_mode: {mode}")

        override = str(entry.get("reference_label_override") or "").strip().upper()
        if override:
            if override not in {"SUPPORT", "CONTRADICT", "NO_EVIDENCE"}:
                raise ValueError(
                    f"Invalid reference_label_override for {source_item_id}: {override}"
                )
            reference_label = override

        selected_ids = _unique(selected_ids)
        if not selected_ids:
            raise ValueError(f"Difficulty task {source_item_id} has no supplied documents")
        missing_sections = [doc_id for doc_id in selected_ids if doc_id not in sections]
        if missing_sections:
            raise ValueError(
                f"Difficulty task {source_item_id} is missing document sections: "
                f"{missing_sections}"
            )

        task_id = f"scifact_difficulty_{source_item_id}_{category}"
        if task_id in seen_ids:
            raise ValueError(f"Duplicate difficulty task ID: {task_id}")
        seen_ids.add(task_id)
        claim = _claim_from_synthesis_prompt(str(base.get("prompt") or ""))
        source_context = "\n\n".join(sections[doc_id] for doc_id in selected_ids)
        task_prompt = (
            "Write a 180–250 word academic synthesis evaluating the following "
            "scientific claim against the supplied source material. State an "
            "overall verdict and discuss the relevant population or system, "
            "exposure or intervention, outcome, and material evidential "
            "limitations. Use four to six substantive factual claims where the "
            "sources permit; do not add filler when evidence is insufficient.\n\n"
            f"CLAIM: {claim}"
        )
        supplied_gold_ids = [doc_id for doc_id in selected_ids if doc_id in evidence_ids]
        omitted_gold_ids = [doc_id for doc_id in evidence_ids if doc_id not in selected_ids]

        tasks.append(
            {
                "task_id": task_id,
                "dataset": dataset_name,
                "prompt": task_prompt,
                "reference_answer": reference_label,
                "source_context": source_context,
                "metadata": {
                    **metadata,
                    "task_type": "academic_evidence_synthesis",
                    "hallucination_target": [
                        "unsupported_addition",
                        "source_contradiction",
                        "evidence_overstatement",
                        "entity_context_confusion",
                        "citation_mismatch",
                        "invalid_document_identifier",
                    ],
                    "requires_verdict": True,
                    "source_dataset": "SciFact",
                    "base_task_id": base.get("task_id"),
                    "base_reference_label": base.get("reference_answer"),
                    "reference_label_overridden": bool(override),
                    "gold_label": reference_label,
                    "difficulty_category": category,
                    "difficulty_description": str(
                        entry.get("difficulty_description") or ""
                    ),
                    "difficulty_design_version": str(
                        design.get("design_version") or "1.0.0"
                    ),
                    "document_mode": mode,
                    "allowed_document_ids": selected_ids,
                    "context_doc_ids": selected_ids,
                    "supplied_gold_document_ids": supplied_gold_ids,
                    "omitted_gold_document_ids": omitted_gold_ids,
                    "documents_per_task": len(selected_ids),
                    "word_range": [180, 250],
                    "base_tasks_file_sha256": sha256_file(base_tasks_path),
                    "difficulty_design_file_sha256": sha256_file(design_path),
                    "supported_strategies": [
                        "baseline",
                        "structured",
                        "source_grounded",
                        "chain_of_verification",
                    ],
                    "adaptation_note": (
                        "Pre-registered evidence-difficulty transformation of a "
                        "pre-audited SciFact synthesis item. Treatment prompts all "
                        "receive this exact same frozen source packet."
                    ),
                },
            }
        )

    write_jsonl(tasks, output)


def prepare_halueval_qa(
    input_path: Path,
    output: Path,
    limit: Optional[int],
    seed: int,
):
    source_hash = sha256_file(input_path)
    indexed_rows = [
        {**row, "_source_item_id": str(index)}
        for index, row in enumerate(load_json_or_jsonl(input_path))
    ]
    rows = choose_rows(indexed_rows, limit, seed)
    tasks = []

    for row in rows:
        question = str(row.get("question", "")).strip()
        if not question:
            continue

        source_item_id = str(row["_source_item_id"])

        tasks.append({
            "task_id": f"halueval_qa_{source_item_id}",
            "dataset": "HaluEval_QA_adapted",
            "prompt": question,
            "reference_answer": row.get("right_answer"),
            "source_context": row.get("knowledge"),
            "metadata": {
                "task_type": "knowledge_grounded_qa",
                "hallucination_target": "unsupported_claim",
                "source_dataset": "HaluEval",
                "source_item_id": source_item_id,
                "original_hallucinated_answer": row.get("hallucinated_answer"),
                "source_file_sha256": source_hash,
                "supported_strategies": [
                    "baseline",
                    "structured",
                    "source_grounded",
                    "chain_of_verification"
                ],
                "adaptation_note": (
                    "HaluEval QA is originally designed for hallucination recognition. "
                    "Here its knowledge/question/right-answer fields are adapted into a "
                    "generation task for mitigation experiments."
                )
            }
        })

    write_jsonl(tasks, output)


def prepare_halueval_synthesis(
    input_path: Path,
    output: Path,
    limit: Optional[int],
    seed: int,
):
    """Adapt HaluEval QA pairs into evidence-controlled answer evaluation.

    Each selected source item contributes one candidate answer. Correct and
    hallucinated candidates alternate after deterministic sampling, producing
    an approximately balanced SUPPORT/CONTRADICT pilot without reusing the
    same source passage twice.
    """
    source_hash = sha256_file(input_path)
    indexed_rows = [
        {**row, "_source_item_id": str(index)}
        for index, row in enumerate(load_json_or_jsonl(input_path))
        if str(row.get("question", "")).strip()
        and str(row.get("knowledge", "")).strip()
        and str(row.get("right_answer", "")).strip()
        and str(row.get("hallucinated_answer", "")).strip()
    ]
    rows = choose_rows(indexed_rows, limit, seed)
    tasks = []

    for position, row in enumerate(rows):
        source_item_id = str(row["_source_item_id"])
        supported_candidate = (position + seed) % 2 == 0
        candidate_field = (
            "right_answer" if supported_candidate else "hallucinated_answer"
        )
        candidate_answer = str(row[candidate_field]).strip()
        reference_label = "SUPPORT" if supported_candidate else "CONTRADICT"
        document_id = f"halueval_{source_item_id}"
        question = str(row["question"]).strip()
        knowledge = str(row["knowledge"]).strip()
        source_context = (
            f"[Document {document_id}]\n"
            f"Source passage: {knowledge}"
        )
        prompt = (
            "Write a 120–180 word academic synthesis evaluating whether the "
            "proposed answer correctly answers the question according to the "
            "supplied source material. Explain whether the source supports, "
            "contradicts, or is insufficient to establish the proposed answer.\n\n"
            f"QUESTION: {question}\n"
            f"PROPOSED ANSWER: {candidate_answer}"
        )

        tasks.append(
            {
                "task_id": (
                    f"halueval_synthesis_{source_item_id}_"
                    f"{reference_label.lower()}"
                ),
                "dataset": "HaluEval_Synthesis",
                "prompt": prompt,
                "reference_answer": reference_label,
                "source_context": source_context,
                "metadata": {
                    "task_type": "academic_evidence_synthesis",
                    "requires_verdict": True,
                    "hallucination_target": [
                        "unsupported_claim",
                        "source_misrepresentation",
                        "fabricated_citation",
                    ],
                    "source_dataset": "HaluEval",
                    "source_item_id": source_item_id,
                    "gold_label": reference_label,
                    "candidate_origin": candidate_field,
                    "right_answer": row.get("right_answer"),
                    "original_hallucinated_answer": row.get(
                        "hallucinated_answer"
                    ),
                    "allowed_document_ids": [document_id],
                    "context_doc_ids": [document_id],
                    "source_file_sha256": source_hash,
                    "sampling_method": "random_without_replacement",
                    "sampling_seed": seed,
                    "candidate_assignment": "alternating_balanced",
                    "documents_per_task": 1,
                    "word_range": [120, 180],
                    "supported_strategies": [
                        "baseline",
                        "structured",
                        "source_grounded",
                        "chain_of_verification",
                    ],
                    "adaptation_note": (
                        "One HaluEval candidate answer is evaluated against the "
                        "associated knowledge passage. Correct and hallucinated "
                        "candidates are deterministically balanced, then checked "
                        "by a pre-run audit because some original hallucinated "
                        "answers may be merely incomplete or ambiguous."
                    ),
                },
            }
        )

    write_jsonl(tasks, output)


def build_parser():
    parser = argparse.ArgumentParser(description="Prepare thesis benchmark tasks")
    sub = parser.add_subparsers(dest="dataset", required=True)

    p = sub.add_parser("truthfulqa")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--limit", type=int)
    p.add_argument("--seed", type=int, default=42)

    p = sub.add_parser("scifact")
    p.add_argument("--claims", required=True)
    p.add_argument("--corpus", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--limit", type=int)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--sampling", choices=("random", "stratified"), default="random")

    p = sub.add_parser("scifact-synthesis")
    p.add_argument("--claims", required=True)
    p.add_argument("--corpus", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--limit", type=int)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--documents-per-task", type=int, default=3)
    p.add_argument("--sampling", choices=("random", "stratified"), default="stratified")
    p.add_argument(
        "--exclude-task-file",
        action="append",
        default=[],
        help=(
            "Previously prepared task JSONL whose SciFact source IDs must be "
            "excluded; may be supplied more than once"
        ),
    )
    p.add_argument(
        "--unique-primary-documents",
        action="store_true",
        help="Prevent selected tasks from sharing a gold or cited source document",
    )

    p = sub.add_parser("scifact-difficulty-pilot")
    p.add_argument(
        "--base-tasks",
        required=True,
        help="Pre-audited SciFact synthesis task JSONL used as source material",
    )
    p.add_argument(
        "--design",
        required=True,
        help="Frozen JSON design declaring difficulty category and evidence mode",
    )
    p.add_argument("--output", required=True)

    p = sub.add_parser("scifact-confirmatory-study")
    p.add_argument(
        "--base-tasks",
        required=True,
        help="Balanced 75-task SciFact synthesis source pool",
    )
    p.add_argument("--design-output", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--seed", type=int, default=20260924)

    p = sub.add_parser("halueval-qa")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--limit", type=int)
    p.add_argument("--seed", type=int, default=42)

    p = sub.add_parser("halueval-synthesis")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--limit", type=int)
    p.add_argument("--seed", type=int, default=42)

    return parser


def main():
    args = build_parser().parse_args()

    if args.dataset == "truthfulqa":
        prepare_truthfulqa(
            Path(args.input), Path(args.output), args.limit, args.seed
        )
    elif args.dataset == "scifact":
        prepare_scifact(
            Path(args.claims),
            Path(args.corpus),
            Path(args.output),
            args.limit,
            args.seed,
            args.sampling,
        )
    elif args.dataset == "halueval-qa":
        prepare_halueval_qa(
            Path(args.input), Path(args.output), args.limit, args.seed
        )
    elif args.dataset == "halueval-synthesis":
        prepare_halueval_synthesis(
            Path(args.input), Path(args.output), args.limit, args.seed
        )
    elif args.dataset == "scifact-synthesis":
        prepare_scifact_synthesis(
            Path(args.claims),
            Path(args.corpus),
            Path(args.output),
            args.limit,
            args.seed,
            args.documents_per_task,
            args.sampling,
            [Path(path) for path in args.exclude_task_file],
            args.unique_primary_documents,
        )
    elif args.dataset == "scifact-difficulty-pilot":
        prepare_scifact_difficulty_pilot(
            Path(args.base_tasks),
            Path(args.design),
            Path(args.output),
        )
    elif args.dataset == "scifact-confirmatory-study":
        prepare_scifact_confirmatory_study(
            Path(args.base_tasks),
            Path(args.design_output),
            Path(args.output),
            args.seed,
        )


if __name__ == "__main__":
    main()
