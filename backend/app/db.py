import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DEFAULT_DATABASE_URL = "postgresql+asyncpg://tracker:tracker@localhost:5432/visibility"

# Query params asyncpg understands (see asyncpg.connect_utils). Anything else
# would degrade into server_settings SETs, which transaction-mode poolers
# (Neon pooled URLs) reject — so unknown params are dropped, not forwarded.
_ASYNCPG_QUERY_PARAMS = frozenset(
    {
        "sslmode",
        "sslcert",
        "sslkey",
        "sslrootcert",
        "sslcrl",
        "sslpassword",
        "ssl_min_protocol_version",
        "ssl_max_protocol_version",
        "sslnegotiation",
    }
)


def normalize_database_url(url: str) -> str:
    """Accept a Neon-style URL; return one SQLAlchemy+asyncpg can use."""
    scheme, netloc, path, query, fragment = urlsplit(url)
    if scheme == "postgresql":
        scheme = "postgresql+asyncpg"
    if query:
        kept = [
            (key, value)
            for key, value in parse_qsl(query, keep_blank_values=True)
            if key in _ASYNCPG_QUERY_PARAMS
        ]
        query = urlencode(kept)
    return urlunsplit((scheme, netloc, path, query, fragment))


def get_database_url() -> str:
    return normalize_database_url(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))


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
