from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.db import lifespan

app = FastAPI(title="AI Search Visibility Tracker", lifespan=lifespan)
register_error_handlers(app)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
