import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.audit import apply_audit, create_audit_rows, write_audit_csv


class AuditTests(unittest.TestCase):
    def test_completed_audit_produces_hashed_approved_dataset(self):
        task = {
            "task_id": "task-1",
            "dataset": "SciFact",
            "prompt": "Claim",
            "reference_answer": "SUPPORT",
            "source_context": "Evidence",
            "metadata": {"task_type": "scientific_claim_verification"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "tasks.jsonl"
            audit = Path(tmp) / "audit.csv"
            approved = Path(tmp) / "approved.jsonl"
            data.write_text(json.dumps(task) + "\n", encoding="utf-8")
            rows = create_audit_rows(data)
            rows[0].update(
                {
                    "claim_clear": "yes",
                    "evidence_addresses_claim": "yes",
                    "gold_label_supported": "yes",
                    "include": "yes",
                }
            )
            write_audit_csv(audit, rows, overwrite=False)
            manifest = apply_audit(data, audit, approved, overwrite=False)

        self.assertEqual(manifest["included_tasks"], 1)
        self.assertEqual(len(manifest["output_data_sha256"]), 64)

    def test_unreviewed_audit_is_rejected(self):
        task = {
            "task_id": "task-1",
            "dataset": "SciFact",
            "prompt": "Claim",
            "reference_answer": "SUPPORT",
            "source_context": "Evidence",
        }
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "tasks.jsonl"
            audit = Path(tmp) / "audit.csv"
            approved = Path(tmp) / "approved.jsonl"
            data.write_text(json.dumps(task) + "\n", encoding="utf-8")
            write_audit_csv(audit, create_audit_rows(data), overwrite=False)
            with self.assertRaisesRegex(ValueError, "must be yes or no"):
                apply_audit(data, audit, approved, overwrite=False)

    def test_inclusion_rule_cannot_be_overridden_after_results(self):
        task = {
            "task_id": "task-1",
            "dataset": "SciFact",
            "prompt": "Claim",
            "reference_answer": "SUPPORT",
            "source_context": "Evidence",
        }
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "tasks.jsonl"
            audit = Path(tmp) / "audit.csv"
            approved = Path(tmp) / "approved.jsonl"
            data.write_text(json.dumps(task) + "\n", encoding="utf-8")
            rows = create_audit_rows(data)
            rows[0].update(
                {
                    "claim_clear": "no",
                    "evidence_addresses_claim": "yes",
                    "gold_label_supported": "yes",
                    "include": "yes",
                }
            )
            write_audit_csv(audit, rows, overwrite=False)
            with self.assertRaisesRegex(ValueError, "predefined rule"):
                apply_audit(data, audit, approved, overwrite=False)


if __name__ == "__main__":
    unittest.main()
