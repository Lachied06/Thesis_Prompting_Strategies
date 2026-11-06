"""Backward-compatible imports for the versioned prompt registry."""

from src.prompting import (  # noqa: F401
    CONTROL_SYSTEM_PROMPT,
    PROMPT_REGISTRY,
    PROMPT_REGISTRY_VERSION,
    PromptPlan,
    build_prompt_plan,
    registry_manifest,
)
