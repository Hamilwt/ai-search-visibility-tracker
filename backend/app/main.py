from fastapi import FastAPI

from app.db import lifespan

app = FastAPI(title="AI Search Visibility Tracker", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
