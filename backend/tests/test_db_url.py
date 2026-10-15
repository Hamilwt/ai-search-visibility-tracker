"""URL normaliser tests: pure string transforms, no database."""

from app.db import get_database_url, normalize_database_url


def test_postgresql_scheme_gains_asyncpg_dialect() -> None:
    assert normalize_database_url("postgresql://u:p@host/db") == "postgresql+asyncpg://u:p@host/db"


def test_asyncpg_scheme_passes_through() -> None:
    url = "postgresql+asyncpg://u:p@host/db"
    assert normalize_database_url(url) == url


def test_sslmode_is_kept() -> None:
    assert (
        normalize_database_url("postgresql://u:p@host/db?sslmode=require")
        == "postgresql+asyncpg://u:p@host/db?sslmode=require"
    )


def test_channel_binding_and_unknown_params_are_dropped() -> None:
    assert (
        normalize_database_url(
            "postgresql://u:p@host/db?sslmode=require&channel_binding=require&foo=bar"
        )
        == "postgresql+asyncpg://u:p@host/db?sslmode=require"
    )


def test_no_query_string_unchanged() -> None:
    url = "postgresql+asyncpg://tracker:tracker@localhost:5432/visibility"
    assert normalize_database_url(url) == url


def test_get_database_url_normalises_env(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://u:p@host/db?sslmode=require&channel_binding=require"
    )
    assert get_database_url() == "postgresql+asyncpg://u:p@host/db?sslmode=require"
