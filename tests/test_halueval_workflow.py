import json
import tempfile
import unittest
from pathlib import Path

import run_halueval_pilot as workflow


class HaluEvalWorkflowTests(unittest.TestCase):
    def test_frozen_inputs_plan_56_result_rows(self):
        config = json.loads(workflow.CONFIG.read_text(encoding="utf-8"))
        tasks = [
            json.loads(line)
            for line in workflow.DATA.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        self.assertEqual(len(tasks), workflow.EXPECTED_TASKS)
        self.assertEqual(
            len(tasks) * len(config["models"]) * len(config["strategies"]),
            workflow.EXPECTED_RESULTS,
        )
        self.assertEqual(
            {task["reference_answer"] for task in tasks},
            {"SUPPORT", "CONTRADICT"},
        )

    def test_result_counts_separates_completed_and_error_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"status": "completed"}),
                        json.dumps({"status": "completed"}),
                        json.dumps({"status": "error"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            completed, errors = workflow._result_counts(path)

        self.assertEqual((completed, errors), (2, 1))

    def test_judge_action_uses_two_model_consensus_without_regeneration(self):
        args = workflow._atomic_args(overwrite=False)

        self.assertEqual(args[0:2], ["evaluate_atomic_claims.py", "consensus"])
        self.assertIn("--primary-judge-model", args)
        self.assertIn(workflow.PRIMARY_JUDGE_MODEL, args)
        self.assertIn("--secondary-judge-model", args)
        self.assertIn(workflow.SECONDARY_JUDGE_MODEL, args)
        self.assertIn("atomic_consensus_v3_8", " ".join(args))
        self.assertNotIn("run_experiment.py", args)


if __name__ == "__main__":
    unittest.main()
