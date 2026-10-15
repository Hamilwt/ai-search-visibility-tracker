"""Share-of-voice tests: real test database, endpoint-level math checks."""

import asyncio
import os
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from app.db import SessionLocal, get_session
from app.main import app
from app.models.brand import Brand, Competitor, Prompt
from app.models.run import Mention, Response, Run
from tests.test_migrations import TEST_URL, alembic_config, recreate_test_database


async def seed(factory, rows: list[tuple[str, int | None, int]]) -> int:
    """Seed one brand with runs. Rows: (brand_name, rank, days_ago) per mention.

    Each tuple becomes one mention in its own response; mentions sharing the
    same days_ago land in the same run.
    """
    async with factory() as session:
        brand = Brand(name="Acme")
        session.add(brand)
        await session.flush()
        session.add(Competitor(brand_id=brand.id, competitor_name="Umbrella"))
        runs: dict[int, Run] = {}
        prompt_no = 0
        for name, rank, days_ago in rows:
            if days_ago not in runs:
                run = Run(
                    brand_id=brand.id,
                    status="completed",
                    triggered_at=datetime.now(UTC) - timedelta(days=days_ago),
                    completed_at=datetime.now(UTC) - timedelta(days=days_ago),
                )
                session.add(run)
                await session.flush()
                runs[days_ago] = run
            # One prompt per response: (run_id, prompt_id) must stay unique.
            prompt_no += 1
            prompt = Prompt(brand_id=brand.id, query_text=f"seed query {prompt_no}")
            session.add(prompt)
            await session.flush()
            response = Response(
                run_id=runs[days_ago].id,
                prompt_id=prompt.id,
                raw_response="text",
                model_name="m",
                status="success",
            )
            session.add(response)
            await session.flush()
            session.add(
                Mention(
                    response_id=response.id,
                    brand_name=name,
                    rank_position=rank,
                    is_target_brand=name.casefold() == "acme",
                )
            )
        await session.commit()
        return brand.id


async def test_share_of_voice_math() -> None:
    await recreate_test_database()
    os.environ["DATABASE_URL"] = TEST_URL
    await asyncio.to_thread(command.upgrade, alembic_config(), "head")
    engine = create_async_engine(TEST_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    SessionLocal.configure(bind=engine)

    async def override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    try:
        brand_id = await seed(
            factory,
            [
                ("Acme", 1, 1),
                ("Umbrella", 2, 1),
                ("Acme", 3, 1),  # run A: 2 target of 3 -> 66.67%
                ("Umbrella", 1, 2),  # run B: 0 target of 1 -> 0.0%
                ("Acme", 1, 60),  # run C: old, outside default window
            ],
        )
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            body = (await http.get(f"/brands/{brand_id}/share-of-voice")).json()
            assert [p["total_mentions"] for p in body["points"]] == [1, 3]
            run_b, run_a = body["points"]
            assert run_a["target_mentions"] == 2
            assert run_a["share"] == 66.67
            assert run_a["avg_rank_position"] == 2.0
            assert run_a["competitor_mentions"] == {"Umbrella": 1}
            assert run_b["share"] == 0.0
            assert run_b["avg_rank_position"] is None

            wide = (await http.get(f"/brands/{brand_id}/share-of-voice?days=90")).json()
            assert len(wide["points"]) == 3
    finally:
        app.dependency_overrides.clear()
        SessionLocal.configure(bind=None)
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, alembic_config(), "base")
        os.environ.pop("DATABASE_URL", None)


async def test_share_of_voice_zero_mentions_is_null() -> None:
    await recreate_test_database()
    os.environ["DATABASE_URL"] = TEST_URL
    await asyncio.to_thread(command.upgrade, alembic_config(), "head")
    engine = create_async_engine(TEST_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    SessionLocal.configure(bind=engine)

    async def override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    try:
        async with factory() as session:
            brand = Brand(name="Solo")
            session.add(brand)
            await session.flush()
            session.add(Run(brand_id=brand.id, status="completed"))
            await session.commit()
            brand_id = brand.id
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            body = (await http.get(f"/brands/{brand_id}/share-of-voice")).json()
            assert len(body["points"]) == 1
            assert body["points"][0]["total_mentions"] == 0
            assert body["points"][0]["share"] is None
            assert body["points"][0]["avg_rank_position"] is None

            missing = await http.get("/brands/999/share-of-voice")
            assert missing.status_code == 404
            assert missing.json()["error"]["code"] == "not_found"
    finally:
        app.dependency_overrides.clear()
        SessionLocal.configure(bind=None)
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, alembic_config(), "base")
        os.environ.pop("DATABASE_URL", None)
