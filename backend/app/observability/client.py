"""Langfuse client factory. Keyless means tracing is disabled entirely."""

from langfuse import Langfuse

from app.llm.settings import LLMSettings


def get_langfuse_client(settings: LLMSettings) -> Langfuse | None:
    """Return a client, or None when keys are missing (tests, local dev).

    None means every tracing wrapper degrades to a pure passthrough:
    no network, no background threads, nothing to flush.
    """
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host or "https://cloud.langfuse.com",
    )
