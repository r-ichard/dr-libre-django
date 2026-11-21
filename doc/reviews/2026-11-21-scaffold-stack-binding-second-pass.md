# Review, second pass: task 01 scaffold and stack binding

Scope: `git diff main...HEAD` (25 files) after the address stage. `origin/main` does not exist in the sandbox, so `main` is the base. The check stage passes `make lint`, `make test` and `make gate`. All five blockers from the first review are fixed: container files, `.dockerignore`, `.gitignore`, `CLAUDE.md` binding and ADR exist, and `require_env`, `DEBUG`, `ALLOWED_HOSTS` and email are read from the environment.

## Confirmed at a glance
`health.py`, `urls.py`, `environment.py`, `settings.py`, `Dockerfile`, `compose.yaml`. `MAILERS` is real in the installed Django 6.1.3 (`django/conf/__init__.py:65`). The db service publishes no port and the other two bind `127.0.0.1`. Image tags are pinned. The web service runs as non-root. `scripts/ensure_database.py` took tracing (`local_and_root`).

## Findings

1. **Later, `scripts/ensure_database.py:21-22,55`.** It reads `os.environ[...]` directly, so a missing variable gives a bare `KeyError` where settings give a clear message. Fix: reuse `require_env`, or print the variable name.
2. **Later, `scripts/ensure_database.py:60`.** Values sit inside single quotes in `\set`, so a quote in a password breaks it. Dev-only values, so low risk. Fix: reject quotes.
3. **Later, `scripts/ensure_database.py:50-51`.** The cluster version `15` and the name `main` are hard-coded. Fix: named constants.
4. **Later, `compose.yaml:30-32`.** The db credentials duplicate `.env.example`. Fix: `env_file` on `db` with a `POSTGRES_*` mapping, or a comment saying they must match.
5. **Later, `drlibre/settings.py:8-9`.** `INSTALLED_APPS` and `MIDDLEWARE` are minimal. Task 02 must revisit them.
6. **Later, `scheduling/views/health.py:11`.** `AlwaysJsonNegotiation` is slightly beyond the request, is tested, and is recorded in the ADR. Acceptable.
7. **Unchecked.** The container stack is unverified (no Docker); the orchestrator verifies it on the host.

## Blocking

None.

## Later

- Findings 1 to 5 above.
