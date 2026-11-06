# Experiment evaluation

## Objective metrics

| Condition | Runs | Accuracy | Label coverage | Parse rate | Abstention | API calls | Tokens | Mean latency (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline@3.1.0 | 14 | 100.0% | 100.0% | 100.0% | 0.0% | 14 | 7185 | 4.1705 |
| chain_of_verification@3.1.0 | 14 | 100.0% | 100.0% | 100.0% | 0.0% | 42 | 41040 | 15.1696 |
| source_grounded@3.1.0 | 14 | 100.0% | 100.0% | 100.0% | 0.0% | 14 | 8815 | 4.2202 |
| structured@3.1.0 | 14 | 100.0% | 100.0% | 100.0% | 0.0% | 14 | 8589 | 4.0716 |

## Automated citation checks

| Condition | Applicable | Responses citing sources | Cited documents | Invalid identifiers | Responses with invalid identifiers | Word-count compliance |
|---|---:|---:|---:|---:|---:|---:|
| baseline@3.1.0 | 14 | 100.0% | 14 | 0 | 0.0% | 100.0% |
| chain_of_verification@3.1.0 | 14 | 100.0% | 14 | 0 | 0.0% | 100.0% |
| source_grounded@3.1.0 | 14 | 100.0% | 14 | 0 | 0.0% | 100.0% |
| structured@3.1.0 | 14 | 100.0% | 14 | 0 | 0.0% | 100.0% |

An invalid identifier is a cited document ID that was not supplied to the model. This automated check does not determine whether a valid supplied document actually supports the attached claim.

Accuracy is calculated only for responses with a parsed label. Label coverage shows the share of completed responses included in that calculation. Accuracy measures label agreement, not explanation faithfulness.

## Reviewer faithfulness review

| Condition | Reviewed | Mean faithfulness (0–2) | Unsupported claim | Source misrepresentation | Fabricated citation | Excessive abstention |
|---|---:|---:|---:|---:|---:|---:|
| baseline@3.1.0 | 14 | 1.9286 | 7.1% | 0.0% | 0.0% | 0.0% |
| chain_of_verification@3.1.0 | 14 | 2 | 0.0% | 0.0% | 0.0% | 0.0% |
| source_grounded@3.1.0 | 14 | 2 | 0.0% | 0.0% | 0.0% | 0.0% |
| structured@3.1.0 | 14 | 2 | 0.0% | 0.0% | 0.0% | 0.0% |

## Interpretation limits

The subjective fields require a documented annotation protocol and calibrated reviewer judgment. Automated citation checks detect identifiers outside the supplied source set; reviewers must still judge whether the cited source supports the associated statement.
