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
