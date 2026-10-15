import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DEFAULT_DATABASE_URL = "postgresql+asyncpg://tracker:tracker@localhost:5432/visibility"


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


engine: AsyncEngine | None = None
SessionLocal = async_sessionmaker(expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    global engine
    engine = create_async_engine(get_database_url(), pool_pre_ping=True)
    SessionLocal.configure(bind=engine)
    yield
    await engine.dispose()
    engine = None
