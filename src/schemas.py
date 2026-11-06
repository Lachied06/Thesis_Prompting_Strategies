import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Task:
    task_id: str
    dataset: str
    prompt: str
    reference_answer: Optional[str] = None
    source_context: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Prompt:
    """A versioned, fully rendered prompt sent to a model."""

    strategy: str
    template_id: str
    template_version: str
    step: str
    system_prompt: Optional[str]
    user_prompt: str
    variables: Dict[str, Any] = field(default_factory=dict)

    @property
    def rendered_prompt(self) -> str:
        parts = []
        if self.system_prompt:
            parts.append(f"SYSTEM:\n{self.system_prompt}")
        parts.append(f"USER:\n{self.user_prompt}")
        return "\n\n".join(parts)

    @property
    def prompt_hash(self) -> str:
        payload = json.dumps(
            {
                "system_prompt": self.system_prompt,
                "user_prompt": self.user_prompt,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "rendered_prompt": self.rendered_prompt,
            "prompt_hash": self.prompt_hash,
        }


@dataclass
class GenerationRequest:
    system_prompt: Optional[str]
    user_prompt: str
    max_output_tokens: int
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResponse:
    text: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    finish_reason: Optional[str] = None
    provider_request_id: Optional[str] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedResponse:
    raw: str
    parsed_label: Optional[str]
    explanation: Optional[str]
    parse_status: str
    cited_document_ids: List[str] = field(default_factory=list)
    invalid_cited_document_ids: List[str] = field(default_factory=list)
    citation_parse_status: str = "not_applicable"


@dataclass
class TraceStep:
    label: str
    prompt: Prompt
    request: GenerationRequest
    response: GenerationResponse
    latency_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "prompt": self.prompt.to_dict(),
            "request": asdict(self.request),
            "response": asdict(self.response),
            "latency_seconds": self.latency_seconds,
        }


@dataclass
class RunResult:
    schema_version: str
    experiment_id: str
    run_id: str
    experiment_name: str
    repetition: int
    task: Task
    provider: str
    model: str
    strategy: Dict[str, Any]
    max_output_tokens: int
    status: str
    started_at_utc: str
    finished_at_utc: str
    latency_seconds: float
    parsed_response: Optional[ParsedResponse]
    trace: List[TraceStep]
    model_settings: Dict[str, Any]
    ground_truth_label: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        input_tokens = sum(step.response.input_tokens or 0 for step in self.trace)
        output_tokens = sum(step.response.output_tokens or 0 for step in self.trace)
        reasoning_tokens = sum(
            step.response.reasoning_tokens or 0 for step in self.trace
        )

        parsed_label = (
            self.parsed_response.parsed_label if self.parsed_response else None
        )
        classification_correct = None
        if parsed_label is not None and self.ground_truth_label is not None:
            classification_correct = parsed_label == self.ground_truth_label

        cited_document_ids = (
            self.parsed_response.cited_document_ids if self.parsed_response else []
        )
        invalid_cited_document_ids = (
            self.parsed_response.invalid_cited_document_ids
            if self.parsed_response
            else []
        )
        response_word_count = None
        word_count_within_range = None
        if self.parsed_response and self.parsed_response.explanation:
            response_word_count = len(
                re.findall(r"\b[\w’-]+\b", self.parsed_response.explanation)
            )
            word_range = self.task.metadata.get("word_range")
            if (
                isinstance(word_range, (list, tuple))
                and len(word_range) == 2
                and all(isinstance(value, int) for value in word_range)
            ):
                word_count_within_range = (
                    word_range[0] <= response_word_count <= word_range[1]
                )

        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "experiment_name": self.experiment_name,
            "repetition": self.repetition,
            "dataset": {
                "name": self.task.dataset,
                "task_id": self.task.task_id,
            },
            "task": {
                "prompt": self.task.prompt,
                "reference_answer": self.task.reference_answer,
                "source_context": self.task.source_context,
                "metadata": self.task.metadata,
            },
            "strategy": self.strategy,
            "model": {
                "provider": self.provider,
                "name": self.model,
                "settings": self.model_settings,
                "max_output_tokens": self.max_output_tokens,
            },
            "status": self.status,
            "timestamps": {
                "started_at_utc": self.started_at_utc,
                "finished_at_utc": self.finished_at_utc,
            },
            "prompts": [step.prompt.to_dict() for step in self.trace],
            "response": (
                asdict(self.parsed_response) if self.parsed_response else None
            ),
            "ground_truth": {
                "raw": self.task.reference_answer,
                "label": self.ground_truth_label,
            },
            "metrics": {
                "classification_correct": classification_correct,
                "cited_document_count": len(cited_document_ids),
                "invalid_citation_count": len(invalid_cited_document_ids),
                "has_invalid_citation": bool(invalid_cited_document_ids),
                "response_word_count": response_word_count,
                "word_count_within_range": word_count_within_range,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "reasoning_tokens": reasoning_tokens,
                "latency_seconds": self.latency_seconds,
            },
            "trace": [step.to_dict() for step in self.trace],
            "error": self.error,
        }
