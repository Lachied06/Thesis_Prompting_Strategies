from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Mapping, Optional, Tuple

from src.schemas import Prompt, Task


PROMPT_REGISTRY_VERSION = "3.2.0"
LEGACY_PROMPT_VERSION = "1.0.0"
EVIDENCE_CONTROLLED_VERSION = "2.0.0"
ACADEMIC_SYNTHESIS_VERSION = "3.0.0"
ACADEMIC_SYNTHESIS_VERDICT_VERSION = "3.1.0"
ACADEMIC_STRESS_VERSION = "3.2.0"
CONTROL_SYSTEM_PROMPT = None
# Deliberately None. External capabilities are controlled at the provider/API
# layer so the baseline is not contaminated by anti-hallucination wording.

SCIFACT_OUTPUT_CONTRACT = """

OUTPUT FORMAT
-------------
Return exactly these two fields:
LABEL: SUPPORT | CONTRADICT | NO_EVIDENCE
EXPLANATION: <brief justification>

Use NO_EVIDENCE when the claim cannot be determined from the information
available in this experimental condition."""

SYNTHESIS_OUTPUT_CONTRACT = """

OUTPUT FORMAT
-------------
Return exactly these two fields:
SYNTHESIS: <a 120–180 word academic paragraph>
CITED_DOCUMENTS: <comma-separated supplied document IDs used, or NONE>

Within the synthesis, cite supplied evidence as [Document ID]. Do not use a
document identifier that is not present in the supplied evidence."""

SYNTHESIS_VERDICT_OUTPUT_CONTRACT = """

OUTPUT FORMAT
-------------
Return exactly these three fields:
VERDICT: SUPPORT | CONTRADICT | NO_EVIDENCE
SYNTHESIS: <a 120–180 word academic paragraph>
CITED_DOCUMENTS: <comma-separated supplied document IDs used, or NONE>

Use NO_EVIDENCE when the proposed claim or answer cannot be determined from
the supplied source material. Within the synthesis, cite supplied evidence as
[Document ID]. Do not use a document identifier that is not present in the
supplied evidence."""

SYNTHESIS_STRESS_OUTPUT_CONTRACT = """

OUTPUT FORMAT
-------------
Return exactly these three fields:
VERDICT: SUPPORT | CONTRADICT | NO_EVIDENCE
SYNTHESIS: <a 180–250 word academic paragraph>
CITED_DOCUMENTS: <comma-separated supplied document IDs used, or NONE>

Use NO_EVIDENCE when the complete claim cannot be established or contradicted
from the supplied source material. Within the synthesis, cite supplied evidence
as [Document ID]. Do not use a document identifier that is not present in the
supplied evidence."""


@dataclass(frozen=True)
class PromptTemplate:
    strategy: str
    template_id: str
    version: str
    step: str
    user_template: str
    components: Tuple[str, ...]
    system_template: Optional[str] = CONTROL_SYSTEM_PROMPT

    def render(self, variables: Dict[str, Any]) -> Prompt:
        system_prompt = (
            self.system_template.format(**variables)
            if self.system_template
            else None
        )
        return Prompt(
            strategy=self.strategy,
            template_id=self.template_id,
            template_version=self.version,
            step=self.step,
            system_prompt=system_prompt,
            user_prompt=self.user_template.format(**variables).strip(),
            variables=variables,
        )

    def metadata(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_version": self.version,
            "step": self.step,
            "components": list(self.components),
        }


@dataclass(frozen=True)
class StrategyDefinition:
    name: str
    version: str
    initial: PromptTemplate
    verification: Optional[PromptTemplate] = None
    revision: Optional[PromptTemplate] = None
    requires_evidence: bool = False

    @property
    def request_count(self) -> int:
        return 1 + int(self.verification is not None) + int(self.revision is not None)

    def metadata(self) -> Dict[str, Any]:
        templates = [self.initial.metadata()]
        if self.verification:
            templates.append(self.verification.metadata())
        if self.revision:
            templates.append(self.revision.metadata())
        return {
            "name": self.name,
            "version": self.version,
            "registry_version": PROMPT_REGISTRY_VERSION,
            "requires_evidence": self.requires_evidence,
            "request_count": self.request_count,
            "templates": templates,
        }


@dataclass
class PromptPlan:
    definition: StrategyDefinition
    first_prompt: Prompt
    task: Task

    @property
    def strategy_metadata(self) -> Dict[str, Any]:
        return self.definition.metadata()

    def render_verification(self, draft: str) -> Optional[Prompt]:
        if not self.definition.verification:
            return None
        return self.definition.verification.render(
            _variables_for_task(
                self.task,
                strategy_version=self.definition.version,
                draft=draft,
            )
        )

    def render_revision(self, draft: str, verification_report: str) -> Optional[Prompt]:
        if not self.definition.revision:
            return None
        return self.definition.revision.render(
            _variables_for_task(
                self.task,
                strategy_version=self.definition.version,
                draft=draft,
                verification_report=verification_report,
            )
        )

    def preview_prompts(self) -> list[Prompt]:
        prompts = [self.first_prompt]
        draft = "{{DRAFT_FROM_INITIAL_GENERATION}}"
        verification = self.render_verification(draft)
        if verification:
            prompts.append(verification)
        revision = self.render_revision(
            draft,
            "{{VERIFICATION_REPORT_FROM_SECOND_GENERATION}}",
        )
        if revision:
            prompts.append(revision)
        return prompts


# Version 1 is retained in substance so historical runs remain reproducible.
# A string strategy entry in an old config resolves to v1.
BASELINE_V1 = StrategyDefinition(
    name="baseline",
    version=LEGACY_PROMPT_VERSION,
    initial=PromptTemplate(
        strategy="baseline",
        template_id="academic_baseline_v1",
        version=LEGACY_PROMPT_VERSION,
        step="initial_generation",
        user_template="{task_prompt}{output_contract}",
        components=("task_definition", "shared_output_contract"),
    ),
)

STRUCTURED_V1 = StrategyDefinition(
    name="structured",
    version=LEGACY_PROMPT_VERSION,
    initial=PromptTemplate(
        strategy="structured",
        template_id="academic_structured_v1",
        version=LEGACY_PROMPT_VERSION,
        step="initial_generation",
        user_template="""\
Complete the following academic task.

REQUIREMENTS
------------
1. Answer the question directly.
2. Distinguish clearly between established information and uncertainty.
3. Do not invent sources, citations, quotations, statistics, or evidence.
4. If the available information is insufficient, state that limitation.
5. Keep the answer focused on the requested task.

TASK
----
{task_prompt}{output_contract}""",
        components=(
            "task_definition",
            "explicit_requirements",
            "uncertainty_instruction",
            "anti-fabrication_instruction",
            "shared_output_contract",
        ),
    ),
)

SOURCE_GROUNDED_V1 = StrategyDefinition(
    name="source_grounded",
    version=LEGACY_PROMPT_VERSION,
    initial=PromptTemplate(
        strategy="source_grounded",
        template_id="academic_source_grounded_v1",
        version=LEGACY_PROMPT_VERSION,
        step="initial_generation",
        user_template="""\
Complete the academic task using only the supplied source material.

GROUNDING RULES
---------------
- Base every factual claim only on the source material below.
- Do not introduce unsupported facts, citations, or studies.
- If the source material is insufficient, say so explicitly.
- Do not use outside information or fill gaps with assumptions.

SOURCE MATERIAL
---------------
{source_context}
---------------

TASK
----
{task_prompt}{output_contract}""",
        components=(
            "task_definition",
            "provided_evidence",
            "evidence_only_constraint",
            "uncertainty_instruction",
            "shared_output_contract",
        ),
    ),
    requires_evidence=True,
)

CHAIN_OF_VERIFICATION_V1 = StrategyDefinition(
    name="chain_of_verification",
    version=LEGACY_PROMPT_VERSION,
    initial=PromptTemplate(
        strategy="chain_of_verification",
        template_id="academic_cov_draft_v1",
        version=LEGACY_PROMPT_VERSION,
        step="initial_generation",
        user_template="""\
Produce an initial answer to the following academic task.

Do not fabricate citations, quotations, statistics, or evidence.

TASK
----
{task_prompt}{output_contract}""",
        components=(
            "task_definition",
            "anti-fabrication_instruction",
            "shared_output_contract",
        ),
    ),
    verification=PromptTemplate(
        strategy="chain_of_verification",
        template_id="academic_cov_verify_v1",
        version=LEGACY_PROMPT_VERSION,
        step="verification_generation",
        user_template="""\
You previously produced the draft below.

DRAFT
-----
{draft}
-----

Verify and correct the draft before giving the final answer.

VERIFICATION STEPS
------------------
1. Identify claims that may be unsupported, fabricated, overstated, or uncertain.
2. Check whether citations, quotations, statistics, source descriptions, or
   research claims were invented.
3. Remove or qualify claims that cannot be justified from the information
   available in this experimental condition.
4. Return only the corrected final answer, not the verification notes.

ORIGINAL TASK
-------------
{task_prompt}{output_contract}""",
        components=(
            "draft_review",
            "claim_verification",
            "correction_instruction",
            "shared_output_contract",
        ),
    ),
)


# Version 2 is an evidence-controlled SciFact treatment family. Every condition
# receives the identical evidence block; treatment varies added structure.
BASELINE_V2 = StrategyDefinition(
    name="baseline",
    version=EVIDENCE_CONTROLLED_VERSION,
    requires_evidence=True,
    initial=PromptTemplate(
        strategy="baseline",
        template_id="scifact_baseline_v2",
        version=EVIDENCE_CONTROLLED_VERSION,
        step="initial_generation",
        user_template="""\
EVIDENCE
--------
{source_context}
--------

TASK
----
{task_prompt}{output_contract}""",
        components=("provided_evidence", "task_definition", "shared_output_contract"),
    ),
)

STRUCTURED_V2 = StrategyDefinition(
    name="structured",
    version=EVIDENCE_CONTROLLED_VERSION,
    requires_evidence=True,
    initial=PromptTemplate(
        strategy="structured",
        template_id="scifact_structured_v2",
        version=EVIDENCE_CONTROLLED_VERSION,
        step="initial_generation",
        user_template="""\
Evaluate the scientific claim against the supplied evidence.

EVIDENCE
--------
{source_context}
--------

TASK
----
{task_prompt}

REQUIREMENTS
------------
1. Identify the claim's central factual assertion.
2. Determine whether the evidence addresses that assertion.
3. Select SUPPORT, CONTRADICT, or NO_EVIDENCE.
4. Briefly explain the classification and state any material uncertainty.
5. Do not invent sources, citations, quotations, statistics, or evidence.
{output_contract}""",
        components=(
            "provided_evidence",
            "task_definition",
            "task_decomposition",
            "uncertainty_instruction",
            "anti-fabrication_instruction",
            "shared_output_contract",
        ),
    ),
)

SOURCE_GROUNDED_V2 = StrategyDefinition(
    name="source_grounded",
    version=EVIDENCE_CONTROLLED_VERSION,
    requires_evidence=True,
    initial=PromptTemplate(
        strategy="source_grounded",
        template_id="scifact_source_grounded_v2",
        version=EVIDENCE_CONTROLLED_VERSION,
        step="initial_generation",
        user_template="""\
Evaluate the scientific claim using only the supplied evidence.

EVIDENCE
--------
{source_context}
--------

TASK
----
{task_prompt}

GROUNDING RULES
---------------
- Every factual statement in the explanation must be supported by the evidence.
- Do not use outside knowledge, assumptions, or information not shown above.
- If the evidence does not establish or contradict the claim, choose NO_EVIDENCE.
- Do not introduce unsupported facts, citations, studies, or causal explanations.
{output_contract}""",
        components=(
            "provided_evidence",
            "task_definition",
            "evidence_only_constraint",
            "claim_level_grounding",
            "uncertainty_instruction",
            "shared_output_contract",
        ),
    ),
)

CHAIN_OF_VERIFICATION_V2 = StrategyDefinition(
    name="chain_of_verification",
    version=EVIDENCE_CONTROLLED_VERSION,
    requires_evidence=True,
    initial=PromptTemplate(
        strategy="chain_of_verification",
        template_id="scifact_cov_draft_v2",
        version=EVIDENCE_CONTROLLED_VERSION,
        step="initial_generation",
        user_template="""\
Produce an initial classification and explanation for the task using the evidence.

EVIDENCE
--------
{source_context}
--------

TASK
----
{task_prompt}{output_contract}""",
        components=("provided_evidence", "task_definition", "shared_output_contract"),
    ),
    verification=PromptTemplate(
        strategy="chain_of_verification",
        template_id="scifact_cov_verify_v2",
        version=EVIDENCE_CONTROLLED_VERSION,
        step="verification_generation",
        user_template="""\
Audit the draft against the supplied evidence. Do not write the final answer yet.

EVIDENCE
--------
{source_context}
--------

ORIGINAL TASK
-------------
{task_prompt}

DRAFT
-----
{draft}
-----

VERIFICATION PROCEDURE
----------------------
1. List each material factual claim in the draft.
2. Mark each claim SUPPORTED, CONTRADICTED, or NOT_IN_EVIDENCE.
3. Quote or precisely identify the evidence used for each judgment.
4. Check whether the draft's label follows from those judgments.
5. State the exact corrections needed. Do not add outside knowledge.

Return a concise verification report only.""",
        components=(
            "provided_evidence",
            "draft_review",
            "atomic_claim_checks",
            "evidence_alignment",
            "label_check",
        ),
    ),
    revision=PromptTemplate(
        strategy="chain_of_verification",
        template_id="scifact_cov_final_v2",
        version=EVIDENCE_CONTROLLED_VERSION,
        step="revision_generation",
        user_template="""\
Revise the draft using the verification report and return the final answer only.

EVIDENCE
--------
{source_context}
--------

ORIGINAL TASK
-------------
{task_prompt}

DRAFT
-----
{draft}
-----

VERIFICATION REPORT
-------------------
{verification_report}
-------------------

REVISION RULES
--------------
- Correct the label when the verification report shows it is unsupported.
- Remove or qualify every claim marked CONTRADICTED or NOT_IN_EVIDENCE.
- Use no outside knowledge and add no new factual claims unless the evidence supports them.
- Return only the final label and explanation, not the audit notes.
{output_contract}""",
        components=(
            "provided_evidence",
            "draft_review",
            "verification_report",
            "correction_instruction",
            "evidence_only_constraint",
            "shared_output_contract",
        ),
    ),
)


# Version 3 is an evidence-controlled academic synthesis family. Every
# condition receives the same source set and output contract. The treatments
# vary only the amount of structure and verification applied to that material.
BASELINE_V3 = StrategyDefinition(
    name="baseline",
    version=ACADEMIC_SYNTHESIS_VERSION,
    requires_evidence=True,
    initial=PromptTemplate(
        strategy="baseline",
        template_id="academic_synthesis_baseline_v3",
        version=ACADEMIC_SYNTHESIS_VERSION,
        step="initial_generation",
        user_template="""\
SOURCE MATERIAL
---------------
{source_context}
---------------

TASK
----
{task_prompt}{output_contract}""",
        components=("provided_evidence", "task_definition", "shared_output_contract"),
    ),
)

STRUCTURED_V3 = StrategyDefinition(
    name="structured",
    version=ACADEMIC_SYNTHESIS_VERSION,
    requires_evidence=True,
    initial=PromptTemplate(
        strategy="structured",
        template_id="academic_synthesis_structured_v3",
        version=ACADEMIC_SYNTHESIS_VERSION,
        step="initial_generation",
        user_template="""\
Write an academic synthesis addressing the task from the supplied source material.

SOURCE MATERIAL
---------------
{source_context}
---------------

TASK
----
{task_prompt}

REQUIREMENTS
------------
1. Identify the central proposition that must be evaluated.
2. Compare the relevant findings across the supplied documents.
3. Distinguish support, contradiction, and evidential limitations.
4. Attribute material claims using the supplied document identifiers.
5. Do not invent studies, citations, quotations, statistics, or findings.
6. Keep the synthesis between 120 and 180 words.
{output_contract}""",
        components=(
            "provided_evidence",
            "task_definition",
            "task_decomposition",
            "cross_source_comparison",
            "anti_fabrication_instruction",
            "shared_output_contract",
        ),
    ),
)

SOURCE_GROUNDED_V3 = StrategyDefinition(
    name="source_grounded",
    version=ACADEMIC_SYNTHESIS_VERSION,
    requires_evidence=True,
    initial=PromptTemplate(
        strategy="source_grounded",
        template_id="academic_synthesis_source_grounded_v3",
        version=ACADEMIC_SYNTHESIS_VERSION,
        step="initial_generation",
        user_template="""\
Write an academic synthesis using only the supplied source material.

SOURCE MATERIAL
---------------
{source_context}
---------------

TASK
----
{task_prompt}

GROUNDING RULES
---------------
- Every material factual statement must be supported by a supplied document.
- Cite the supporting document immediately after the relevant statement.
- Use only the document identifiers shown in the source material.
- Do not use outside knowledge or infer findings not established by the text.
- If the sources are insufficient or conflict, state that limitation explicitly.
- Do not invent studies, authors, quotations, statistics, mechanisms, or citations.
- Keep the synthesis between 120 and 180 words.
{output_contract}""",
        components=(
            "provided_evidence",
            "task_definition",
            "evidence_only_constraint",
            "claim_level_grounding",
            "citation_constraint",
            "uncertainty_instruction",
            "shared_output_contract",
        ),
    ),
)

CHAIN_OF_VERIFICATION_V3 = StrategyDefinition(
    name="chain_of_verification",
    version=ACADEMIC_SYNTHESIS_VERSION,
    requires_evidence=True,
    initial=PromptTemplate(
        strategy="chain_of_verification",
        template_id="academic_synthesis_cov_draft_v3",
        version=ACADEMIC_SYNTHESIS_VERSION,
        step="initial_generation",
        user_template="""\
Produce an initial academic synthesis for the task using the supplied material.

SOURCE MATERIAL
---------------
{source_context}
---------------

TASK
----
{task_prompt}{output_contract}""",
        components=("provided_evidence", "task_definition", "shared_output_contract"),
    ),
    verification=PromptTemplate(
        strategy="chain_of_verification",
        template_id="academic_synthesis_cov_verify_v3",
        version=ACADEMIC_SYNTHESIS_VERSION,
        step="verification_generation",
        user_template="""\
Audit the draft against the source material. Do not write the final synthesis yet.

SOURCE MATERIAL
---------------
{source_context}
---------------

ORIGINAL TASK
-------------
{task_prompt}

DRAFT
-----
{draft}
-----

VERIFICATION PROCEDURE
----------------------
1. List every material factual claim in the draft.
2. Identify the supplied document, if any, that supports each claim.
3. Mark unsupported, overstated, contradictory, or ambiguous claims.
4. Check every citation identifier against the supplied documents.
5. Check whether each citation actually supports the statement attached to it.
6. State the exact corrections needed without adding outside knowledge.

Return a concise verification report only.""",
        components=(
            "provided_evidence",
            "draft_review",
            "atomic_claim_checks",
            "citation_validation",
            "evidence_alignment",
        ),
    ),
    revision=PromptTemplate(
        strategy="chain_of_verification",
        template_id="academic_synthesis_cov_final_v3",
        version=ACADEMIC_SYNTHESIS_VERSION,
        step="revision_generation",
        user_template="""\
Revise the draft using the verification report. Return the final synthesis only.

SOURCE MATERIAL
---------------
{source_context}
---------------

ORIGINAL TASK
-------------
{task_prompt}

DRAFT
-----
{draft}
-----

VERIFICATION REPORT
-------------------
{verification_report}
-------------------

REVISION RULES
--------------
- Remove or qualify every unsupported, overstated, or contradictory claim.
- Retain only citations whose identifiers and attributed findings are valid.
- Add no factual claim unless a supplied document supports it.
- State material evidential limitations clearly.
- Keep the synthesis between 120 and 180 words.
- Return only the requested output fields, not the verification notes.
{output_contract}""",
        components=(
            "provided_evidence",
            "draft_review",
            "verification_report",
            "correction_instruction",
            "citation_validation",
            "evidence_only_constraint",
            "shared_output_contract",
        ),
    ),
)


def _with_synthesis_verdict_contract(
    definition: StrategyDefinition,
) -> StrategyDefinition:
    """Create a new prompt version without mutating the frozen v3.0 family."""

    def upgrade(template: Optional[PromptTemplate]) -> Optional[PromptTemplate]:
        if template is None:
            return None
        return replace(
            template,
            template_id=template.template_id.replace("_v3", "_v3_1"),
            version=ACADEMIC_SYNTHESIS_VERDICT_VERSION,
        )

    return replace(
        definition,
        version=ACADEMIC_SYNTHESIS_VERDICT_VERSION,
        initial=upgrade(definition.initial),
        verification=upgrade(definition.verification),
        revision=upgrade(definition.revision),
    )


# Version 3.1 retains the v3 treatment wording and adds a machine-readable
# verdict to the shared output contract. Version 3.0 remains available so the
# completed SciFact synthesis pilots can always be reproduced exactly.
BASELINE_V3_1 = _with_synthesis_verdict_contract(BASELINE_V3)
STRUCTURED_V3_1 = _with_synthesis_verdict_contract(STRUCTURED_V3)
SOURCE_GROUNDED_V3_1 = _with_synthesis_verdict_contract(SOURCE_GROUNDED_V3)
CHAIN_OF_VERIFICATION_V3_1 = _with_synthesis_verdict_contract(
    CHAIN_OF_VERIFICATION_V3
)


def _with_stress_contract(definition: StrategyDefinition) -> StrategyDefinition:
    """Create the longer v3.2 stress family without mutating v3.0 or v3.1."""

    def upgrade(template: Optional[PromptTemplate]) -> Optional[PromptTemplate]:
        if template is None:
            return None
        return replace(
            template,
            template_id=template.template_id.replace("_v3_1", "_v3_2"),
            version=ACADEMIC_STRESS_VERSION,
            user_template=template.user_template.replace(
                "between 120 and 180 words", "between 180 and 250 words"
            ),
        )

    return replace(
        definition,
        version=ACADEMIC_STRESS_VERSION,
        initial=upgrade(definition.initial),
        verification=upgrade(definition.verification),
        revision=upgrade(definition.revision),
    )


# Version 3.2 preserves the v3.1 treatment differences but increases the
# response budget for claim-level factuality measurement in the difficulty
# pilot. Earlier prompt families remain immutable for reproducibility.
BASELINE_V3_2 = _with_stress_contract(BASELINE_V3_1)
STRUCTURED_V3_2 = _with_stress_contract(STRUCTURED_V3_1)
SOURCE_GROUNDED_V3_2 = _with_stress_contract(SOURCE_GROUNDED_V3_1)
CHAIN_OF_VERIFICATION_V3_2 = _with_stress_contract(
    CHAIN_OF_VERIFICATION_V3_1
)


PROMPT_REGISTRY: Dict[str, Dict[str, StrategyDefinition]] = {}
for _definition in (
    BASELINE_V1,
    STRUCTURED_V1,
    SOURCE_GROUNDED_V1,
    CHAIN_OF_VERIFICATION_V1,
    BASELINE_V2,
    STRUCTURED_V2,
    SOURCE_GROUNDED_V2,
    CHAIN_OF_VERIFICATION_V2,
    BASELINE_V3,
    STRUCTURED_V3,
    SOURCE_GROUNDED_V3,
    CHAIN_OF_VERIFICATION_V3,
    BASELINE_V3_1,
    STRUCTURED_V3_1,
    SOURCE_GROUNDED_V3_1,
    CHAIN_OF_VERIFICATION_V3_1,
    BASELINE_V3_2,
    STRUCTURED_V3_2,
    SOURCE_GROUNDED_V3_2,
    CHAIN_OF_VERIFICATION_V3_2,
):
    PROMPT_REGISTRY.setdefault(_definition.name, {})[_definition.version] = _definition


def parse_strategy_spec(spec: str | Mapping[str, Any]) -> tuple[str, str]:
    """Resolve config syntax while preserving legacy string behavior."""
    if isinstance(spec, str):
        return spec.lower().strip(), LEGACY_PROMPT_VERSION
    if not isinstance(spec, Mapping):
        raise ValueError("Each strategy must be a name string or an object")
    name = str(spec.get("name", "")).lower().strip()
    version = str(spec.get("version", "")).strip()
    if not name or not version:
        raise ValueError("Strategy objects must include non-empty name and version")
    return name, version


def strategy_label(spec: str | Mapping[str, Any]) -> str:
    name, version = parse_strategy_spec(spec)
    return f"{name}@{version}"


def resolve_strategy(spec: str | Mapping[str, Any]) -> StrategyDefinition:
    name, version = parse_strategy_spec(spec)
    if name not in PROMPT_REGISTRY:
        available = ", ".join(sorted(PROMPT_REGISTRY))
        raise ValueError(f"Unknown strategy: {name}. Available strategies: {available}")
    if version not in PROMPT_REGISTRY[name]:
        versions = ", ".join(sorted(PROMPT_REGISTRY[name]))
        raise ValueError(
            f"Unknown version {version!r} for strategy {name!r}. "
            f"Available versions: {versions}"
        )
    return PROMPT_REGISTRY[name][version]


def _output_contract(task: Task, strategy_version: Optional[str] = None) -> str:
    if task.metadata.get("task_type") == "scientific_claim_verification":
        return SCIFACT_OUTPUT_CONTRACT
    if task.metadata.get("task_type") == "academic_evidence_synthesis":
        if strategy_version == ACADEMIC_STRESS_VERSION:
            return SYNTHESIS_STRESS_OUTPUT_CONTRACT
        if strategy_version == ACADEMIC_SYNTHESIS_VERDICT_VERSION:
            return SYNTHESIS_VERDICT_OUTPUT_CONTRACT
        return SYNTHESIS_OUTPUT_CONTRACT
    return ""


def _variables_for_task(
    task: Task,
    *,
    strategy_version: Optional[str] = None,
    draft: Optional[str] = None,
    verification_report: Optional[str] = None,
) -> Dict[str, Any]:
    variables: Dict[str, Any] = {
        "task_prompt": task.prompt,
        "source_context": task.source_context,
        "output_contract": _output_contract(task, strategy_version),
    }
    if draft is not None:
        variables["draft"] = draft
    if verification_report is not None:
        variables["verification_report"] = verification_report
    return variables


def build_prompt_plan(
    strategy: str | Mapping[str, Any],
    task: Task,
) -> PromptPlan:
    definition = resolve_strategy(strategy)
    if definition.requires_evidence and not task.source_context:
        raise ValueError(
            f"{definition.name}@{definition.version} requires task.source_context"
        )
    first_prompt = definition.initial.render(
        _variables_for_task(task, strategy_version=definition.version)
    )
    return PromptPlan(definition=definition, first_prompt=first_prompt, task=task)


def registry_manifest() -> Dict[str, Any]:
    return {
        "registry_version": PROMPT_REGISTRY_VERSION,
        "legacy_string_default": LEGACY_PROMPT_VERSION,
        "strategies": {
            name: {
                version: definition.metadata()
                for version, definition in sorted(versions.items())
            }
            for name, versions in sorted(PROMPT_REGISTRY.items())
        },
    }
