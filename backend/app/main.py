from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.runs import router as runs_router
from app.api.share import router as share_router
from app.db import lifespan

app = FastAPI(title="AI Search Visibility Tracker", lifespan=lifespan)
register_error_handlers(app)
app.include_router(runs_router)
app.include_router(share_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
