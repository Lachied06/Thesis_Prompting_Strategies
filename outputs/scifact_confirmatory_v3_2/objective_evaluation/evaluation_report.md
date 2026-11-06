# Experiment evaluation

## Objective metrics

| Condition | Runs | Accuracy | Label coverage | Parse rate | NO_EVIDENCE prediction | False NO_EVIDENCE on decisive tasks | NO_EVIDENCE recall | API calls | Tokens | Mean latency (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openai:gpt-5.4-mini-2026-03-17 | baseline@3.2.0 | 100 | 88.0% | 100.0% | 100.0% | 53.0% | 12.0% | 94.0% | 100 | 198592 | 2.5742 |
| openai:gpt-5.4-mini-2026-03-17 | chain_of_verification@3.2.0 | 100 | 91.9% | 99.0% | 100.0% | 56.6% | 12.2% | 100.0% | 300 | 801411 | 9.0794 |
| openai:gpt-5.4-mini-2026-03-17 | source_grounded@3.2.0 | 100 | 88.0% | 100.0% | 100.0% | 52.0% | 12.0% | 92.0% | 100 | 209226 | 2.4177 |
| openai:gpt-5.4-mini-2026-03-17 | structured@3.2.0 | 100 | 84.7% | 98.0% | 100.0% | 44.9% | 8.3% | 80.0% | 100 | 207946 | 2.5247 |
| openai:gpt-5.5-2026-04-23 | baseline@3.2.0 | 100 | 91.0% | 100.0% | 100.0% | 53.0% | 10.0% | 96.0% | 100 | 202094 | 5.2614 |
| openai:gpt-5.5-2026-04-23 | chain_of_verification@3.2.0 | 100 | 89.0% | 100.0% | 100.0% | 55.0% | 14.0% | 96.0% | 300 | 899113 | 19.5974 |
| openai:gpt-5.5-2026-04-23 | source_grounded@3.2.0 | 100 | 91.0% | 100.0% | 100.0% | 55.0% | 12.0% | 98.0% | 100 | 213550 | 4.9757 |
| openai:gpt-5.5-2026-04-23 | structured@3.2.0 | 100 | 88.0% | 100.0% | 100.0% | 50.0% | 10.0% | 90.0% | 100 | 212133 | 5.2261 |

## Automated citation checks

| Condition | Applicable | Responses citing sources | Cited documents | Invalid identifiers | Responses with invalid identifiers | Word-count compliance |
|---|---:|---:|---:|---:|---:|---:|
| openai:gpt-5.4-mini-2026-03-17 | baseline@3.2.0 | 100 | 99.0% | 257 | 0 | 0.0% | 96.0% |
| openai:gpt-5.4-mini-2026-03-17 | chain_of_verification@3.2.0 | 100 | 100.0% | 261 | 0 | 0.0% | 91.0% |
| openai:gpt-5.4-mini-2026-03-17 | source_grounded@3.2.0 | 100 | 100.0% | 257 | 0 | 0.0% | 94.0% |
| openai:gpt-5.4-mini-2026-03-17 | structured@3.2.0 | 100 | 100.0% | 291 | 0 | 0.0% | 98.0% |
| openai:gpt-5.5-2026-04-23 | baseline@3.2.0 | 100 | 100.0% | 271 | 1 | 1.0% | 97.0% |
| openai:gpt-5.5-2026-04-23 | chain_of_verification@3.2.0 | 100 | 100.0% | 283 | 0 | 0.0% | 99.0% |
| openai:gpt-5.5-2026-04-23 | source_grounded@3.2.0 | 100 | 100.0% | 300 | 0 | 0.0% | 95.0% |
| openai:gpt-5.5-2026-04-23 | structured@3.2.0 | 100 | 100.0% | 345 | 0 | 0.0% | 98.0% |

An invalid identifier is a cited document ID that was not supplied to the model. This automated check does not determine whether a valid supplied document actually supports the attached claim.

Accuracy is calculated only for responses with a parsed label. Label coverage shows the share of completed responses included in that calculation. Accuracy measures label agreement, not explanation faithfulness.

## Reviewer faithfulness review

No completed annotations were supplied. Fill in the generated manual-review CSV, then rerun this command with `--annotations`.

## Interpretation limits

The subjective fields require a documented annotation protocol and calibrated reviewer judgment. Automated citation checks detect identifiers outside the supplied source set; reviewers must still judge whether the cited source supports the associated statement.
