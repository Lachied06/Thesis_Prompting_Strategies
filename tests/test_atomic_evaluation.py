import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.atomic_evaluation import (
    _paired_bootstrap_mean_ci,
    blinded_atomic_review_package,
    build_atomic_consensus,
    build_atomic_judge_request,
    compare_atomic_annotations,
    judge_existing_claims,
    judge_results,
    parse_atomic_judgment,
    render_atomic_consensus_report,
    retry_failed_secondary_claims,
    summarize_atomic_consensus,
    summarize_atomic_annotations,
    summarize_atomic_judgments,
    write_atomic_review_csv,
    write_atomic_disagreements_csv,
)
from src.schemas import GenerationResponse


def result_row(run_id="run-1", model="model-a", strategy="baseline", difficulty="direct"):
    return {
        "experiment_id": "exp-1",
        "run_id": run_id,
        "dataset": {"name": "SciFact_Difficulty_Pilot", "task_id": "task-1"},
        "task": {
            "prompt": "Evaluate claim X.",
            "source_context": "[Document 1] Claim X is supported.",
            "metadata": {"difficulty_category": difficulty},
        },
        "model": {"provider": "fake", "name": model},
        "strategy": {"name": strategy, "version": "3.2.0"},
        "status": "completed",
        "response": {"raw": "Claim X is supported [Document 1]."},
    }


def hallucination_type_for(support):
    return "NONE" if support in {"SUPPORTED", "NOT_FACTUAL"} else "UNSUPPORTED_ADDITION"


def judgment_record(run_id="run-1", support="NOT_IN_SOURCES"):
    row = result_row(run_id=run_id)
    return {
        "status": "parsed",
        "subject": {
            "run_id": run_id,
            "task_id": "task-1",
            "task_prompt": row["task"]["prompt"],
            "source_context": row["task"]["source_context"],
            "response_text": row["response"]["raw"],
            "difficulty_category": "direct",
            "model": row["model"],
            "strategy": row["strategy"],
        },
        "claims": [
            {
                "claim_id": f"{run_id}:claim:001",
                "claim": "Claim X is supported.",
                "support_status": support,
                "hallucination_type": hallucination_type_for(support),
                "cited_document_ids": ["1"],
                "citation_status": "SUPPORTED",
                "rationale": "Document 1 states it.",
            }
        ],
    }


class FakeProvider:
    def generate(self, request):
        return GenerationResponse(
            text=json.dumps(
                {
                    "claims": [
                        {
                            "claim": "Claim X is supported.",
                            "support_status": "SUPPORTED",
                            "hallucination_type": "NONE",
                            "cited_document_ids": ["1"],
                            "citation_status": "SUPPORTED",
                            "rationale": "Document 1 states it.",
                        }
                    ]
                }
            ),
            input_tokens=20,
            output_tokens=10,
        )


class RetryProvider:
    def __init__(self):
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        if self.calls == 1:
            return GenerationResponse(
                text="This is not valid JSON.",
                input_tokens=20,
                output_tokens=5,
            )
        return FakeProvider().generate(request)


class SecondaryProvider:
    def __init__(self, support="SUPPORTED", citation="SUPPORTED"):
        self.support = support
        self.citation = citation
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        return GenerationResponse(
            text=json.dumps(
                {
                    "claims": [
                        {
                            "claim_id": "run-1:claim:001",
                            "support_status": self.support,
                            "hallucination_type": hallucination_type_for(self.support),
                            "citation_status": self.citation,
                            "rationale": "Independent source-only decision.",
                        }
                    ]
                }
            ),
            input_tokens=25,
            output_tokens=8,
        )


class AtomicEvaluationTests(unittest.TestCase):
    def test_bootstrap_clusters_paired_evidence_transformations(self):
        interval = _paired_bootstrap_mean_ci(
            [1.0, -1.0, 1.0, -1.0],
            cluster_ids=["source-a", "source-a", "source-b", "source-b"],
            seed_material="test",
            samples=100,
        )

        self.assertEqual(interval, [0.0, 0.0])

    def test_primary_prompt_excludes_meta_claims_and_requires_strict_identity(self):
        request = build_atomic_judge_request(result_row(), max_output_tokens=500)

        self.assertIn("EXCLUDE all of the following", request.user_prompt)
        self.assertIn("descriptions of the question, task, or proposed answer", request.user_prompt)
        self.assertIn("Treat entity identity strictly", request.user_prompt)
        self.assertIn("EVIDENCE_OVERSTATEMENT", request.user_prompt)

    def test_atomic_parser_validates_structured_labels(self):
        claims = parse_atomic_judgment(FakeProvider().generate(None).text, "run-1")
        self.assertEqual(claims[0]["support_status"], "SUPPORTED")
        self.assertEqual(claims[0]["hallucination_type"], "NONE")
        with self.assertRaisesRegex(ValueError, "invalid support_status"):
            parse_atomic_judgment(
                '{"claims":[{"claim":"X","support_status":"MAYBE",'
                '"cited_document_ids":[],"citation_status":"NO_CITATION"}]}',
                "run-1",
            )

    def test_judge_logs_exact_prompt_and_summary_counts_claims(self):
        checkpointed_judgments = []
        checkpointed_prompts = []
        judgments, prompts = judge_results(
            [result_row()],
            judge_provider="fake",
            judge_model="judge",
            provider_builder=lambda provider, model: FakeProvider(),
            on_judgment=checkpointed_judgments.append,
            on_prompt=checkpointed_prompts.append,
        )
        summary = summarize_atomic_judgments(judgments)
        condition = summary["conditions"]["fake:model-a | baseline@3.2.0"]

        self.assertEqual(judgments[0]["status"], "parsed")
        self.assertEqual(len(prompts[0]["prompt_hash"]), 64)
        self.assertEqual(condition["factual_claims"], 1)
        self.assertEqual(condition["unsupported_atomic_claim_rate"], 0.0)
        self.assertEqual(checkpointed_judgments, judgments)
        self.assertEqual(checkpointed_prompts, prompts)

    def test_judge_retries_parse_failures_and_logs_each_attempt(self):
        provider = RetryProvider()
        judgments, prompts = judge_results(
            [result_row()],
            judge_provider="fake",
            judge_model="judge",
            max_attempts=2,
            retry_delay_seconds=0,
            provider_builder=lambda provider_name, model_name: provider,
        )

        self.assertEqual(provider.calls, 2)
        self.assertEqual(judgments[0]["status"], "parsed")
        self.assertEqual(judgments[0]["attempt_count"], 2)
        self.assertEqual(len(judgments[0]["attempts"]), 2)
        self.assertEqual(judgments[0]["attempts"][0]["status"], "error")
        self.assertEqual(judgments[0]["attempts"][1]["status"], "parsed")
        self.assertEqual(judgments[0]["usage"]["input_tokens"], 40)
        self.assertEqual(judgments[0]["usage"]["output_tokens"], 15)
        self.assertEqual([prompt["attempt_number"] for prompt in prompts], [1, 2])

    def test_dual_judge_consensus_preserves_disagreement_as_uncertain(self):
        primary, _ = judge_results(
            [result_row()],
            judge_provider="fake",
            judge_model="primary",
            provider_builder=lambda provider, model: FakeProvider(),
        )
        checkpointed_secondary = []
        checkpointed_secondary_prompts = []
        secondary, prompts = judge_existing_claims(
            primary,
            judge_provider="fake",
            judge_model="secondary",
            retry_delay_seconds=0,
            provider_builder=lambda provider, model: SecondaryProvider(
                support="NOT_IN_SOURCES",
                citation="UNSUPPORTED",
            ),
            on_judgment=checkpointed_secondary.append,
            on_prompt=checkpointed_secondary_prompts.append,
        )
        consensus = build_atomic_consensus(primary, secondary)
        summary = summarize_atomic_consensus(
            consensus,
            primary_records=primary,
            secondary_records=secondary,
        )
        condition = summary["conditions"]["fake:model-a | baseline@3.2.0"]
        claim = consensus[0]["claims"][0]

        self.assertEqual(claim["support_consensus"], "UNCERTAIN")
        self.assertEqual(claim["hallucination_type_consensus"], "UNCERTAIN_TYPE")
        self.assertTrue(claim["possible_unsupported"])
        self.assertEqual(condition["consensus_unsupported_claim_rate"], 0.0)
        self.assertEqual(condition["possible_unsupported_claim_rate"], 1.0)
        self.assertEqual(
            condition["possible_hallucination_type_counts"]["UNSUPPORTED_ADDITION"],
            1,
        )
        self.assertEqual(condition["support_binary_agreement"], 0.0)
        self.assertEqual(prompts[0]["judge_role"], "secondary")
        self.assertEqual(checkpointed_secondary, secondary)
        self.assertEqual(checkpointed_secondary_prompts, prompts)
        self.assertIn("direct", condition["by_difficulty"])
        self.assertIn(
            "Consensus results by difficulty",
            render_atomic_consensus_report(summary),
        )

    def test_retry_only_failed_secondary_claims_preserves_successes(self):
        primary_failed = judgment_record(run_id="run-1", support="SUPPORTED")
        primary_success = judgment_record(run_id="run-2", support="SUPPORTED")
        successful_secondary = {
            **primary_success,
            "judge_role": "secondary",
            "judge": {"provider": "fake", "model": "secondary"},
            "attempt_count": 1,
            "attempts": [{"attempt_number": 1, "status": "parsed"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "latency_seconds": 0.1,
        }
        failed_secondary = {
            **primary_failed,
            "judge_role": "secondary",
            "judge": {"provider": "fake", "model": "secondary"},
            "status": "error",
            "claims": [],
            "attempt_count": 2,
            "attempts": [
                {"attempt_number": 1, "status": "error"},
                {"attempt_number": 2, "status": "error"},
            ],
            "usage": {"input_tokens": 20, "output_tokens": 6},
            "latency_seconds": 0.2,
            "error": "parse failure",
        }
        provider = SecondaryProvider()

        repaired, prompts, run_ids = retry_failed_secondary_claims(
            [primary_failed, primary_success],
            [failed_secondary, successful_secondary],
            judge_provider="fake",
            judge_model="secondary",
            retry_delay_seconds=0,
            provider_builder=lambda provider_name, model_name: provider,
        )

        repaired_by_run = {
            record["subject"]["run_id"]: record for record in repaired
        }
        self.assertEqual(provider.calls, 1)
        self.assertEqual(run_ids, ["run-1"])
        self.assertEqual(repaired_by_run["run-1"]["status"], "parsed")
        self.assertEqual(repaired_by_run["run-1"]["attempt_count"], 3)
        self.assertEqual(prompts[0]["attempt_number"], 3)
        self.assertIs(repaired_by_run["run-2"], successful_secondary)

    def test_dual_judge_consensus_counts_shared_unsupported_label(self):
        primary = [judgment_record(support="NOT_IN_SOURCES")]
        primary[0]["judge"] = {"provider": "fake", "model": "primary"}
        primary[0]["usage"] = {"input_tokens": 10, "output_tokens": 5}
        primary[0]["attempt_count"] = 1
        primary[0]["latency_seconds"] = 0.1
        secondary = [
            {
                **primary[0],
                "judge_role": "secondary",
                "judge": {"provider": "fake", "model": "secondary"},
                "claims": [
                    {
                        **primary[0]["claims"][0],
                        "support_status": "CONTRADICTED",
                        "citation_status": "SUPPORTED",
                    }
                ],
            }
        ]
        consensus = build_atomic_consensus(primary, secondary)
        summary = summarize_atomic_consensus(consensus)
        condition = summary["conditions"]["fake:model-a | baseline@3.2.0"]

        self.assertEqual(
            consensus[0]["claims"][0]["support_consensus"],
            "CONSENSUS_UNSUPPORTED",
        )
        self.assertEqual(condition["consensus_unsupported_claim_rate"], 1.0)
        self.assertEqual(condition["possible_unsupported_claim_rate"], 1.0)
        self.assertEqual(condition["support_binary_agreement"], 1.0)
        self.assertEqual(
            condition["consensus_hallucination_type_counts"]["UNSUPPORTED_ADDITION"],
            1,
        )
        self.assertEqual(condition["mean_evaluable_claims_per_response"], 1.0)
        self.assertEqual(
            condition["mean_consensus_supported_claims_per_response"], 0.0
        )

    def test_summary_reports_paired_strategy_effects_against_baseline(self):
        baseline = judgment_record(run_id="run-base", support="NOT_IN_SOURCES")
        treatment = judgment_record(run_id="run-treatment", support="SUPPORTED")
        treatment["subject"]["strategy"] = {
            "name": "source_grounded",
            "version": "3.2.0",
        }
        summary = summarize_atomic_judgments([baseline, treatment])
        effect = summary["paired_strategy_effects_vs_baseline"]["fake:model-a"][
            "source_grounded@3.2.0"
        ]

        self.assertEqual(effect["paired_responses"], 1)
        self.assertEqual(
            effect["mean_paired_unsupported_claim_rate_difference"], -1.0
        )
        self.assertEqual(
            effect["mean_paired_response_hallucination_difference"], -1
        )

    def test_consensus_paired_effects_include_deterministic_intervals_and_yield(self):
        baseline = judgment_record(run_id="run-base", support="NOT_IN_SOURCES")
        treatment = judgment_record(run_id="run-treatment", support="SUPPORTED")
        treatment["subject"]["strategy"] = {
            "name": "source_grounded",
            "version": "3.2.0",
        }
        primary = [baseline, treatment]
        secondary = [
            {**record, "claims": [dict(record["claims"][0])]}
            for record in primary
        ]
        consensus = build_atomic_consensus(primary, secondary)
        summary = summarize_atomic_consensus(consensus)
        effect = summary["paired_strategy_effects_vs_baseline"]["fake:model-a"][
            "source_grounded@3.2.0"
        ]

        self.assertEqual(
            effect[
                "paired_consensus_unsupported_claim_rate_difference_95ci"
            ],
            [-1.0, -1.0],
        )
        self.assertEqual(
            effect["mean_paired_consensus_supported_claim_count_difference"],
            1.0,
        )

    def test_blinded_sample_hides_treatment_and_validates_agreement(self):
        rows, mapping = blinded_atomic_review_package([judgment_record()], seed=42)
        self.assertNotIn("model", rows[0])
        self.assertNotIn("automatic_support_label", rows[0])
        rows[0]["reviewer_support_label"] = "NOT_IN_SOURCES"
        rows[0]["reviewer_citation_label"] = "SUPPORTED"

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "review.csv"
            map_path = Path(tmp) / "mapping.json"
            write_atomic_review_csv(csv_path, rows)
            map_path.write_text(json.dumps(mapping), encoding="utf-8")
            agreement = summarize_atomic_annotations(csv_path, map_path)

        self.assertEqual(agreement["completed_claims"], 1)
        self.assertEqual(agreement["support_label_exact_agreement"], 1.0)
        self.assertEqual(agreement["binary_unsupported_agreement"], 1.0)

    def test_annotation_comparison_exports_unblinded_disagreements(self):
        rows, mapping = blinded_atomic_review_package([judgment_record()], seed=42)
        rows[0]["reviewer_support_label"] = "SUPPORTED"
        rows[0]["reviewer_citation_label"] = "UNSUPPORTED"
        rows[0]["reviewer_notes"] = "Reviewer disagreed."

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "review.csv"
            map_path = Path(tmp) / "mapping.json"
            disagreement_path = Path(tmp) / "review_disagreements.csv"
            write_atomic_review_csv(csv_path, rows)
            map_path.write_text(json.dumps(mapping), encoding="utf-8")
            agreement, disagreements = compare_atomic_annotations(csv_path, map_path)
            written = write_atomic_disagreements_csv(
                disagreement_path, disagreements
            )
            with disagreement_path.open(encoding="utf-8", newline="") as handle:
                exported = list(csv.DictReader(handle))

        self.assertEqual(agreement["support_label_exact_disagreement_count"], 1)
        self.assertEqual(agreement["binary_unsupported_disagreement_count"], 1)
        self.assertEqual(agreement["binary_unsupported_confusion"]["false_positive"], 1)
        self.assertEqual(agreement["claims_with_any_exact_label_disagreement"], 1)
        self.assertEqual(written, 1)
        self.assertEqual(exported[0]["review_id"], rows[0]["review_id"])
        self.assertEqual(exported[0]["binary_unsupported_match"], "no")
        self.assertEqual(exported[0]["model_name"], "model-a")


if __name__ == "__main__":
    unittest.main()
