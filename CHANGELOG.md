# Historical changelog

The following version notes are preserved from the pre-cleanup README in their original reverse chronology. They describe changes and intended workflows at those times, not proof that every referenced artifact or review is shipped. Current scope, verified counts, parser limitations and later researcher-review disclosure are in [README.md](README.md). The research-design freeze and metadata are not evidence of an external prospective registration. No historical code was patched during documentation cleanup.

## What changed in v3.9.1

- Live generation now supports `--resume`: completed logical jobs are retained,
  failed or missing jobs are retried, and duplicate result/prompt rows are
  compacted before execution.
- Resume checks the existing manifest's configuration and dataset hashes before
  making any API call, preventing an interrupted study from being continued
  with changed frozen inputs.
- Dual-judge consensus now checkpoints every prompt and judgment immediately.
  `consensus --resume` retains parsed judgments and retries only failed or
  missing primary and secondary decisions.
- `run_confirmatory_study.py all --resume` resumes both expensive stages and
  safely rebuilds deterministic objective and integrated reports.

## What changed in v3.9

- The dual-judge evaluator now assigns a dominant hallucination type to every
  unsupported claim: unsupported addition, source contradiction, evidence
  overstatement, entity/context confusion, or other.
- Type-level findings require both judges to agree that the claim is unsupported
  and agree on the type; other cases remain `UNCERTAIN_TYPE`.
- Consensus reports now show supported factual claims per response and mean
  per-response unsupported-claim rates, preventing a shorter or more abstaining
  strategy from appearing automatically superior.
- `build_study_report.py` combines factuality, citation, verdict, abstention,
  content-yield, token, and latency outcomes in one final analysis package.
- `run_confirmatory_study.py` validates the frozen 100-task, four-stratum design
  before allowing the planned 800-response confirmatory run.
- `RESEARCH_DESIGN.md` freezes the research-question mapping, endpoints,
  interpretation rules, and validity limits used for the thesis methodology.

## What changed in v3.8.1

- `python run_difficulty_pilot.py repair` retries only failed or missing
  secondary consensus judgments. Successful primary and secondary judgments
  are reused without additional API calls.
- Repair output is written to a new directory, preserving the original v3.8
  consensus artifacts and their complete attempt history.
- Consensus summaries and reports now include model × strategy × difficulty
  results for direct evidence, near-match distractors, evidence omission, and
  conflicting or partial evidence.
- Repair attempts retain cumulative token, latency, prompt, and error records.

## What changed in v3.8

- Atomic evaluation now uses two different automated judges over one shared
  claim inventory. The primary judge extracts and labels claims; the secondary
  judge independently relabels those exact claims.
- Claim extraction is restricted to subject-matter factual propositions.
  Verdict wording, task restatements, statements about what a source says or
  omits, and other evaluation commentary are excluded from hallucination rates.
- Entity identity is strict: similar names, aliases, or abbreviations are not
  treated as equivalent unless the supplied source establishes the link.
- A claim is `CONSENSUS_UNSUPPORTED` only when both judges mark it unsupported.
  Judge disagreements are retained as `UNCERTAIN`, and a sensitivity endpoint
  (`possible_unsupported`) counts claims flagged by either judge.
- `run_halueval_pilot.py judge` and `run_difficulty_pilot.py judge` perform the
  entire automated consensus workflow. Human annotation is optional and is not
  required to continue the pilots.

## What changed in v3.7

- Atomic judging retries API or parse failures once by default and records
  every attempt, its prompt, token usage, latency, raw output, and error.
- Validated atomic reviews produce `review_disagreements.csv` with both labels,
  a binary supported/unsupported flag, the claim, source, response, treatment
  identity, and reviewer note.
- Agreement reports now include exact counts and support/citation confusion
  matrices in addition to agreement rates.
- `run_halueval_pilot.py` provides a fixed preview/smoke/run/judge workflow for
  the audited 14-task HaluEval synthesis pilot.

## What changed in v3.6

- A frozen 12-task SciFact difficulty pilot replaces another easy random sample
  with four predeclared strata: direct controls, near-match distractors,
  decisive-evidence omission, and conflicting/partial evidence.
- Two fixed OpenAI model snapshots and all four prompt strategies produce 96
  directly comparable final responses.
- Version 3.2 prompts request a 180–250 word synthesis so each response contains
  enough factual propositions for claim-level analysis.
- `evaluate_atomic_claims.py` decomposes responses into atomic claims, judges
  each claim only against the supplied sources, logs the exact judge prompt,
  and reports unsupported-claim and citation-support rates.
- A legacy stratified review workflow remains available for optional external
  validation; it is not part of the automated v3.8 execution path.
- `run_difficulty_pilot.py` provides a fixed preview/run/judge workflow and
  refuses evaluation unless all 96 response rows completed without errors.

## What changed in v3.5.1

- Citation parsing now recognises compound document identifiers such as
  `halueval_497` when they appear as bare values in `CITED_DOCUMENTS`.
- Unknown compound identifiers are retained and reported as invalid rather
  than silently discarded.
- Parser version 1.3.0 and regression tests support offline correction with
  `reparse_results.py`; existing model responses do not need to be rerun.

## What changed in v3.5

- A new v3.1 synthesis prompt family adds an explicit `VERDICT` while keeping
  all completed v3.0 prompts immutable and reproducible.
- Synthesis verdicts are parsed into `SUPPORT`, `CONTRADICT`, or
  `NO_EVIDENCE`, enabling accuracy and confusion-matrix reporting.
- HaluEval QA data can now be loaded from its actual JSON Lines format.
- A HaluEval academic-synthesis adapter creates deterministic, approximately
  balanced answer-evaluation tasks with source citations and pre-run auditing.
- The included 20-candidate HaluEval audit retains 14 suitable tasks and has a
  complete no-cost prompt preview ready for inspection.

## What changed in v3.4

- Benchmark preparation can exclude source items used in earlier task files.
- Stress-set sampling can require unique primary documents, preventing
  near-duplicate claims from sharing the same gold source.
- A frozen 18-candidate SciFact synthesis stress set uses five documents per
  task and excludes all 12 original pilot candidates.
- An explicitly AI-assisted pre-run audit retained 14 suitable stress tasks;
  the project includes their approved dataset, dedicated config, and prompt
  preview workflow.

## What changed in v3.3

- Citation extraction now requires citation-shaped syntax. Ordinary prose such
  as "the document does" or "the document specifically" is no longer mistaken
  for a document identifier.
- `reparse_results.py` rebuilds parsed responses and all response-derived
  metrics from stored raw model output, without making any model API calls.
- Evaluation output now uses the neutral label **reviewer faithfulness review**
  so AI-assisted pilot annotations are not presented as independent human
  review.
- Regression tests cover the repaired parser and offline reprocessing path.

## What changed in v3.2

- A separately versioned v3 prompt family tests 120–180 word academic
  synthesis with controlled document citations.
- Reproducible stratified SciFact sampling balances SUPPORT, CONTRADICT, and
  NO_EVIDENCE tasks as closely as the source data permits.
- Synthesis tasks combine relevant material with deterministic, lexically
  related supplementary documents.
- Responses retain extracted document identifiers and automatically flag IDs
  that were not supplied to the model.
- Evaluation reports citation coverage and invalid-identifier rates separately
  from human judgments of semantic faithfulness.
- The v1 and v2 prompt families remain available unchanged for historical
  reproducibility.

The earlier v3.0/v3.1 work also introduced:

- SciFact prompt family v2 gives **the same evidence to every condition**.
- Chain-of-verification v2 uses three stateless requests: draft, evidence audit,
  and final revision.
- The original v1 prompts remain available and unchanged in substance.
- A pre-run benchmark audit flags unclear claims, irrelevant evidence, and
  questionable labels before results are collected.
- An evaluation command computes objective metrics and creates a human
  faithfulness-review sheet.

This fixes the main confound in the first pilot: v1 baseline, structured, and
chain-of-verification did not receive SciFact evidence, while source-grounded
did. New SciFact comparisons should use the explicit v2 strategy objects in
`config_scifact.json`.


## Documentation cleanup — 5 November 2026

The README became the examiner entry point; architecture and pilot guides were added; author-facing documents were externally archived after verified copying and substantive-content preservation. Frozen code and research records remain unchanged. The benchmark spreadsheet was retained as an explicitly documented extra baseline file absent from the original checksum inventory. See the current package manifest for old/new documentation hashes and archival provenance.
