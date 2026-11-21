# Plan: task 01a, scaffold hardening (2026-11-21)

One sentence: fix five scaffold defects with the least new code; no feature, no new dependency.

## Focal point
`drlibre/test_settings.py` (item 1) and a pytest collection guard (item 2); items 3 to 5 are config and script edits.

## Blocks
1. **Settings test** (`drlibre/test_settings.py`): set unique env values with `monkeypatch`, `importlib.reload(settings)`, assert settings carry exactly those values, reload again after `monkeypatch.undo()` so later tests see the real environment.
2. **Collection guard**:
   - `drlibre/collection_guard.py`: pure function `uncollected_test_names(module, patterns)` returns names of functions defined in the module (matched by `__module__`, so imports are skipped) that match no pattern, do not start with `_`, and are not fixtures.
   - `conftest.py` at root: hook `pytest_pycollect_makeitem` calls it for `test_*.py` modules and raises `pytest.UsageError` naming the functions, so the suite fails at collection (a lint rule cannot see pytest patterns).
   - `pyproject.toml`: `python_functions = ["returns_*", "raises_*", "rejects_*"]`; guard reads the patterns from pytest config, no second list.
3. **Inbox port** (`compose.yaml`, `CLAUDE.md`): publish `127.0.0.1:8025:80`; CLAUDE.md inbox URL `http://127.0.0.1:8025`. The plan and retro files are history, untouched.
4. **`scripts/ensure_database.py`**:
   - `require(name)` helper: missing variable → `SystemExit("Missing required environment variable NAME")`, same wording as settings.
   - `refuse_quote(name, value)`: `'`, `"`, newline or backslash in role, database or password → `SystemExit` naming the variable (never the value, it can be a password).
   - Constants `CLUSTER_VERSION = "15"`, `CLUSTER_NAME = "main"`.
5. **Single source for db credentials** (`compose.yaml`): `db` gets `env_file: .env.example` and an entrypoint that maps `DB_NAME/DB_USER/DB_PASSWORD` to `POSTGRES_*` then execs `docker-entrypoint.sh postgres`; healthcheck uses `$$DB_USER`/`$$DB_NAME`. Chosen over `${VAR}` interpolation because compose only reads `.env`, which would change the documented commands, and over duplicate `POSTGRES_*` lines in `.env.example`. Orchestrator verifies on host.

## Files, in order
`pyproject.toml`, `drlibre/test_settings.py`, `drlibre/collection_guard.py` + `drlibre/test_collection_guard.py`, `conftest.py`, `scripts/ensure_database.py` + `scripts/test_ensure_database.py`, `compose.yaml`, `CLAUDE.md`.
Not touched: `.env.example`, `settings.py`, `Makefile`, `doc/plans/*`, `doc/reviews/*`, `INSTALLED_APPS`/`MIDDLEWARE` (finding 5, task 02), health view.

## Failing tests first
- `returns_names_of_functions_matching_no_pattern_when_module_has_unmatched_function`: module with `checks_x` and `returns_y` yields `["checks_x"]`. Shown failing in red (guard absent, then the example `checks_x` file fails the suite).
- `returns_nothing_when_unmatched_function_is_private_helper`: `_build_x` is allowed.
- `returns_nothing_when_function_is_imported_or_a_fixture`.
- `returns_nothing_when_function_matches_rejects_pattern`.
- `returns_environment_values_when_settings_are_loaded`: with `EMAIL_HOST=mail-example`, `EMAIL_PORT=2525`, `ALLOWED_HOSTS=a.example,b.example`, settings hold exactly those.
- `raises_system_exit_naming_variable_when_variable_is_missing` (`DB_USER` unset: message names `DB_USER`).
- `raises_system_exit_naming_variable_when_value_has_quote` (password with `'`: message names `DB_PASSWORD`, does not contain the value).
- `returns_statements_unchanged_when_values_are_clean`: if the script is split so statements are testable; else skipped (the SQL path needs root + PostgreSQL).
- Items 3 and 5 have no sandbox test (Docker); orchestrator checks `curl 127.0.0.1:8025`, `docker compose exec web make test`, `docker compose up` with a healthy db.

## Invariants, trust boundaries, blast radius
Double booking, authorization, audit log: not touched. Boundary: environment values into SQL via psql `\set`; refused if they carry quote characters, still never on a command line. Blast radius: test run, local dev scripts, compose stack. Entities: none from the domain vocabulary.

## Will not do
New dependency (pytester, ruff plugin), a generic collection framework, `.env` interpolation, mail port changes beyond the published host port.

## Architect review

Verdict: approve. Smallest sufficient change, no new dependency, all five items covered, tests named as behaviours with expected values.

Notes, not blocking:
- `pytest_pycollect_makeitem` fires per object, not per module. Implement the guard where a module is known (`pytest_collectstart` for a `Module`, or `pytest_pycollect_makemodule`) so it runs once per `test_*.py`.
- Guard should also skip classes' methods and non-function names; plan limits it to top-level functions, which matches the task.
- Red stage must show the guard failing on a real example file (`checks_x`), as planned; remove that example afterwards.
- Reload of `settings` in the test must be restored in a `finally`/fixture teardown so a failure does not leak env values into later tests.
- Item 5: confirm `web` also reads `.env.example` so both services share one source; the entrypoint mapping is host-verified only, state that in the hand-off.
