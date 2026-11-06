# Confirmatory research design

This retained local design document describes the original automated study. It does not establish external prospective preregistration. The completed package and actual task-construction caveats are documented in [README.md](README.md) and [CODE_GUIDE.md](CODE_GUIDE.md). The shipped endpoint is automated and not independently validated across the full dataset; a later separate sampled researcher review is now represented by approved [Appendix G data-only records](electronic_appendices/G_Human_Audit/README.md), while the original XLSX workbooks remain external and the original automated analysis is unchanged.

## Scope and research questions

The confirmatory study evaluates complete prompting strategies for
evidence-grounded academic synthesis. It does not attempt to identify the effect
of an individual sentence inside a prompt package.

**RQ1.** To what extent do structured, source-grounded, and
chain-of-verification prompting strategies reduce unsupported or
source-inconsistent claims relative to a baseline prompt?

**RQ2.** How do the strategy effects vary across hallucination type, model
capability, and evidence difficulty?

**RQ3.** What trade-offs do the strategies create in verdict accuracy,
supported content, citation support, abstention, token consumption, and latency?

The claims supported by this study are limited to source-grounded academic
synthesis. The citation measures cover invalid supplied-document identifiers and
claim-source mismatch. They do not establish whether a model would fabricate a
plausible-looking bibliographic reference in an unconstrained citation-generation
task.

## Confirmatory design

The final SciFact study contains 100 frozen tasks, with 25 tasks in each
predeclared evidence-difficulty stratum:

| Stratum | Purpose |
|---|---|
| Direct control | Establishes basic synthesis and verdict competence with decisive evidence |
| Near-match distractors | Tests source selection and attribution when related material competes with the gold source |
| Evidence omission | Tests whether the model infers beyond the supplied sources and whether it abstains appropriately |
| Conflicting or partial evidence | Tests qualification, scope control, and resistance to overstatement |

Every task is crossed with two fixed model snapshots and four frozen v3.2 prompt
strategies. This produces 800 final responses. Run order is shuffled with a fixed
seed. Every strategy receives the same task, source packet, word range, output
contract, and model settings. Prompt wording must not be changed after the final
dataset is generated.

The pre-appendix package contained the 14 approved HaluEval tasks and audit but
lacked their complete run records. [Appendix F](electronic_appendices/F_Pilots/README.md)
now preserves 56 recovered historical responses and reviewer records. These do
not establish completed atomic dual judging or independent human validation;
the pilot remains exploratory and outside the confirmatory 800 responses.

## Prompt treatments

| Treatment | Experimental interpretation |
|---|---|
| Baseline | Evidence and output contract without explicit mitigation structure |
| Structured | Ordered task decomposition, explicit uncertainty handling, and anti-fabrication instructions |
| Source-grounded | Strong evidence-only constraint and requirement that factual statements be source-supported |
| Chain-of-verification | Draft, separate evidence audit, and revision across three requests |

These are complete treatment packages. A difference may be attributed to the
configured strategy as a whole, not to an individual instruction. Chain of
Verification also receives more requests and computation, so effectiveness must
always be reported alongside tokens, latency, and request count.

## Outcome definitions

The response is decomposed into atomic subject-matter factual claims. A primary
judge extracts the fixed claim inventory and labels it, and a secondary judge
independently labels the same claims without seeing the primary labels.

### Primary endpoint

The primary endpoint is the mean per-response proportion of factual atomic
claims that both judges classify as `CONTRADICTED` or `NOT_IN_SOURCES`. The
response, rather than an individual claim, is the analysis unit so verbose
strategies do not receive disproportionate weight.

### Sensitivity and secondary endpoints

- Possible unsupported-claim proportion: either judge flags the claim.
- Responses containing at least one consensus or possible unsupported claim.
- Judge disagreement rate, retained as `UNCERTAIN` rather than forced into a
  binary label.
- Consensus-supported factual claims per response, which measures useful
  supported content and prevents abstention or brevity from appearing
  automatically superior.
- Verdict accuracy, label coverage, confusion matrix, overall `NO_EVIDENCE`
  prediction rate, false `NO_EVIDENCE` rate on decisive SUPPORT/CONTRADICT tasks,
  and recall against dataset-assigned `NO_EVIDENCE` labels. The packet builder
  does not semantically verify insufficiency of expanded or omission packets.
- Claim citation coverage, semantic citation-support rate, invalid supplied-ID
  rate, and responses containing an invalid identifier.
- Response word count, factual-claim count, token usage, request count, and
  latency.

### Hallucination types

Each unsupported claim receives one dominant type from each judge:

- `UNSUPPORTED_ADDITION`
- `SOURCE_CONTRADICTION`
- `EVIDENCE_OVERSTATEMENT`
- `ENTITY_CONTEXT_CONFUSION`
- `OTHER`

A type is treated as consensus only when both judges agree that the claim is
unsupported and agree on the type. Otherwise, the claim is retained as
`UNCERTAIN_TYPE`. Citation mismatch is measured separately through
`citation_status`; the parser compares recognised identifiers with the supplied
set. Its bare numeric inline-citation blind spot is documented in the README.

## Analysis plan

1. Compare every strategy with baseline on the same tasks within each model.
2. Report absolute paired differences for the conservative consensus endpoint
   and the possible-unsupported sensitivity endpoint.
3. Report deterministic paired cluster-bootstrap 95% intervals for the principal
   differences, clustering direct and evidence-omission transformations by their
   original SciFact source item. These intervals describe source-task sampling
   uncertainty conditional on the automated labels; they do not validate judge
   accuracy.
4. Report results overall and separately for each evidence-difficulty stratum.
5. Report hallucination-type distributions, citation outcomes, verdict accuracy,
   supported-claim yield, and cost beside the hallucination outcomes.
6. Preserve both judge thresholds. Do not select the threshold that gives the
   preferred strategy ranking.
7. Emphasise effect magnitudes and consistency across models and difficulty
   strata. Any sampling uncertainty is conditional on the automated labels and
   does not validate the judges as human ground truth.

## Interpretation rules

| Result pattern | Interpretation |
|---|---|
| Lower consensus and possible unsupported rates without material loss of accuracy or supported content | Effective mitigation |
| Lower hallucination rate with lower accuracy, excessive abstention, or lower supported-claim yield | Caution/completeness trade-off |
| Direction differs by model, difficulty, or judge threshold | Mixed or context-dependent effect |
| Little consistent difference from baseline | No clear mitigation effect |
| Improvement occurs only with disproportionate request, token, or latency cost | Inefficient mitigation |
| Unsupported content increases | Counterproductive under the tested condition |

## Validity limits

- Evaluation is automated and AI-assisted. It is not human-validated ground
  truth.
- The two judges share the same supplied evidence and a fixed rubric, but may
  still make correlated errors.
- The study estimates the effects of prompt packages within two fixed model
  snapshots and one primary academic-synthesis task family.
- One generated response is collected per task-model-strategy cell; the study
  estimates variation across tasks rather than repeated-sampling variability.
- The experiment measures evidence-relative faithfulness. It does not verify
  every generated proposition against all external scientific knowledge.

## Design-freeze checklist

- Freeze the 100-task source packets and their hashes before model generation.
- Confirm 25 tasks in every difficulty stratum.
- Confirm both model snapshots and all four strategies are present.
- Preview prompts and verify that evidence, output contract, and word range are
  identical across treatments within a task.
- Record exact prompt hashes and all Chain-of-Verification stages.
- Require all 800 final responses to complete before the primary analysis.
- Run both automated judges with strategy/model identities omitted from their
  prompts; response wording may still reveal stylistic clues.
- Preserve parse failures, retries, disagreements, usage, and exact judge
  prompts.
- Generate objective, consensus, difficulty, type, supported-yield, and cost
  tables before interpreting strategy rankings.
