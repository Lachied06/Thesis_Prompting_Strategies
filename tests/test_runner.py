import json
import tempfile
import unittest
from pathlib import Path

from src.runner import run_experiment, write_prompt_preview
from src.schemas import GenerationResponse, Task


class FakeProvider:
    def __init__(self):
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if len(self.requests) == 1:
            text = "LABEL: SUPPORT\nEXPLANATION: Initial explanation."
        else:
            text = "LABEL: SUPPORT\nEXPLANATION: Verified explanation."
        return GenerationResponse(
            text=text,
            input_tokens=10,
            output_tokens=5,
            reasoning_tokens=0,
            finish_reason="completed",
            provider_request_id=f"fake-{len(self.requests)}",
        )


class SynthesisProvider:
    def generate(self, request):
        return GenerationResponse(
            text=(
                "SYNTHESIS: The evidence supports the supplied claim [Document 101], "
                "while an unavailable source adds an unsupported detail [Document 999].\n"
                "CITED_DOCUMENTS: 101, 999"
            ),
            input_tokens=20,
            output_tokens=30,
            finish_reason="completed",
        )


class VerdictSynthesisProvider:
    def generate(self, request):
        return GenerationResponse(
            text=(
                "VERDICT: CONTRADICT\n"
                "SYNTHESIS: The proposed answer conflicts with the supplied "
                "source [Document halueval_1].\n"
                "CITED_DOCUMENTS: halueval_1"
            ),
            input_tokens=20,
            output_tokens=30,
            finish_reason="completed",
        )


class FailingProvider:
    def generate(self, request):
        raise RuntimeError("temporary provider failure")


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.task = Task(
            task_id="scifact_1",
            dataset="SciFact",
            prompt="Assess claim X.",
            reference_answer="SUPPORT",
            source_context="Evidence supports X.",
            metadata={"task_type": "scientific_claim_verification"},
        )
        self.config = {
            "experiment_name": "test_experiment",
            "repetitions": 1,
            "shuffle_run_order": False,
            "random_seed": 42,
            "max_output_tokens": 200,
            "models": [{"provider": "fake", "model": "fake-model"}],
            "strategies": ["chain_of_verification"],
        }

    def test_run_writes_v3_result_and_exact_prompts(self):
        provider = FakeProvider()
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp) / "results.jsonl"
            prompts = Path(tmp) / "prompts.jsonl"
            summary = run_experiment(
                self.config,
                [self.task],
                str(results),
                prompt_log_path=str(prompts),
                experiment_id="experiment-1",
                provider_builder=lambda provider_name, model_name: provider,
            )

            result = json.loads(results.read_text(encoding="utf-8"))
            prompt_rows = [
                json.loads(line)
                for line in prompts.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(summary["completed"], 1)
        self.assertEqual(result["schema_version"], "3.1.0")
        self.assertEqual(result["strategy"]["name"], "chain_of_verification")
        self.assertEqual(result["response"]["parsed_label"], "SUPPORT")
        self.assertTrue(result["metrics"]["classification_correct"])
        self.assertEqual(result["metrics"]["input_tokens"], 20)
        self.assertEqual(len(result["trace"]), 2)
        self.assertEqual(len(prompt_rows), 2)
        self.assertIn("Initial explanation", prompt_rows[1]["prompt"]["user_prompt"])

    def test_v2_cov_runs_three_separate_requests(self):
        self.config["strategies"] = [
            {"name": "chain_of_verification", "version": "2.0.0"}
        ]
        provider = FakeProvider()
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp) / "results.jsonl"
            prompts = Path(tmp) / "prompts.jsonl"
            run_experiment(
                self.config,
                [self.task],
                str(results),
                prompt_log_path=str(prompts),
                experiment_id="experiment-v2",
                provider_builder=lambda provider_name, model_name: provider,
            )
            result = json.loads(results.read_text(encoding="utf-8"))
            prompt_rows = prompts.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(provider.requests), 3)
        self.assertEqual(len(result["trace"]), 3)
        self.assertEqual(result["trace"][2]["label"], "revision_generation")
        self.assertEqual(len(prompt_rows), 3)
        self.assertIn("Verified explanation", result["trace"][2]["prompt"]["user_prompt"])

    def test_preview_does_not_need_a_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            preview = Path(tmp) / "preview.md"
            summary = write_prompt_preview(
                self.config, [self.task], preview, task_limit=1
            )
            text = preview.read_text(encoding="utf-8")

        self.assertEqual(summary["rendered_prompts"], 2)
        self.assertIn("academic_cov_verify_v1", text)
        self.assertIn("{{DRAFT_FROM_INITIAL_GENERATION}}", text)

    def test_synthesis_run_records_citation_validity_metrics(self):
        task = Task(
            task_id="synthesis-1",
            dataset="SciFact_Synthesis",
            prompt="Write a synthesis evaluating claim X.",
            reference_answer="SUPPORT",
            source_context="[Document 101] Evidence supports X.",
            metadata={
                "task_type": "academic_evidence_synthesis",
                "allowed_document_ids": ["101"],
                "word_range": [1, 50],
            },
        )
        config = {
            **self.config,
            "strategies": [{"name": "baseline", "version": "3.0.0"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp) / "results.jsonl"
            run_experiment(
                config,
                [task],
                str(results),
                experiment_id="synthesis-experiment",
                provider_builder=lambda provider_name, model_name: SynthesisProvider(),
            )
            result = json.loads(results.read_text(encoding="utf-8"))

        self.assertEqual(result["response"]["cited_document_ids"], ["101", "999"])
        self.assertEqual(result["response"]["invalid_cited_document_ids"], ["999"])
        self.assertEqual(result["metrics"]["cited_document_count"], 2)
        self.assertEqual(result["metrics"]["invalid_citation_count"], 1)
        self.assertTrue(result["metrics"]["word_count_within_range"])
        self.assertIsNone(result["metrics"]["classification_correct"])

    def test_v3_1_synthesis_verdict_is_scored(self):
        task = Task(
            task_id="halueval-1",
            dataset="HaluEval_Synthesis",
            prompt="Evaluate a proposed answer.",
            reference_answer="CONTRADICT",
            source_context="[Document halueval_1] Correct evidence.",
            metadata={
                "task_type": "academic_evidence_synthesis",
                "requires_verdict": True,
                "allowed_document_ids": ["halueval_1"],
                "word_range": [1, 50],
            },
        )
        config = {
            **self.config,
            "strategies": [{"name": "baseline", "version": "3.1.0"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp) / "results.jsonl"
            run_experiment(
                config,
                [task],
                str(results),
                experiment_id="halueval-experiment",
                provider_builder=(
                    lambda provider_name, model_name: VerdictSynthesisProvider()
                ),
            )
            result = json.loads(results.read_text(encoding="utf-8"))

        self.assertEqual(result["response"]["parsed_label"], "CONTRADICT")
        self.assertTrue(result["metrics"]["classification_correct"])

    def test_resume_retains_completed_job_without_another_api_call(self):
        self.config["strategies"] = [{"name": "baseline", "version": "3.2.0"}]
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp) / "results.jsonl"
            prompts = Path(tmp) / "prompts.jsonl"
            first_provider = FakeProvider()
            run_experiment(
                self.config,
                [self.task],
                str(results),
                prompt_log_path=str(prompts),
                experiment_id="resume-experiment",
                provider_builder=lambda provider_name, model_name: first_provider,
            )

            def unexpected_provider(provider_name, model_name):
                raise AssertionError("resume repeated a completed API call")

            summary = run_experiment(
                self.config,
                [self.task],
                str(results),
                prompt_log_path=str(prompts),
                experiment_id="resume-experiment",
                provider_builder=unexpected_provider,
                resume=True,
            )
            result_rows = results.read_text(encoding="utf-8").splitlines()
            prompt_rows = prompts.read_text(encoding="utf-8").splitlines()

        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["resumed_existing"], 1)
        self.assertEqual(summary["errors"], 0)
        self.assertEqual(len(result_rows), 1)
        self.assertEqual(len(prompt_rows), 1)

    def test_resume_retries_error_and_removes_stale_attempt(self):
        self.config["strategies"] = [{"name": "baseline", "version": "3.2.0"}]
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp) / "results.jsonl"
            prompts = Path(tmp) / "prompts.jsonl"
            first = run_experiment(
                self.config,
                [self.task],
                str(results),
                prompt_log_path=str(prompts),
                experiment_id="retry-experiment",
                provider_builder=lambda provider_name, model_name: FailingProvider(),
            )
            second_provider = FakeProvider()
            resumed = run_experiment(
                self.config,
                [self.task],
                str(results),
                prompt_log_path=str(prompts),
                experiment_id="retry-experiment",
                provider_builder=lambda provider_name, model_name: second_provider,
                resume=True,
            )
            result_rows = [
                json.loads(line)
                for line in results.read_text(encoding="utf-8").splitlines()
            ]
            prompt_rows = prompts.read_text(encoding="utf-8").splitlines()

        self.assertEqual(first["errors"], 1)
        self.assertEqual(resumed["retried_errors"], 1)
        self.assertEqual(resumed["completed"], 1)
        self.assertEqual(len(result_rows), 1)
        self.assertEqual(result_rows[0]["status"], "completed")
        self.assertEqual(len(prompt_rows), 1)


if __name__ == "__main__":
    unittest.main()
