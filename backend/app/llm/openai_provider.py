import time

import openai

from app.llm.base import BaseLLMProvider, LLMResult, Usage
from app.llm.errors import (
    LLMAPIError,
    LLMConfigurationError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.retry import run_guarded
from app.llm.settings import LLMSettings, get_settings


class OpenAIProvider(BaseLLMProvider):
    """OpenAI or any OpenAI-compatible endpoint (e.g. Groq) via ``base_url``."""

    def __init__(
        self,
        settings: LLMSettings | None = None,
        client: openai.AsyncOpenAI | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        if not self._settings.openai_api_key:
            raise LLMConfigurationError("OPENAI_API_KEY is not set")
        if not self._settings.openai_model:
            raise LLMConfigurationError("OPENAI_MODEL is not set")
        self._model = self._settings.openai_model
        self._client = client or openai.AsyncOpenAI(
            api_key=self._settings.openai_api_key,
            base_url=self._settings.openai_base_url,
            timeout=self._settings.llm_timeout_s,
            max_retries=0,  # tenacity in retry.py owns all retries
        )

    async def generate(self, prompt: str) -> LLMResult:
        started = time.perf_counter()

        async def _call() -> tuple[str, Usage | None]:
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                )
            except openai.OpenAIError as exc:
                raise self._translate(exc) from exc
            text = response.choices[0].message.content
            if not text:
                raise LLMAPIError("OpenAI-compatible endpoint returned empty content")
            usage = None
            if response.usage is not None:
                usage = Usage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                )
            return text, usage

        text, usage = await run_guarded(_call, self._settings)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return LLMResult(text=text, model_name=self._model, latency_ms=latency_ms, usage=usage)

    @staticmethod
    def _translate(exc: openai.OpenAIError) -> LLMError:
        if isinstance(exc, openai.RateLimitError):
            return LLMRateLimitError(f"Rate limit hit: {exc}")
        if isinstance(exc, openai.APITimeoutError):
            return LLMTimeoutError(f"Request timed out: {exc}")
        if isinstance(exc, openai.AuthenticationError):
            return LLMConfigurationError(f"Invalid API key: {exc}")
        status = getattr(exc, "status_code", None)
        if status == 429:
            return LLMRateLimitError(f"Rate limit hit: {exc}")
        if isinstance(status, int) and 500 <= status < 600:
            return LLMAPIError(f"Server error (status {status}): {exc}")
        if isinstance(exc, openai.APIConnectionError):
            return LLMAPIError(f"Connection failed: {exc}")
        return LLMConfigurationError(f"Request rejected (status {status}): {exc}")
