"""Migration tests: prove the schema applies cleanly on an empty database."""

import asyncio
import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models.brand  # noqa: F401
import app.models.run  # noqa: F401
from alembic import command
from app.models.brand import Brand, Prompt
from app.models.run import Citation, Mention, Response, Run

TEST_DB_NAME = "visibility_test"
TEST_URL = os.getenv(
    "TEST_DATABASE_URL",
    f"postgresql+asyncpg://tracker:tracker@localhost:5432/{TEST_DB_NAME}",
)
ADMIN_URL = os.getenv(
    "TEST_DATABASE_ADMIN_URL",
    "postgresql+asyncpg://tracker:tracker@localhost:5432/postgres",
)
EXPECTED_TABLES = {
    "brands",
    "competitors",
    "prompts",
    "runs",
    "responses",
    "mentions",
    "citations",
}


def alembic_config() -> Config:
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "backend" / "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_URL)
    return cfg


async def recreate_test_database() -> None:
    admin_engine = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    await admin_engine.dispose()


async def table_names(url: str) -> set[str]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    finally:
        await engine.dispose()


async def insert_result_chain() -> tuple[int, int]:
    engine = create_async_engine(TEST_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            brand = Brand(name="Acme")
            session.add(brand)
            await session.flush()
            prompt = Prompt(brand_id=brand.id, query_text="best widgets?")
            run = Run(brand_id=brand.id, status="running")
            session.add_all([prompt, run])
            await session.flush()
            response = Response(
                run_id=run.id,
                prompt_id=prompt.id,
                raw_response="Acme is great",
                model_name="test-model",
                latency_ms=12,
                status="success",
            )
            session.add(response)
            await session.flush()
            session.add(
                Mention(
                    response_id=response.id,
                    brand_name="Acme",
                    rank_position=1,
                    is_target_brand=True,
                    sentiment="positive",
                )
            )
            session.add(
                Citation(
                    response_id=response.id,
                    url="https://example.com/a",
                    domain="example.com",
                )
            )
            await session.commit()
            return run.id, prompt.id
    finally:
        await engine.dispose()


async def test_migrations_apply_on_empty_database() -> None:
    await recreate_test_database()
    os.environ["DATABASE_URL"] = TEST_URL
    try:
        await asyncio.to_thread(command.upgrade, alembic_config(), "head")
        assert EXPECTED_TABLES <= await table_names(TEST_URL)

        run_id, prompt_id = await insert_result_chain()

        # One stored answer per prompt per run: duplicates must fail.
        engine = create_async_engine(TEST_URL)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                session.add(
                    Response(
                        run_id=run_id,
                        prompt_id=prompt_id,
                        raw_response="duplicate",
                        model_name="test-model",
                        status="success",
                    )
                )
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

        # Prompts with stored results cannot be deleted (RESTRICT).
        engine = create_async_engine(TEST_URL)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                prompt = await session.get(Prompt, prompt_id)
                assert prompt is not None
                await session.delete(prompt)
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()
    finally:
        await asyncio.to_thread(command.downgrade, alembic_config(), "base")
        os.environ.pop("DATABASE_URL", None)
        # Only Alembic's own bookkeeping table remains: empty DB, ready for reuse.
        assert await table_names(TEST_URL) == {"alembic_version"}
