from abc import ABC, abstractmethod
from src.schemas import GenerationRequest, GenerationResponse


class ModelProvider(ABC):
    """
    Provider-neutral interface.

    Important experimental guardrail:
    adapters must perform plain text generation only. Do not add web search,
    retrieval, file search, code execution, agents, functions, or other tools.
    """

    provider_name: str

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResponse:
        raise NotImplementedError
