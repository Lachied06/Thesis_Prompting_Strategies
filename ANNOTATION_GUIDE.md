# Benchmark and Response Annotation Guide

This is a retained protocol and optional workflow reference, not proof that any particular audit or human validation was completed. The shipped final endpoint is automated and not independently validated across the full dataset. Approved [Appendix G data-only exports](electronic_appendices/G_Human_Audit/README.md) now preserve the later 40-response/433-claim researcher audit with distinct assessment stages; original XLSX files remain external. The original automated endpoint is unchanged. See [README.md](README.md) for current scope and [PILOT_WORKFLOWS.md](PILOT_WORKFLOWS.md) for historical audit states, including a missing reviewed CSV version.

Use this guide before final data collection. Record decisions in the generated
CSV files; do not edit model outputs or benchmark text.

## A. Pre-run benchmark audit

Run `audit_benchmarks.py create` before any final experiment. The audit file
contains no model responses, so inclusion decisions cannot be based on model
success or failure.

For every task, mark:

- `claim_clear`: **yes** when the claim has a reasonably unambiguous grammatical
  and semantic reading; otherwise **no**.
- `evidence_addresses_claim`: **yes** when the supplied passage directly bears
  on the central assertion, even if the correct outcome is contradiction;
  otherwise **no**.
- `gold_label_supported`: **yes** when the reference label follows from the
  supplied evidence under the experiment's label definitions; otherwise **no**.
- `include`: apply the predefined rule below.

Recommended inclusion rule: include only when all three quality checks are
`yes`. If a task is excluded, choose a concise reason such as
`ambiguous_claim`, `evidence_mismatch`, `label_mismatch`, or `missing_evidence`.
Apply the same rule to every task and report all exclusions.

An audit does not prove a benchmark is incorrect. It records whether this
specific task/evidence adaptation is suitable for the experiment.

For an academic synthesis task, apply the same checks to the complete supplied
source set. `evidence_addresses_claim` can be yes when at least one document
materially bears on the claim and the remaining documents are legitimate
comparison material. `gold_label_supported` concerns the underlying SciFact
relationship used to construct the synthesis task; the model is not shown that
label in the requested output.

## B. Reviewer response review

Generate `manual_review.csv` with `evaluate_results.py`. Review only the final
answer in each experimental condition; use the trace separately for CoV process
analysis.

For formal data collection, use `evaluate_results.py --blind-review` instead.
It creates a randomized `manual_review.blinded.csv` and a separate private
mapping file. Give reviewers only the blinded CSV; do not reveal the mapping,
strategy, model, prediction, ground truth, or correctness until annotation is
complete. Use the same `--review-seed` when documenting or reproducing the
review package. The pilot guide describes aggregation with `--annotations` and `--review-map`.

Record whether each review stage was human, AI-assisted, independently
double-reviewed, or adjudicated. AI-assisted pilot annotations must not be
reported as independent human judgments.

### Faithfulness score

- **2 — fully faithful:** every material factual claim in the explanation is
  supported by the supplied evidence and the evidence is represented fairly.
- **1 — partly faithful:** the central conclusion is evidence-aligned, but the
  explanation contains a minor unsupported detail, overstatement, or omission
  that does not reverse the overall meaning.
- **0 — materially unfaithful:** a central claim is unsupported, contradicts the
  evidence, substantially distorts the source, or relies on invented evidence.

### Binary error fields

Enter `yes` or `no` for every field:

- `unsupported_claim`: at least one factual statement is not established by the
  supplied evidence.
- `source_misrepresentation`: the answer reverses, overstates, or materially
  changes what the source reports.
- `fabricated_citation`: the answer invents a citation, study, identifier,
  quotation, or attribution not present in the task. For synthesis responses,
  mark yes when an identifier was not supplied or the answer invents a named
  study/source. A valid supplied identifier attached to a finding that the
  document does not contain is primarily `source_misrepresentation`; both may
  be marked when both errors genuinely occur.
- `excessive_abstention`: the answer selects `NO_EVIDENCE`, refuses to
  synthesise, or claims the sources are unusable even though they clearly
  support or contradict the central claim.
- `ambiguous_task`: the item is difficult to score reliably because the claim,
  evidence, or label mapping is ambiguous. This does not automatically change
  the benchmark audit after results are seen.

Use `reviewer_notes` for the exact unsupported phrase, the relevant evidence,
and the reason for difficult decisions.

The automated invalid-citation check is only a reviewer aid. It can establish
that a document ID was not supplied, but it cannot establish that a valid ID
semantically supports the sentence in which it appears.

## C. Automated atomic-claim consensus

The v3.8 default is a fully automated two-judge protocol. The primary model
extracts only subject-matter factual propositions and labels them against the
supplied source. The secondary model sees the same claim inventory, cannot add
or rewrite claims, and independently assigns support and citation labels.

Use `evaluate_atomic_claims.py consensus` or the pilot wrapper's `judge`
action. A claim is `CONSENSUS_UNSUPPORTED` only when both judges mark it
unsupported. If either judge does, it is also marked `possible_unsupported` for
sensitivity analysis. Support disagreements outside the shared unsupported category remain `UNCERTAIN`;
both unsupported labels yield consensus even when the exact labels differ.
Citation-label disagreements separately yield citation `UNCERTAIN`.

The protocol excludes verdict labels, task restatements, statements about what
a source says or omits, and other evaluation commentary from the subject-matter
hallucination denominator. It also requires source-explicit identity evidence
before treating similar names or aliases as the same entity.

Report the judge models, exact prompts, agreement, uncertain rate, conservative
consensus rate, and sensitivity rate. Describe these results as AI-assisted
measurement, not independent human ground truth.

## D. Optional external validation review

The legacy workflow uses a source-only LLM judge to split each final synthesis into
minimal factual claims. Its output is AI-assisted measurement, not independent
human ground truth. `evaluate_atomic_claims.py judge` therefore creates a
blinded validation CSV containing one randomly selected response from every
model × strategy × difficulty cell.

For every row, assign `reviewer_support_label`:

- `SUPPORTED`: the proposition is directly established by the supplied source
  material.
- `CONTRADICTED`: the supplied sources are inconsistent with the proposition.
- `NOT_IN_SOURCES`: the proposition is neither established nor contradicted by
  the supplied sources.
- `NOT_FACTUAL`: the text is not an externally checkable factual proposition.

Assign `reviewer_citation_label`:

- `SUPPORTED`: at least one citation attached to the proposition supports it.
- `UNSUPPORTED`: attached supplied citation IDs do not support it.
- `NO_CITATION`: a factual proposition has no attached citation.
- `NOT_APPLICABLE`: use only for `NOT_FACTUAL` rows.

Review the proposition in the context of the complete response, but judge it
only against the supplied source material. Do not use subject-matter knowledge
to fill gaps. Keep `atomic_review.mapping.json` away from reviewers until all
labels are complete; it contains model, strategy, and automatic judge labels.

The validation report gives exact four-way label agreement, binary unsupported
agreement, and citation-label agreement. Report these values alongside all
automatic results. Low agreement means the automatic endpoint is not reliable
enough for final inference. This section applies only if an external review is
actually performed; do not imply otherwise.

## Optional human-review calibration procedure

1. Have reviewers independently annotate the same small, strategy-balanced
   sample.
2. Discuss disagreements using this guide, then clarify the guide without
   looking at aggregate condition performance.
3. Re-annotate a fresh shared sample.
4. Report the reviewer count, overlap size, agreement statistic, adjudication
   method, and final scoring rule in the thesis.
5. Where possible, blind reviewers to strategy names and randomize row order.

The current evaluator aggregates completed judgments but does not claim that a
deterministic script can reliably decide semantic faithfulness.
