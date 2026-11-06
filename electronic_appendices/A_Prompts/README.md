> Distribution note, 6 November 2026: this interim public release omits the 70 conditional files; full-archive claims and commands below require lawful private restoration. See the withheld-file register linked below.

# A — Prompt packages and output contract

Correspondence: printed Appendix A, Table A1, and §3.4. **VERIFIED** against the frozen registry and all 1,200 saved generation-stage prompts.

[template_registry_v3_2.json](template_registry_v3_2.json) exports the six actual `PromptTemplate` definitions, with user placeholders, `system_template: null`, semantic version 3.2.0, stage and component metadata. The source is [src/prompting.py](../../src/prompting.py), including `PROMPT_REGISTRY`, `_with_stress_contract()` and `_output_contract()`. All six templates have no system instruction. Each `.txt` is the exact user-template string, not a task-specific rendered prompt:

| Treatment / stage | Exact template text |
|---|---|
| Baseline / initial | [academic_synthesis_baseline_v3_2.txt](academic_synthesis_baseline_v3_2.txt) |
| Structured / initial | [academic_synthesis_structured_v3_2.txt](academic_synthesis_structured_v3_2.txt) |
| Source-grounded / initial | [academic_synthesis_source_grounded_v3_2.txt](academic_synthesis_source_grounded_v3_2.txt) |
| CoV / draft | [academic_synthesis_cov_draft_v3_2.txt](academic_synthesis_cov_draft_v3_2.txt) |
| CoV / audit | [academic_synthesis_cov_verify_v3_2.txt](academic_synthesis_cov_verify_v3_2.txt) |
| CoV / revision | [academic_synthesis_cov_final_v3_2.txt](academic_synthesis_cov_final_v3_2.txt) |

[shared_output_contract.txt](shared_output_contract.txt) is the exact `SYNTHESIS_STRESS_OUTPUT_CONTRACT`. Its verdict, synthesis and supplied-ID requirements apply to all four treatments. It is inserted through `{output_contract}` rather than being invented as a system message. `{task_prompt}` and `{source_context}` insert the frozen task and evidence. Later CoV calls also receive `{draft}` and `{verification_report}`; they are separate stateless calls whose actual inputs are logged.

Authoritative realised requests: [results.prompts.jsonl — original path `../../outputs/scifact_confirmatory_v3_2/results.prompts.jsonl`; withheld](../../rights/WITHHELD_FILES.csv) and each `trace[].prompt/request` in [results.jsonl — original path `../../outputs/scifact_confirmatory_v3_2/results.jsonl`; withheld](../../rights/WITHHELD_FILES.csv). The [preview — original path `../../outputs/scifact_confirmatory_v3_2/results.prompt_preview.md`; withheld](../../rights/WITHHELD_FILES.csv) has placeholders for not-yet-generated intermediate text; it is not the complete live trace. [export provenance](../export_provenance.json) records source hashes and mechanical extraction. No wording, source template or original prompt record was edited.
