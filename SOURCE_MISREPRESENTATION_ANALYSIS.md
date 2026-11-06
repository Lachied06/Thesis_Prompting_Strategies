# Secondary source-misrepresentation analysis

This completed secondary RQ2 analysis reuses the original 800 responses and saved dual-judge labels. It does not change the original primary unsupported-claim endpoint, prompt registry, responses or judgments. Scripts, complete machine-readable results and figures are already integrated into this package; no copying or add-on merge is required. The former Word memo's substantive methods, diagnostics and bounded interpretation are retained here and in the linked complete tables; thesis-edit instructions were externally archived.

## Inputs and safe offline reproduction

Input: `outputs/scifact_confirmatory_v3_2/atomic_consensus_v3_9/atomic_consensus.jsonl`.

Outputs: `outputs/scifact_confirmatory_v3_2/source_misrepresentation_analysis_v1/`.

Use the temporary-directory commands in [README.md](README.md) to reproduce independently without overwriting shipped outputs. `analyse_source_misrepresentation.py` uses only the standard library, needs no credentials and makes no API calls. Defaults are 2,000 bootstrap resamples and analysis seed 20261010, separate from run-order seed 20260924. It records input/script hashes, Python version and each estimate's seed material in `analysis_summary.json`. Use settings and interval endpoints from the same saved analysis, not a mixture of historical calculations. [VERIFICATION_NOTES.md](VERIFICATION_NOTES.md) distinguishes historical checks from current reproduction evidence.

The finished PNG, SVG and PDF are supplied. Optional `plot_source_misrepresentation.py --summary SUMMARY --output-dir NEW` reads saved estimates, uses matplotlib and does not repeat judging or inference. Plotting was not rerun during cleanup; its original matplotlib version is not recorded. Installation/figure regeneration is unnecessary for offline report verification.

## Outcome definitions

- **Evaluable claims:** exclude only items both judges mark non-factual. One-judge non-factual disagreements remain evaluable.
- **Cited claims:** evaluable claims with at least one source ID attached in the primary extraction. All such IDs in this dataset belong to the supplied packet. This is separate from an invalid identifier detected in a full response by objective parsing.
- **Consensus mismatch:** both saved citation labels are `UNSUPPORTED`.
- **Either-judge mismatch:** at least one saved citation label is `UNSUPPORTED`; union, without double-counting. Generic `UNCERTAIN` alone is not an error.
- **Response mismatch rate:** flagged cited claims divided by cited evaluable claims within the response. Condition means average these proportions; pooled counts do not reproduce the principal estimates.
- **Citation attachment coverage:** cited claims divided by evaluable claims per response, then averaged.
- **Earlier harness coverage:** pooled agreement-resolved `SUPPORTED`/`UNSUPPORTED` citation labels divided by citation-evaluable claims. The original helper excludes `NOT_APPLICABLE` citation consensus; in these saved data the corresponding denominator agrees with the evaluable-claim count. This agreement requirement makes it different from physical attachment. Mean and pooled variants are retained separately in the new CSV.
- **Multiple sources:** the rubric treats a claim as citation-supported if at least one attached supplied source supports it. The unit is a claim with its attached source set, not every claim–source pair; inappropriate extra citations can escape this measure.

No cited claims would make a response mismatch rate undefined rather than zero. A paired comparison excludes a task if either response has an undefined rate and reports exclusions. All observed responses have cited/evaluable claims, and all 100 tasks remain eligible for every contrast. Missing citations remain visible in coverage.

For the GPT-5.4 mini baseline, the older pooled agreement-resolved coverage is 80.81%, pooled physical attachment is 88.48%, and mean per-response attachment is 88.85%. These differ because of label agreement and response versus claim weighting; they are not interchangeable measures.

## Paired inference

Each of three strategies is compared with baseline within each model on the same 100 tasks. Effects are mean task-specific treatment-minus-baseline differences: negative mismatch is favourable, positive coverage indicates more complete attachment.

The bootstrap resamples 75 original SciFact source-claim clusters with replacement, retaining every associated task difference together. There are 25 two-task direct/omission clusters and 50 one-task clusters. Each replicate averages sampled task differences, retaining equal task weighting rather than equal cluster-mean weighting. The analysis uses 2,000 replicates; endpoint-specific seed material incorporates 20261010 and is saved in CSV/JSON. Sorted percentile indices are `int(.025*(B-1))` and `int(.975*(B-1))`, matching the original helper's convention. The secondary script retains full precision until presentation; the original helper rounds returned bounds to four decimals.

Intervals are pointwise, unadjusted for multiple comparisons and conditional on saved labels. They describe source-task sampling uncertainty, not judge accuracy. This was a secondary analysis of existing outputs, not a new primary endpoint or evidence of prospective external preregistration. There is no direct strategy-versus-strategy or model-interaction test. An interval including zero is inconclusive; different significance patterns do not themselves establish different effects.

## Complete findings and interpretation

The [saved complete report](outputs/scifact_confirmatory_v3_2/source_misrepresentation_analysis_v1/analysis_report.md) contains all eight condition means and all 18 paired effects/intervals (12 mismatch, six coverage). [condition_summary.csv](outputs/scifact_confirmatory_v3_2/source_misrepresentation_analysis_v1/condition_summary.csv) retains exact counts, mean/pooled coverage and affected-response rates; [paired_contrasts.csv](outputs/scifact_confirmatory_v3_2/source_misrepresentation_analysis_v1/paired_contrasts.csv) retains full-precision estimates, sample sizes and seeds. These verified tables preserve the substantive numeric results formerly displayed in the Word memo without importing thesis-edit instructions.

CoV has the clearest citation-mismatch pattern: GPT-5.4 mini intervals exclude zero under both definitions; GPT-5.5 does so only under either-judge mismatch. On GPT-5.4 mini, mean consensus mismatch changes from 2.01% to 0.31%, a difference of -1.70 percentage points (95% interval -2.77 to -0.68); either-judge mismatch changes from 9.78% to 6.06%, a difference of -3.72 (-6.28 to -1.27). Responses with consensus mismatch change from 15 to three of 100. GPT-5.5 has a low consensus baseline (0.61%); its CoV consensus interval includes zero, while either-judge mismatch falls from 4.20% to 2.06%, difference -2.14 (-3.90 to -0.38).

Source-grounded prompting reduces either-judge mismatch on GPT-5.4 mini by 3.48 percentage points (interval -6.14 to -0.77); its other mismatch intervals include zero. Structured has favourable mismatch point estimates, but all four mismatch intervals include zero. Source grounding increases mean citation attachment from 88.85% to 95.91% on GPT-5.4 mini and from 82.08% to 96.86% on GPT-5.5; both paired coverage intervals exclude zero. Attachment completeness and semantic support remain distinct outcomes.

This supports a qualified source-attribution finding within the controlled task setting. The pattern is compatible with a benefit from verification/revision, but the package comparison does not isolate the causal contribution of that stage. It does not validate the fine-grained taxonomy or establish prevention of open-ended invented references. Complete primary results and supported-yield/resource trade-offs remain in `study_analysis/`, with CSV/JSON preferred over the original Markdown's malformed condition cells.

## Measurement diagnostics and uncertainty

The saved [diagnostics](outputs/scifact_confirmatory_v3_2/source_misrepresentation_analysis_v1/measurement_diagnostics.json) verify:

- 8,326 extracted items, six both-non-factual exclusions, 8,320 evaluable claims and 7,380 cited evaluable claims.
- 197 evaluable claims have at least one `UNSUPPORTED` citation label despite no attached ID in the primary extraction. They are excluded from mismatch and remain in the coverage denominator. Saved labels were not corrected.
- 32 cited claims are non-factual according to one judge only; they remain evaluable, with eight contributing to either-judge mismatch.
- 78 consensus mismatch and 417 either-judge mismatch claims across conditions. These pooled audit totals are not response-mean estimates.
- No response lacks cited or evaluable claims; no task pair is dropped for an undefined denominator.

Fine-grained type agreement among consensus-unsupported claims is limited. Counts below were verified directly from `atomic_consensus.jsonl`; the denominator is consensus-unsupported claims, not all extracted claims or all possible-unsupported claims.

| Model | Strategy | Agreed type / consensus unsupported | Fraction |
|---|---|---:|---:|
| GPT-5.4 mini | Baseline | 9/64 | 14.1% |
| GPT-5.4 mini | Structured | 4/42 | 9.5% |
| GPT-5.4 mini | Source-grounded | 13/30 | 43.3% |
| GPT-5.4 mini | CoV | 2/11 | 18.2% |
| GPT-5.5 | Baseline | 9/52 | 17.3% |
| GPT-5.5 | Structured | 11/30 | 36.7% |
| GPT-5.5 | Source-grounded | 3/12 | 25.0% |
| GPT-5.5 | CoV | 2/20 | 10.0% |

Both judges share the primary extractor's claims and citation attachments, and are model families also tested as generators. Second-judge relabeling does not detect every extraction omission or provide independent claim extraction. The shipped experimental endpoint is automated and is not independently validated across the full dataset. Approved [Appendix G data-only records](electronic_appendices/G_Human_Audit/README.md) now document the later separate researcher review, with original XLSX sources external and assessment stages preserved separately. That review is not the source of these estimates and does not establish full-corpus accuracy, systematic validation of citation mismatch or human-confirmed rankings. Historical `human_validation_completed: false` and report statements describe this original automated analysis and remain untouched.

Only one full response has an invalid supplied-document identifier in the objective evaluation. This floor effect and the closed packet design limit claims about bibliographic fabrication. IDs do not test invented authors, titles, journals or DOIs. Automated citation alignment and subtype uncertainty must remain explicit when interpreting these findings.

## Output inventory

| File under `source_misrepresentation_analysis_v1/` | Role |
|---|---|
| `response_metrics.csv` | 800 response-level numerators, denominators, rates and pairing keys |
| `condition_summary.csv` | Eight conditions, coverage variants, counts and affected-response rates |
| `paired_contrasts.csv` | All 18 effects, confidence intervals, eligibility and seeds |
| `analysis_summary.json` | Complete results, analysis version 1.0.0, input/script hashes and settings |
| `measurement_diagnostics.json` | Citation-label cross-tabulation and eligibility diagnostics |
| `analysis_report.md` | Definitions and complete readable results |
| `source_misrepresentation_forest.png`, `.svg`, `.pdf` | 300 dpi PNG and vector figures from saved estimates |

The seven focused provider-free tests cover citation eligibility/union, undefined denominators, cluster resampling, row-order-independent task pairing, duplicate rejection, out-of-packet attached-ID rejection and overwrite protection. No new primary/secondary judging was performed for this analysis or for documentation cleanup.
