import os
from mistralai.client import Mistral

from src.providers.base import ModelProvider
from src.schemas import GenerationRequest, GenerationResponse


class MistralProvider(ModelProvider):
    provider_name = "mistral"

    def __init__(self, model: str):
        super().__init__(model)
        self.client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_prompt})

        # Plain chat completion only; no tools/agents/RAG are configured.
        response = self.client.chat.complete(
            model=self.model,
            messages=messages,
            max_tokens=request.max_output_tokens,
        )

        choice = response.choices[0]
        usage = getattr(response, "usage", None)

        return GenerationResponse(
            text=choice.message.content or "",
            input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            output_tokens=getattr(usage, "completion_tokens", None) if usage else None,
            finish_reason=str(getattr(choice, "finish_reason", "")),
            provider_request_id=getattr(response, "id", None),
        )
