# AI Search Visibility Tracker

Shows how often AI search engines mention or cite a brand versus its competitors.

## Stack

- Backend: Python 3.12+, FastAPI (async), Pydantic v2
- Database: PostgreSQL (SQLAlchemy 2.0 async + Alembic, from Phase 1)
- Frontend: Next.js (App Router) + TypeScript + Recharts (from Phase 6)
- LLM: Gemini (primary) + OpenAI-compatible provider (from Phase 2)

## Local development

```powershell
Copy-Item .env.example .env
docker compose up -d db
cd backend
..\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Health check: `GET http://localhost:8000/health` returns `{"status": "ok"}`.

## Tests

```powershell
cd backend
..\.venv\Scripts\Activate.ps1
ruff check .
ruff format --check .
pytest -q
```

## Docs

- `docs/DECISIONS.md` — architecture decisions (one entry per non-obvious choice)
- `docs/DEBUG_LOG.md` — real bugs hit during development
- `docs/METRICS.md` — script-measured numbers with exact commands
