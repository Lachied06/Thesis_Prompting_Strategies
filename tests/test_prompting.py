import unittest

from src.prompting import PROMPT_REGISTRY_VERSION, build_prompt_plan
from src.schemas import Task


def scifact_task(source_context="Evidence text"):
    return Task(
        task_id="scifact_1",
        dataset="SciFact",
        prompt="Assess claim X.",
        reference_answer="SUPPORT",
        source_context=source_context,
        metadata={"task_type": "scientific_claim_verification"},
    )


def synthesis_task(source_context="[Document 101] Evidence text"):
    return Task(
        task_id="synthesis_1",
        dataset="SciFact_Synthesis",
        prompt="Write an academic synthesis evaluating claim X.",
        reference_answer="SUPPORT",
        source_context=source_context,
        metadata={
            "task_type": "academic_evidence_synthesis",
            "allowed_document_ids": ["101"],
        },
    )


class PromptingTests(unittest.TestCase):
    def test_prompts_are_versioned_and_inspectable(self):
        plan = build_prompt_plan("structured", scifact_task())
        prompt = plan.first_prompt

        self.assertEqual(prompt.template_id, "academic_structured_v1")
        self.assertEqual(prompt.template_version, "1.0.0")
        self.assertEqual(
            plan.strategy_metadata["registry_version"], PROMPT_REGISTRY_VERSION
        )
        self.assertIn("LABEL: SUPPORT | CONTRADICT | NO_EVIDENCE", prompt.user_prompt)
        self.assertIn("USER:", prompt.rendered_prompt)
        self.assertEqual(len(prompt.prompt_hash), 64)

    def test_output_contract_is_shared_across_scifact_conditions(self):
        task = scifact_task()
        for strategy in (
            "baseline",
            "structured",
            "source_grounded",
            "chain_of_verification",
        ):
            with self.subTest(strategy=strategy):
                prompt = build_prompt_plan(strategy, task).first_prompt
                self.assertIn("OUTPUT FORMAT", prompt.user_prompt)

    def test_source_grounded_requires_evidence(self):
        with self.assertRaisesRegex(ValueError, "requires task.source_context"):
            build_prompt_plan("source_grounded", scifact_task(source_context=None))

    def test_cov_preview_and_live_rendering_are_distinguishable(self):
        plan = build_prompt_plan("chain_of_verification", scifact_task())
        preview = plan.preview_prompts()[1]
        live = plan.render_verification("LABEL: SUPPORT\nEXPLANATION: Draft")

        self.assertIn("{{DRAFT_FROM_INITIAL_GENERATION}}", preview.user_prompt)
        self.assertIn("EXPLANATION: Draft", live.user_prompt)
        self.assertNotEqual(preview.prompt_hash, live.prompt_hash)

    def test_v2_holds_evidence_constant_across_conditions(self):
        task = scifact_task(source_context="IDENTICAL EVIDENCE BLOCK")
        for strategy in (
            "baseline",
            "structured",
            "source_grounded",
            "chain_of_verification",
        ):
            with self.subTest(strategy=strategy):
                plan = build_prompt_plan(
                    {"name": strategy, "version": "2.0.0"}, task
                )
                self.assertIn("IDENTICAL EVIDENCE BLOCK", plan.first_prompt.user_prompt)
                self.assertEqual(plan.strategy_metadata["version"], "2.0.0")

    def test_v2_cov_has_draft_audit_and_revision(self):
        plan = build_prompt_plan(
            {"name": "chain_of_verification", "version": "2.0.0"},
            scifact_task(),
        )
        preview = plan.preview_prompts()

        self.assertEqual(len(preview), 3)
        self.assertEqual(preview[1].step, "verification_generation")
        self.assertEqual(preview[2].step, "revision_generation")
        self.assertIn("VERIFICATION_REPORT_FROM_SECOND_GENERATION", preview[2].user_prompt)

    def test_legacy_string_configs_still_resolve_to_v1(self):
        plan = build_prompt_plan("baseline", scifact_task())
        self.assertEqual(plan.strategy_metadata["version"], "1.0.0")
        self.assertNotIn("Evidence text", plan.first_prompt.user_prompt)

    def test_v3_synthesis_family_shares_sources_and_output_contract(self):
        task = synthesis_task(source_context="IDENTICAL SYNTHESIS SOURCES")
        for strategy in (
            "baseline",
            "structured",
            "source_grounded",
            "chain_of_verification",
        ):
            with self.subTest(strategy=strategy):
                plan = build_prompt_plan(
                    {"name": strategy, "version": "3.0.0"}, task
                )
                self.assertIn(
                    "IDENTICAL SYNTHESIS SOURCES", plan.first_prompt.user_prompt
                )
                self.assertIn("SYNTHESIS:", plan.first_prompt.user_prompt)
                self.assertIn("CITED_DOCUMENTS:", plan.first_prompt.user_prompt)

    def test_v3_cov_audits_claims_and_citations_before_revision(self):
        plan = build_prompt_plan(
            {"name": "chain_of_verification", "version": "3.0.0"},
            synthesis_task(),
        )
        preview = plan.preview_prompts()

        self.assertEqual(len(preview), 3)
        self.assertIn("Check every citation identifier", preview[1].user_prompt)
        self.assertIn("VERIFICATION_REPORT_FROM_SECOND_GENERATION", preview[2].user_prompt)

    def test_v3_1_adds_verdict_without_changing_v3_contract(self):
        task = synthesis_task()
        v3 = build_prompt_plan(
            {"name": "baseline", "version": "3.0.0"}, task
        ).first_prompt
        v3_1 = build_prompt_plan(
            {"name": "baseline", "version": "3.1.0"}, task
        ).first_prompt

        self.assertNotIn("VERDICT:", v3.user_prompt)
        self.assertIn(
            "VERDICT: SUPPORT | CONTRADICT | NO_EVIDENCE",
            v3_1.user_prompt,
        )
        self.assertEqual(v3.template_id, "academic_synthesis_baseline_v3")
        self.assertEqual(v3_1.template_id, "academic_synthesis_baseline_v3_1")
        self.assertNotEqual(v3.prompt_hash, v3_1.prompt_hash)

    def test_v3_2_expands_claim_budget_without_mutating_v3_1(self):
        task = synthesis_task()
        v3_1 = build_prompt_plan(
            {"name": "structured", "version": "3.1.0"}, task
        ).first_prompt
        v3_2 = build_prompt_plan(
            {"name": "structured", "version": "3.2.0"}, task
        ).first_prompt

        self.assertIn("between 120 and 180 words", v3_1.user_prompt)
        self.assertIn("between 180 and 250 words", v3_2.user_prompt)
        self.assertIn("VERDICT: SUPPORT | CONTRADICT | NO_EVIDENCE", v3_2.user_prompt)
        self.assertEqual(v3_2.template_id, "academic_synthesis_structured_v3_2")
        self.assertNotEqual(v3_1.prompt_hash, v3_2.prompt_hash)


if __name__ == "__main__":
    unittest.main()
