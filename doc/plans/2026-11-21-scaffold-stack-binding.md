# Plan: task 01, scaffold and stack binding

Focal point: `GET /api/v1/health` returning `{"status": "ok"}`, served by a Django +
DRF project that runs against PostgreSQL in the sandbox and in compose. Everything else
is binding: Makefile, containers, docs.

## Versions (looked up on PyPI and Docker Hub, 2026-11-21, §11)

| Package | Pin | Supports |
| --- | --- | --- |
| Django | 6.1.3 | Python >=3.12 (3.12-3.15) |
| djangorestframework | 3.18.3 | Django 5.2, 6.0, 6.1; Python 3.10-3.15 |
| psycopg (`psycopg[binary]`) | 3.3.9 | Python >=3.10 |
| pytest / pytest-django | 9.2.0 / 4.14.0 | Python >=3.10 |
| ruff | 0.17.6 | |
| mypy | 2.4.1 | strict mode; django-stubs wants mypy <2.5, >=1.13 |
| django-stubs | 6.1.2 | Django 5.2-6.1, Python >=3.11 |
| djangorestframework-stubs | 3.18.2 | needs django-stubs >=6.1.2 |

- **Python 3.13** (`.python-version`, `requires-python = ">=3.13,<3.14"`). Django 6.1
  needs >=3.12; sandbox system Python is 3.11, so uv downloads 3.13 during `make setup`.
  3.13 is supported by every package above.
- Pin exact (`==`) in `pyproject.toml`; commit `uv.lock`; `uv sync --locked`. Implementer
  re-checks each version still exists on PyPI before writing.
- Images: `python:3.13.18-slim-bookworm`, `postgres:15.20-bookworm` (sandbox apt gives
  PostgreSQL 15, same major), `rnwood/smtp4dev:3.16.1`. Tags verified on Docker Hub.
- psycopg binary extra: no compiler or libpq-dev in sandbox or image.

## Contrib applications

None. No admin, auth, sessions, contenttypes, messages, staticfiles: the product gets its
own user model, session store and admin console (task 02+), and an unused contrib app
would put Django's `auth_user` migration in the database before the custom user model.
Task 02 adds what it needs. Middleware: `SecurityMiddleware`, `CommonMiddleware` only
(no CSRF or session until a cookie-authenticated mutation exists).
Risk: DRF may import `django.contrib.auth` models on first request. Mitigate in
`REST_FRAMEWORK`: `DEFAULT_AUTHENTICATION_CLASSES=[]`, `DEFAULT_PERMISSION_CLASSES=[]`,
`UNAUTHENTICATED_USER=None`. If DRF still needs contrib.auth, stop and report; do not
install contrib.auth quietly.

## Files, in order

1. `scratch/plan.path` (done), this plan.
2. **Red first** (red stage): `pyproject.toml` (deps, pytest, ruff, mypy config, no code),
   `uv.lock`, `.python-version`, `.env.example`, `scripts/ensure_database.py`, Makefile
   `test`/`setup`, then `scheduling/views/test_health.py`. Test must fail on assertion
   (404 is not 200), not on setup. This needs a minimal `drlibre/settings.py` and
   `urls.py` with no route; the test therefore fails with 404, right reason.
3. `drlibre/__init__.py`, `drlibre/environment.py`, `drlibre/settings.py`, `drlibre/urls.py`, `manage.py`.
4. `scheduling/__init__.py`, `scheduling/apps.py` (empty domain app), 
   `scheduling/views/__init__.py`, `scheduling/views/health.py`.
5. `Makefile` (`setup`, `test`, `lint`; `gate`, `mutate` untouched).
6. `Dockerfile`, `compose.yaml`, `.dockerignore`, `.gitignore` extension.
7. `CLAUDE.md` Stack line, Fresh checkout order, Test placement, layer paths.
8. `doc/adr/0001-stack.md`.

Not touched: `scripts/comment_cap.py`, `escape_hatches.sh`, `.fabro/**`, `.claude/**`,
`doc/backlog*`, `doc/retro.md`, `drlibre-specs.md`, `doc/engineering-conventions.md`. No
README, CI, migrations, models, front end, auth.

## Blocks

- **`drlibre/settings.py`**: reads environment; `require_env(name)` raises
  `ImproperlyConfigured("Missing required environment variable X")`. Required:
  `SECRET_KEY`, `ALLOWED_HOSTS` (comma list), `DB_NAME`, `DB_USER`, `DB_PASSWORD`,
  `DB_HOST`, `DB_PORT`, `EMAIL_HOST`, `EMAIL_PORT`. `DEBUG` true only when env is `true`.
  `REST_FRAMEWORK` also sets `DEFAULT_RENDERER_CLASSES=[JSONRenderer]` only: the browsable
  API needs `TEMPLATES` and staticfiles, absent here, so a browser hit would 500.
  `require_env` lives in pure `drlibre/environment.py` (no Django import beyond the
  exception), tested beside it.
  `TIME_ZONE="UTC"`, `USE_TZ=True`, DB engine `django.db.backends.postgresql`,
  `DEFAULT_AUTO_FIELD` BigAutoField, `EMAIL_BACKEND` smtp. Installed apps: `rest_framework`,
  `scheduling`.
- **`drlibre/urls.py`**: one `path("api/v1/health", health)`, no trailing slash as in §14.
- **`scheduling/views/health.py`**: DRF `@api_view(["GET"])` returning `Response({"status":"ok"})`.
  Thin, format only (§8). No DB touch: liveness.
- **`.env.example`**: development-only values, plain `KEY=value`, host `localhost`.
- **`scripts/ensure_database.py`**: typed Python, reads env. (1) TCP connect to
  `DB_HOST:DB_PORT`; answers -> exit 0, installs nothing. (2) else if host is
  localhost/127.0.0.1 and `apt-get` exists and uid 0: `apt-get install -y postgresql` if
  `pg_ctlcluster` missing, `pg_ctlcluster 15 main start`, wait until it answers (timeout,
  clear error), create role (LOGIN, CREATEDB for pytest-django's `test_` database) and
  database idempotently via `su postgres -c psql`, password passed without logging.
  (3) else exit non-zero: "No PostgreSQL at host:port and cannot start one here". Run via
  `uv run --env-file .env.example` so one file holds the values; real environment wins
  (implementer verifies uv does not override set variables; compose depends on it).
- **Makefile**: `setup` = `uv sync --locked` (now unconditional) then ensure_database.
  `test` = ensure_database, then `uv run --env-file .env.example pytest`. `lint` =
  `ruff check`, `ruff format --check` (bare `uv run`, no settings import), then
  `uv run --env-file .env.example mypy .` (django-stubs plugin imports `drlibre.settings`,
  which raises on missing env). Every `uv run` that imports settings carries `--env-file`. `mutate` stays unbound.
- **pyproject.toml tools**: pytest `DJANGO_SETTINGS_MODULE=drlibre.settings`,
  `python_files=test_*.py` (tests beside code, §10); ruff select a broad set, line length
  100, no per-line ignore; mypy `strict = true`, plugins `mypy_django_plugin.main`,
  `mypy_drf_plugin.main`, `[tool.django-stubs] django_settings_module`.
- **Dockerfile**: `python:3.13.18-slim-bookworm`; copy uv from pinned `ghcr.io/astral-sh/uv:0.12.13`;
  install `make` via apt (so `docker compose exec web make test` works); non-root user
  `app`; `uv sync --locked` into `/opt/venv` (outside the mounted source) via
  `UV_PROJECT_ENVIRONMENT`; default CMD runserver `0.0.0.0:8000`.
- **compose.yaml**: `web` (build, bind-mount `.:/app`, `env_file: .env.example`,
  `environment` overrides `DB_HOST=db`, `EMAIL_HOST=mail`, `ALLOWED_HOSTS` incl. localhost,
  `DEBUG=true`, `depends_on: db: service_healthy`, port `127.0.0.1:8000:8000`, command
  `runserver 0.0.0.0:8000` with reload default). `db` (`postgres:15.20-bookworm`, named
  volume, `pg_isready` healthcheck, env from same values, no ports). `mail`
  (`rnwood/smtp4dev:3.16.1`, ports `127.0.0.1:5000:80`; SMTP 25 stays internal).
- **.gitignore**: add `.env`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `*.pyc`.
  **.dockerignore**: `.git`, `.venv`, caches, `.env`, `scratch`, `doc`, `.fabro`.

## Failing test first

`scheduling/views/test_health.py`:
`returns_200_when_health_endpoint_is_requested`: `GET /api/v1/health` through Django's
test client answers status 200 and JSON body exactly `{"status": "ok"}` (§14). Written
before `health.py`; expected failure: `assert 404 == 200`.
Second test, `drlibre/test_environment.py`: `raises_improperly_configured_naming_variable_
when_required_value_is_missing` (message "Missing required environment variable X") and
`returns_value_when_required_variable_is_set`. Written before `environment.py`.
Health test also asserts `Content-Type` is JSON; the browser-renderer case is covered by
the renderer setting plus a request with `Accept: text/html` in the same test file
(`returns_json_when_browser_accepts_html`: status 200, body still `{"status": "ok"}`).

## Invariants and blast radius

Double booking, server-side authorization, audit log: no code exists yet; nothing can
break. The binding does constrain them: PostgreSQL only (constraints, row locks), tests
included. Blast radius: every later task (settings, Makefile, layout, env names). Health
endpoint is public by spec, answers no data.

## Trust boundaries

Only HTTP `GET /api/v1/health`: no input read, constant output. Environment is the other
boundary: validated at start-up, required values fail loud, `.env.example` holds dev-only
values (no real secret), compose publishes on `127.0.0.1` only, database unpublished,
`DEBUG` off by default, secrets never logged (script never echoes the password).

## Domain entities

None. One empty app `scheduling` for the domain. Layer paths, recorded in CLAUDE.md:
domain `scheduling/domain/`, use cases `scheduling/use_cases/`, views and API endpoints
`scheduling/views/`; created when first used (no empty packages except `views/`, which
holds health). Tests sit beside the code (`test_*.py`).

## Will not do

No `dj-database-url`, `python-dotenv`, `pytest-env`, gunicorn, whitenoise, wsgi/asgi
modules, logging config, CSRF/session middleware, migrations, README, CI, Node. No
`ensure_database` abstraction beyond the one script. Extra deps: none beyond the allowed
list.

## Unverifiable here

Container stack: sandbox has no Docker; orchestrator verifies `docker compose up` on the
host. The Dockerfile and compose files are checked by reading only.

## Architect review (round 1, both material points and recommendations addressed above)

Verdict was: revise (two material gaps, both break "done when" or the compose acceptance).

Material:
1. `make lint` runs `mypy .` with the django-stubs plugin, which imports `drlibre.settings`.
   Settings raise on missing env, so lint fails on a fresh clone unless it also runs under
   `uv run --env-file .env.example`. The plan gives that only to `test` and
   `ensure_database`. Say so for every `uv run` in the Makefile (ruff can stay bare).
2. DRF default renderers include the browsable API, which needs `TEMPLATES` and
   `staticfiles`; neither exists in the plan. A browser request to `/api/v1/health`
   (the compose acceptance check) would 500. Set
   `DEFAULT_RENDERER_CLASSES=["rest_framework.renderers.JSONRenderer"]` (also right for an
   API-only surface). The test client would not catch this.

Recommended, not blocking:
- Add a cheap test for the start-up failure ("Missing required environment variable X"),
  since it is requested behaviour; the by-hand check is not repeatable. A small pure
  `require_env` in its own module tested beside it would do.
- Verify DRF import with no `contrib.auth` in INSTALLED_APPS early; the stop-and-report rule
  is good.
- Verify uv `--env-file` does not override already-set variables (plan already says so).

Ladder, vocabulary, scope, security and architecture otherwise fine: no extra deps, no
speculative layers, 127.0.0.1-only ports, db unpublished, DEBUG off by default, tests
beside code, first test named with the spec value.

## Architect review

Round 2. Verdict: approve.

Round 1 points are fixed in the plan: every `uv run` that imports settings carries
`--env-file .env.example`, and DRF is limited to `JSONRenderer`, with a test for an
`Accept: text/html` request.

- Ladder: no extra dependencies and no speculative layers. `require_env` is a small pure
  module with its own tests. Contrib applications: none, with a reason, and a stop-and-report
  rule if DRF needs `django.contrib.auth`.
- First tests: `returns_200_when_health_endpoint_is_requested` uses the §14 value. It fails
  with 404, not on setup. The environment tests and the HTML-accept test are named as
  behaviours.
- Security: ports bind to `127.0.0.1`, the database publishes nothing, `DEBUG` is off by
  default, required values fail at start-up, and no secret is logged.
- Scope: the plan covers all ten task items. `make mutate` stays unbound. No model or
  migration is created.

Non-blocking notes for the implementer:
1. `ensure_database.py` exits 0 as soon as a server answers. In the sandbox that skips
   role and database creation if a server runs but the role is missing. Cheap fix: also
   run the idempotent role and database creation when the local server answers and the
   script is root on localhost.
2. Confirm that `uv run --env-file` does not override variables already set, because
   compose relies on it.
3. Confirm the `django-stubs` plugin loads with no `contrib.auth` installed.
4. The versions and image tags in the table were not re-checked in this review.
   The implementer re-checks them on PyPI and Docker Hub, as the plan says.
