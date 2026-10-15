"""Runs API tests: real test database, scripted LLM, no network calls."""

import asyncio
import json
import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from app.api.schemas import RunCreateResponse, RunDetailOut
from app.db import SessionLocal, get_session
from app.llm.base import BaseLLMProvider, LLMResult
from app.main import app
from app.models.brand import Brand, Competitor
from tests.test_migrations import TEST_URL, alembic_config, recreate_test_database


class ScriptedProvider(BaseLLMProvider):
    """Replays canned texts in order; fails loudly when exhausted."""

    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.calls = 0

    async def generate(self, prompt: str) -> LLMResult:
        self.calls += 1
        assert self._texts, "scripted provider ran out of texts"
        return LLMResult(text=self._texts.pop(0), model_name="script", latency_ms=1)


def extraction_json() -> str:
    return json.dumps(
        {
            "mentions": [
                {"brand_name": "Acme", "rank_position": 1, "sentiment": "positive"},
                {"brand_name": "Umbrella", "rank_position": 2},
            ],
            "citations": [{"url": "https://example.com/a", "domain": "example.com"}],
            "status": "success",
        }
    )


@pytest.fixture
async def client():
    # Separate test database only; the dev database is never touched here.
    await recreate_test_database()
    os.environ["DATABASE_URL"] = TEST_URL
    await asyncio.to_thread(command.upgrade, alembic_config(), "head")
    engine = create_async_engine(TEST_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    # Mirror app lifespan: the background pipeline uses SessionLocal directly,
    # and lifespan never runs under ASGITransport, so bind it here.
    SessionLocal.configure(bind=engine)

    async def override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c, factory
    finally:
        app.dependency_overrides.clear()
        SessionLocal.configure(bind=None)
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, alembic_config(), "base")
        os.environ.pop("DATABASE_URL", None)


async def seed_brand(factory) -> int:  # noqa: ANN001
    async with factory() as session:
        brand = Brand(name="Acme")
        session.add(brand)
        await session.flush()
        session.add(Competitor(brand_id=brand.id, competitor_name="Umbrella"))
        await session.commit()
        return brand.id


def script(monkeypatch, texts: list[str]) -> ScriptedProvider:
    provider = ScriptedProvider(texts)
    monkeypatch.setattr("app.services.pipeline.get_provider", lambda name: provider)
    return provider


async def wait_for_run(http: AsyncClient, run_id: int) -> dict:  # noqa: ANN001
    """Poll until the background pipeline finishes (mirrors real clients)."""
    for _ in range(100):
        detail = await http.get(f"/runs/{run_id}")
        assert detail.status_code == 200
        body = detail.json()
        if body["status"] in ("completed", "failed"):
            return body
        await asyncio.sleep(0.1)
    raise TimeoutError(f"run {run_id} did not finish in time")


async def test_post_runs_executes_pipeline(client, monkeypatch) -> None:
    http, factory = client
    brand_id = await seed_brand(factory)
    provider = script(monkeypatch, ["Acme is the best widget", extraction_json()])

    response = await http.post(
        "/runs",
        json={"brand_id": brand_id, "prompts": ["best widgets?"], "provider": "gemini"},
    )
    assert response.status_code == 202
    created = RunCreateResponse.model_validate(response.json())
    run = RunDetailOut.model_validate(await wait_for_run(http, created.run_id))
    assert provider.calls == 2  # one answer call + one extraction call
    assert run.status == "completed"
    assert run.completed_at is not None
    assert len(run.responses) == 1
    answer = run.responses[0]
    assert answer.query_text == "best widgets?"
    assert answer.status == "success"
    assert [(m.brand_name, m.is_target_brand) for m in answer.mentions] == [
        ("Acme", True),
        ("Umbrella", False),
    ]
    assert [c.domain for c in answer.citations] == ["example.com"]


async def test_post_runs_reuses_prompts(client, monkeypatch) -> None:
    http, factory = client
    brand_id = await seed_brand(factory)
    script(monkeypatch, ["a1", extraction_json(), "a2", extraction_json()])

    first = (
        await http.post("/runs", json={"brand_id": brand_id, "prompts": ["best widgets?"]})
    ).json()["run_id"]
    second = (
        await http.post("/runs", json={"brand_id": brand_id, "prompts": ["best widgets?"]})
    ).json()["run_id"]

    first_prompts = [r["prompt_id"] for r in (await wait_for_run(http, first))["responses"]]
    second_prompts = [r["prompt_id"] for r in (await wait_for_run(http, second))["responses"]]
    assert first_prompts == second_prompts  # upserted, not duplicated


async def test_post_runs_unknown_brand_is_enveloped_404(client) -> None:
    http, _ = client
    response = await http.post("/runs", json={"brand_id": 999, "prompts": ["best widgets?"]})
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Brand 999 not found",
            "details": None,
        }
    }


async def test_post_runs_validation_error_is_enveloped(client) -> None:
    http, _ = client
    response = await http.post("/runs", json={"brand_id": 1, "prompts": []})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"


async def test_get_run_not_found_is_enveloped_404(client) -> None:
    http, _ = client
    response = await http.get("/runs/123")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_failed_extraction_still_completes_run(client, monkeypatch) -> None:
    http, factory = client
    brand_id = await seed_brand(factory)
    script(monkeypatch, ["some answer", "garbage one", "garbage two"])

    run_id = (
        await http.post("/runs", json={"brand_id": brand_id, "prompts": ["best widgets?"]})
    ).json()["run_id"]
    run = RunDetailOut.model_validate(await wait_for_run(http, run_id))
    assert run.status == "completed"
    assert run.responses[0].status == "failed_extraction"
    assert run.responses[0].mentions == []
