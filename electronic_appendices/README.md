# Electronic Appendices A–G

This public evidence layer accompanies **Evaluating the Effectiveness of Structured Prompt Engineering in Reducing Hallucinations in Large Language Models for Academic Writing Tasks**. It indexes the frozen experiment and includes available traceable exports and approved data-only human-review records. The complete unchanged scientific archive, including canonical large records omitted here, remains privately preserved; these appendices do not replace or correct it.

**CURRENT 226-FILE RIGHTS-LIMITED PUBLIC RESEARCH RELEASE.** Seventy original source-bearing paths remain withheld pending redistribution clearance. See the [exact withheld paths and original hashes](../rights/WITHHELD_FILES.csv), [rights explanation](../DATA_LICENSES.md) and [lawful restoration guide](../RESTORATION.md). Documentation is aligned to the locally available *Thesis Draft v7.1 Final.docx*, SHA-256 `29568a3920630e904d1755e906827109aebca35eaaee9d79ad9a33a5573a309b`, inspected read-only through an external private snapshot. The 1,070 Word XML paragraphs are snapshot locators, not rendered page numbers. The manuscript was not copied into this repository. Scientific records and historical v6 figure/export provenance remain unchanged; original-script/checklist and other scientific provenance gaps remain explicit. Author-confirmed software/API decisions do not clear conditional third-party source text.

| Appendix | Purpose / printed thesis correspondence | Start here |
|---|---|---|
| A | Appendix A / §3.4: exact six stage templates and common output contract | [A_Prompts](A_Prompts/README.md) |
| B | Appendix B / §3.2: 100 task mappings and transformations; complete claim-212 example withheld | [B_Tasks](B_Tasks/README.md) |
| C | Appendix C / §3.5: six exclusions and evaluation methods; saved judge requests and extraction-fidelity example withheld | [C_Evaluation](C_Evaluation/README.md) |
| D | Appendix D / Chapter 4: stored primary, sensitivity, citation, exploratory and resource results | [D_Results](D_Results/README.md) |
| E | Appendix E / §3.9: execution settings, current checks, source hashes and safe offline reproduction | [E_Reproducibility](E_Reproducibility/README.md) |
| F | Appendix F: historical pilot-development metadata; source-bearing audits and recovered HaluEval outputs withheld | [F_Pilots](F_Pilots/README.md) |
| G | Appendix G / §3.7: available stage metadata, summaries and extraction-review evidence; source-bearing annotations/response packets withheld | [G_Human_Audit](G_Human_Audit/README.md) |

The repository root [README](../README.md) describes the current public scope; [CODE_GUIDE](../CODE_GUIDE.md) explains the frozen implementation. Root documentation distinguishes the historical pre-appendix absence of human/pilot evidence from the later recovered private records and the permitted data-only extracts included here. Original XLSX workbooks remain external; the original 800-response automated analysis is unchanged.

## Reading the evidence

Keep source abstracts, task transformations, generated responses, traces, parser fields, judge extraction, judge labels, derived analysis and human judgments distinct. The primary study contains 800 responses to 100 tasks from 75 original claims. Its primary endpoint is the mean of within-response consensus unsupported proportions and paired treatment-minus-baseline changes, not an indiscriminately pooled claim rate. The secondary citation analysis and later researcher audit did not replace that endpoint. Shared primary-judge extraction is a measurement limitation; neither automated consensus nor the single-reviewer sample is independent full-corpus ground truth.

[export_provenance.json](export_provenance.json) identifies canonical export sources/hashes and methods. The [file manifest](E_Reproducibility/authoritative_file_manifest.csv) indexes included and linked files. Worksheet exports preserve values and source row/cell locations, while omitting personal OOXML metadata; source hashes identify their external originals. Figures D1/D2 are exact manuscript image bytes, not regenerated plots. Nothing in this layer changes original labels or scientific outputs.

## Offline inspection

Public-file integrity can be checked from the repository root with `shasum -a 256 --check SHA256SUMS.txt`. The full appendix validator, human-audit checker and analysis-reproduction commands require withheld frozen inputs and will not complete on this public-only checkout. Obtain any required records lawfully and work in a separate restored copy. [RESTORATION.md](../RESTORATION.md) distinguishes independently reconstructable SciFact task inputs from original model responses, rendered requests, judge evaluations and human annotations, which upstream downloads cannot recreate.

Only after lawful restoration, run the full checks from that copy's root with the recorded Python 3.12.14 environment:

```bash
PYTHONDONTWRITEBYTECODE=1 python3.12 electronic_appendices/tools/validate_appendices.py
PYTHONDONTWRITEBYTECODE=1 python3.12 electronic_appendices/tools/check_human_audit.py
```

On 6 November 2026, the author authorised refreshing the file index after the documentation revision. Only the 15 stale documentation entries were updated to current sizes and hashes; paths, roles and all other entries were retained. The previous index and complete pre-audit package were preserved externally before the correction. Current hashes are in the root [SHA256SUMS.txt](../SHA256SUMS.txt), with the correction and historical hash scopes recorded in [PACKAGE_MANIFEST.json](../PACKAGE_MANIFEST.json). The original validation script is unchanged; scientific records were not modified.

After lawful restoration of their required original inputs, the [reproduction walkthrough](E_Reproducibility/README.md) and [commands](E_Reproducibility/offline_analysis_commands.txt) write independent reports outside the repository. They reproduce stored summaries, not model generation, judging or judge accuracy. No API key is needed. Commands using POSIX environment syntax require the corresponding environment setting/interpreter invocation on Windows.

## Open items and delivery boundaries

- Original task-selection/workbook-generation code was not located. The original workbook log documents the seed, strata and selected IDs, but not exact RNG draw calls/candidate ordering.
- Review stages are preserved separately; the comparison workbook's archived-reference column differs from the available initial workbook on six claims. Actual blinding compliance and elapsed reassessment interval cannot be established from workbook instructions alone.
- D1/D2 embedded images exist and their displayed values are traceable, but original plotting code was not located. Saved 5,000-resample sensitivity intervals are preserved, not claimed newly reproduced.
- The manuscript's original numbered checks 1–19 were not located as a historical checklist. Newly performed checks use EA-prefixed IDs and must not be described as that original record.
- The initial SciFact synthesis reviewed-audit CSV remains missing. Recovered HaluEval reviewer annotations do not establish a completed dual-judge atomic evaluation or independent expert review.
- Redistribution clearance for the 70 withheld source-bearing originals remains unresolved; this public release is limited to the permitted 226-file scope. Personal workbook properties were excluded and original XLSX workbooks remain external. The complete large result file remains intact in the private archive. The earlier no-ZIP/commit/push/publication preparation statement described the historical private proposal, not the current published interim release.

An optional [packaging tool](tools/package_appendices.py) can create a deterministic **external** ZIP after dataset/public-release decisions. It packages the repository path structure once, keeping appendix links valid. It requires explicit acknowledgment of unresolved redistribution rights and does not write into the repository.

The root README and licence schedule describe this initial interim public release. Conditional originals are withheld as tracked in [the conditional-file register](../rights/CONDITIONAL_FILES.csv); no legal clearance is inferred from validation or manuscript alignment.
