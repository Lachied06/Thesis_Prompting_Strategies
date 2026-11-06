# Source misrepresentation analysis

Secondary analysis of the existing 800 responses. No new generation, judging or human validation was performed.

## Definitions

An evaluable claim excludes only items both judges marked non-factual. A cited claim has at least one extracted attached source identifier; all such identifiers in this dataset belong to the supplied packet. Consensus mismatch requires both citation labels to be UNSUPPORTED. Either-judge mismatch requires at least one UNSUPPORTED label. UNCERTAIN alone is not a mismatch. Claims without attached IDs are excluded from the mismatch numerator and denominator, and are retained in the citation-coverage denominator.

Rates are calculated within each response, then averaged across responses. The unit is a claim with its attached source set, not an individual claim-source pair. The judge protocol calls a citation supported when at least one attached supplied source supports the claim; it cannot identify every misleading extra citation in a multi-source set.

Citation attachment coverage is cited claims divided by all evaluable claims. The earlier harness coverage measure is pooled agreement-resolved citation-label coverage and is reported separately here. Undefined rates (zero denominator) remain missing; a paired comparison excludes a pair if either rate is undefined. No such exclusions occur in these data.

Paired differences are strategy minus baseline within each model and task. Intervals use 2,000 deterministic cluster-bootstrap resamples of the 75 original SciFact source items, preserving paired tasks within each source cluster. The mean remains task-weighted. Intervals are pointwise and unadjusted for multiple comparisons; they are conditional on the saved automated labels. Bootstrap seed material is recorded for every estimate in the CSV and JSON.

## Condition means

| Model | Strategy | Consensus mismatch | Either-judge mismatch | Citation attachment coverage |
|---|---|---:|---:|---:|
| gpt-5.4-mini-2026-03-17 | Baseline | 2.01% | 9.78% | 88.85% |
| gpt-5.4-mini-2026-03-17 | Structured | 1.75% | 7.89% | 89.17% |
| gpt-5.4-mini-2026-03-17 | Source-grounded | 1.71% | 6.30% | 95.91% |
| gpt-5.4-mini-2026-03-17 | Chain of Verification | 0.31% | 6.06% | 92.76% |
| gpt-5.5-2026-04-23 | Baseline | 0.61% | 4.20% | 82.08% |
| gpt-5.5-2026-04-23 | Structured | 0.27% | 3.30% | 88.01% |
| gpt-5.5-2026-04-23 | Source-grounded | 0.60% | 3.10% | 96.86% |
| gpt-5.5-2026-04-23 | Chain of Verification | 0.29% | 2.06% | 84.08% |

## Paired comparisons

Differences and intervals are in percentage points. Negative mismatch differences favour the strategy; positive coverage differences indicate more complete citation attachment.

| Model | Strategy | Outcome | Difference and 95% CI | Paired tasks | Source clusters |
|---|---|---|---:|---:|---:|
| gpt-5.4-mini-2026-03-17 | Structured | consensus_mismatch_rate | -0.26 [-1.87, +1.26] | 100 | 75 |
| gpt-5.4-mini-2026-03-17 | Structured | either_judge_mismatch_rate | -1.89 [-4.43, +0.47] | 100 | 75 |
| gpt-5.4-mini-2026-03-17 | Structured | citation_attachment_coverage | +0.32 [-3.56, +4.10] | 100 | 75 |
| gpt-5.4-mini-2026-03-17 | Source-grounded | consensus_mismatch_rate | -0.29 [-1.70, +1.14] | 100 | 75 |
| gpt-5.4-mini-2026-03-17 | Source-grounded | either_judge_mismatch_rate | -3.48 [-6.14, -0.77] | 100 | 75 |
| gpt-5.4-mini-2026-03-17 | Source-grounded | citation_attachment_coverage | +7.06 [+4.08, +9.98] | 100 | 75 |
| gpt-5.4-mini-2026-03-17 | Chain of Verification | consensus_mismatch_rate | -1.70 [-2.77, -0.68] | 100 | 75 |
| gpt-5.4-mini-2026-03-17 | Chain of Verification | either_judge_mismatch_rate | -3.72 [-6.28, -1.27] | 100 | 75 |
| gpt-5.4-mini-2026-03-17 | Chain of Verification | citation_attachment_coverage | +3.91 [+0.77, +7.11] | 100 | 75 |
| gpt-5.5-2026-04-23 | Structured | consensus_mismatch_rate | -0.34 [-1.02, +0.26] | 100 | 75 |
| gpt-5.5-2026-04-23 | Structured | either_judge_mismatch_rate | -0.90 [-2.67, +1.07] | 100 | 75 |
| gpt-5.5-2026-04-23 | Structured | citation_attachment_coverage | +5.93 [+2.76, +9.29] | 100 | 75 |
| gpt-5.5-2026-04-23 | Source-grounded | consensus_mismatch_rate | -0.01 [-0.67, +0.56] | 100 | 75 |
| gpt-5.5-2026-04-23 | Source-grounded | either_judge_mismatch_rate | -1.10 [-2.68, +0.40] | 100 | 75 |
| gpt-5.5-2026-04-23 | Source-grounded | citation_attachment_coverage | +14.77 [+11.90, +17.94] | 100 | 75 |
| gpt-5.5-2026-04-23 | Chain of Verification | consensus_mismatch_rate | -0.32 [-1.00, +0.32] | 100 | 75 |
| gpt-5.5-2026-04-23 | Chain of Verification | either_judge_mismatch_rate | -2.14 [-3.90, -0.38] | 100 | 75 |
| gpt-5.5-2026-04-23 | Chain of Verification | citation_attachment_coverage | +1.99 [-1.22, +5.17] | 100 | 75 |

## Measurement checks

There are 8,326 extracted items, 6 exclusions and 8,320 evaluable claims, of which 7,380 have attached source IDs.

197 evaluable claims have an UNSUPPORTED citation label from at least one judge but no attached ID in the shared extraction. They are excluded from citation mismatch; treating these as source misrepresentation would conflate missing citations with incorrect attribution. The saved labels remain unchanged.

32 cited claims are judged non-factual by one judge only. They remain in the evaluable denominator under the existing protocol; 8 contribute to the either-judge numerator. The diagnostic JSON preserves the full cited-label cross-tabulation.

The two judges share the primary extractor's claim and citation inventory. No final human validation was completed. This analysis therefore estimates semantic citation mismatch under automated measurement. It does not validate the fine-grained five-way taxonomy or establish prevention of open-ended fabricated references.
