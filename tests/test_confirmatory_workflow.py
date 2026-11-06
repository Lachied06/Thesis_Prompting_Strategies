import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_confirmatory_study as workflow


class ConfirmatoryWorkflowTests(unittest.TestCase):
    def test_expected_design_plans_800_responses(self):
        self.assertEqual(workflow._expected_results(100), 800)
        config = workflow._config()
        self.assertEqual(len(config["models"]), 2)
        self.assertEqual(len(config["strategies"]), 4)
        self.assertEqual(
            {strategy["version"] for strategy in config["strategies"]},
            {"3.2.0"},
        )

    def test_validate_requires_balanced_frozen_categories(self):
        rows = []
        for category, count in workflow.EXPECTED_CATEGORIES.items():
            for index in range(count):
                if category == "direct_control":
                    source_item_id = f"direct-{index}"
                    label = "SUPPORT" if index < 13 else "CONTRADICT"
                elif category == "evidence_omission":
                    source_item_id = f"direct-{index}"
                    label = "NO_EVIDENCE"
                elif category == "near_match_distractors":
                    source_item_id = f"near-{index}"
                    label = "SUPPORT" if index < 12 else "CONTRADICT"
                else:
                    source_item_id = f"partial-{index}"
                    label = "NO_EVIDENCE"
                rows.append(
                    {
                        "task_id": f"{category}-{index}",
                        "dataset": "SciFact_Confirmatory",
                        "reference_answer": label,
                        "metadata": {
                            "source_item_id": source_item_id,
                            "difficulty_category": category,
                            "word_range": [180, 250],
                            "allowed_document_ids": ["1"],
                        },
                    }
                )

        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "confirmatory.jsonl"
            data.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            with patch.object(workflow, "DATA", data):
                workflow._validate_frozen_dataset()

    def test_resume_is_forwarded_to_generation_and_consensus(self):
        experiment_args = workflow._experiment_args(
            preview=False,
            overwrite=False,
            resume=True,
        )
        atomic_args = workflow._atomic_args(overwrite=False, resume=True)

        self.assertIn("--resume", experiment_args)
        self.assertIn("--resume", atomic_args)
        self.assertNotIn("--overwrite", experiment_args)
        self.assertNotIn("--overwrite", atomic_args)


if __name__ == "__main__":
    unittest.main()
