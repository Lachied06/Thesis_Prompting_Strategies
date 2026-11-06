import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.evaluation import (
    blinded_review_package,
    manual_review_rows,
    read_review_condition_lookup,
    render_report,
    summarize_annotations,
    summarize_results,
    write_review_csv,
)


def result_row(
    strategy="baseline",
    version="2.0.0",
    predicted="SUPPORT",
    truth="SUPPORT",
    run_id="run-1",
    task_id="task-1",
    model="fake-model",
):
    return {
        "experiment_id": "exp-1",
        "run_id": run_id,
        "dataset": {"name": "SciFact", "task_id": task_id},
        "task": {"prompt": "Claim", "source_context": "Evidence"},
        "strategy": {"name": strategy, "version": version, "templates": []},
        "model": {"provider": "fake", "name": model},
        "status": "completed",
        "response": {
            "raw": f"LABEL: {predicted}\nEXPLANATION: Because.",
            "parsed_label": predicted,
            "explanation": "Because.",
            "parse_status": "parsed_strict",
        },
        "ground_truth": {"label": truth},
        "metrics": {
            "classification_correct": predicted == truth,
            "input_tokens": 10,
            "output_tokens": 5,
            "reasoning_tokens": 0,
            "latency_seconds": 1.25,
        },
        "trace": [{"response": {"text": "LABEL: SUPPORT\nEXPLANATION: draft"}}],
    }


def synthesis_result_row():
    row = result_row(version="3.0.0", predicted=None, truth="SUPPORT")
    row["dataset"] = {"name": "SciFact_Synthesis", "task_id": "synthesis-1"}
    row["task"] = {
        "prompt": "Write an academic synthesis.",
        "source_context": "[Document 101] Evidence",
        "metadata": {
            "task_type": "academic_evidence_synthesis",
            "allowed_document_ids": ["101"],
        },
    }
    row["response"] = {
        "raw": (
            "SYNTHESIS: Supported [Document 101], but invented [Document 999].\n"
            "CITED_DOCUMENTS: 101, 999"
        ),
        "parsed_label": None,
        "explanation": "Supported [Document 101], but invented [Document 999].",
        "parse_status": "parsed_strict",
        "cited_document_ids": ["101", "999"],
        "invalid_cited_document_ids": ["999"],
        "citation_parse_status": "parsed_strict",
    }
    row["metrics"]["classification_correct"] = None
    row["metrics"]["response_word_count"] = 8
    row["metrics"]["word_count_within_range"] = True
    return row


class EvaluationTests(unittest.TestCase):
    def test_objective_summary_keeps_accuracy_separate(self):
        summary = summarize_results([result_row()])
        condition = summary["conditions"]["baseline@2.0.0"]
        self.assertEqual(condition["accuracy"], 1.0)
        self.assertEqual(condition["label_coverage"], 1.0)
        self.assertEqual(condition["parse_rate"], 1.0)
        self.assertEqual(condition["api_calls"], 1)
        self.assertNotIn("hallucination_rate", condition)

    def test_multiple_models_are_reported_as_separate_conditions(self):
        summary = summarize_results(
            [
                result_row(run_id="run-1", model="large"),
                result_row(run_id="run-2", model="small", predicted="CONTRADICT"),
            ]
        )

        self.assertEqual(
            set(summary["conditions"]),
            {
                "fake:large | baseline@2.0.0",
                "fake:small | baseline@2.0.0",
            },
        )
        self.assertEqual(
            summary["conditions"]["fake:large | baseline@2.0.0"]["accuracy"],
            1.0,
        )
        self.assertEqual(
            summary["conditions"]["fake:small | baseline@2.0.0"]["accuracy"],
            0.0,
        )

    def test_no_evidence_recall_is_separate_from_false_abstention(self):
        summary = summarize_results(
            [
                result_row(
                    run_id="run-1",
                    task_id="decisive",
                    predicted="NO_EVIDENCE",
                    truth="SUPPORT",
                ),
                result_row(
                    run_id="run-2",
                    task_id="insufficient",
                    predicted="NO_EVIDENCE",
                    truth="NO_EVIDENCE",
                ),
            ]
        )
        condition = summary["conditions"]["baseline@2.0.0"]

        self.assertEqual(condition["abstention_rate"], 1.0)
        self.assertEqual(
            condition["false_no_evidence_rate_on_decisive_tasks"], 1.0
        )
        self.assertEqual(condition["no_evidence_recall"], 1.0)

    def test_review_template_and_annotation_aggregation(self):
        rows = manual_review_rows([result_row()])
        rows[0].update(
            {
                "faithfulness_score": "2",
                "unsupported_claim": "no",
                "source_misrepresentation": "no",
                "fabricated_citation": "no",
                "excessive_abstention": "no",
                "ambiguous_task": "no",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.csv"
            write_review_csv(path, rows)
            summary = summarize_annotations(path)

        self.assertEqual(summary["annotated_rows"], 1)
        self.assertEqual(
            summary["conditions"]["baseline@2.0.0"]["mean_faithfulness_score_0_to_2"],
            2,
        )

    def test_empty_annotation_file_is_rejected(self):
        rows = manual_review_rows([result_row()])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.csv"
            write_review_csv(path, rows)
            with self.assertRaisesRegex(ValueError, "zero completed rows"):
                summarize_annotations(path)

    def test_blinded_review_is_reproducible_and_aggregates_with_mapping(self):
        results = [
            result_row(run_id="run-1", task_id="task-1"),
            result_row(
                strategy="structured",
                run_id="run-2",
                task_id="task-2",
            ),
        ]
        blinded, mapping = blinded_review_package(results, seed=42)
        repeated, repeated_mapping = blinded_review_package(results, seed=42)

        self.assertEqual(blinded, repeated)
        self.assertEqual(mapping, repeated_mapping)
        self.assertEqual(
            set(blinded[0]),
            {
                "review_id",
                "task_prompt",
                "source_context",
                "explanation",
                "faithfulness_score",
                "unsupported_claim",
                "source_misrepresentation",
                "fabricated_citation",
                "excessive_abstention",
                "ambiguous_task",
                "reviewer_notes",
            },
        )
        for row in blinded:
            row.update(
                {
                    "faithfulness_score": "2",
                    "unsupported_claim": "no",
                    "source_misrepresentation": "no",
                    "fabricated_citation": "no",
                    "excessive_abstention": "no",
                    "ambiguous_task": "no",
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            review_path = Path(tmp) / "review.blinded.csv"
            mapping_path = Path(tmp) / "review.mapping.json"
            write_review_csv(review_path, blinded)
            mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
            lookup = read_review_condition_lookup(mapping_path)
            summary = summarize_annotations(review_path, lookup)

        self.assertEqual(summary["annotated_rows"], 2)
        self.assertEqual(
            set(summary["conditions"]),
            {"baseline@2.0.0", "structured@2.0.0"},
        )

    def test_synthesis_summary_reports_invalid_citation_identifiers(self):
        summary = summarize_results([synthesis_result_row()])
        condition = summary["conditions"]["baseline@3.0.0"]
        citation = condition["citation_metrics"]
        report = render_report(summary)

        self.assertIsNone(condition["accuracy"])
        self.assertEqual(condition["label_coverage"], 0.0)
        self.assertIsNone(condition["abstention_rate"])
        self.assertEqual(citation["applicable_responses"], 1)
        self.assertEqual(citation["cited_documents"], 2)
        self.assertEqual(citation["invalid_citations"], 1)
        self.assertEqual(citation["invalid_citation_response_rate"], 1.0)
        self.assertEqual(citation["word_count_compliance_rate"], 1.0)
        self.assertIn("Automated citation checks", report)
        self.assertIn("Reviewer faithfulness review", report)
        self.assertNotIn("Human faithfulness review", report)


if __name__ == "__main__":
    unittest.main()
