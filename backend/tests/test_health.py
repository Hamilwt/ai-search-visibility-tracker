from httpx import ASGITransport, AsyncClient

from app.db import SessionLocal
from app.main import app


async def test_health_returns_ok() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_needs_no_database() -> None:
    # Cold-start state: lifespan never ran, so no engine is bound.
    # /health must still answer 200 (Render probes it during deploys).
    SessionLocal.configure(bind=None)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
