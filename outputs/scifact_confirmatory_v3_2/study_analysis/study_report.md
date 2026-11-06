# Confirmatory strategy analysis

## Overall strategy outcomes

| Condition | Responses | Verdict accuracy | Mean supported claims | Mean consensus unsupported | Mean possible unsupported | Any consensus unsupported | Any possible unsupported | Citation support | Mean tokens | Mean latency (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openai:gpt-5.4-mini-2026-03-17 | baseline@3.2.0 | 100 | 88.0% | 8.81 | 5.9% | 14.4% | 36.0% | 67.0% | 97.7% | 1985.92 | 2.57 |
| openai:gpt-5.4-mini-2026-03-17 | chain_of_verification@3.2.0 | 100 | 91.9% | 8.33 | 1.1% | 9.8% | 10.0% | 57.0% | 99.6% | 8014.11 | 9.08 |
| openai:gpt-5.4-mini-2026-03-17 | source_grounded@3.2.0 | 100 | 88.0% | 8.62 | 3.1% | 8.9% | 20.0% | 46.0% | 97.8% | 2092.26 | 2.42 |
| openai:gpt-5.4-mini-2026-03-17 | structured@3.2.0 | 100 | 84.7% | 8.12 | 4.0% | 12.8% | 28.0% | 64.0% | 97.8% | 2079.46 | 2.52 |
| openai:gpt-5.5-2026-04-23 | baseline@3.2.0 | 100 | 91.0% | 9.65 | 4.4% | 12.7% | 31.0% | 64.0% | 99.2% | 2020.94 | 5.26 |
| openai:gpt-5.5-2026-04-23 | chain_of_verification@3.2.0 | 100 | 89.0% | 10.68 | 1.6% | 6.6% | 13.0% | 41.0% | 99.7% | 8991.13 | 19.60 |
| openai:gpt-5.5-2026-04-23 | source_grounded@3.2.0 | 100 | 91.0% | 10.45 | 1.1% | 4.5% | 11.0% | 35.0% | 99.3% | 2135.50 | 4.98 |
| openai:gpt-5.5-2026-04-23 | structured@3.2.0 | 100 | 88.0% | 9.49 | 2.8% | 8.9% | 23.0% | 49.0% | 99.7% | 2121.33 | 5.23 |

## Content, abstention, and measurement checks

| Condition | Mean factual claims | Supported-claim rate | NO_EVIDENCE prediction | False NO_EVIDENCE on decisive tasks | NO_EVIDENCE recall | Citation coverage | Invalid-ID responses | Mean words | Judge binary agreement |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openai:gpt-5.4-mini-2026-03-17 | baseline@3.2.0 | 10.42 | 84.5% | 53.0% | 12.0% | 94.0% | 80.8% | 0.0% | 209.51 | 91.2% |
| openai:gpt-5.4-mini-2026-03-17 | chain_of_verification@3.2.0 | 9.30 | 89.6% | 56.6% | 12.2% | 100.0% | 86.7% | 0.0% | 201.05 | 91.0% |
| openai:gpt-5.4-mini-2026-03-17 | source_grounded@3.2.0 | 9.63 | 89.5% | 52.0% | 12.0% | 92.0% | 90.2% | 0.0% | 204.32 | 93.2% |
| openai:gpt-5.4-mini-2026-03-17 | structured@3.2.0 | 9.47 | 85.7% | 44.9% | 8.3% | 80.0% | 82.5% | 0.0% | 207.94 | 90.9% |
| openai:gpt-5.5-2026-04-23 | baseline@3.2.0 | 11.21 | 86.1% | 53.0% | 10.0% | 96.0% | 77.4% | 1.0% | 228.52 | 91.2% |
| openai:gpt-5.5-2026-04-23 | chain_of_verification@3.2.0 | 11.57 | 92.3% | 55.0% | 14.0% | 96.0% | 80.7% | 0.0% | 227.68 | 94.9% |
| openai:gpt-5.5-2026-04-23 | source_grounded@3.2.0 | 11.05 | 94.6% | 55.0% | 12.0% | 98.0% | 93.6% | 0.0% | 227.25 | 96.4% |
| openai:gpt-5.5-2026-04-23 | structured@3.2.0 | 10.55 | 90.0% | 50.0% | 10.0% | 90.0% | 83.6% | 0.0% | 229.19 | 93.5% |

## Consensus hallucination types

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

## Paired effects versus baseline

Negative hallucination-rate differences favour the named strategy. Positive supported-claim differences indicate more source-supported content.

| Model | Strategy | Paired tasks | Consensus-rate difference | Possible-rate difference | Supported-claim difference | Factual-claim difference |
|---|---|---:|---:|---:|---:|---:|
| openai:gpt-5.4-mini-2026-03-17 | chain_of_verification@3.2.0 | 100 | -0.049 [-0.069, -0.029] | -0.046 [-0.081, -0.013] | -0.480 [-1.113, +0.093] | -1.120 |
| openai:gpt-5.4-mini-2026-03-17 | source_grounded@3.2.0 | 100 | -0.028 [-0.051, -0.005] | -0.055 [-0.087, -0.022] | -0.190 [-0.750, +0.340] | -0.790 |
| openai:gpt-5.4-mini-2026-03-17 | structured@3.2.0 | 100 | -0.019 [-0.041, +0.002] | -0.016 [-0.043, +0.013] | -0.690 [-1.240, -0.223] | -0.950 |
| openai:gpt-5.5-2026-04-23 | chain_of_verification@3.2.0 | 100 | -0.028 [-0.045, -0.011] | -0.061 [-0.087, -0.035] | +1.030 [+0.576, +1.481] | 0.360 |
| openai:gpt-5.5-2026-04-23 | source_grounded@3.2.0 | 100 | -0.033 [-0.050, -0.018] | -0.082 [-0.110, -0.055] | +0.800 [+0.167, +1.484] | -0.160 |
| openai:gpt-5.5-2026-04-23 | structured@3.2.0 | 100 | -0.016 [-0.036, +0.003] | -0.038 [-0.067, -0.010] | -0.160 [-0.792, +0.486] | -0.660 |

## Interpretation limits

- The primary endpoint is the paired mean per-response consensus unsupported-claim proportion; the either-judge measure is a sensitivity endpoint.
- The judges are automated and the labels are not human-validated ground truth.
- Bracketed intervals are deterministic paired cluster-bootstrap 95% intervals, clustered by original SciFact source item when available. They quantify source-task sampling uncertainty conditional on the automated labels, not judge validity.
- Strategy effects refer to complete prompt packages. Chain of Verification also uses additional requests and computation.
- Citation measures concern supplied document identifiers and semantic claim-source support, not unconstrained bibliographic-reference fabrication.
- Accuracy, supported-claim yield, abstention, and cost must be interpreted beside hallucination rates; a strategy is not better merely because it says less.
