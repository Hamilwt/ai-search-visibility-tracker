"""List endpoint tests: real test database, no LLM involved."""

import asyncio
import os

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from app.db import SessionLocal, get_session
from app.main import app
from app.models.brand import Brand, Prompt
from app.models.run import Response, Run
from tests.test_migrations import TEST_URL, alembic_config, recreate_test_database


async def seed(factory) -> tuple[int, int]:  # noqa: ANN001
    async with factory() as session:
        acme = Brand(name="Acme")
        umbrella = Brand(name="Umbrella")
        session.add_all([acme, umbrella])
        await session.flush()
        prompt = Prompt(brand_id=acme.id, query_text="q?")
        session.add(prompt)
        await session.flush()
        runs = [
            Run(brand_id=acme.id, status="completed"),
            Run(brand_id=acme.id, status="pending"),
            Run(brand_id=umbrella.id, status="completed"),
        ]
        session.add_all(runs)
        await session.flush()
        session.add(
            Response(
                run_id=runs[0].id,
                prompt_id=prompt.id,
                raw_response="r",
                model_name="m",
                status="success",
            )
        )
        await session.commit()
        return acme.id, umbrella.id


async def test_list_endpoints() -> None:
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
        acme_id, umbrella_id = await seed(factory)
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            brands = (await http.get("/brands")).json()
            assert [b["name"] for b in brands] == ["Acme", "Umbrella"]

            runs = (await http.get("/runs")).json()
            assert len(runs) == 3
            assert runs[0]["id"] > runs[1]["id"] > runs[2]["id"]  # latest first
            assert runs[2]["response_count"] == 1
            assert runs[2]["brand_name"] == "Acme"
            assert runs[1]["response_count"] == 0

            filtered = (await http.get(f"/runs?brand_id={umbrella_id}")).json()
            assert len(filtered) == 1
            assert filtered[0]["brand_id"] == umbrella_id

            limited = (await http.get("/runs?limit=2")).json()
            assert len(limited) == 2

            assert acme_id != umbrella_id
    finally:
        app.dependency_overrides.clear()
        SessionLocal.configure(bind=None)
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, alembic_config(), "base")
        os.environ.pop("DATABASE_URL", None)
