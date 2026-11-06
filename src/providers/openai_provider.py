import os
from openai import OpenAI

from src.providers.base import ModelProvider
from src.schemas import GenerationRequest, GenerationResponse


class OpenAIProvider(ModelProvider):
    provider_name = "openai"

    def __init__(self, model: str):
        super().__init__(model)
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        # No `tools` argument is supplied: web search, file search, code
        # execution, etc. are therefore outside this experimental condition.
        kwargs = {
            "model": self.model,
            "input": request.user_prompt,
            "max_output_tokens": request.max_output_tokens,
        }

        if request.system_prompt:
            kwargs["instructions"] = request.system_prompt

        effort = request.settings.get("reasoning_effort")
        if effort is not None:
            kwargs["reasoning"] = {"effort": effort}

        response = self.client.responses.create(**kwargs)

        usage = getattr(response, "usage", None)
        output_details = getattr(usage, "output_tokens_details", None) if usage else None

        return GenerationResponse(
            text=response.output_text or "",
            input_tokens=getattr(usage, "input_tokens", None) if usage else None,
            output_tokens=getattr(usage, "output_tokens", None) if usage else None,
            reasoning_tokens=getattr(output_details, "reasoning_tokens", None) if output_details else None,
            finish_reason=getattr(response, "status", None),
            provider_request_id=getattr(response, "id", None),
        )
