"""Tracing tests: recording fake client, no Langfuse keys, no network."""

import asyncio
import json
import os
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from app.db import SessionLocal
from app.llm.base import BaseLLMProvider, LLMResult, Usage
from app.llm.errors import LLMAPIError
from app.llm.settings import LLMSettings
from app.llm.tracing import TracedProvider
from app.models.brand import Brand, Competitor, Prompt
from app.models.run import Run
from app.observability.client import get_langfuse_client
from app.services.pipeline import execute_run
from tests.test_migrations import TEST_URL, alembic_config, recreate_test_database


class RecordingClient:
    """Stands in for Langfuse: captures observations, counts flushes."""

    def __init__(self) -> None:
        self.observations: list[dict] = []
        self.flushes = 0

    def start_observation(self, **kwargs):  # noqa: ANN001, ANN204
        self.observations.append(kwargs)
        return SimpleNamespace(id="obs-1")

    def flush(self) -> None:
        self.flushes += 1


class ScriptedProvider(BaseLLMProvider):
    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)

    async def generate(self, prompt: str) -> LLMResult:
        return LLMResult(
            text=self._texts.pop(0),
            model_name="gemini-test",
            latency_ms=7,
            usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )


def traced(inner, client, kind="answer"):  # noqa: ANN001, ANN204
    return TracedProvider(
        inner,
        client,
        trace_id="trace-1",
        run_id=7,
        brand_id=3,
        prompt_id=5,
        provider_name="gemini",
        call_kind=kind,
    )


async def test_disabled_client_is_passthrough() -> None:
    inner = ScriptedProvider(["hi"])
    result = await traced(inner, None).generate("hello?")
    assert result.text == "hi"


async def test_get_langfuse_client_none_without_keys() -> None:
    settings = LLMSettings(langfuse_public_key="", langfuse_secret_key="")
    assert get_langfuse_client(settings) is None


async def test_records_generation_with_metadata_and_usage() -> None:
    client = RecordingClient()
    result = await traced(ScriptedProvider(["answer text"]), client).generate("the prompt")
    assert result.text == "answer text"
    assert len(client.observations) == 1
    obs = client.observations[0]
    assert obs["name"] == "answer-gemini"
    assert obs["as_type"] == "generation"
    assert obs["input"] == "the prompt"
    assert obs["output"] == "answer text"
    assert obs["model"] == "gemini-test"
    assert obs["metadata"] == {
        "run_id": 7,
        "brand_id": 3,
        "prompt_id": 5,
        "provider": "gemini",
        "call_kind": "answer",
        "attempt": 1,
    }
    assert obs["usage_details"] == {"input": 10, "output": 20, "total": 30}


async def test_attempt_counter_distinguishes_extract_from_repair() -> None:
    client = RecordingClient()
    provider = traced(ScriptedProvider(["a", "b"]), client, kind="extraction")
    await provider.generate("first")
    await provider.generate("second")
    assert [o["metadata"]["attempt"] for o in client.observations] == [1, 2]


async def test_error_is_recorded_and_reraised() -> None:
    class FailingProvider(BaseLLMProvider):
        async def generate(self, prompt: str) -> LLMResult:
            raise LLMAPIError("boom")

    client = RecordingClient()
    with pytest.raises(LLMAPIError):
        await traced(FailingProvider(), client).generate("hello?")
    assert len(client.observations) == 1
    obs = client.observations[0]
    assert obs["level"] == "ERROR"
    assert "boom" in obs["status_message"]
    assert obs["output"] is None


async def test_pipeline_traces_answer_and_extraction() -> None:
    await recreate_test_database()
    os.environ["DATABASE_URL"] = TEST_URL
    await asyncio.to_thread(command.upgrade, alembic_config(), "head")
    engine = create_async_engine(TEST_URL)
    SessionLocal.configure(bind=engine)
    fake_langfuse = RecordingClient()
    import app.services.pipeline as pipeline

    real_provider_fn = pipeline.get_provider
    real_client_fn = pipeline.get_langfuse_client
    pipeline.get_provider = lambda name: ScriptedProvider(
        ["Acme is great", json.dumps({"mentions": [], "citations": []})]
    )
    pipeline.get_langfuse_client = lambda settings: fake_langfuse
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            brand = Brand(name="Acme")
            session.add(brand)
            await session.flush()
            session.add(Competitor(brand_id=brand.id, competitor_name="Umbrella"))
            prompt = Prompt(brand_id=brand.id, query_text="best widgets?")
            run = Run(brand_id=brand.id, status="pending")
            session.add_all([prompt, run])
            await session.commit()
            run_id, prompt_id, brand_id = run.id, prompt.id, brand.id
        await execute_run(run_id, [prompt_id], "gemini")
        kinds = [o["metadata"]["call_kind"] for o in fake_langfuse.observations]
        assert kinds == ["answer", "extraction"]
        for obs in fake_langfuse.observations:
            assert obs["metadata"]["run_id"] == run_id
            assert obs["metadata"]["brand_id"] == brand_id
            assert obs["metadata"]["prompt_id"] == prompt_id
        assert fake_langfuse.flushes == 1
    finally:
        pipeline.get_provider = real_provider_fn
        pipeline.get_langfuse_client = real_client_fn
        SessionLocal.configure(bind=None)
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, alembic_config(), "base")
        os.environ.pop("DATABASE_URL", None)
