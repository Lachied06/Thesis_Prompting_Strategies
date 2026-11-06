import unittest

from build_study_report import combined_condition_rows, render_study_report


class StudyReportTests(unittest.TestCase):
    def test_combined_report_keeps_risk_utility_and_cost_together(self):
        condition = "openai:model-a | source_grounded@3.2.0"
        objective = {
            "conditions": {
                condition: {
                    "provider": "openai",
                    "model": "model-a",
                    "strategy": "source_grounded",
                    "version": "3.2.0",
                    "accuracy": 0.9,
                    "abstention_rate": 0.2,
                    "api_calls": 10,
                    "tokens": {"mean_total_per_run": 500.0},
                    "latency_seconds": {"mean": 1.5},
                    "citation_metrics": {
                        "invalid_citation_response_rate": 0.0,
                        "mean_response_word_count": 210.0,
                    },
                }
            }
        }
        atomic = {
            "conditions": {
                condition: {
                    "consensus_responses": 10,
                    "mean_evaluable_claims_per_response": 5.0,
                    "mean_consensus_supported_claims_per_response": 4.0,
                    "consensus_supported_claim_rate": 0.8,
                    "mean_response_consensus_unsupported_claim_rate": 0.05,
                    "mean_response_possible_unsupported_claim_rate": 0.1,
                    "consensus_response_hallucination_rate": 0.2,
                    "possible_response_hallucination_rate": 0.3,
                    "uncertain_claim_rate": 0.05,
                    "consensus_claim_citation_coverage": 0.9,
                    "consensus_citation_support_rate": 0.95,
                    "support_binary_agreement": 0.9,
                    "consensus_hallucination_type_counts": {
                        "EVIDENCE_OVERSTATEMENT": 2
                    },
                }
            },
            "paired_strategy_effects_vs_baseline": {},
        }

        rows = combined_condition_rows(objective, atomic)
        self.assertEqual(rows[0]["verdict_accuracy"], 0.9)
        self.assertEqual(rows[0]["mean_supported_claims_per_response"], 4.0)
        self.assertEqual(
            rows[0]["hallucination_type_counts"]["EVIDENCE_OVERSTATEMENT"],
            2,
        )
        report = render_study_report(objective, atomic, rows)
        self.assertIn("Overall strategy outcomes", report)
        self.assertIn("Mean supported claims", report)
        self.assertIn("Evidence overstatement", report)


if __name__ == "__main__":
    unittest.main()
