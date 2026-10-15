from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResult:
    """Uniform result from any provider."""

    text: str
    model_name: str
    latency_ms: int


class BaseLLMProvider(ABC):
    """Contract every LLM provider implements.

    Callers (and Phase 3) depend only on this, never on vendor SDKs.
    """

    @abstractmethod
    async def generate(self, prompt: str) -> LLMResult:
        """Send one prompt, return the model's raw text plus metadata."""
