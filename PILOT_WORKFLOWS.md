# Historical pilot workflows and provenance

This supplementary guide preserves substantive methodology from the former README and the externally archived author checklists (original filenames: `NEXT_STEPS.md`, `STRESS_PILOT_NEXT_STEPS.md`, `HALUEVAL_NEXT_STEPS.md`, `DIFFICULTY_PILOT_NEXT_STEPS.md`). Those originals are not shipped; they remain in the verified external archive and complete pre-cleanup backup. Their next-step status statements have been checked against the supplied files. The final confirmatory study is described in [README.md](README.md), not inferred from pilot names or intended counts.

All historical commands below are reference examples for separate working copies. They are not required to reproduce the submitted confirmatory reports, and none were executed during cleanup. Use temporary output paths for any independent offline check; never overwrite frozen data/audits/results. Every Python command should use `PYTHONDONTWRITEBYTECODE=1`. Live commands require separate authorisation and provider access.

## Evidence control and prompt history

The v1 pilot was confounded for a prompt-only comparison: baseline, structured and CoV lacked SciFact evidence while source-grounded received it. v2 classification supplies identical evidence to all four strategies, with `LABEL` and `EXPLANATION`; CoV uses draft, evidence audit and revision across three stateless calls. A config string such as `"baseline"` still resolves to v1.0.0; explicit objects select v2.0.0 or a synthesis version.

v3.0 synthesis uses 120–180 words and supplied document identifiers. v3.1 adds an explicit `VERDICT`; v3.2 extends the common contract to 180–250 words and requests four to six substantive claims where evidence permits. These are different task/measurement contracts and should not be pooled as one experimental condition. [PROMPT_DESIGN.md](PROMPT_DESIGN.md) and [CHANGELOG.md](CHANGELOG.md) preserve the design and version history.

## Supplied pilot artifacts and actual approval states

| Workflow | Candidate / approved counts | Recorded construction and caveats |
|---|---|---|
| SciFact classification | 10 / 8 | Original 10-task preparation; two exclusions (evidence mismatch, ambiguous claim). Reviewed audit is `audits/scifact_dev_10.audit.reviewed.csv`; `results/scifact_dev_10.jsonl` is historical, not part of final 800 |
| SciFact initial synthesis | 12 / **7** | Seed 42, stratified labels, three documents per base packet, 120–180 words, v3.0. Actual approved labels: 2 SUPPORT, 3 CONTRADICT, 2 NO_EVIDENCE. Filename `_12` does not mean 12 approved |
| SciFact synthesis stress | 18 / 14 | Seed 20260922; stratified sampling, unique primary documents, earlier claim exclusions, five abstracts; 120–180-word v3.0 contract. Approved: 4 SUPPORT, 6 CONTRADICT, 4 NO_EVIDENCE |
| SciFact difficulty | 12 / 12 | Three tasks per difficulty category, 180–250 words, two model snapshots/four v3.2 strategies. Actual labels: 3 SUPPORT, 4 CONTRADICT, 5 NO_EVIDENCE; pilot category labels do not imply all partial packets are native NO_EVIDENCE |
| HaluEval synthesis | 20 / 14 | Seed 20260922; deterministic proposed-answer construction and source IDs; v3.1. Approved: 8 SUPPORT, 6 CONTRADICT. Audit is explicitly AI-assisted |

Sources are the relevant processed/approved JSONL, `data/design/scifact_difficulty_pilot_12.design.json`, and the five approved `*.audit_manifest.json` files. Initial-synthesis exclusions in its manifest are one each of `ambiguous_claim_and_label_mismatch`, `label_mismatch`, `endpoint_mismatch`, `scope_mismatch` and `entity_mismatch`. The stress audit excludes two evidence mismatches, one label mismatch and one ambiguous claim before model calls. HaluEval excludes six candidates with task-specific evidence/label/clarity concerns recorded verbatim in its audit and manifest.

The initial synthesis CSV currently shipped at `audits/scifact_synthesis_pilot_12.audit.csv` has 12 blank decision rows. Its hash does **not** match the reviewed version recorded by `data/approved/scifact_synthesis_pilot_12.audit_manifest.json`: recorded audit hash `15ad84afdff71940fcdf7acf63950024b1b699e4f0aca86a5725f67cb33bce82`, current CSV hash `41ddb8ade4e2b4cba9526aa252a9226b43f68c82a623dec93e6bc0a743c689a4`. Source-data and approved-output hashes do match that manifest. The reviewed CSV version cannot be reconstructed or claimed present. All other shipped pilot audit manifests match their referenced current source/audit/output bytes. This is a historical provenance gap, not a checksum failure introduced by cleanup; no audit or manifest was changed.

The difficulty audit marks all 12 included and explicitly identifies AI-assisted review in notes. The stress and HaluEval audits are AI-assisted, not independent expert validation. No completed confirmatory pre-run audit file is included. The external checklists' intended future expert spot-checks are not evidence they occurred.

## Sampling, packet transformations and pilot-specific differences

`prepare_benchmarks.py` adapts raw SciFact and HaluEval. `scifact-synthesis` supports label-stratified sampling, `--exclude-task-file` repeated for previous claim exclusions, and `--unique-primary-documents`. The latter constrains primary source reuse, not all supplementary abstracts. Supplementary documents use weighted lexical overlap, with seeded tie handling as described in the README. The saved stress metadata confirms exclusion of all 12 source claims in `data/processed/scifact_synthesis_pilot_12.jsonl`, with that input's hash retained; it excludes the candidate pool rather than only the seven approved items.

The difficulty pilot uses three direct-control claims paired with three omission versions; three other claims supply near-match tasks; three supply the historical partial/conflicting category. The design names source IDs 143, 1140 and 516 for direct/omission; 619, 859 and 1019 for near-match; and 1266, 1132 and 1213 for partial/conflicting. It includes a deliberate `reference_label_override: NO_EVIDENCE` for claim 1266, described as a compound claim requiring scope qualification. Other descriptions refer to TCR/CD3 necessity wording and myeloid/monocyte mechanisms. These are intended diagnostic choices, not automated conflict-generation guarantees. The final confirmatory partial stratum instead uses 25 native NO_EVIDENCE claims with no override.

`gold_only` retains evidence IDs; `full_distractor_first` moves supplementary IDs before primary IDs; `omit_gold` removes annotated evidence IDs and assigns NO_EVIDENCE. Removing known evidence does not verify semantic insufficiency of every remaining abstract. The small difficulty pilot is exploratory, with three tasks per stratum, not a powered confirmatory significance test. The preserved design states selection did not consult model outputs; this is a local design record, not external registration evidence.

## Historical run sizes and request accounting

For one model and all four v2/v3 strategies, N tasks produce 4N final responses and 6N generation calls. Therefore 12 hypothetically approved initial synthesis tasks would produce 48 responses/72 calls, but the shipped approved file has seven tasks: the configured one-model run would have 28 responses/42 calls. The old checklist's 48/72 figures were conditional, not verified completed counts.

The 14-task stress pilot plans 56 responses/84 generation calls. HaluEval plans 56 responses/84 generation calls, a one-task smoke test with four responses/six calls, and 112 initial judge calls plus retries. The two-model difficulty pilot plans 96 responses/144 generation calls; its smoke test plans eight responses/12 calls; judging plans 192 initial requests plus retries. The wrapper checks completion counts before evaluation. These are configured/planned counts. The pre-appendix package lacked complete corresponding live pilot folders. [Appendix F](electronic_appendices/F_Pilots/README.md) now contains 56 recovered completed HaluEval responses and historical reviewer records; these do not establish independent human validation or complete atomic dual judging. Other unprovided pilot outputs remain unverified.

Only the confirmatory main, preview and smoke folders are supplied under `outputs/`. Example paths such as `outputs/scifact_v2_pilot/`, `outputs/scifact_synthesis_v3_pilot/`, `outputs/scifact_synthesis_stress_v3_pilot/`, `outputs/scifact_difficulty_pilot_v3_2/` and `outputs/halueval_synthesis_v3_1_pilot/` are historical/generated locations, not directories promised in this package. Approved datasets and audit files are retained even when live pilot results are absent.

## Preparation, auditing and execution examples

The original 12-candidate synthesis preparation was:

```bash
PYTHONDONTWRITEBYTECODE=1 python3.12 prepare_benchmarks.py scifact-synthesis \
  --claims data/raw/scifact/data/claims_dev.jsonl \
  --corpus data/raw/scifact/data/corpus.jsonl \
  --output /path/to/empty-working-directory/synthesis_candidates.jsonl \
  --limit 12 --seed 42 --documents-per-task 3 --sampling stratified
```

`/path/to/empty-working-directory` is an explicit placeholder outside the submission. This example documents parameters; it is not an instruction to recreate approved records. `audit_benchmarks.py create --data INPUT --output AUDIT.csv` creates task/evidence rows without responses. `apply --data INPUT --audit AUDIT.csv --output APPROVED.jsonl` accepts only completed consistent decisions and writes input/audit/output hashes. The inclusion rule is yes only if claim clarity, evidence relevance and reference-label support are all yes; exclusions require reasons. The current blank initial-synthesis audit cannot reproduce the historical approval decision.

`run_experiment.py --config CONFIG --data APPROVED.jsonl --output NEW/results.jsonl --preview-prompts` renders without SDKs, credentials or network. Open the resulting Markdown in an editor; do not execute a Markdown filename as a shell command. Without `--preview-prompts` the command is live and costly. Use the appropriate retained configuration from the README map.

The `run_halueval_pilot.py` wrapper supports preview, smoke, run, judge and all. `run_difficulty_pilot.py` additionally supports repair. Difficulty repair reads prior consensus, retains primary/successful secondary decisions, retries failed/missing secondary work and writes a distinct `atomic_consensus_v3_8_repaired` folder with cumulative usage/error records and stratum tables. It is not an offline report-only operation. The historical planned judge output set comprises primary/secondary judgments, consensus JSONL/summary/report and exact primary/secondary prompt logs.

## Optional review, reparse and endpoints

`evaluate_results.py --results INPUT --output-dir NEW --blind-review --review-seed SEED` creates `manual_review.blinded.csv` and `manual_review.mapping.json`. Initial synthesis/classification examples used seed 20260921; stress/HaluEval examples used 20260922. Keep mappings from reviewers until annotation completes. Aggregate completed rows with `--annotations COMPLETED.csv --review-map MAPPING.json --output-dir NEW`; the evaluator rejects zero completed rows. These optional files are not shipped completed evidence of a human audit.

`reparse_results.py --results INPUT --output NEW/results.reparsed.jsonl` is an offline historical repair tool. It preserves raw text and run IDs while recalculating parsed fields; existing review mappings can still refer to those run IDs. It was not run during cleanup because submitted parsed records are frozen. `review_disagreements.csv` is generated by the optional atomic review comparison workflow, not included here. [ANNOTATION_GUIDE.md](ANNOTATION_GUIDE.md) provides reviewer support/citation labels, calibration, blinding and provenance reporting. The later researcher sample is separately documented by approved [Appendix G data-only records](electronic_appendices/G_Human_Audit/README.md), with original XLSX sources retained externally; it does not replace the frozen automated analysis.

The exploratory difficulty endpoint is the mean per-response proportion marked unsupported by both judges (`CONTRADICTED` or `NOT_IN_SOURCES`). Either-judge flags are sensitivity results; both non-factual excludes an item, while disagreement remains uncertain. Additional outcomes include any-error response rates, supported yield, type/agreement, citation support/coverage, verdict accuracy, abstention, invalid IDs, tokens and latency. Report rates, counts and effect directions for small pilots; do not tune task selection after observing a winning strategy. A null result can reflect limited effects or measurement/sample limitations and is not proof of equivalence. Current inference and human-review boundaries are in the README.

## Other retained historical material

TruthfulQA generation CSV and its adapter/config remain for background and historical QA workflows; they do not enter the final SciFact study. `config.json` is a legacy v1 example. `data/sample_tasks.jsonl` is illustrative. Earlier `results/` records have historical schema/treatment semantics and must not be merged into current schema-v3 confirmatory inference.
