# Evaluating the Effectiveness of Structured Prompt Engineering in Reducing Hallucinations in Large Language Models for Academic Writing Tasks

This repository accompanies the 2026 University of Sydney Software Engineering Honours thesis. This initial public release contains the original experimental implementation, permitted benchmark components, available analysis outputs and supporting electronic appendix materials.

The study compares Baseline, Structured, Source-grounded and Chain-of-Verification workflows on 100 SciFact-derived synthesis tasks using two fixed OpenAI snapshots: `gpt-5.5-2026-04-23` and `gpt-5.4-mini-2026-03-17`. The original experiment produced 800 completed final responses through 1,200 generation requests, followed by automated atomic-claim evaluation, source-attribution/citation analyses and supplementary researcher-conducted human review. Its findings concern faithfulness to supplied evidence; automated judgments are measurements rather than independent ground truth.

**Release scope and reproduction limits**

Seventy original paths containing third-party source text are withheld pending redistribution clearance. These include the SciFact abstract corpus, raw HaluEval QA, source-bearing task packets, final response/prompt and atomic-evaluation records, and affected audit/review extracts. The exact paths and original hashes are listed in [rights/WITHHELD_FILES.csv](rights/WITHHELD_FILES.csv).

The complete original research archive is preserved separately and has not been modified. This public release cannot independently reproduce the entire original 800-response evaluation. No frozen model responses, judge labels or human annotations have been recreated or substituted. The original 94,682,411-byte final `results.jsonl` is absent, with no pointer or replacement at its canonical path.

**Repository contents**

| Location | Contents |
|---|---|
| `src/`, root Python scripts, `tests/` | Original prompting, execution, evaluation and analysis implementation; unchanged original tests |
| `data/raw/`, `data/design/` | Licensed SciFact claims/annotations, TruthfulQA data, project configuration and frozen task designs; conditional source-text records are omitted |
| `outputs/scifact_confirmatory_v3_2/` | Available objective, atomic-consensus and integrated study summaries; secondary source-misrepresentation outputs and figures |
| `electronic_appendices/` | Available Electronic Appendices A–G material, provenance and navigation; source-bearing portions are withheld |
| `reconstruction/` | Explicitly dated release-preparation helper and metadata-only recipes for ten original SciFact task files |

[Electronic Appendices A–G](electronic_appendices/README.md) cover prompts, tasks, evaluation, results, reproducibility, pilots and human audit. The original human-review Excel workbooks remain external; available data-only extracts do not replace withheld annotations or response packets. The planning workbook and duplicate SciFact tar archive are excluded.

**Environment and offline checks**

The recorded environment is Python 3.12.14. [requirements.txt](requirements.txt) lists original minimum dependencies; [requirements-lock.txt](requirements-lock.txt) records direct runtime versions rather than a complete cross-platform dependency lock. Provider SDKs and credentials are needed for live operations, not the provider-free unit checks. Keep real credentials outside Git; `.env.example` contains blank settings.

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests
shasum -a 256 --check SHA256SUMS.txt
```

The 76 self-contained original tests pass. The unchanged full command discovers 77 tests and reports one expected missing-input error: `test_frozen_inputs_plan_56_result_rows` requires withheld `data/approved/halueval_synthesis_pilot_14.jsonl`. Some original appendix integrity/export checks likewise require withheld frozen inputs. Neither the tests nor the full appendix validator have been weakened to report a complete pass.

Exact SciFact task reconstruction requires users independently to obtain the matching upstream corpus under applicable terms. The [restoration guide](RESTORATION.md) explains the frozen corpus hash and existing helper. It writes ten task-input files into a new external directory and checks their original hashes. Retrieval and reconstruction do not recreate saved model outputs/evaluations or establish onward redistribution permission.

Saved analyses retain their original canonical locations. Recomputing reports requires the withheld original inputs: objective reporting uses final responses; integrated reporting also uses atomic consensus; secondary source-misrepresentation reporting uses saved consensus. See [CODE_GUIDE.md](CODE_GUIDE.md), [SOURCE_MISREPRESENTATION_ANALYSIS.md](SOURCE_MISREPRESENTATION_ANALYSIS.md) and the [offline command guide](electronic_appendices/E_Reproducibility/offline_analysis_commands.txt). After lawful restoration, work in a separate full copy and write regenerated reports to new external directories. Do not rerun models as a substitute for the frozen evidence.

**Licensing and provenance**

MIT applies only to the 72 original software files listed in [LICENSE_SCOPE.json](LICENSE_SCOPE.json). Data, research outputs, figures and other unlisted material are outside that grant. Retained third-party components have their own terms: see [DATA_LICENSES.md](DATA_LICENSES.md), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [dataset citations](DATASET_CITATIONS.bib).

The forest-plot PDF contains DejaVu font subsets; see the [PDF-specific font notice](THIRD_PARTY_NOTICES.md#embedded-dejavu-fonts--forest-plot-pdf) and [complete font licence](licenses/DejaVu-LICENSE.txt), which should accompany separate redistribution of the PDF.

Documentation follows the checked v7.1 thesis manuscript; historical scientific provenance is retained. Missing historical sampling/figure-generation and sensitivity-analysis scripts, review blinding/timing gaps and other measurement limits remain documented in [VERIFICATION_NOTES.md](VERIFICATION_NOTES.md) and the appendix guides. No missing historical script is represented as recovered.

[PACKAGE_FILES.txt](PACKAGE_FILES.txt), [PACKAGE_MANIFEST.json](PACKAGE_MANIFEST.json), [the supplementary index](electronic_appendices/E_Reproducibility/authoritative_file_manifest.csv) and `SHA256SUMS.txt` describe this exact 226-file interim package.
