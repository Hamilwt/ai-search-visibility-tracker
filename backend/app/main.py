from fastapi import FastAPI

app = FastAPI(title="AI Search Visibility Tracker")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
