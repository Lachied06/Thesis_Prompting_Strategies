> Distribution note, 6 November 2026: this interim public release omits the 70 conditional files; full-archive claims and commands below require lawful private restoration. See the withheld-file register linked below.

# Code guide

This guide describes the frozen implementation and saved confirmatory records. Documentation cleanup did not patch code or rerun generation/judging. Function locations below refer to the preserved source files; [README.md](README.md) gives the offline reproduction commands and current measurement caveats.

## Life of one observation

An observation is one frozen task × model × strategy, with one repetition in this experiment. `src/data.py:load_jsonl_tasks()` (line 8) reads the approved JSONL into `src/schemas.py:Task` (line 9): task identity, prompt, reference label, source packet and metadata. All four strategies and both models receive that same task packet; the reference label is retained for measurement, not exposed as the answer in the task prompt.

`run_experiment.py:main()` loads/validates configuration, constructs artifact paths and records a manifest. `src/runner.py:build_jobs()` (line 127) expands repetitions, tasks, models and strategies, then shuffles the job list with a local `random.Random` using configuration seed 20260924. This randomises execution order; it does not change source order inside a task.

`src/prompting.py:build_prompt_plan()` (line 913) resolves the explicit strategy version into templates and fills task variables. `PromptTemplate`, `StrategyDefinition` and `PromptPlan` (lines 71, 106 and 135) represent registry entries and execution plans. `resolve_strategy()` (868), `_variables_for_task()` (894), and `registry_manifest()` (928) expose resolution, substitution and provenance. Template definitions are in this module; `_with_synthesis_verdict_contract()` (755) and `_with_stress_contract()` (789) derive the v3.1 and v3.2 contracts. `src/schemas.py:Prompt.prompt_hash` hashes a canonical system/user JSON representation. Historical versions remain available; plain strings resolve to v1.0.0 rather than silently adopting current wording.

`src/runner.py:run_experiment()` (255) executes the plan. Baseline, Structured and Source-grounded make one request. CoV v3.2 makes `initial_generation`, `verification_generation`, then `revision_generation`. The audit sees the draft and evidence; revision sees the draft, audit and original evidence. “Separate” or “independent” verification in the template means a separate stateless call, not an independently validated evaluator or isolated causal manipulation. Preview rendering uses placeholders for future generated text; live prompt logs preserve the realised strings.

A `GenerationRequest` carries system/user text, the output-token cap and settings. `src/providers/factory.py:build_provider()` (line 7) lazily selects the adapter. The final study uses `OpenAIProvider.generate()` in `src/providers/openai_provider.py`, which calls `client.responses.create` with model, input, optional instructions, output cap and reasoning effort. It supplies no external tools and no explicit temperature. Anthropic, Gemini and Mistral adapters and the abstract `ModelProvider` are retained for historical/multi-provider use, not evidence of final comparisons with those providers.

Every response enters a `TraceStep` with prompt, request, raw text, usage, provider status/request ID and latency. `src/parsing.py:parse_response()` (line 145) extracts the final verdict, synthesis and cited IDs. `_citation_details()` (114) compares parsed IDs with task-allowed IDs. The parser is syntactic and cannot determine semantic citation support. Its inline patterns require “Document”; bare numeric bracket citations are a documented blind spot.

`src/schemas.py:RunResult.to_dict()` serialises the task/source metadata, final raw and parsed fields, ground truth, exact trace, errors, timings, request count and summed input/output/reasoning token fields. The result is appended to `results.jsonl`; prompts are logged separately. `src/experiment.py:build_manifest()` (98) records config/data hashes, prompt registry, planned jobs/calls, runtime and dependency versions. Token accounting measures recorded consumption, not a price calculation.

`evaluate_results.py` reads saved results and uses `src/evaluation.py:summarize_results()` (103) for objective metrics. The v3.2 verdict and ID checks are separate from semantic judging. `manual_review_rows()` and `blinded_review_package()` (329, 371) create optional blank review packages; their existence does not establish completed review. `_initial_label()` (89) uses legacy classification parsing on CoV drafts, so the saved v3.2 label-change summaries are empty.

`evaluate_atomic_claims.py consensus` passes each saved response, task and evidence to the primary judge. `src/atomic_evaluation.py:build_atomic_judge_request()` (97) defines the subject-matter extraction and labeling rubric; `parse_atomic_judgment()` (204) validates returned JSON/categories. `judge_results()` (287) saves exact prompts, outputs, attempts and errors. The extraction prompt excludes verdicts, task restatements, evidential commentary and unsupported entity-identity assumptions; these are instructions to a model, not formal guarantees about its inventory.

`build_atomic_secondary_request()` (428) sends the task, sources, full response and fixed claim texts/attached IDs to the secondary judge, withholding primary labels and rationales. `parse_atomic_secondary_judgment()` (522) and `judge_existing_claims()` (584) validate and checkpoint secondary labels. Neither judge prompt explicitly supplies the generator's model or strategy. Shared evidence, response style and a common primary inventory still permit dependence and common errors.

`build_atomic_consensus()` (880) joins the two outputs by run and claim IDs. Both `NOT_FACTUAL` labels produce `EXCLUDED_NOT_FACTUAL`; both unsupported labels (`CONTRADICTED`/`NOT_IN_SOURCES`) produce `CONSENSUS_UNSUPPORTED`, even if the exact unsupported labels differ. Either unsupported label sets `possible_unsupported`; disagreements and one-judge non-factual cases remain `UNCERTAIN`. Citation consensus requires exact citation-label agreement. Fine-grained type consensus requires both unsupported plus the same type; otherwise the type remains uncertain.

`summarize_atomic_consensus()` (1442), `_consensus_bucket()` (1116), `_consensus_response_metrics()` (1278), and `_consensus_baseline_contrasts()` (1311) calculate condition/difficulty summaries and paired primary estimates. Claims both judges mark non-factual are excluded; all other extracted claims enter the evaluable denominator. Primary inference averages within-response unsupported proportions. Pooled claim rates and responses with any error are additional summaries and must not be substituted for that estimand.

`build_study_report.py:combined_condition_rows()` (44) combines objective and atomic metrics. `render_study_report()` (119) writes original integrated tables; `write_condition_csv()` (237) preserves their structured form. Condition strings include an unescaped `|` in Markdown rendering, so consult `strategy_results.csv` or `study_summary.json` for column alignment.

The later `analyse_source_misrepresentation.py` reads saved consensus, validates the complete design with `validate_records()` (93), calculates response-level citation denominators with `response_metrics()` (70), and writes six outputs through `run_analysis()` (269). `condition_summaries()` (150), `paired_contrasts()` (176), `cluster_interval()` (40), and `diagnostics()` (215) implement the secondary endpoint and inference. `plot_source_misrepresentation.py:main()` reads its saved JSON and produces optional PNG/SVG/PDF figures; it does not relabel or estimate outcomes.

## Task construction and source provenance

The frozen task builder is `prepare_benchmarks.py`:

| Function / location | Responsibility and inputs → outputs |
|---|---|
| `scifact_label()` (67) | Evidence rationale labels → canonical reference label; empty labels → NO_EVIDENCE |
| `_primary_scifact_document_ids()` (122) | Evidence keys, else cited IDs → primary document set |
| `choose_scifact_rows_with_unique_primary_documents()` (128) | Eligible claim rows, limit, seed, strata → rows without repeated primary IDs |
| `_tokens()` (204), `_supplementary_document_ids()` (212) | Claim + primary titles, corpus, target count, seed → primary plus highest lexical-overlap candidates |
| `scifact_source_ids_from_task_files()` (459) | Earlier task files → excluded original claim IDs |
| `prepare_scifact_synthesis()` (561) | Raw claim/corpus files + sampling/exclusion settings → base packets and metadata |
| `prepare_scifact_confirmatory_study()` (303) | Balanced 75-task base + design seed → 100-entry design and final dataset via transformation |
| `_document_sections()` (675), `prepare_scifact_difficulty_pilot()` (702) | Existing rendered packet + design → verbatim retained source sections in declared order |
| `src/audit.py:apply_audit()` (102) | Completed recorded decisions → included rows and audit hash manifest; no semantic adjudication by the script |

The near-match stratum uses `full_distractor_first` (763–767), placing ranked supplementary IDs before evidence IDs and inheriting SUPPORT/CONTRADICT. Target size is five, not “always four distractors”: claim 261 retains two evidence abstracts and three supplementary abstracts. The native NO_EVIDENCE stratum uses the same mode, with four supplementary abstracts before its original cited abstract. No synthetic conflict or insufficiency verifier is involved. `omit_gold` (768–776) excludes annotated evidence IDs and assigns NO_EVIDENCE, without checking the remaining packet semantically.

The selector excludes only the current primary IDs, shuffles the corpus candidates with the effective claim seed, then stably sorts descending by `3*title_overlap + abstract_overlap`. There is no threshold, semantic filter or exclusion of other tasks' gold documents. Task metadata preserve selected IDs, exact source text, raw/base/design hashes and seeds; scores/rejected rankings are not saved. The supplied raw/base/design hashes match final task metadata. No confirmatory audit CSV/manifest is included.

## Orchestration, resume and preservation

`run_confirmatory_study.py:_validate_frozen_dataset()` (75) checks counts, reference-label distributions, source pairing, word ranges and configuration shape; it does not semantically verify evidence labels. Its `main()` exposes `validate`, `preview`, `smoke`, `run`, `judge`, `repair`, and `all`. `all` executes generation, objective reporting, dual judging and integrated reporting; it does not run the later secondary analysis. Judge repair targets failed/missing secondary work and writes a distinct repaired directory. These live actions are separate from the README's saved-record report reproduction.

`run_experiment.py:_resume_manifest()` compares config/data hashes before continuation. `src/runner.py:_prepare_resume_artifacts()` (90) retains completed/skipped logical jobs, compacts records and filters prompt logs to retained run IDs; failed/missing jobs can be rerun. This rewrites checkpoint files and is therefore a live-working-copy operation. In `evaluate_atomic_claims.py`, consensus resume reuses parsed primary/secondary checkpoints; `retry_failed_secondary_claims()` (791) and `_merge_secondary_retry()` (746) preserve successful labels and accumulate retry provenance. Avoid treating resume as a read-only check.

`src/runner.py` records `finish_reason` but does not reject an incomplete intermediate report. Seven GPT-5.5 verification calls hit 1,600 output tokens and are marked incomplete; revision still completed. This limits interpretations about the fidelity of every verification stage. No fix was applied.

The package checksums verify included bytes. The manifest preserves original archive metadata as historical claims, documents cleanup revisions separately, and does not assert a new archive was inspected. Recorded direct dependency versions are not a transitive lock. Historical pilot audit/hash discrepancies are disclosed in [PILOT_WORKFLOWS.md](PILOT_WORKFLOWS.md).

## Paired inference and measurement boundaries

`src/atomic_evaluation.py:_paired_bootstrap_mean_ci()` (1044) hashes endpoint-specific seed material, resamples original-source clusters, averages sampled task differences, sorts 2,000 replicates and returns percentile-index bounds rounded to four decimals. The primary contrasts group by model, strategy and task; `source_item_id` links direct/omission pairs. The secondary `cluster_interval()` uses the same cluster/quantile convention, retaining precision; `paired_contrasts()` includes seed 20261010 in saved per-estimate seed material. Run-order seed 20260924 controls execution, not bootstrap accuracy.

There are 75 clusters (25 with two tasks and 50 with one), not 100 independent original claims. Whole-cluster resampling preserves dependence between paired task transformations. The statistic remains equally task-weighted. Intervals quantify source-task sampling uncertainty conditional on the saved labels, with no multiplicity adjustment; they do not account for extraction or judge error.

The secondary endpoint conditions on attached citations. Claims lacking attached IDs remain in attachment-coverage denominators but do not count as citation mismatch. One attached supporting source is sufficient under the rubric; misleading extra citations can escape a claim-with-source-set measure. All 100 task pairs remain eligible for each observed secondary contrast. Consensus definitions and mean versus pooled weighting must be kept distinct.

The code does not establish unconstrained bibliographic-fabrication performance, fully independent ground truth, generalisation across arbitrary models/tasks or an internal causal mechanism. The original automated endpoints have no full-corpus independent human validation. Approved data-only records from the later sampled researcher review are now indexed in [Appendix G](electronic_appendices/G_Human_Audit/README.md), with initial, intermediate, repeat and adjudicated versions distinct; original XLSX workbooks remain external. This does not establish independent full-corpus validation or human-confirmed rankings. The unchanged implementation remains authoritative.

## 30-minute review path

1. [README.md](README.md): design, verified offline commands, known limitations and dataset permissions.
2. [config_scifact_confirmatory.json](config_scifact_confirmatory.json), [approved tasks — original path `data/approved/scifact_confirmatory_100.jsonl`; withheld](rights/WITHHELD_FILES.csv) and [design](data/design/scifact_confirmatory_100.design.json): fixed cells, evidence and labels.
3. [src/prompting.py](src/prompting.py), [src/runner.py](src/runner.py), [src/providers/openai_provider.py](src/providers/openai_provider.py): complete treatments, actual calls and traces.
4. [src/parsing.py](src/parsing.py), [src/evaluation.py](src/evaluation.py): objective endpoint and parser limitations.
5. [src/atomic_evaluation.py](src/atomic_evaluation.py): both judge prompts, shared extraction, consensus and bootstrap.
6. [build_study_report.py](build_study_report.py) and [structured original results](outputs/scifact_confirmatory_v3_2/study_analysis/strategy_results.csv): original primary tables.
7. [analyse_source_misrepresentation.py](analyse_source_misrepresentation.py), [secondary analysis guide](SOURCE_MISREPRESENTATION_ANALYSIS.md), and [verification notes](VERIFICATION_NOTES.md): later endpoint, diagnostics and reproducibility scope.
