# Prompt Treatment Design

This document preserves the treatment history. The final confirmatory study uses v3.2.0; older task families remain separate. [README.md](README.md) documents the completed study, parser caveats and later sampled researcher review, whose approved data-only records are now in [Appendix G](electronic_appendices/G_Human_Audit/README.md); original XLSX sources remain external. No prompt code was changed during cleanup.

## Experimental principle

For evidence-relative claim verification, task content, evidence, model
configuration, and output contract must remain fixed. The prompting strategy is
the treatment. SciFact v2 therefore supplies the identical evidence block to
all four conditions.

The original v1 family is retained for historical reproducibility, but it must
not be used to claim a controlled prompt-only comparison on SciFact because
evidence access differed between conditions.

## SciFact v2 components

| Condition | Same evidence | Task decomposition | Evidence-only rule | Uncertainty rule | Explicit claim audit | Requests |
|---|---:|---:|---:|---:|---:|---:|
| Baseline v2 | Yes | No | No | Shared output rule only | No | 1 |
| Structured v2 | Yes | Yes | No | Yes | No | 1 |
| Source-grounded v2 | Yes | Limited | Yes | Yes | No | 1 |
| Chain-of-verification v2 | Yes, every stage | During audit | Final revision only | Via evidence checks | Yes | 3 |

The shared SciFact output contract is measurement scaffolding:

```text
LABEL: SUPPORT | CONTRADICT | NO_EVIDENCE
EXPLANATION: <brief justification>
```

## Operational definitions

### Baseline v2

The model receives the evidence, task, and shared output contract. It receives
no explicit grounding, anti-fabrication, decomposition, or verification rule.

### Structured v2

The model receives the same evidence and an ordered decision procedure. It is
asked to identify the central assertion, determine whether the evidence
addresses it, choose a label, explain uncertainty, and avoid fabrication.

### Source-grounded v2

The model receives the same evidence plus the strongest direct treatment: each
factual statement must be evidence-supported, outside knowledge is forbidden,
and gaps must resolve to `NO_EVIDENCE` rather than inference.

### Chain-of-verification v2

Three stateless calls are made:

1. Draft a classification using the evidence.
2. Audit each material claim against the same evidence, check the label, and
   produce correction instructions without giving a new final answer.
3. Revise using the original evidence, draft, and verification report.

Separating verification from revision makes it possible to inspect whether the
audit identified a problem and whether the final step acted on it. The harness
records each realised request and response in order.

## Academic synthesis v3

The v3 family turns SciFact source sets into a more generative academic-writing
task. Each condition receives the same claim and the same supplied documents,
including the same relevant and supplementary material. The model must write a
120–180 word synthesis and identify the supplied document IDs it used.

The shared output contract is:

```text
SYNTHESIS: <a 120–180 word academic paragraph>
CITED_DOCUMENTS: <comma-separated supplied document IDs used, or NONE>
```

| Condition | Same sources | Task decomposition | Evidence-only rule | Citation constraint | Explicit verification | Requests |
|---|---:|---:|---:|---:|---:|---:|
| Baseline v3 | Yes | No | No | Shared output rule only | No | 1 |
| Structured v3 | Yes | Yes | No | Yes | No | 1 |
| Source-grounded v3 | Yes | Limited | Yes | Strong | No | 1 |
| Chain-of-verification v3 | Yes, every stage | During audit | Final revision only | Audited before revision | Yes | 3 |

The harness extracts document identifiers from the final response. An ID not
present in the task's `allowed_document_ids` is an automatically detectable
invalid citation. This is deliberately narrower than semantic citation
faithfulness: a valid supplied ID can still be attached to a claim that the
document does not support, which requires semantic assessment rather than an ID check.
The final study uses automated semantic judges; a later separate researcher
review is now represented by approved Appendix G data-only exports; its original
XLSX files remain external and it does not replace the automated endpoint. Bare numeric inline IDs are a
known parser limitation; see the README.

The v2 classification and v3 synthesis conditions must be analysed separately.
They use different task formats and output contracts, so a v3 score is not a
direct continuation of a v2 condition.

## Academic synthesis v3.1

Version 3.1 retains the four v3 treatment packages and adds one
machine-readable field to the shared synthesis contract:

```text
VERDICT: SUPPORT | CONTRADICT | NO_EVIDENCE
SYNTHESIS: <a 120–180 word academic paragraph>
CITED_DOCUMENTS: <comma-separated supplied document IDs used, or NONE>
```

The verdict enables objective label accuracy, confusion matrices, abstention
rates alongside the reviewer faithfulness assessment. The legacy CoV draft-label
helper does not parse the v3.x `VERDICT` contract; the saved confirmatory
label-change maps are empty and do not establish absence of changes. It is measurement scaffolding shared by all four
conditions, not an additional mitigation instruction.

Version 3.0 remains registered and unchanged for exact reproduction of the
completed SciFact synthesis pilots. New synthesis experiments that require
classification accuracy should explicitly select v3.1 in their config.

## Academic synthesis v3.2 difficulty pilot

Version 3.2 keeps the four v3.1 treatment packages and verdict field, but
expands the shared synthesis target to 180–250 words. This creates enough
substantive propositions to measure factuality at the atomic-claim level. It
does not add a stronger mitigation instruction to any one condition.

```text
VERDICT: SUPPORT | CONTRADICT | NO_EVIDENCE
SYNTHESIS: <a 180–250 word academic paragraph>
CITED_DOCUMENTS: <comma-separated supplied document IDs used, or NONE>
```

The task instruction also requests four to six substantive factual claims
where the sources permit. Models must not invent filler when the evidence is
insufficient. All prompt strategies receive the same task-specific evidence
packet, model settings, and output contract. The evidence packet varies only
across the predeclared difficulty categories, not across prompt treatments.

The primary v3.2 outcome is the mean per-response proportion of factual atomic
claims that both source-only judges label `CONTRADICTED` or `NOT_IN_SOURCES`.
The either-judge proportion is retained as a sensitivity endpoint, and supported
factual claims per response is reported to distinguish genuine mitigation from
brevity or excessive abstention. Verdict accuracy remains secondary because a
correct verdict can coexist with unsupported details in the synthesis.

## Version behavior

Prompt IDs and wording are immutable after data collection. Every prompt has a
stable template ID, semantic version, component list, step name, registry
version, and rendered SHA-256 hash.

- Config strings resolve to v1.0.0 for backward compatibility.
- Config objects select a version explicitly.
- Revised wording requires a new semantic version and template ID.
- Historical results must never be relabelled as a newer treatment.

## Interpretation limits

These are four complete treatment packages, not a factorial isolation of every
sentence. A difference can be attributed to the configured strategy as a
whole, but not automatically to one individual instruction within it.

CoV also uses more calls and tokens. Report effectiveness alongside request
count, token use, and latency rather than treating the conditions as equal-cost.
