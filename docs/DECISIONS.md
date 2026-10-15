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
