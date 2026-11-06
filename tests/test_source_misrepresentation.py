"""Provider-free tests of citation eligibility and paired cluster estimation."""
import copy
import tempfile
import unittest
from pathlib import Path

from analyse_source_misrepresentation import (
    MODELS, STRATEGIES, cluster_interval, paired_contrasts,
    response_metrics, run_analysis, validate_records,
)


def claim(primary, secondary, cited=True, excluded=False):
    return {"claim_id": "1", "support_consensus": "EXCLUDED_NOT_FACTUAL" if excluded else "UNCERTAIN",
            "cited_document_ids": ["doc"] if cited else [],
            "primary_citation_status": primary, "secondary_citation_status": secondary,
            "citation_consensus": primary if primary == secondary else "UNCERTAIN"}


def record(claims):
    return {"status": "consensus_computed", "subject": {
        "model": {"provider": "openai", "name": MODELS[0]},
        "strategy": {"name": "baseline", "version": "3.2.0"},
        "task_id": "task", "source_item_id": "source", "run_id": "run",
        "task_prompt": "Task", "source_context": "[Document doc]\nEvidence"}, "claims": claims}


class SourceMisrepresentationTests(unittest.TestCase):
    def test_citation_denominator_and_either_judge_union(self):
        r = record([claim("UNSUPPORTED", "UNSUPPORTED"),
                    claim("SUPPORTED", "UNSUPPORTED"),
                    claim("SUPPORTED", "SUPPORTED"),
                    claim("NOT_APPLICABLE", "UNSUPPORTED"),
                    claim("NO_CITATION", "UNSUPPORTED", cited=False),
                    claim("NOT_APPLICABLE", "NOT_APPLICABLE", cited=False, excluded=True)])
        m = response_metrics(r)
        self.assertEqual((m["evaluable_claims"], m["cited_claims"]), (5, 4))
        self.assertEqual(m["consensus_mismatch_rate"], .25)
        self.assertEqual(m["either_judge_mismatch_rate"], .75)
        self.assertEqual(m["citation_attachment_coverage"], .8)

    def test_zero_citations_is_undefined_mismatch_not_perfect_performance(self):
        m = response_metrics(record([claim("NO_CITATION", "UNSUPPORTED", cited=False)]))
        self.assertIsNone(m["consensus_mismatch_rate"])
        self.assertIsNone(m["either_judge_mismatch_rate"])
        self.assertEqual(m["citation_attachment_coverage"], 0)
        self.assertIsNone(response_metrics(record([]))["citation_attachment_coverage"])

    def test_whole_source_cluster_is_resampled_together(self):
        ci = cluster_interval([-1, 1, -2, 2], ["A", "A", "B", "B"], "test")
        self.assertEqual(ci, [0, 0])

    def test_duplicate_task_is_rejected(self):
        r = record([claim("SUPPORTED", "SUPPORTED")])
        with self.assertRaisesRegex(ValueError, "Duplicate model-strategy-task"):
            validate_records([r, copy.deepcopy(r)])

    def test_out_of_packet_attached_identifier_is_rejected(self):
        r = record([claim("SUPPORTED", "SUPPORTED")])
        r["claims"][0]["cited_document_ids"] = ["unknown"]
        with self.assertRaisesRegex(ValueError, "out-of-packet"):
            validate_records([r])

    def test_pairing_uses_task_ids_and_undefined_pairs_are_disclosed(self):
        rows = []
        for model in MODELS:
            for strategy in STRATEGIES:
                for task, value in [("B", .2), ("A", .8)]:
                    value = value if strategy == "baseline" else value / 2
                    rows.append({"model": model, "strategy": strategy, "task_id": task,
                                 "source_item_id": task, "consensus_mismatch_rate": value,
                                 "either_judge_mismatch_rate": value, "citation_attachment_coverage": 1})
        first = paired_contrasts(rows, samples=100)
        self.assertEqual(first, paired_contrasts(list(reversed(rows)), samples=100))
        self.assertAlmostEqual(first[0]["mean_paired_difference"], -.25)
        for row in rows:
            if row["model"] == MODELS[0] and row["strategy"] == "structured" and row["task_id"] == "A":
                row["consensus_mismatch_rate"] = None
        changed = paired_contrasts(rows, samples=100)[0]
        self.assertEqual(changed["paired_tasks"], 1)
        self.assertEqual(changed["excluded_pairs_undefined_rate"], 1)
        self.assertAlmostEqual(changed["mean_paired_difference"], -.1)

    def test_existing_analysis_is_not_overwritten_by_default(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            marker = out / "analysis_report.md"
            marker.write_text("Keep this")
            with self.assertRaises(FileExistsError):
                run_analysis(out / "nonexistent.jsonl", out)
            self.assertEqual(marker.read_text(), "Keep this")


if __name__ == "__main__":
    unittest.main()
