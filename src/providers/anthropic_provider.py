import os
import anthropic

from src.providers.base import ModelProvider
from src.schemas import GenerationRequest, GenerationResponse


class AnthropicProvider(ModelProvider):
    provider_name = "anthropic"

    def __init__(self, model: str):
        super().__init__(model)
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        # No tools are supplied.
        kwargs = {
            "model": self.model,
            "max_tokens": request.max_output_tokens,
            "messages": [{"role": "user", "content": request.user_prompt}],
        }

        if request.system_prompt:
            kwargs["system"] = request.system_prompt

        # Sonnet 5 has provider-specific thinking behaviour. We record and
        # explicitly disable it for the controlled prompting experiment.
        if request.settings.get("thinking") == "disabled":
            kwargs["thinking"] = {"type": "disabled"}

        message = self.client.messages.create(**kwargs)

        text_parts = [
            block.text
            for block in message.content
            if getattr(block, "type", None) == "text"
        ]
        usage = getattr(message, "usage", None)

        return GenerationResponse(
            text="".join(text_parts),
            input_tokens=getattr(usage, "input_tokens", None) if usage else None,
            output_tokens=getattr(usage, "output_tokens", None) if usage else None,
            finish_reason=getattr(message, "stop_reason", None),
            provider_request_id=getattr(message, "id", None),
        )
