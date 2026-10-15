from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Usage:
    """Token counts for one call. All optional: SDKs may omit them."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class LLMResult:
    """Uniform result from any provider."""

    text: str
    model_name: str
    latency_ms: int
    usage: Usage | None = None


class BaseLLMProvider(ABC):
    """Contract every LLM provider implements.

    Callers (and Phase 3) depend only on this, never on vendor SDKs.
    """

    @abstractmethod
    async def generate(self, prompt: str) -> LLMResult:
        """Send one prompt, return the model's raw text plus metadata."""
