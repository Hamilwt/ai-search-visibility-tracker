from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM configuration, read from environment variables.

    Field names map to UPPER_SNAKE env vars automatically
    (``gemini_api_key`` <- ``GEMINI_API_KEY``). Types are validated
    at startup instead of failing deep inside a provider call.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = ""
    openai_api_key: str = ""
    openai_base_url: str | None = None
    openai_model: str = ""
    llm_timeout_s: float = 60.0
    max_concurrent_llm_calls: int = 5


def get_settings() -> LLMSettings:
    # No cache on purpose: tests override env vars between cases.
    return LLMSettings()
