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
