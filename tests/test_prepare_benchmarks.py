import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from prepare_benchmarks import (
    choose_scifact_rows,
    choose_scifact_rows_with_unique_primary_documents,
    load_json_or_jsonl,
    prepare_halueval_synthesis,
    prepare_scifact_confirmatory_study,
    prepare_scifact_difficulty_pilot,
    prepare_scifact_synthesis,
    scifact_label,
)


def claim(claim_id, label, document_id):
    evidence = {}
    if label != "NO_EVIDENCE":
        evidence = {
            str(document_id): [
                {"label": label, "sentences": [0]},
            ]
        }
    return {
        "id": claim_id,
        "claim": f"Scientific claim {claim_id}",
        "evidence": evidence,
        "cited_doc_ids": [document_id],
    }


class PrepareBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.claims = [
            claim(1, "SUPPORT", 1),
            claim(2, "SUPPORT", 2),
            claim(3, "CONTRADICT", 3),
            claim(4, "CONTRADICT", 4),
            claim(5, "NO_EVIDENCE", 5),
            claim(6, "NO_EVIDENCE", 6),
        ]

    def test_stratified_scifact_selection_is_balanced_and_reproducible(self):
        selected = choose_scifact_rows(self.claims, 3, 42, "stratified")
        repeated = choose_scifact_rows(self.claims, 3, 42, "stratified")

        self.assertEqual(selected, repeated)
        self.assertEqual(
            Counter(scifact_label(row) for row in selected),
            {"SUPPORT": 1, "CONTRADICT": 1, "NO_EVIDENCE": 1},
        )

    def test_unique_primary_document_selection_removes_source_duplicates(self):
        rows = self.claims + [claim(7, "SUPPORT", 1)]
        selected = choose_scifact_rows_with_unique_primary_documents(
            rows, 6, 42, "stratified"
        )
        primary_ids = [
            str(next(iter(row["evidence"]), row["cited_doc_ids"][0]))
            for row in selected
        ]

        self.assertEqual(len(primary_ids), len(set(primary_ids)))
        self.assertEqual(len(selected), 6)

    def test_synthesis_tasks_have_fixed_multi_document_source_sets(self):
        corpus = [
            {
                "doc_id": index,
                "title": f"Scientific topic {index}",
                "abstract": [f"Evidence sentence for scientific topic {index}."],
            }
            for index in range(1, 10)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            claims_path = Path(tmp) / "claims.jsonl"
            corpus_path = Path(tmp) / "corpus.jsonl"
            output_path = Path(tmp) / "synthesis.jsonl"
            claims_path.write_text(
                "".join(json.dumps(row) + "\n" for row in self.claims),
                encoding="utf-8",
            )
            corpus_path.write_text(
                "".join(json.dumps(row) + "\n" for row in corpus),
                encoding="utf-8",
            )

            prepare_scifact_synthesis(
                claims_path,
                corpus_path,
                output_path,
                limit=3,
                seed=42,
                documents_per_task=3,
                sampling="stratified",
            )
            tasks = [
                json.loads(line)
                for line in output_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(len(tasks), 3)
        self.assertEqual(
            {task["reference_answer"] for task in tasks},
            {"SUPPORT", "CONTRADICT", "NO_EVIDENCE"},
        )
        for task in tasks:
            metadata = task["metadata"]
            self.assertEqual(metadata["task_type"], "academic_evidence_synthesis")
            self.assertEqual(len(metadata["allowed_document_ids"]), 3)
            for document_id in metadata["allowed_document_ids"]:
                self.assertIn(f"[Document {document_id}]", task["source_context"])

    def test_synthesis_can_exclude_previously_prepared_source_items(self):
        corpus = [
            {
                "doc_id": index,
                "title": f"Scientific topic {index}",
                "abstract": [f"Evidence sentence for scientific topic {index}."],
            }
            for index in range(1, 10)
        ]
        excluded = [
            {
                "task_id": f"scifact_synthesis_{claim_id}",
                "metadata": {"source_item_id": str(claim_id)},
            }
            for claim_id in (1, 3, 5)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            claims_path = Path(tmp) / "claims.jsonl"
            corpus_path = Path(tmp) / "corpus.jsonl"
            excluded_path = Path(tmp) / "previous.jsonl"
            output_path = Path(tmp) / "stress.jsonl"
            claims_path.write_text(
                "".join(json.dumps(row) + "\n" for row in self.claims),
                encoding="utf-8",
            )
            corpus_path.write_text(
                "".join(json.dumps(row) + "\n" for row in corpus),
                encoding="utf-8",
            )
            excluded_path.write_text(
                "".join(json.dumps(row) + "\n" for row in excluded),
                encoding="utf-8",
            )

            prepare_scifact_synthesis(
                claims_path,
                corpus_path,
                output_path,
                limit=3,
                seed=42,
                documents_per_task=5,
                sampling="stratified",
                exclude_task_files=[excluded_path],
                unique_primary_documents=True,
            )
            tasks = [
                json.loads(line)
                for line in output_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(
            {task["metadata"]["source_item_id"] for task in tasks},
            {"2", "4", "6"},
        )
        self.assertEqual(
            {task["reference_answer"] for task in tasks},
            {"SUPPORT", "CONTRADICT", "NO_EVIDENCE"},
        )
        for task in tasks:
            self.assertEqual(len(task["metadata"]["allowed_document_ids"]), 5)
            self.assertEqual(task["metadata"]["excluded_source_item_count"], 3)
            self.assertTrue(task["metadata"]["unique_primary_documents"])

    def test_json_or_jsonl_loader_accepts_halueval_json_lines(self):
        rows = [
            {"question": "Q1", "knowledge": "K1"},
            {"question": "Q2", "knowledge": "K2"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "qa_data.json"
            path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            loaded = load_json_or_jsonl(path)

        self.assertEqual(loaded, rows)

    def test_halueval_synthesis_is_balanced_and_requires_verdict(self):
        rows = [
            {
                "knowledge": f"Source fact {index} is correct.",
                "question": f"What is source fact {index}?",
                "right_answer": f"Source fact {index}",
                "hallucinated_answer": f"Incorrect fact {index}",
            }
            for index in range(6)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "qa_data.json"
            output_path = Path(tmp) / "halueval_synthesis.jsonl"
            input_path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            prepare_halueval_synthesis(
                input_path,
                output_path,
                limit=6,
                seed=42,
            )
            tasks = [
                json.loads(line)
                for line in output_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(len(tasks), 6)
        self.assertEqual(
            Counter(task["reference_answer"] for task in tasks),
            {"SUPPORT": 3, "CONTRADICT": 3},
        )
        self.assertEqual(
            len({task["metadata"]["source_item_id"] for task in tasks}),
            6,
        )
        for task in tasks:
            self.assertTrue(task["metadata"]["requires_verdict"])
            document_id = task["metadata"]["allowed_document_ids"][0]
            self.assertIn(f"[Document {document_id}]", task["source_context"])

    def test_difficulty_pilot_can_remove_decisive_evidence(self):
        base_task = {
            "task_id": "base_1",
            "dataset": "SciFact_Synthesis",
            "prompt": "Write a synthesis.\n\nCLAIM: Treatment improves outcome.",
            "reference_answer": "SUPPORT",
            "source_context": (
                "[Document 10]\nTitle: Gold\nAbstract: Treatment improves outcome.\n\n"
                "[Document 20]\nTitle: Related\nAbstract: A related outcome was measured."
            ),
            "metadata": {
                "source_item_id": "1",
                "evidence_doc_ids": ["10"],
                "cited_doc_ids": ["10"],
                "supplementary_doc_ids": ["20"],
            },
        }
        design = {
            "design_version": "1.0.0",
            "expected_categories": {"direct": 1, "omission": 1},
            "tasks": [
                {
                    "source_item_id": "1",
                    "difficulty_category": "direct",
                    "document_mode": "gold_only",
                },
                {
                    "source_item_id": "1",
                    "difficulty_category": "omission",
                    "document_mode": "omit_gold",
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            base_path = Path(tmp) / "base.jsonl"
            design_path = Path(tmp) / "design.json"
            output_path = Path(tmp) / "difficulty.jsonl"
            base_path.write_text(json.dumps(base_task) + "\n", encoding="utf-8")
            design_path.write_text(json.dumps(design), encoding="utf-8")
            prepare_scifact_difficulty_pilot(base_path, design_path, output_path)
            tasks = [
                json.loads(line)
                for line in output_path.read_text(encoding="utf-8").splitlines()
            ]

        direct, omission = tasks
        self.assertEqual(direct["reference_answer"], "SUPPORT")
        self.assertEqual(omission["reference_answer"], "NO_EVIDENCE")
        self.assertIn("[Document 10]", direct["source_context"])
        self.assertNotIn("[Document 10]", omission["source_context"])
        self.assertEqual(omission["metadata"]["omitted_gold_document_ids"], ["10"])
        self.assertEqual(omission["metadata"]["word_range"], [180, 250])

    def test_confirmatory_design_is_balanced_and_predeclared(self):
        base_tasks = []
        labels = ["SUPPORT"] * 25 + ["CONTRADICT"] * 25 + ["NO_EVIDENCE"] * 25
        for index, label in enumerate(labels, start=1):
            document_ids = [f"{index}-{number}" for number in range(1, 6)]
            evidence_ids = [] if label == "NO_EVIDENCE" else [document_ids[0]]
            cited_ids = [document_ids[0]]
            source_context = "\n\n".join(
                f"[Document {document_id}]\nTitle: Topic\nAbstract: Evidence text."
                for document_id in document_ids
            )
            base_tasks.append(
                {
                    "task_id": f"base-{index}",
                    "dataset": "SciFact_Synthesis",
                    "prompt": f"Write a synthesis.\n\nCLAIM: Claim {index}.",
                    "reference_answer": label,
                    "source_context": source_context,
                    "metadata": {
                        "source_item_id": str(index),
                        "evidence_doc_ids": evidence_ids,
                        "cited_doc_ids": cited_ids,
                        "supplementary_doc_ids": document_ids[1:],
                        "allowed_document_ids": document_ids,
                    },
                }
            )

        with tempfile.TemporaryDirectory() as tmp:
            base_path = Path(tmp) / "base.jsonl"
            design_path = Path(tmp) / "design.json"
            output_path = Path(tmp) / "confirmatory.jsonl"
            base_path.write_text(
                "".join(json.dumps(row) + "\n" for row in base_tasks),
                encoding="utf-8",
            )
            prepare_scifact_confirmatory_study(
                base_path,
                design_path,
                output_path,
                seed=42,
            )
            design = json.loads(design_path.read_text(encoding="utf-8"))
            tasks = [
                json.loads(line)
                for line in output_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(len(tasks), 100)
        self.assertEqual(
            Counter(task["metadata"]["difficulty_category"] for task in tasks),
            {
                "direct_control": 25,
                "near_match_distractors": 25,
                "evidence_omission": 25,
                "conflicting_or_partial_evidence": 25,
            },
        )
        self.assertEqual(design["dataset_name"], "SciFact_Confirmatory")
        self.assertEqual(
            Counter(task["reference_answer"] for task in tasks),
            {"SUPPORT": 25, "CONTRADICT": 25, "NO_EVIDENCE": 50},
        )
        self.assertEqual(
            len(
                {
                    task["metadata"]["source_item_id"]
                    for task in tasks
                    if task["metadata"]["difficulty_category"] != "evidence_omission"
                }
            ),
            75,
        )


if __name__ == "__main__":
    unittest.main()
