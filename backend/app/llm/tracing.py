"""Provider decorator that records one Langfuse generation per LLM call."""

from langfuse import Langfuse
from langfuse.types import TraceContext

from app.llm.base import BaseLLMProvider, LLMResult


class TracedProvider(BaseLLMProvider):
    """Wraps any provider; the pipeline still sees a plain provider.

    With ``client=None`` this is a pure passthrough (no keys, no network).
    """

    def __init__(
        self,
        inner: BaseLLMProvider,
        client: Langfuse | None,
        *,
        trace_id: str,
        run_id: int,
        brand_id: int,
        prompt_id: int,
        provider_name: str,
        call_kind: str,
    ) -> None:
        self._inner = inner
        self._client = client
        self._trace_id = trace_id
        self._metadata_base = {
            "run_id": run_id,
            "brand_id": brand_id,
            "prompt_id": prompt_id,
            "provider": provider_name,
            "call_kind": call_kind,
        }
        self._calls = 0

    async def generate(self, prompt: str) -> LLMResult:
        if self._client is None:
            return await self._inner.generate(prompt)
        self._calls += 1
        try:
            result = await self._inner.generate(prompt)
        except Exception as exc:
            self._observe(prompt, output=None, error=f"{type(exc).__name__}: {exc}")
            raise
        self._observe(prompt, output=result.text, result=result)
        return result

    def _observe(
        self,
        prompt: str,
        *,
        output: str | None,
        result: LLMResult | None = None,
        error: str | None = None,
    ) -> None:
        assert self._client is not None
        usage_details: dict[str, int] = {}
        if result is not None and result.usage is not None:
            if result.usage.prompt_tokens is not None:
                usage_details["input"] = result.usage.prompt_tokens
            if result.usage.completion_tokens is not None:
                usage_details["output"] = result.usage.completion_tokens
            if result.usage.total_tokens is not None:
                usage_details["total"] = result.usage.total_tokens
        self._client.start_observation(
            trace_context=TraceContext(trace_id=self._trace_id),
            name=f"{self._metadata_base['call_kind']}-{self._metadata_base['provider']}",
            as_type="generation",
            input=prompt,
            output=output,
            model=result.model_name if result is not None else None,
            metadata={**self._metadata_base, "attempt": self._calls},
            usage_details=usage_details or None,
            level="ERROR" if error is not None else None,
            status_message=error,
        )
