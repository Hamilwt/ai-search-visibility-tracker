# Decisions

One short entry per non-obvious architectural decision: context, choice, alternatives, consequences.

## 1. Phase 1 schema: VARCHAR+CHECK, CASCADE/RESTRICT map, functional and partial indexes

- Context: seven tables (brands, competitors, prompts, runs, responses, mentions, citations) on Postgres via SQLAlchemy 2.0 async.
- Choice: statuses as VARCHAR with CHECK constraints; `ON DELETE CASCADE` everywhere except `responses.prompt_id`, which is RESTRICT; case-insensitive uniqueness via `UNIQUE (brand_id, lower(...))` functional indexes; partial indexes for active prompts and open runs.
- Alternatives: native Postgres ENUMs (rejected: adding a value needs migration surgery); Python-side ORM cascades (rejected: loads every child row to delete it); plain case-sensitive uniques (rejected: allows "Nike" vs "nike" duplicates).
- Consequences: new statuses are one-line changes; deleting a brand cleans its subtree in one statement; prompts with stored results cannot be deleted, protecting evidence.
