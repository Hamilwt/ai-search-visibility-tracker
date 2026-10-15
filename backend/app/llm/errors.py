"""Internal LLM errors. Providers translate SDK exceptions into these,

so retry logic and callers never import vendor SDKs.
"""


class LLMError(Exception):
    """Base class for all LLM failures."""


class LLMRateLimitError(LLMError):
    """Provider throttled us (HTTP 429). Safe to retry with backoff."""


class LLMTimeoutError(LLMError):
    """A single call exceeded the configured timeout. Safe to retry."""


class LLMAPIError(LLMError):
    """Any other provider-side failure (5xx, malformed SDK response)."""


class LLMConfigurationError(LLMError):
    """Missing API key, model name, or other setup problem. Never retried."""
