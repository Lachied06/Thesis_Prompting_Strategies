import unittest

from src.reprocessing import RESPONSE_PARSER_VERSION, reparse_result_row


class ReprocessingTests(unittest.TestCase):
    def test_reparse_repairs_false_citation_and_derived_metrics(self):
        row = {
            "run_id": "run-1",
            "dataset": {"name": "SciFact_Synthesis", "task_id": "task-1"},
            "task": {
                "prompt": "Write a synthesis.",
                "reference_answer": None,
                "source_context": "[Document 101] Evidence",
                "metadata": {
                    "task_type": "academic_evidence_synthesis",
                    "allowed_document_ids": ["101"],
                    "word_range": [1, 100],
                },
            },
            "status": "completed",
            "response": {
                "raw": (
                    "SYNTHESIS: The document does address the claim [Document 101].\n"
                    "CITED_DOCUMENTS: 101"
                ),
                "cited_document_ids": ["does", "101"],
                "invalid_cited_document_ids": ["does"],
            },
            "ground_truth": {"label": None},
            "metrics": {
                "invalid_citation_count": 1,
                "has_invalid_citation": True,
                "input_tokens": 10,
            },
        }

        reparsed, changed = reparse_result_row(row)

        self.assertTrue(changed)
        self.assertEqual(reparsed["response"]["cited_document_ids"], ["101"])
        self.assertEqual(reparsed["response"]["invalid_cited_document_ids"], [])
        self.assertEqual(reparsed["metrics"]["invalid_citation_count"], 0)
        self.assertFalse(reparsed["metrics"]["has_invalid_citation"])
        self.assertEqual(reparsed["metrics"]["input_tokens"], 10)
        self.assertTrue(reparsed["metrics"]["word_count_within_range"])
        self.assertEqual(
            reparsed["postprocessing"]["response_parser_version"],
            RESPONSE_PARSER_VERSION,
        )
        self.assertEqual(row["response"]["invalid_cited_document_ids"], ["does"])

    def test_error_rows_are_preserved(self):
        row = {"run_id": "run-error", "status": "error", "response": None}
        reparsed, changed = reparse_result_row(row)
        self.assertFalse(changed)
        self.assertEqual(reparsed, row)


if __name__ == "__main__":
    unittest.main()
