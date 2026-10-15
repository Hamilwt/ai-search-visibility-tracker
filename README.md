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

Frontend: `cd frontend`, create `.env.local` with
`NEXT_PUBLIC_API_URL=http://localhost:8000`, then `npm install` and
`npm run dev` (opens `http://localhost:3000`).

## Ops automation (n8n)

`docker compose up -d n8n` starts self-hosted n8n at `http://localhost:5678`
(first run creates the owner account in the browser; data persists in the
`n8n_data` volume). The daily visibility-alert workflow lives in
`ops/kuku_alert_workflow.json`: cron trigger → `GET /brands/{id}/share-of-voice`
→ Code node summarizing the trend → LLM node writing a 2-sentence alert →
Slack node.

### Importing the workflow (click-by-click)

1. Open `http://localhost:5678` and finish the setup account screen.
2. Click **Workflows** in the left sidebar, then the **…** menu (top right) →
   **Import from File**.
3. Choose `ops/kuku_alert_workflow.json` from this repo and confirm. The
   canvas shows: Daily schedule → Fetch share of voice → Summarize trend →
   Write alert → Post to Slack (with the OpenAI model attached below the chain).
4. Set the two env inputs: in Docker they come from your `.env`
   (`API_BASE_URL`, `VISIBILITY_BRAND_ID`) and are readable in expressions as
   `$env.API_BASE_URL` / `$env.VISIBILITY_BRAND_ID`.
5. Connect credentials: open the **OpenAI model** node → **Create new
   credential** → paste your key; open **Post to Slack** → create new
   credential → paste your Slack OAuth token and pick `#visibility-alerts`.
6. Click **Execute workflow** (manual test run first), inspect each node's
   input/output, then flip the **Active** toggle so the cron schedule owns it.

## Deployment (free tier, no credit card)

Live URLs live here once deployed:
- Backend: _pending_
- Frontend: _pending_

### Backend on Render + Postgres on Neon

1. Create a free project at neon.tech → **Create database** → copy the
   **pooled** connection string. Change its scheme to
   `postgresql+asyncpg://` and keep `?sslmode=require` so asyncpg connects.
2. In the Render dashboard: **New → Blueprint**, point it at this repo.
   Render reads `render.yaml` (backend web service, free plan).
3. Fill the `sync: false` secrets, most importantly `DATABASE_URL` with the
   Neon string from step 1, plus your `GEMINI_*`/`OPENAI_*` keys.
4. Deploy. `preDeployCommand` runs `alembic upgrade head` automatically;
   `GET /health` is the health check.

### Frontend on Vercel

1. Import this repo in Vercel. When prompted, set the **Root Directory** to
   `frontend` (Vercel then auto-detects Next.js — no config file needed).
2. Add the environment variable
   `NEXT_PUBLIC_API_URL=https://<your-render-backend>.onrender.com`.
3. Deploy and paste both URLs above.

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
