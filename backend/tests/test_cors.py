"""CORS tests: parsing plus real middleware behaviour, no database."""

from httpx import ASGITransport, AsyncClient

from app.main import app, parse_cors_origins


def test_parse_defaults_to_localhost(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert parse_cors_origins() == ["http://localhost:3000"]


def test_parse_splits_and_strips(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example.com, https://b.example.com ,,")
    assert parse_cors_origins() == ["https://a.example.com", "https://b.example.com"]


def test_parse_blank_falls_back(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("CORS_ORIGINS", "  , ")
    assert parse_cors_origins() == ["http://localhost:3000"]


async def test_allowed_origin_is_reflected() -> None:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_disallowed_origin_gets_no_cors_headers() -> None:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
