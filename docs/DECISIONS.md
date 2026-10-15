# Decisions

One short entry per non-obvious architectural decision: context, choice, alternatives, consequences.

## 1. Phase 1 schema: VARCHAR+CHECK, CASCADE/RESTRICT map, functional and partial indexes

- Context: seven tables (brands, competitors, prompts, runs, responses, mentions, citations) on Postgres via SQLAlchemy 2.0 async.
- Choice: statuses as VARCHAR with CHECK constraints; `ON DELETE CASCADE` everywhere except `responses.prompt_id`, which is RESTRICT; case-insensitive uniqueness via `UNIQUE (brand_id, lower(...))` functional indexes; partial indexes for active prompts and open runs.
- Alternatives: native Postgres ENUMs (rejected: adding a value needs migration surgery); Python-side ORM cascades (rejected: loads every child row to delete it); plain case-sensitive uniques (rejected: allows "Nike" vs "nike" duplicates).
- Consequences: new statuses are one-line changes; deleting a brand cleans its subtree in one statement; prompts with stored results cannot be deleted, protecting evidence.

## 2. Phase 2 LLM layer: provider contract, normalized errors, server-side trust

- Context: two vendors (Gemini primary, OpenAI-compatible) behind one interface, with retries, timeouts, concurrency limits, and JSON extraction.
- Choice: `BaseLLMProvider` ABC + `get_provider` factory; providers translate SDK exceptions into three internal errors (`LLMRateLimitError`, `LLMTimeoutError`, `LLMAPIError`) so retry code never imports vendor SDKs; tenacity owns all retries with the SDKs' built-in retry disabled (`max_retries=0`); `pydantic-settings` for env config; extraction schemas use `extra="forbid"`; `is_target_brand` and citation domains are computed server-side, never trusted from the model.
- Alternatives: `if provider == ...` branches (rejected: spaghetti at three providers); SDK-default retries plus wrapper retries (rejected: double backoff); trusting model-sent flags/domains (rejected: silently corrupts share-of-voice).
- Consequences: adding a vendor means one provider class plus one factory line; malformed model output degrades to a `failed_extraction` row instead of crashing a run.

## 3. Phase 3 API: prompt upsert, per-run SoV points, background owns its session

- Context: runs execute LLM calls after the 202 response, and share-of-voice must be unambiguous.
- Choice: prompt strings upserted on `(brand_id, query_text)` (reuse + reactivate, never duplicate); SoV as one point per run with `share` 0–100 (`None` when a run has zero mentions); background pipeline opens its own `async_sessionmaker` session with per-prompt flush; one error envelope for 400/404/422/500.
- Alternatives: always-create prompt rows (rejected: trips the unique constraint on resubmission); per-day buckets with interpolation (rejected: invents measurements); sharing the request session into the background task (rejected: closed before the task runs).
- Consequences: resubmitting prompts is idempotent; partial run results survive crashes; clients parse exactly one error shape.

## 4. Phase 4 observability: decorator tracing, explicit ids, keyless passthrough

- Context: every LLM call needs input/output/latency/tokens plus our domain ids, without breaking tests or local runs without keys.
- Choice: `TracedProvider` decorator (same `BaseLLMProvider` interface, zero business-logic changes); per-prompt wrappers carrying explicit `run_id`/`brand_id`/`prompt_id` plus `call_kind` (`answer` vs `extraction`) and an attempt counter (extract = attempt 1, repair = attempt 2); one shared trace id per run; keyless `get_langfuse_client() -> None` means pure passthrough; `flush()` in a `finally` via `to_thread`, guarded so observability can never fail a run; 100% capture, no sampling; SoV reads untraced.
- Alternatives: `@observe` decorators inside providers (rejected: vendor code imports Langfuse, ids need smuggling); `ContextVar` id propagation (rejected: implicit); SDK-verified note: installed `langfuse` is v5 (OTel-based), so the wrapper uses post-hoc `start_observation(as_type="generation")` with `usage_details={input, output, total}` — verified against the installed package, not docs memory.
- Consequences: adding a traced call site is one wrapper line; tests inject a recording fake and run fully offline.

## Debugging a failed extraction with a trace (walkthrough)

1. Run the pipeline for a brand; note a response with `status = failed_extraction` (e.g. run 7, prompt 3).
2. Open Langfuse, filter observations by metadata `run_id = 7` and `prompt_id = 3`.
3. Three generations appear in order: `answer` (the raw answer text — check whether the answer itself was thin or refusal-like), `extraction` attempt 1 with `level = ERROR` (read `output`: is it truncated JSON? markdown fences? a wrong schema? — this tells you whether to fix the extraction template or the model choice), `extraction` attempt 2 with `level = ERROR` (read the repair `input` to confirm what the repair prompt sent, and its `output` to see why the fix failed).
4. Decide: malformed shape → tighten `EXTRACTION_TEMPLATE`/schema; valid JSON but refused content → the answer had nothing to extract (expected `failed_extraction`, not a bug); repeated truncation → raise `LLM_TIMEOUT_S` or shorten prompts.

## 5. Phase 5 evaluation: pure math, thin scripts, owner-labeled truth

- Context: accuracy numbers must be reproducible and attributable, not vibes.
- Choice: pure comparison functions in `app/eval/metrics.py` (unit-tested, DB-free) with thin `backend/scripts/` CLIs for export and scoring; `Name@rank` label syntax; micro-averaged precision/recall (30 rows can't support per-brand metrics); divide-by-zero prints `n/a`; sentiment explicitly out of scope for v1.
- Alternatives: scoring logic embedded in the script (rejected: untestable without a database); per-brand metrics (rejected: meaningless confidence intervals at n=30).
- Consequences: `export → hand-label → evaluate → paste block into docs/METRICS.md` is the only path numbers enter the repo.

## Hand-labeling workflow (for the owner)

1. `cd backend` and ensure the dev database is migrated: `alembic upgrade head`.
2. `python scripts/export_for_labels.py --limit 30 --out labels/labeled_30.csv` (latest `success` responses only).
3. Fill `expected_brands` (`Acme@1;Umbrella@2`) and `expected_urls` (`https://…;https://…`) in the CSV.
4. `python scripts/evaluate.py --labels labels/labeled_30.csv` prints the metrics block.
5. Append the printed block verbatim to `docs/METRICS.md`. Never hand-edit the numbers.

## 6. Phase 6 frontend: Client Components only, typed client, two new list endpoints

- Context: owner new to React; pages need brand/run lists the backend didn't expose.
- Choice: all-Client-Components v1 (one mental model: state + `useEffect` fetching); `lib/types.ts` hand-mirrored from Pydantic schemas with `tsc` catching drift; one `api.ts` translating the error envelope into thrown `ApiError`; tiny backend addition (`GET /brands`, `GET /runs` with grouped join) instead of frontend workarounds; Next.js 15 (not the scaffold's 16 — Turbopack has no Windows binaries here) with Tailwind v4 via PostCSS; `typescript-eslint` flat config (the v15 Next preset ships legacy format).
- Alternatives: Server Components/fetch-on-server (rejected: two mental models while learning); localStorage run ids instead of list endpoints (rejected: hacky, breaks across browsers); Next 16 defaults (rejected: doesn't build on this machine).
- Consequences: every fetch has loading/error/empty states; `npm run lint` + `npm run build` gate each commit and run in CI.

## Frontend local run (for the owner)

1. Backend: `docker compose up -d db`, `cd backend`, `..\.venv\Scripts\Activate.ps1`, `uvicorn app.main:app --reload` (port 8000).
2. Frontend: `cd frontend`, create `.env.local` with `NEXT_PUBLIC_API_URL=http://localhost:8000`, `npm install`, `npm run dev`, open `http://localhost:3000`.
3. Click through: runs list (empty state first) → New run → back to list → brand dashboard chart.

## 7. Phase 7 deploy + ops: Render backend, Neon Postgres, local n8n, JSON workflow

- Context: portfolio needs live URLs (free, no credit card) plus demonstrable ops automation for an AI & Ops role.
- Choice: Render free web service from `render.yaml` (migrations via `preDeployCommand`, `/health` check) with the database on Neon (pooled URL, `sslmode=require`) instead of Render Postgres (90-day deletion risk); n8n self-hosted beside Postgres with default SQLite storage; workflow as versioned JSON using `$env` inputs so one file works on any machine; Vercel by dashboard instructions (auto-detects Next.js, no config file to drift).
- Alternatives: Render Postgres (rejected: expiry risk); n8n on our Postgres (rejected: couples ops tooling to product DB); `vercel.json` (rejected: duplicates dashboard settings).
- Consequences: `docker compose up -d n8n` + UI import is the whole local ops demo; live URLs get pasted into the README after first deploy.

## 8. Phase 8 LangGraph v2: reflection graph as primary extraction path

- Context: showcase multi-step agentic reasoning with a critique loop, without breaking the working pipeline.
- Choice: `StateGraph` with `TypedDict` blackboard (`raw_attempt`, `attempts`, `validation_error`, `result`); three nodes reusing v1's templates and `_parse` verbatim (no duplicated validation); conditional edge `validate → END | fix` with budget initial + 2 fixes; v2 ON by default behind `USE_EXTRACTION_V2=0` opt-out; mermaid diagram generated from the compiled graph by a checked-in script.
- Alternatives: LangChain `LLMChain` + manual loop (rejected: control flow hidden in Python, nothing to visualize); separate v2 pipeline module (rejected: duplicated DB logic); v1 default with v2 opt-in (rejected: the point of the phase is showcasing the agent).
- Consequences: every extraction is now traceable as extract → validate → fix hops; existing tests parametrized over v1/v2 prove identical stored rows; Langfuse keeps working unchanged because the graph calls the same `TracedProvider` wrappers (each fix appears as another `extraction` observation with a higher attempt number).
