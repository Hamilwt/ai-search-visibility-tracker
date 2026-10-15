import time

from google import genai
from google.genai import errors as genai_errors

from app.llm.base import BaseLLMProvider, LLMResult, Usage
from app.llm.errors import (
    LLMAPIError,
    LLMConfigurationError,
    LLMError,
    LLMRateLimitError,
)
from app.llm.retry import run_guarded
from app.llm.settings import LLMSettings, get_settings


class GeminiProvider(BaseLLMProvider):
    """Primary provider using the official ``google-genai`` SDK (free tier)."""

    def __init__(
        self,
        settings: LLMSettings | None = None,
        client: genai.Client | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        if not self._settings.gemini_api_key:
            raise LLMConfigurationError("GEMINI_API_KEY is not set")
        if not self._settings.gemini_model:
            raise LLMConfigurationError("GEMINI_MODEL is not set")
        self._model = self._settings.gemini_model
        self._client = client or genai.Client(api_key=self._settings.gemini_api_key)

    async def generate(self, prompt: str) -> LLMResult:
        started = time.perf_counter()

        async def _call() -> tuple[str, Usage | None]:
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model, contents=prompt
                )
            except genai_errors.APIError as exc:
                raise self._translate(exc) from exc
            if not response.text:
                raise LLMAPIError("Gemini returned an empty response")
            return response.text, self._usage_of(response)

        text, usage = await run_guarded(_call, self._settings)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return LLMResult(text=text, model_name=self._model, latency_ms=latency_ms, usage=usage)

    @staticmethod
    def _usage_of(response) -> Usage | None:  # noqa: ANN001
        meta = getattr(response, "usage_metadata", None)
        if meta is None:
            return None
        completion = getattr(meta, "response_token_count", None)
        if completion is None:  # older SDK field name
            completion = getattr(meta, "candidates_token_count", None)
        return Usage(
            prompt_tokens=getattr(meta, "prompt_token_count", None),
            completion_tokens=completion,
            total_tokens=getattr(meta, "total_token_count", None),
        )

    @staticmethod
    def _translate(exc: genai_errors.APIError) -> LLMError:
        code = exc.code
        if code == 429:
            return LLMRateLimitError(f"Gemini rate limit hit: {exc}")
        if 500 <= code < 600:
            return LLMAPIError(f"Gemini server error (code {code}): {exc}")
        return LLMConfigurationError(f"Gemini rejected the request (code {code}): {exc}")
