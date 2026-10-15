from app.llm.base import BaseLLMProvider
from app.llm.errors import LLMConfigurationError
from app.llm.gemini import GeminiProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.settings import LLMSettings, get_settings

PROVIDERS = ("gemini", "openai")


def get_provider(name: str, settings: LLMSettings | None = None) -> BaseLLMProvider:
    """Return the provider contract for ``name``. Unknown names fail fast."""
    settings = settings or get_settings()
    if name == "gemini":
        return GeminiProvider(settings=settings)
    if name == "openai":
        return OpenAIProvider(settings=settings)
    raise LLMConfigurationError(f"Unknown provider {name!r}. Choose from: {', '.join(PROVIDERS)}")
