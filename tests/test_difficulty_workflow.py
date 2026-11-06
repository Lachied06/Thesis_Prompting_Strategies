import unittest

import run_difficulty_pilot as workflow


class DifficultyWorkflowTests(unittest.TestCase):
    def test_repair_action_reuses_existing_consensus_artifacts(self):
        args = workflow._repair_args(overwrite=False)

        self.assertEqual(
            args[0:2],
            ["evaluate_atomic_claims.py", "repair-consensus"],
        )
        self.assertIn("atomic_consensus_v3_8", " ".join(args))
        self.assertIn("atomic_consensus_v3_8_repaired", " ".join(args))
        self.assertIn(workflow.SECONDARY_JUDGE_MODEL, args)
        self.assertNotIn("run_experiment.py", args)


if __name__ == "__main__":
    unittest.main()
