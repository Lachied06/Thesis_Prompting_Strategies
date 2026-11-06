import os
from google import genai
from google.genai import types

from src.providers.base import ModelProvider
from src.schemas import GenerationRequest, GenerationResponse


class GeminiProvider(ModelProvider):
    provider_name = "gemini"

    def __init__(self, model: str):
        super().__init__(model)
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        # No tools are configured, so Google Search grounding, URL context,
        # file search, code execution, etc. are not part of the request.
        thinking_level = request.settings.get("thinking_level", "low")

        config = types.GenerateContentConfig(
            system_instruction=request.system_prompt,
            max_output_tokens=request.max_output_tokens,
            thinking_config=types.ThinkingConfig(
                thinking_level=thinking_level
            ),
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=request.user_prompt,
            config=config,
        )

        usage = getattr(response, "usage_metadata", None)

        return GenerationResponse(
            text=response.text or "",
            input_tokens=getattr(usage, "prompt_token_count", None) if usage else None,
            output_tokens=getattr(usage, "candidates_token_count", None) if usage else None,
            reasoning_tokens=getattr(usage, "thoughts_token_count", None) if usage else None,
            finish_reason=(
                str(getattr(response.candidates[0], "finish_reason", ""))
                if getattr(response, "candidates", None)
                else None
            ),
        )
