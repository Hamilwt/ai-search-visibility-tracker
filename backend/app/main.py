import os

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.brands import router as brands_router
from app.api.errors import register_error_handlers
from app.api.runs import router as runs_router
from app.api.share import router as share_router
from app.db import lifespan

DEFAULT_CORS_ORIGINS = ["http://localhost:3000"]


def parse_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "")
    origins = [part.strip() for part in raw.split(",") if part.strip()]
    return origins or DEFAULT_CORS_ORIGINS


app = FastAPI(title="AI Search Visibility Tracker", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
register_error_handlers(app)
app.include_router(brands_router)
app.include_router(runs_router)
app.include_router(share_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
