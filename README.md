# AI Search Visibility Tracker

Customers increasingly discover products through AI answers, not search-result
pages — and brands have no idea when those answers stop recommending them.
This tracker measures exactly that: give it a brand, its competitors, and a
set of prompts, and it records how often AI models mention or cite each brand,
turning the results into a share-of-voice dashboard over time.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router) + TypeScript + Tailwind CSS + Recharts |
| Backend | Python 3.12+, FastAPI (async), Pydantic v2 |
| Database | PostgreSQL (SQLAlchemy 2.0 async + Alembic) |
| Agentic extraction | LangGraph reflection loop (extract → validate → fix) |
| Observability | Langfuse tracing on every LLM call |
| LLM providers | Gemini (primary, free tier) + OpenAI-compatible endpoints |

## Agentic architecture

**Extraction reflection loop.** Every model answer passes through a LangGraph
workflow instead of a single parse call: an `extract` node produces JSON, a
`validate` node checks it strictly with Pydantic, and a conditional edge loops
back to a `fix` node carrying the exact validation error (initial attempt +
2 fixes, then a defined `failed_extraction` row — never a crash). Server-side
rules the model can't corrupt: `is_target_brand` is computed, not extracted,
and citation domains are normalized locally. Full diagram and node reference:
[docs/langgraph_architecture.md](docs/langgraph_architecture.md).

## Key endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/brands` | Brand list (id + name) |
| `POST` | `/runs` | Start a run (202 + background execution) |
| `GET` | `/runs` | Run list, latest first (`?brand_id=`, `?limit=`) |
| `GET` | `/runs/{id}` | Run status with extracted responses/mentions |
| `GET` | `/brands/{id}/share-of-voice?days=` | Per-run visibility points, 0–100 share |

All errors share one envelope: `{"error": {"code", "message", "details"}}`.

## Quickstart (local development)

Prerequisites: Docker, Python 3.12+, Node 22+.

```powershell
Copy-Item .env.example .env
# Fill in LLM keys in .env, then:
docker compose up -d db
cd backend
..\.venv\Scripts\Activate.ps1
pip install ".[test]"
alembic upgrade head
uvicorn app.main:app --reload   # backend on http://localhost:8000
```

macOS/Linux equivalent:

```bash
cp .env.example .env
# Fill in LLM keys in .env, then:
docker compose up -d db
cd backend
source ../.venv/bin/activate
pip install ".[test]"
alembic upgrade head
uvicorn app.main:app --reload   # backend on http://localhost:8000
```

Frontend (new terminal):

```powershell
cd frontend
# create .env.local with: NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                    # UI on http://localhost:3000
```

macOS/Linux equivalent (same commands; only the `.env.local` step differs in
how you create the file):

```bash
cd frontend
# create .env.local with: NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                    # UI on http://localhost:3000
```

Click through: runs list (empty state first) → New run → back to the list →
brand dashboard chart.

## Tests

```powershell
cd backend
..\.venv\Scripts\Activate.ps1
ruff check .
ruff format --check .
pytest -q
```

Frontend: `cd frontend`, then `npm run lint` and `npm run build`.

## Evaluation

Accuracy is measured, not asserted: `backend/scripts/export_for_labels.py`
dumps stored responses to CSV, you hand-label brands/URLs, and
`backend/scripts/evaluate.py` prints micro-averaged precision/recall plus
rank-match rate. Latest numbers: [docs/METRICS.md](docs/METRICS.md)
(currently awaiting the first labeled run — see the workflow in
[docs/DECISIONS.md](docs/DECISIONS.md)).

## Deployment (free tier, no credit card)

Live URLs live here once deployed:
- Backend: [(https://visibility-backend.onrender.com/)](https://visibility-backend.onrender.com/)
- Frontend: [(https://ai-search-visibility-tracker-9ihm-in00h558t-hamil3.vercel.app/)](https://ai-search-visibility-tracker-9ihm-in00h558t-hamil3.vercel.app/)

- **Backend → Render:** New → Blueprint from this repo (`render.yaml`: free web
  service, `alembic upgrade head` pre-deploy, `/health` check). Fill the
  dashboard values, starting with `DATABASE_URL`. Required names (never commit
  values): `DATABASE_URL`, `DIRECT_DATABASE_URL`, `CORS_ORIGINS`,
  `MAX_PROMPTS_PER_RUN`, `MAX_RUNS_PER_HOUR_PER_IP`, `GEMINI_API_KEY`,
  `GEMINI_MODEL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`,
  `LLM_TIMEOUT_S`, `MAX_CONCURRENT_LLM_CALLS`, `LANGFUSE_HOST`,
  `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`,
  `USE_EXTRACTION_V2`.
- **Database → Neon:** free project at neon.tech. Copy **two** URLs from the
  Connect modal: the **pooled** URL (`-pooler` host) goes into `DATABASE_URL`
  for the app; the **direct** URL goes into `DIRECT_DATABASE_URL` for
  migrations (Neon's PgBouncer rejects migration-style statements, so Alembic
  prefers the direct URL automatically). Paste either URL exactly as Neon
  gives it — the app normalises the scheme and drops params asyncpg rejects.
  Manual/one-time migration from `backend/`:
  `DIRECT_DATABASE_URL=postgresql://user:pass@host/db?sslmode=require alembic upgrade head`.
- **Frontend → Vercel:** import the repo with **Root Directory** `frontend`,
  set `NEXT_PUBLIC_API_URL` to the Render backend URL, deploy.

## Known limitations

- No authentication or multi-tenancy (single-operator local design).
- Sentiment is extracted but not scored in evaluation.
- Share-of-voice is per-run points; no interpolated daily buckets.
- Render free services sleep when idle; Neon free tier has usage caps.

## Docs

- [docs/langgraph_architecture.md](docs/langgraph_architecture.md) — agent diagram
- [docs/METRICS.md](docs/METRICS.md) — script-measured numbers with commands
- [docs/DECISIONS.md](docs/DECISIONS.md) — architecture decisions
- [docs/DEBUG_LOG.md](docs/DEBUG_LOG.md) — real bugs hit during development
