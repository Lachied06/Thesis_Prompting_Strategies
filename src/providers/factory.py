from src.providers.openai_provider import OpenAIProvider
from src.providers.anthropic_provider import AnthropicProvider
from src.providers.gemini_provider import GeminiProvider
from src.providers.mistral_provider import MistralProvider


def build_provider(provider: str, model: str):
    provider = provider.lower()

    if provider == "openai":
        return OpenAIProvider(model)
    if provider == "anthropic":
        return AnthropicProvider(model)
    if provider == "gemini":
        return GeminiProvider(model)
    if provider == "mistral":
        return MistralProvider(model)

    raise ValueError(f"Unsupported provider: {provider}")
