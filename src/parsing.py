from __future__ import annotations

import re
from typing import Iterable, Optional

from src.schemas import ParsedResponse, Task


CANONICAL_LABELS = ("SUPPORT", "CONTRADICT", "NO_EVIDENCE")

_STRICT_LABEL = re.compile(
    r"(?im)^\s*(?:\*\*)?LABEL(?:\*\*)?\s*:\s*"
    r"(?:\*\*)?(SUPPORT(?:ED)?|CONTRADICT(?:ED)?|NO[_ ]EVIDENCE)"
    r"\b(?:\*\*)?"
)
_STRICT_VERDICT = re.compile(
    r"(?im)^\s*(?:\*\*)?VERDICT(?:\*\*)?\s*:\s*"
    r"(?:\*\*)?(SUPPORT(?:ED)?|CONTRADICT(?:ED)?|NO[_ ]EVIDENCE)"
    r"\b(?:\*\*)?"
)
_LEADING_LABEL = re.compile(
    r"(?is)^\s*(?:\*\*)?(?:ASSESSMENT\s*:\s*)?"
    r"(SUPPORT(?:ED)?|CONTRADICT(?:ED)?|NO[_ ]EVIDENCE|"
    r"CANNOT BE DETERMINED|INSUFFICIENT EVIDENCE)\b(?:\*\*)?"
)
_SYNTHESIS_FIELD = re.compile(
    r"(?ims)^\s*(?:\*\*)?SYNTHESIS(?:\*\*)?\s*:\s*"
    r"(.+?)(?=^\s*(?:\*\*)?CITED_DOCUMENTS(?:\*\*)?\s*:|\Z)"
)
_CITED_DOCUMENTS_FIELD = re.compile(
    r"(?im)^\s*(?:\*\*)?CITED_DOCUMENTS(?:\*\*)?\s*:\s*(.+?)\s*$"
)
_BRACKETED_DOCUMENT_REFERENCE = re.compile(
    r"(?i)\[\s*Document\s+([A-Za-z0-9][A-Za-z0-9_.:-]*)\s*\]"
)
_NUMBERED_DOCUMENT_REFERENCE = re.compile(
    r"(?i)\bDocument\s+"
    r"((?=[A-Za-z0-9_.:-]*\d)[A-Za-z0-9][A-Za-z0-9_.:-]*)\b"
)
_FIELD_DOCUMENT_REFERENCE = re.compile(
    r"(?i)\bDocument\s+([A-Za-z0-9][A-Za-z0-9_.:-]*)\b"
)
_BARE_DOCUMENT_ID = re.compile(r"\b[0-9]{1,18}\b")
_DOCUMENT_ID_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*")


def normalize_label(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = re.sub(r"[\s-]+", "_", str(value).strip().upper())
    if normalized in {"SUPPORT", "SUPPORTED"}:
        return "SUPPORT"
    if normalized in {"CONTRADICT", "CONTRADICTED"}:
        return "CONTRADICT"
    if normalized in {
        "NO_EVIDENCE",
        "CANNOT_BE_DETERMINED",
        "INSUFFICIENT_EVIDENCE",
    }:
        return "NO_EVIDENCE"
    return None


def _extract_explanation(text: str, match: re.Match[str]) -> str:
    remaining = (text[: match.start()] + text[match.end() :]).strip()
    remaining = re.sub(
        r"(?im)^\s*(?:\*\*)?EXPLANATION(?:\*\*)?\s*:\s*",
        "",
        remaining,
        count=1,
    )
    return remaining.strip()


def _deduplicate(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = str(value).strip().strip("[](){}.,;")
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _allowed_document_ids(task: Task) -> list[str]:
    metadata = task.metadata or {}
    values = metadata.get("allowed_document_ids")
    if values is None:
        values = metadata.get("context_doc_ids")
    if values is None:
        return []
    if not isinstance(values, (list, tuple, set)):
        values = [values]
    return _deduplicate(str(value) for value in values)


def _inline_document_references(raw: str) -> list[str]:
    """Extract citation-shaped references without treating prose as a citation.

    Purely alphabetic identifiers are accepted only in the explicit bracketed
    form. Unbracketed references must contain a digit, which prevents phrases
    such as "the document does" from producing the false identifier "does".
    """
    references = [
        match.group(1) for match in _BRACKETED_DOCUMENT_REFERENCE.finditer(raw)
    ]
    references.extend(
        match.group(1) for match in _NUMBERED_DOCUMENT_REFERENCE.finditer(raw)
    )
    return references


def _citation_details(raw: str, task: Task) -> tuple[list[str], list[str], str]:
    references = _inline_document_references(raw)
    field = _CITED_DOCUMENTS_FIELD.search(raw)
    if field and field.group(1).strip().upper() != "NONE":
        field_text = field.group(1)
        references.extend(
            match.group(1)
            for match in _FIELD_DOCUMENT_REFERENCE.finditer(field_text)
        )
        references.extend(_BARE_DOCUMENT_ID.findall(field_text))
        # The output contract permits bare comma-separated identifiers. Accept
        # alphabetic/compound IDs such as ``halueval_497`` as well as numeric
        # SciFact IDs, while retaining unknown IDs so validation can flag them.
        for value in re.split(r"[,;]", field_text):
            candidate = value.strip().strip("[](){}.")
            candidate = re.sub(r"(?i)^Document\s+", "", candidate).strip()
            if _DOCUMENT_ID_TOKEN.fullmatch(candidate):
                references.append(candidate)

    cited = _deduplicate(references)
    allowed = set(_allowed_document_ids(task))
    invalid = [document_id for document_id in cited if allowed and document_id not in allowed]
    if field:
        citation_status = "parsed_none" if not cited else "parsed_strict"
    elif cited:
        citation_status = "parsed_inline_only"
    else:
        citation_status = "missing" if allowed else "not_applicable"
    return cited, invalid, citation_status


def parse_response(text: str, task: Task) -> ParsedResponse:
    raw = text or ""
    cited, invalid, citation_status = _citation_details(raw, task)
    task_type = task.metadata.get("task_type")

    if task_type == "academic_evidence_synthesis":
        verdict_match = _STRICT_VERDICT.search(raw)
        synthesis_match = _SYNTHESIS_FIELD.search(raw)
        citations_match = _CITED_DOCUMENTS_FIELD.search(raw)
        verdict_required = bool(task.metadata.get("requires_verdict"))
        if (
            synthesis_match
            and citations_match
            and (verdict_match or not verdict_required)
        ):
            return ParsedResponse(
                raw=raw,
                parsed_label=(
                    normalize_label(verdict_match.group(1))
                    if verdict_match
                    else None
                ),
                explanation=synthesis_match.group(1).strip() or None,
                parse_status="parsed_strict",
                cited_document_ids=cited,
                invalid_cited_document_ids=invalid,
                citation_parse_status=citation_status,
            )
        return ParsedResponse(
            raw=raw,
            parsed_label=(
                normalize_label(verdict_match.group(1))
                if verdict_match
                else None
            ),
            explanation=raw.strip() or None,
            parse_status="parsed_fallback" if raw.strip() else "unparsed",
            cited_document_ids=cited,
            invalid_cited_document_ids=invalid,
            citation_parse_status=citation_status,
        )

    if task_type != "scientific_claim_verification":
        return ParsedResponse(
            raw=raw,
            parsed_label=None,
            explanation=raw.strip() or None,
            parse_status="not_applicable",
            cited_document_ids=cited,
            invalid_cited_document_ids=invalid,
            citation_parse_status=citation_status,
        )

    match = _STRICT_LABEL.search(raw)
    if match:
        return ParsedResponse(
            raw=raw,
            parsed_label=normalize_label(match.group(1)),
            explanation=_extract_explanation(raw, match) or None,
            parse_status="parsed_strict",
            cited_document_ids=cited,
            invalid_cited_document_ids=invalid,
            citation_parse_status=citation_status,
        )

    match = _LEADING_LABEL.search(raw)
    if match:
        return ParsedResponse(
            raw=raw,
            parsed_label=normalize_label(match.group(1)),
            explanation=_extract_explanation(raw, match) or None,
            parse_status="parsed_fallback",
            cited_document_ids=cited,
            invalid_cited_document_ids=invalid,
            citation_parse_status=citation_status,
        )

    return ParsedResponse(
        raw=raw,
        parsed_label=None,
        explanation=raw.strip() or None,
        parse_status="unparsed",
        cited_document_ids=cited,
        invalid_cited_document_ids=invalid,
        citation_parse_status=citation_status,
    )
