# Automated dual-judge atomic evaluation

## Consensus results

| Condition | Responses | Both parsed | Claims | Consensus unsupported | Possible unsupported | Uncertain | Consensus response rate | Possible response rate | Binary judge agreement |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openai:gpt-5.4-mini-2026-03-17 | baseline@3.2.0 | 100 | 100.0% | 1042 | 64 (6.1%) | 156 (15.0%) | 97 (9.3%) | 36.0% | 67.0% | 91.2% |
| openai:gpt-5.4-mini-2026-03-17 | chain_of_verification@3.2.0 | 100 | 100.0% | 930 | 11 (1.2%) | 95 (10.2%) | 86 (9.2%) | 10.0% | 57.0% | 91.0% |
| openai:gpt-5.4-mini-2026-03-17 | source_grounded@3.2.0 | 100 | 100.0% | 963 | 30 (3.1%) | 96 (10.0%) | 71 (7.4%) | 20.0% | 46.0% | 93.2% |
| openai:gpt-5.4-mini-2026-03-17 | structured@3.2.0 | 100 | 100.0% | 947 | 42 (4.4%) | 128 (13.5%) | 93 (9.8%) | 28.0% | 64.0% | 90.9% |
| openai:gpt-5.5-2026-04-23 | baseline@3.2.0 | 100 | 100.0% | 1121 | 52 (4.6%) | 151 (13.5%) | 104 (9.3%) | 31.0% | 64.0% | 91.2% |
| openai:gpt-5.5-2026-04-23 | chain_of_verification@3.2.0 | 100 | 100.0% | 1157 | 20 (1.7%) | 79 (6.8%) | 69 (6.0%) | 13.0% | 41.0% | 94.9% |
| openai:gpt-5.5-2026-04-23 | source_grounded@3.2.0 | 100 | 100.0% | 1105 | 12 (1.1%) | 52 (4.7%) | 48 (4.3%) | 11.0% | 35.0% | 96.4% |
| openai:gpt-5.5-2026-04-23 | structured@3.2.0 | 100 | 100.0% | 1055 | 30 (2.8%) | 99 (9.4%) | 76 (7.2%) | 23.0% | 49.0% | 93.5% |

## Supported-content yield and claim exposure

| Condition | Mean factual claims/response | Mean consensus-supported claims/response | Consensus-supported claim rate | Mean per-response consensus unsupported rate | Mean per-response possible unsupported rate |
|---|---:|---:|---:|---:|---:|
| openai:gpt-5.4-mini-2026-03-17 | baseline@3.2.0 | 10.42 | 8.81 | 84.5% | 5.9% | 14.4% |
| openai:gpt-5.4-mini-2026-03-17 | chain_of_verification@3.2.0 | 9.3 | 8.33 | 89.6% | 1.1% | 9.8% |
| openai:gpt-5.4-mini-2026-03-17 | source_grounded@3.2.0 | 9.63 | 8.62 | 89.5% | 3.1% | 8.9% |
| openai:gpt-5.4-mini-2026-03-17 | structured@3.2.0 | 9.47 | 8.12 | 85.7% | 4.0% | 12.8% |
| openai:gpt-5.5-2026-04-23 | baseline@3.2.0 | 11.21 | 9.65 | 86.1% | 4.4% | 12.7% |
| openai:gpt-5.5-2026-04-23 | chain_of_verification@3.2.0 | 11.57 | 10.68 | 92.3% | 1.6% | 6.6% |
| openai:gpt-5.5-2026-04-23 | source_grounded@3.2.0 | 11.05 | 10.45 | 94.6% | 1.1% | 4.5% |
| openai:gpt-5.5-2026-04-23 | structured@3.2.0 | 10.55 | 9.49 | 90.0% | 2.8% | 8.9% |

## Consensus hallucination types

Counts include only claims both judges marked unsupported. A type is reported as `UNCERTAIN_TYPE` when the judges agree that a claim is unsupported but disagree on the dominant error mechanism.

| Condition | Unsupported addition | Source contradiction | Evidence overstatement | Entity/context confusion | Other | Uncertain type |
|---|---:|---:|---:|---:|---:|---:|
| openai:gpt-5.4-mini-2026-03-17 | baseline@3.2.0 | 5 | 2 | 2 | 0 | 0 | 55 |
| openai:gpt-5.4-mini-2026-03-17 | chain_of_verification@3.2.0 | 0 | 1 | 1 | 0 | 0 | 9 |
| openai:gpt-5.4-mini-2026-03-17 | source_grounded@3.2.0 | 5 | 1 | 5 | 0 | 2 | 17 |
| openai:gpt-5.4-mini-2026-03-17 | structured@3.2.0 | 1 | 1 | 2 | 0 | 0 | 38 |
| openai:gpt-5.5-2026-04-23 | baseline@3.2.0 | 7 | 1 | 0 | 0 | 1 | 43 |
| openai:gpt-5.5-2026-04-23 | chain_of_verification@3.2.0 | 2 | 0 | 0 | 0 | 0 | 18 |
| openai:gpt-5.5-2026-04-23 | source_grounded@3.2.0 | 2 | 0 | 1 | 0 | 0 | 9 |
| openai:gpt-5.5-2026-04-23 | structured@3.2.0 | 9 | 0 | 2 | 0 | 0 | 19 |

## Consensus results by difficulty

| Condition | Difficulty | Responses | Both parsed | Claims | Consensus unsupported | Possible unsupported | Uncertain | Consensus response rate | Possible response rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| openai:gpt-5.4-mini-2026-03-17 | baseline@3.2.0 | conflicting_or_partial_evidence | 25 | 100.0% | 218 | 10 (4.6%) | 29 (13.3%) | 19 (8.7%) | 24.0% | 56.0% |
| openai:gpt-5.4-mini-2026-03-17 | baseline@3.2.0 | direct_control | 25 | 100.0% | 299 | 21 (7.0%) | 49 (16.4%) | 33 (11.0%) | 44.0% | 76.0% |
| openai:gpt-5.4-mini-2026-03-17 | baseline@3.2.0 | evidence_omission | 25 | 100.0% | 220 | 13 (5.9%) | 22 (10.0%) | 9 (4.1%) | 32.0% | 48.0% |
| openai:gpt-5.4-mini-2026-03-17 | baseline@3.2.0 | near_match_distractors | 25 | 100.0% | 305 | 20 (6.6%) | 56 (18.4%) | 36 (11.8%) | 44.0% | 88.0% |
| openai:gpt-5.4-mini-2026-03-17 | chain_of_verification@3.2.0 | conflicting_or_partial_evidence | 25 | 100.0% | 197 | 2 (1.0%) | 23 (11.7%) | 21 (10.7%) | 8.0% | 64.0% |
| openai:gpt-5.4-mini-2026-03-17 | chain_of_verification@3.2.0 | direct_control | 25 | 100.0% | 267 | 4 (1.5%) | 33 (12.4%) | 30 (11.2%) | 16.0% | 68.0% |
| openai:gpt-5.4-mini-2026-03-17 | chain_of_verification@3.2.0 | evidence_omission | 25 | 100.0% | 204 | 2 (1.0%) | 12 (5.9%) | 10 (4.9%) | 8.0% | 36.0% |
| openai:gpt-5.4-mini-2026-03-17 | chain_of_verification@3.2.0 | near_match_distractors | 25 | 100.0% | 262 | 3 (1.1%) | 27 (10.3%) | 25 (9.5%) | 8.0% | 60.0% |
| openai:gpt-5.4-mini-2026-03-17 | source_grounded@3.2.0 | conflicting_or_partial_evidence | 25 | 100.0% | 201 | 8 (4.0%) | 16 (8.0%) | 8 (4.0%) | 20.0% | 32.0% |
| openai:gpt-5.4-mini-2026-03-17 | source_grounded@3.2.0 | direct_control | 25 | 100.0% | 283 | 8 (2.8%) | 31 (10.9%) | 24 (8.5%) | 20.0% | 64.0% |
| openai:gpt-5.4-mini-2026-03-17 | source_grounded@3.2.0 | evidence_omission | 25 | 100.0% | 201 | 3 (1.5%) | 8 (4.0%) | 5 (2.5%) | 8.0% | 24.0% |
| openai:gpt-5.4-mini-2026-03-17 | source_grounded@3.2.0 | near_match_distractors | 25 | 100.0% | 278 | 11 (4.0%) | 41 (14.8%) | 34 (12.2%) | 32.0% | 64.0% |
| openai:gpt-5.4-mini-2026-03-17 | structured@3.2.0 | conflicting_or_partial_evidence | 25 | 100.0% | 204 | 9 (4.4%) | 24 (11.8%) | 15 (7.3%) | 28.0% | 52.0% |
| openai:gpt-5.4-mini-2026-03-17 | structured@3.2.0 | direct_control | 25 | 100.0% | 279 | 15 (5.4%) | 40 (14.3%) | 25 (9.0%) | 44.0% | 88.0% |
| openai:gpt-5.4-mini-2026-03-17 | structured@3.2.0 | evidence_omission | 25 | 100.0% | 201 | 7 (3.5%) | 25 (12.4%) | 20 (10.0%) | 16.0% | 56.0% |
| openai:gpt-5.4-mini-2026-03-17 | structured@3.2.0 | near_match_distractors | 25 | 100.0% | 263 | 11 (4.2%) | 39 (14.8%) | 33 (12.6%) | 24.0% | 60.0% |
| openai:gpt-5.5-2026-04-23 | baseline@3.2.0 | conflicting_or_partial_evidence | 25 | 100.0% | 248 | 12 (4.8%) | 25 (10.1%) | 14 (5.7%) | 32.0% | 56.0% |
| openai:gpt-5.5-2026-04-23 | baseline@3.2.0 | direct_control | 25 | 100.0% | 327 | 19 (5.8%) | 52 (15.9%) | 34 (10.4%) | 36.0% | 72.0% |
| openai:gpt-5.5-2026-04-23 | baseline@3.2.0 | evidence_omission | 25 | 100.0% | 238 | 8 (3.4%) | 20 (8.4%) | 12 (5.0%) | 16.0% | 44.0% |
| openai:gpt-5.5-2026-04-23 | baseline@3.2.0 | near_match_distractors | 25 | 100.0% | 308 | 13 (4.2%) | 54 (17.5%) | 44 (14.3%) | 40.0% | 84.0% |
| openai:gpt-5.5-2026-04-23 | chain_of_verification@3.2.0 | conflicting_or_partial_evidence | 25 | 100.0% | 261 | 11 (4.2%) | 25 (9.6%) | 14 (5.4%) | 24.0% | 44.0% |
| openai:gpt-5.5-2026-04-23 | chain_of_verification@3.2.0 | direct_control | 25 | 100.0% | 338 | 6 (1.8%) | 24 (7.1%) | 23 (6.8%) | 16.0% | 60.0% |
| openai:gpt-5.5-2026-04-23 | chain_of_verification@3.2.0 | evidence_omission | 25 | 100.0% | 236 | 0 (0.0%) | 7 (3.0%) | 7 (3.0%) | 0.0% | 16.0% |
| openai:gpt-5.5-2026-04-23 | chain_of_verification@3.2.0 | near_match_distractors | 25 | 100.0% | 322 | 3 (0.9%) | 23 (7.1%) | 25 (7.8%) | 12.0% | 44.0% |
| openai:gpt-5.5-2026-04-23 | source_grounded@3.2.0 | conflicting_or_partial_evidence | 25 | 100.0% | 255 | 4 (1.6%) | 10 (3.9%) | 6 (2.4%) | 12.0% | 24.0% |
| openai:gpt-5.5-2026-04-23 | source_grounded@3.2.0 | direct_control | 25 | 100.0% | 297 | 4 (1.4%) | 22 (7.4%) | 23 (7.7%) | 16.0% | 56.0% |
| openai:gpt-5.5-2026-04-23 | source_grounded@3.2.0 | evidence_omission | 25 | 100.0% | 257 | 1 (0.4%) | 8 (3.1%) | 7 (2.7%) | 4.0% | 24.0% |
| openai:gpt-5.5-2026-04-23 | source_grounded@3.2.0 | near_match_distractors | 25 | 100.0% | 296 | 3 (1.0%) | 12 (4.0%) | 12 (4.0%) | 12.0% | 36.0% |
| openai:gpt-5.5-2026-04-23 | structured@3.2.0 | conflicting_or_partial_evidence | 25 | 100.0% | 259 | 13 (5.0%) | 31 (12.0%) | 22 (8.5%) | 36.0% | 56.0% |
| openai:gpt-5.5-2026-04-23 | structured@3.2.0 | direct_control | 25 | 100.0% | 292 | 9 (3.1%) | 40 (13.7%) | 34 (11.6%) | 28.0% | 68.0% |
| openai:gpt-5.5-2026-04-23 | structured@3.2.0 | evidence_omission | 25 | 100.0% | 209 | 7 (3.4%) | 13 (6.2%) | 6 (2.9%) | 24.0% | 40.0% |
| openai:gpt-5.5-2026-04-23 | structured@3.2.0 | near_match_distractors | 25 | 100.0% | 295 | 1 (0.3%) | 15 (5.1%) | 14 (4.8%) | 4.0% | 32.0% |

Consensus unsupported requires both judges to flag a claim. Possible unsupported includes every claim flagged by either judge. Claims on which the judges disagree remain uncertain.

## Citation and exact-label agreement

| Condition | Exact support agreement | Exact citation agreement | Claim citation coverage | Citation support among agreed citations |
|---|---:|---:|---:|---:|
| openai:gpt-5.4-mini-2026-03-17 | baseline@3.2.0 | 90.5% | 89.2% | 80.8% | 97.7% |
| openai:gpt-5.4-mini-2026-03-17 | chain_of_verification@3.2.0 | 90.8% | 92.4% | 86.7% | 99.6% |
| openai:gpt-5.4-mini-2026-03-17 | source_grounded@3.2.0 | 92.3% | 93.2% | 90.2% | 97.8% |
| openai:gpt-5.4-mini-2026-03-17 | structured@3.2.0 | 89.8% | 90.6% | 82.5% | 97.8% |
| openai:gpt-5.5-2026-04-23 | baseline@3.2.0 | 90.5% | 90.1% | 77.4% | 99.2% |
| openai:gpt-5.5-2026-04-23 | chain_of_verification@3.2.0 | 93.9% | 93.2% | 80.7% | 99.7% |
| openai:gpt-5.5-2026-04-23 | source_grounded@3.2.0 | 95.7% | 95.8% | 93.6% | 99.3% |
| openai:gpt-5.5-2026-04-23 | structured@3.2.0 | 92.7% | 93.3% | 83.6% | 99.7% |

## Judge usage

| Judge | Responses | Parsed | API calls | Input tokens | Output tokens | Reasoning tokens | Total latency (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Primary | 800 | 800 | 800 | 2125170 | 901773 | 0 | 6765.9154 |
| Secondary | 800 | 800 | 821 | 2694446 | 789279 | 0 | 3471.5526 |

## Paired strategy effects versus baseline

Negative values favour the named strategy.

| Model | Strategy | Paired responses | Consensus claim-rate difference | Possible claim-rate difference | Consensus response difference | Possible response difference | Supported-claim difference | Factual-claim difference |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| openai:gpt-5.4-mini-2026-03-17 | chain_of_verification@3.2.0 | 100 | -0.049 [-0.069, -0.029] | -0.046 [-0.081, -0.013] | -0.260 | -0.100 | -0.480 | -1.120 |
| openai:gpt-5.4-mini-2026-03-17 | source_grounded@3.2.0 | 100 | -0.028 [-0.051, -0.005] | -0.055 [-0.087, -0.022] | -0.160 | -0.210 | -0.190 | -0.790 |
| openai:gpt-5.4-mini-2026-03-17 | structured@3.2.0 | 100 | -0.019 [-0.041, +0.002] | -0.016 [-0.043, +0.013] | -0.080 | -0.030 | -0.690 | -0.950 |
| openai:gpt-5.5-2026-04-23 | chain_of_verification@3.2.0 | 100 | -0.028 [-0.045, -0.011] | -0.061 [-0.087, -0.035] | -0.180 | -0.230 | +1.030 | +0.360 |
| openai:gpt-5.5-2026-04-23 | source_grounded@3.2.0 | 100 | -0.033 [-0.050, -0.018] | -0.082 [-0.110, -0.055] | -0.200 | -0.290 | +0.800 | -0.160 |
| openai:gpt-5.5-2026-04-23 | structured@3.2.0 | 100 | -0.016 [-0.036, +0.003] | -0.038 [-0.067, -0.010] | -0.080 | -0.150 | -0.160 | -0.660 |

## Interpretation limit

A primary model extracts and labels subject-matter claims. A secondary model independently labels the same fixed claims. Consensus unsupported means both judges flag a claim; possible unsupported means either judge flags it. Disagreements remain uncertain. This is automated, AI-assisted measurement and is not human-validated ground truth.
