# Confirmatory study operation guide

The saved 100-task × two-model × four-strategy study is complete. Use [README.md](README.md) for offline inspection and report reproduction; neither generation nor judging is necessary to read the findings. The following live commands are operational reference only and were not executed during documentation cleanup.

## Environment and working copy

Run relative to the repository root in a separate full working copy. The wrapper writes fixed paths under `outputs/`; never use its overwrite option against submission records. Existing artifacts cause ordinary new runs to refuse replacement. Continuing an interrupted live run is a different operation from reproducing reports offline.

The original manifest records Python 3.12.14 on macOS arm64. Additional platform/version support has not been established. If setting up a separate live environment, install dependencies there using the unchanged `requirements.txt` or consult the recorded direct versions in `requirements-lock.txt`; neither is a verified transitive environment lock. This setup requires network access and is outside offline verification.

Typical setup commands in that separate copy:

```bash
PYTHONDONTWRITEBYTECODE=1 python3.12 -m venv .venv
# macOS/Linux: .venv/bin/python; Windows: .venv/Scripts/python.exe
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pip install -r requirements.txt
```

On Windows set `PYTHONDONTWRITEBYTECODE=1` using the shell's environment syntax and use the Windows interpreter path. Populate a local `.env` using the variable names in `.env.example`, or supply environment variables through the shell. Never commit credentials. No real `.env` was inspected during cleanup.

## Read-only checks

```bash
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests
PYTHONDONTWRITEBYTECODE=1 python3.12 run_confirmatory_study.py validate
```

The verified local results are 77 passing tests and successful frozen-design validation. Source insufficiency is not semantically checked by validation.

## Optional live actions

Only in a separately prepared live working copy:

```bash
PYTHONDONTWRITEBYTECODE=1 python3.12 run_confirmatory_study.py preview
PYTHONDONTWRITEBYTECODE=1 python3.12 run_confirmatory_study.py smoke
PYTHONDONTWRITEBYTECODE=1 python3.12 run_confirmatory_study.py all
```

Preview makes no API calls but writes a preview/manifest. Smoke targets one task, two models and four strategies: eight final responses and 12 generation calls. `all` targets 800 final responses in 1,200 generation calls, then nominally 1,600 judge calls plus retries. Shipped checkpoints contain 21 secondary retries. Models, effort, token caps and fixed output locations are described in the README and configuration; availability and cost were not tested during cleanup.

For an interrupted live run in that working copy:

```bash
PYTHONDONTWRITEBYTECODE=1 python3.12 run_confirmatory_study.py all --resume
```

Generation resume checks config/data hashes and retains completed jobs; consensus resume retains parsed checkpoints. Resume compacts/writes files. `--overwrite` deliberately replaces selected artifacts and must not be used on this submission. `repair` retries failed secondary work into separate repaired outputs; it is still an API operation.

## Saved analysis locations

- `outputs/scifact_confirmatory_v3_2/study_analysis/study_report.md`
- `outputs/scifact_confirmatory_v3_2/study_analysis/study_summary.json`
- `outputs/scifact_confirmatory_v3_2/study_analysis/strategy_results.csv`
- `outputs/scifact_confirmatory_v3_2/objective_evaluation/evaluation_summary.json`
- `outputs/scifact_confirmatory_v3_2/atomic_consensus_v3_9/atomic_consensus_summary.json`
- `outputs/scifact_confirmatory_v3_2/source_misrepresentation_analysis_v1/analysis_report.md`

The integrated Markdown tables contain an unescaped-condition-pipe defect; use CSV/JSON for column alignment. Automated endpoints are not full-corpus independently human-validated. Approved data-only records from the later researcher review are now indexed in [Appendix G](electronic_appendices/G_Human_Audit/README.md); original XLSX files remain external, and the automated analysis is unchanged. The secondary analysis is a separate offline step, not part of wrapper `all`.
