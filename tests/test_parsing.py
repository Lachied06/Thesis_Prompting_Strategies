import unittest

from src.parsing import normalize_label, parse_response
from src.schemas import Task


class ParsingTests(unittest.TestCase):
    def setUp(self):
        self.task = Task(
            task_id="1",
            dataset="SciFact",
            prompt="Assess a claim",
            metadata={"task_type": "scientific_claim_verification"},
        )

    def test_strict_response(self):
        parsed = parse_response(
            "LABEL: SUPPORT\nEXPLANATION: The evidence states the claim.",
            self.task,
        )
        self.assertEqual(parsed.parsed_label, "SUPPORT")
        self.assertEqual(parsed.parse_status, "parsed_strict")
        self.assertEqual(parsed.explanation, "The evidence states the claim.")

    def test_markdown_label(self):
        parsed = parse_response(
            "**LABEL**: **CONTRADICT**\n**EXPLANATION**: Opposite result.",
            self.task,
        )
        self.assertEqual(parsed.parsed_label, "CONTRADICT")
        self.assertEqual(parsed.explanation, "Opposite result.")

    def test_fallback_response(self):
        parsed = parse_response("Cannot be determined. No source.", self.task)
        self.assertEqual(parsed.parsed_label, "NO_EVIDENCE")
        self.assertEqual(parsed.parse_status, "parsed_fallback")

    def test_normalize_ground_truth(self):
        self.assertEqual(normalize_label("supported"), "SUPPORT")
        self.assertEqual(normalize_label("NO EVIDENCE"), "NO_EVIDENCE")
        self.assertIsNone(normalize_label("not supported"))

    def test_synthesis_response_extracts_and_validates_document_ids(self):
        task = Task(
            task_id="synthesis-1",
            dataset="SciFact_Synthesis",
            prompt="Write a synthesis",
            source_context="[Document 101] Evidence\n[Document 102] Evidence",
            metadata={
                "task_type": "academic_evidence_synthesis",
                "allowed_document_ids": ["101", "102"],
            },
        )
        parsed = parse_response(
            "SYNTHESIS: The supplied evidence supports one point [Document 101] "
            "but another statement relies on an unavailable source [Document 999].\n"
            "CITED_DOCUMENTS: 101, 999",
            task,
        )

        self.assertEqual(parsed.parse_status, "parsed_strict")
        self.assertEqual(parsed.cited_document_ids, ["101", "999"])
        self.assertEqual(parsed.invalid_cited_document_ids, ["999"])
        self.assertEqual(parsed.citation_parse_status, "parsed_strict")

    def test_synthesis_without_contract_uses_fallback(self):
        task = Task(
            task_id="synthesis-1",
            dataset="SciFact_Synthesis",
            prompt="Write a synthesis",
            metadata={"task_type": "academic_evidence_synthesis"},
        )
        parsed = parse_response("Free-form synthesis.", task)
        self.assertEqual(parsed.parse_status, "parsed_fallback")

    def test_synthesis_verdict_is_parsed_for_objective_accuracy(self):
        task = Task(
            task_id="synthesis-verdict",
            dataset="HaluEval_Synthesis",
            prompt="Evaluate a proposed answer",
            reference_answer="CONTRADICT",
            metadata={
                "task_type": "academic_evidence_synthesis",
                "requires_verdict": True,
                "allowed_document_ids": ["halueval_1"],
            },
        )
        parsed = parse_response(
            "VERDICT: CONTRADICT\n"
            "SYNTHESIS: The proposed answer conflicts with the supplied passage "
            "[Document halueval_1].\n"
            "CITED_DOCUMENTS: halueval_1",
            task,
        )

        self.assertEqual(parsed.parsed_label, "CONTRADICT")
        self.assertEqual(parsed.parse_status, "parsed_strict")
        self.assertEqual(parsed.cited_document_ids, ["halueval_1"])

    def test_required_synthesis_verdict_cannot_silently_pass_as_strict(self):
        task = Task(
            task_id="synthesis-verdict",
            dataset="HaluEval_Synthesis",
            prompt="Evaluate a proposed answer",
            metadata={
                "task_type": "academic_evidence_synthesis",
                "requires_verdict": True,
                "allowed_document_ids": ["halueval_1"],
            },
        )
        parsed = parse_response(
            "SYNTHESIS: Grounded response [Document halueval_1].\n"
            "CITED_DOCUMENTS: halueval_1",
            task,
        )

        self.assertIsNone(parsed.parsed_label)
        self.assertEqual(parsed.parse_status, "parsed_fallback")

    def test_synthesis_does_not_treat_ordinary_document_prose_as_citation(self):
        task = Task(
            task_id="synthesis-2",
            dataset="SciFact_Synthesis",
            prompt="Write a synthesis",
            metadata={
                "task_type": "academic_evidence_synthesis",
                "allowed_document_ids": ["101"],
            },
        )
        parsed = parse_response(
            "SYNTHESIS: The document does not address this outcome, and the only "
            "document specifically discussing it is [Document 101].\n"
            "CITED_DOCUMENTS: 101",
            task,
        )

        self.assertEqual(parsed.cited_document_ids, ["101"])
        self.assertEqual(parsed.invalid_cited_document_ids, [])

    def test_bracketed_alphabetic_document_identifier_is_supported(self):
        task = Task(
            task_id="synthesis-3",
            dataset="SciFact_Synthesis",
            prompt="Write a synthesis",
            metadata={
                "task_type": "academic_evidence_synthesis",
                "allowed_document_ids": ["source_alpha"],
            },
        )
        parsed = parse_response(
            "SYNTHESIS: The finding is reported [Document source_alpha].\n"
            "CITED_DOCUMENTS: Document source_alpha",
            task,
        )

        self.assertEqual(parsed.cited_document_ids, ["source_alpha"])
        self.assertEqual(parsed.invalid_cited_document_ids, [])

    def test_bare_compound_id_in_cited_documents_field_is_supported(self):
        task = Task(
            task_id="halueval-1",
            dataset="HaluEval_Synthesis",
            prompt="Evaluate a proposed answer",
            metadata={
                "task_type": "academic_evidence_synthesis",
                "requires_verdict": True,
                "allowed_document_ids": ["halueval_497"],
            },
        )
        parsed = parse_response(
            "VERDICT: SUPPORT\n"
            "SYNTHESIS: The answer follows from the passage [halueval_497].\n"
            "CITED_DOCUMENTS: halueval_497",
            task,
        )

        self.assertEqual(parsed.cited_document_ids, ["halueval_497"])
        self.assertEqual(parsed.invalid_cited_document_ids, [])
        self.assertEqual(parsed.citation_parse_status, "parsed_strict")

    def test_unknown_bare_compound_id_is_flagged(self):
        task = Task(
            task_id="halueval-1",
            dataset="HaluEval_Synthesis",
            prompt="Evaluate a proposed answer",
            metadata={
                "task_type": "academic_evidence_synthesis",
                "requires_verdict": True,
                "allowed_document_ids": ["halueval_497"],
            },
        )
        parsed = parse_response(
            "VERDICT: SUPPORT\n"
            "SYNTHESIS: Unsupported citation.\n"
            "CITED_DOCUMENTS: invented_source_9",
            task,
        )

        self.assertEqual(parsed.cited_document_ids, ["invented_source_9"])
        self.assertEqual(parsed.invalid_cited_document_ids, ["invented_source_9"])


if __name__ == "__main__":
    unittest.main()
