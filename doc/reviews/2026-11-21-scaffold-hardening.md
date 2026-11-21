# Review: task 01a scaffold hardening

Diff `main...HEAD`, product files only. Gate output in the run shows lint, 22 tests and gate green.

## Plan check (§2.5)
- `conftest.py:6`: abort collection of any module holding an unprivate function that matches no `python_functions` pattern. Confirmed at a glance.
- `drlibre/collection_guard.py:8`: pure filter over module members (defined here, not imported, not `_`, no pattern match). Traced the fixture case: pytest 9 wraps fixtures, so `inspect.isfunction` is false; test at `test_collection_guard.py:46` covers it.
- `drlibre/test_settings.py:21`: set env, reload settings, assert values follow the env. Passes in sandbox and container whatever `.env.example` holds.
- `scripts/ensure_database.py:59-80`: name missing variable, refuse unsafe characters without echoing the value, named cluster constants. Confirmed.
- `compose.yaml:24-30`: database name, user, password come from `.env.example` via `env_file` and an entrypoint that maps `DB_*` to `POSTGRES_*`. Traced; correct, but host-only verification (see Later).
- Port 8025 and `CLAUDE.md:46` agree.

## Findings
- **nit**, `conftest.py:13`: `UsageError` aborts the whole run on the first offender. Intended ("fails the suite"); message names module and functions. No fix.
- **nit**, `drlibre/test_settings.py:11`: `reloaded_settings` calls `monkeypatch.undo()` itself to order the reload after env restore. Works, subtle; the comment cap leaves no comment there. Add one line on why.
- **nit**, `scripts/ensure_database.py:70`: `FORBIDDEN_VALUE_CHARACTERS` also bans `"`, which `\set` with single quotes tolerates. Stricter than needed, safe. No fix.
- **nit**, `compose.yaml:24`: `env_file: .env.example` hands every `DB_*`, `EMAIL_*` variable to the `db` container. Harmless for dev values; a real secret in the file would spread. Dev-only.
- **nit**, `scripts/ensure_database.py:25`: `int(require_environment("DB_PORT"))` still raises a bare `ValueError` on a non-numeric port. Same class as item 4, not requested.
- No security, double-booking, audit or authorization surface touched. No dependencies added. No type escape hatches; `# noqa: S102` and `S603` name their codes.
- Test quality: guard tests are derived from the requirement (the red stage showed `ImportError`, so the guard failing on an example is shown at module level only). Unsafe-character test also asserts the value is not echoed.

## Blocking
None.

## Later
- Host check: `docker compose exec web make test`, `docker compose up` with fresh volume (db entrypoint override, healthcheck `$$` expansion), inbox at `127.0.0.1:8025`.
- Name a bad `DB_PORT` like the missing variable.
- Comment on the `undo()` ordering in `test_settings.py`.
- Consider a dedicated db env file if secrets ever enter `.env.example`.
