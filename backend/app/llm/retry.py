"""Shared reliability wrapper: concurrency limit, retries, timeout.

Providers pass a zero-argument async callable; this handles everything else.
"""

import asyncio
from collections.abc import Awaitable, Callable

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.llm.errors import LLMAPIError, LLMRateLimitError, LLMTimeoutError
from app.llm.settings import LLMSettings

MAX_ATTEMPTS = 3

_semaphore: asyncio.Semaphore | None = None
_semaphore_limit: int | None = None


def get_semaphore(limit: int) -> asyncio.Semaphore:
    """Process-wide semaphore, recreated if the configured limit changes."""
    global _semaphore, _semaphore_limit
    if _semaphore is None or _semaphore_limit != limit:
        _semaphore = asyncio.Semaphore(limit)
        _semaphore_limit = limit
    return _semaphore


def llm_retry() -> AsyncRetrying:
    # Retries rate limits, timeouts, and transient 5xx only.
    # Auth/config errors are never retried (different exception types).
    return AsyncRetrying(
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential_jitter(initial=1, max=10),
        retry=retry_if_exception_type((LLMRateLimitError, LLMTimeoutError, LLMAPIError)),
        reraise=True,
    )


async def run_guarded[T](call: Callable[[], Awaitable[T]], settings: LLMSettings) -> T:
    """Run one LLM call with semaphore, retry-with-backoff, and timeout."""
    semaphore = get_semaphore(settings.max_concurrent_llm_calls)
    async with semaphore:
        async for attempt in llm_retry():
            with attempt:
                try:
                    return await asyncio.wait_for(call(), timeout=settings.llm_timeout_s)
                except TimeoutError as exc:
                    raise LLMTimeoutError(f"LLM call exceeded {settings.llm_timeout_s}s") from exc
    raise AssertionError("unreachable: tenacity always returns or reraises")
