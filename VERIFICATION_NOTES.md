# Verification notes

## Historical secondary-analysis checks — 10 October 2026

The supplied pre-cleanup notes record that all 18 intervals agreed with the original harness helper at four-decimal precision under identical seed material; 12 previously reported mismatch means agreed to two decimals, and eight legacy coverage values agreed. They record seven focused provider-free tests, a second offline run reproducing six analysis files byte-for-byte, and 75 source clusters (50 one-task, 25 two-task) retaining 100 pairs per contrast. These are preserved historical claims; an original thesis draft or source ZIP was not newly verified during cleanup.

The consensus input SHA-256 is `8f97313e9f0fb64738c9a3145cbe95b2d94c55c930d914b729b3147744cc8287`. Original records and archive provenance are retained in the package manifest. The secondary script keeps precision; the original helper rounds returned bounds to four decimals. Unrecorded interval seeds from earlier draft calculations cannot be reconstructed from the supplied package.

## Documentation-cleanup checks — 5 November 2026

Before editing, all 151 original checksum entries matched. There were 153 regular files including the checksum file: the extra `Thesis_Benchmarks_Datasets.xlsx` had no original checksum entry. The user authorised its unchanged retention as a separately documented baseline addition. Its original size was 10,629 bytes and SHA-256 `9f5c63e89ad3d1fa7989728abb683211684258ec93f2a1d2439efba66658a330`; this does not establish earlier provenance or integrity verification. A complete sibling backup was copied and every original/backup path, size and SHA-256 matched before editing.

The frozen dataset has 100 unique tasks, four 25-task strata and 75 original source claims. Final results have 800 completed rows, 100 per model–strategy cell. The uncompressed results file is 94,682,411 bytes (90.3 MiB) and was retained intact.

The baseline and final local runs used `PYTHONDONTWRITEBYTECODE=1` and temporary directories outside the submission. Python 3.12.14 passed all 77 tests. The three independent report-reproduction commands in the README reproduced:

- All three objective files byte-for-byte: summary JSON, report Markdown, blank review CSV.
- All three original study files byte-for-byte: report Markdown, summary JSON, strategy CSV.
- All six secondary files byte-for-byte, including `analysis_summary.json` on Python 3.12.14.

A preliminary local Python 3.9.6 run also passed 77 tests. Nine of those 12 files matched bytes; secondary condition/contrast CSVs differed at floating-point precision. Structural differences in the secondary summary included `python_version` and numeric rounding, with a maximum absolute numeric difference approximately 7.11e-15. The secondary Markdown, response metrics and diagnostics remained identical. This difference is disclosed, not silently normalised. Other environments are not verified.

For other interpreters, `analysis_summary.json` may legitimately differ in its `python_version` field; any further difference must be investigated and reported rather than ignored. The exact 3.12.14 byte reproduction supports the shipped analysis, not reproduction of raw model responses or automated judge labels.

The final complete checksum inventory and unchanged frozen-file hashes were verified after documentation changes. No generation, judging, network requests, package installation, staging, commits or publishing occurred. Optional plotting and live workflows were not rerun. The original audit-hash gap described in [PILOT_WORKFLOWS.md](PILOT_WORKFLOWS.md) is preserved. Original checksum text, old/new inventories, command logs, diff records and the cleanup report are held outside the submission in the sibling cleanup working directory.

The original automated evaluation is not independently human-validated across the full corpus. The pre-appendix package lacked the later sampled researcher-review evidence; the current package includes approved [Appendix G data-only records](electronic_appendices/G_Human_Audit/README.md) for 40 responses and 433 claims, preserving separate assessment stages. Original XLSX sources remain external. This addition does not change the original automated outputs or establish full-corpus ground truth.
