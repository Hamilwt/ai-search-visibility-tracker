"""Provider unit tests. SDK clients are fakes; no network calls are made."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest
from google.genai import errors as genai_errors

from app.llm.errors import (
    LLMAPIError,
    LLMConfigurationError,
    LLMTimeoutError,
)
from app.llm.factory import get_provider
from app.llm.gemini import GeminiProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.settings import LLMSettings


def make_settings(**overrides: object) -> LLMSettings:
    base: dict[str, object] = {
        "gemini_api_key": "test-key",
        "gemini_model": "test-model",
        "openai_api_key": "test-key",
        "openai_model": "test-model",
    }
    base.update(overrides)
    return LLMSettings(**base)  # type: ignore[arg-type]


def gemini_answer(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text)


def openai_answer(text: str) -> SimpleNamespace:
    message = SimpleNamespace(content=text)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


async def test_gemini_success() -> None:
    fake = AsyncMock()
    fake.aio.models.generate_content.return_value = gemini_answer("hello")
    result = await GeminiProvider(settings=make_settings(), client=fake).generate("hi")
    assert result.text == "hello"
    assert result.model_name == "test-model"
    assert result.latency_ms >= 0


async def test_gemini_rate_limit_then_success() -> None:
    fake = AsyncMock()
    fake.aio.models.generate_content.side_effect = [
        genai_errors.APIError(429, {"error": "slow down"}),
        gemini_answer("recovered"),
    ]
    result = await GeminiProvider(settings=make_settings(), client=fake).generate("hi")
    assert result.text == "recovered"
    assert fake.aio.models.generate_content.call_count == 2


async def test_gemini_server_error_gives_up_after_three_attempts() -> None:
    fake = AsyncMock()
    fake.aio.models.generate_content.side_effect = genai_errors.ServerError(
        500, {"error": "broken"}
    )
    with pytest.raises(LLMAPIError):
        await GeminiProvider(settings=make_settings(), client=fake).generate("hi")
    assert fake.aio.models.generate_content.call_count == 3


async def test_openai_timeout_gives_up_after_three_attempts() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    fake = AsyncMock()
    fake.chat.completions.create.side_effect = openai.APITimeoutError(request)
    with pytest.raises(LLMTimeoutError):
        await OpenAIProvider(settings=make_settings(), client=fake).generate("hi")
    assert fake.chat.completions.create.call_count == 3


async def test_openai_auth_error_is_not_retried() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(401, request=request)
    fake = AsyncMock()
    fake.chat.completions.create.side_effect = openai.AuthenticationError(
        "bad key", response=response, body={}
    )
    with pytest.raises(LLMConfigurationError):
        await OpenAIProvider(settings=make_settings(), client=fake).generate("hi")
    assert fake.chat.completions.create.call_count == 1


async def test_semaphore_limits_concurrency() -> None:
    peak = 0
    current = 0

    async def slow_answer(*args: object, **kwargs: object) -> SimpleNamespace:
        nonlocal peak, current
        current += 1
        peak = max(peak, current)
        await asyncio.sleep(0.05)
        current -= 1
        return gemini_answer("ok")

    fake = AsyncMock()
    fake.aio.models.generate_content.side_effect = slow_answer
    provider = GeminiProvider(settings=make_settings(max_concurrent_llm_calls=2), client=fake)
    results = await asyncio.gather(*(provider.generate("hi") for _ in range(5)))
    assert peak <= 2
    assert [r.text for r in results] == ["ok"] * 5


async def test_provider_requires_api_key() -> None:
    with pytest.raises(LLMConfigurationError):
        GeminiProvider(settings=make_settings(gemini_api_key="", gemini_model=""))


async def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(LLMConfigurationError):
        get_provider("nope", settings=make_settings())
