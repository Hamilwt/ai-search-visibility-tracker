# Debug Log

Log every real bug or failure hit during development: symptom, log/trace evidence, root cause, fix, prevention.

## 1. Alembic offline render failed: missing `greenlet`

- Symptom: `alembic upgrade head --sql` raised `ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed`.
- Root cause: `pyproject.toml` declared plain `sqlalchemy>=2.0`; the `asyncio` extra (which pulls in `greenlet`) was never installed.
- Fix: changed the dependency to `sqlalchemy[asyncio]>=2.0` and installed it (`fix: require sqlalchemy asyncio extra for greenlet`).
- Prevention: any use of `sqlalchemy.ext.asyncio` needs the extra; CI installs from `pyproject.toml`, so declaring it there covers fresh environments.

## 2. Piping Alembic output to `Select-Object -First N` raised `OSError: [Errno 22]`

- Symptom: full traceback ending in `OSError: [Errno 22] Invalid argument` on `sys.stdout` flush; migration SQL before the crash was correct.
- Root cause: PowerShell closed the pipe after the first N lines while Alembic was still writing (Windows broken-pipe behavior), not a migration bug.
- Fix: redirect to a file (`alembic upgrade head --sql > upgrade_head.sql`) and inspect the file instead.
- Prevention: on Windows, never pipe long CLI output through `Select-Object -First`; redirect to a file.

## 3. Migration test teardown assertion failed on `alembic_version`

- Symptom: `assert await table_names(TEST_URL) == set()` failed with `Extra items: 'alembic_version'`.
- Root cause: `alembic downgrade base` removes all schema tables and version rows, but Alembic's own `alembic_version` bookkeeping table itself remains.
- Fix: assert the remaining tables equal `{"alembic_version"}` with a comment explaining why.
- Prevention: none needed beyond knowing downgrade never drops the version table.

## 4. CI install from `pyproject.toml` failed: setuptools flat-layout discovery

- Symptom: `pip install "./backend[test]"` failed with `error: Multiple top-level packages discovered in a flat-layout: ['app', 'alembic']`.
- Root cause: setuptools auto-discovery treated the `alembic/` migrations directory as a distributable package alongside `app/`.
- Fix: added `[tool.setuptools.packages.find] include = ["app*"]` to `backend/pyproject.toml` so only the app is packaged; migrations stay as scripts.
- Prevention: dry-run `pip install --dry-run "./backend[test]"` locally before changing the CI install step.

## 5. Unmatched-path 404s bypassed the error envelope

- Symptom: `GET /nope` returned FastAPI's default `{"detail": "Not Found"}` instead of the unified envelope.
- Root cause: router 404s raise Starlette's `HTTPException`, but the handler was registered for FastAPI's subclass; Starlette matches handlers up the exception's MRO, never down to subclasses.
- Fix: register the handler for `starlette.exceptions.HTTPException`, which also covers FastAPI's subclass.
- Prevention: smoke-test an unknown path (not just a known route's 404) when adding error handlers.

## 6. `add_exception_handler(Exception, ...)` never fires under test transport

- Symptom: a route raising `RuntimeError` propagated out of `httpx.ASGITransport` instead of returning the enveloped 500.
- Root cause: read FastAPI's `build_middleware_stack`: handlers keyed `Exception` (or `500`) are diverted to `ServerErrorMiddleware`, which sends the response and then always re-raises; `httpx` with default `raise_app_exceptions=True` surfaces the raise. Production behavior was correct (enveloped 500 on the wire); only the test view differed.
- Fix: no app change; test clients use `ASGITransport(raise_app_exceptions=False)` to assert 500 envelopes.
- Prevention: when testing 500 shapes, set `raise_app_exceptions=False`; read the installed framework's middleware wiring before assuming handler routing.

## 7. Background pipeline stayed `pending` in API tests (unbound session)

- Symptom: `POST /runs` returned 202 but the run never left `pending`; provider fake recorded zero calls.
- Root cause: `SessionLocal` is bound in app lifespan, which never runs under `ASGITransport`; the background task's first DB access raised `UnboundExecutionError`, swallowed by the transport.
- Fix: test fixture calls `SessionLocal.configure(bind=test_engine)` (mirroring lifespan) and unbinds in teardown.
- Prevention: any test touching code paths that use `SessionLocal` directly must bind it; request-scoped `get_session` overrides are not enough.

## 8. `completed_at` update crashed: naive vs aware datetimes

- Symptom: background run stuck at `running`; DBAPIError `invalid input for query argument $2 ... can't subtract offset-naive and offset-aware datetimes` on `UPDATE runs ... completed_at`.
- Root cause: timestamp columns relied on annotation-inferred `DateTime` (naive) while the migration created `TIMESTAMPTZ`; writing `datetime.now(UTC)` through a naive-typed column broke asyncpg encoding. Phase 1 tests never wrote Python-side datetimes, so it slipped through.
- Fix: explicit `DateTime(timezone=True)` on all five timestamp columns (`fix: declare timezone on timestamp columns`).
- Prevention: always declare temporal column types explicitly; never rely on annotation inference for types with variants.

## 9. Export smoke test failed: dev database was never migrated

- Symptom: `scripts/export_for_labels.py` raised `UndefinedTableError: relation "responses" does not exist` against the dev `visibility` database.
- Root cause: migrations had only ever run against `visibility_test` inside pytest; the dev database was created empty by `docker compose` and never upgraded. Script and query were correct.
- Fix: ran `alembic upgrade head` with `DATABASE_URL` pointed at the dev database (no code change).
- Prevention: after `docker compose up -d db` on a fresh machine, `alembic upgrade head` is a required setup step — now recorded in the hand-labeling workflow.

## 10. Next 16 scaffold cannot build on Windows (no Turbopack binaries)

- Symptom: fresh `create-next-app` (Next 16.4.1) failed with `Turbopack is not supported on this platform (win32/x64)`.
- Root cause: Turbopack native bindings aren't published/installed for this Windows box; only WASM bindings loaded.
- Fix: downgraded to `next@15` + `eslint-config-next@15` (webpack default), moved Tailwind v4 to `@tailwindcss/postcss` with a `postcss.config.mjs`, dropped 16-only `next.config.ts` keys. Recorded as the reason for Next 15 in DECISIONS entry 6.
- Prevention: run `npm run build` on the scaffold before writing any code; never assume the latest major builds everywhere.

## 11. Tailwind build failed: missing `lightningcss.win32-x64-msvc.node`

- Symptom: webpack build failed in `next/font` with `Cannot find module '../lightningcss.win32-x64-msvc.node'`.
- Root cause: npm skipped the platform-specific lightningcss native optional dependency during the churned installs.
- Fix: explicit `npm install -D lightningcss-win32-x64-msvc`; verified with a clean build.
- Prevention: when native-binding errors appear after interrupted installs, prefer a fresh `node_modules` + lockfile over incremental installs.

## 12. Scaffold flat ESLint config is legacy format in v15 preset

- Symptom: `npm run lint` failed first with `Cannot find module 'eslint-config-next/core-web-vitals'` (no `exports` map + Node 23 strict ESM), then after adding `.js`, with `nextVitals is not iterable` (file is eslintrc-style, not a flat array).
- Root cause: `eslint-config-next@15` subpaths are legacy-format configs; the flat-config scaffold template targets v16.
- Fix: removed `eslint-config-next`, installed `typescript-eslint`, minimal flat config with recommended rules.
- Prevention: match lint presets to the major version actually installed; read the preset's file format before importing it.

## 13. Recharts Tooltip formatter rejected by `tsc`

- Symptom: `tsc` error: `(value: number | undefined)` not assignable to Recharts `Formatter`.
- Root cause: annotated the formatter narrower than Recharts' value union (`ValueType` includes strings).
- Fix: dropped the annotation and let TS infer the parameter from the `Formatter` signature.
- Prevention: for library callback props, omit annotations and let inference satisfy the declared type.
