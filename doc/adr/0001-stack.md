# ADR 0001: stack

Status: accepted, 2026-11-21.

## Decisions

- **Django 6.1.3 and djangorestframework 3.18.3 on Python 3.13.** Owner decision: latest
  stable of each. DRF 3.18 supports Django 6.1; Django 6.1 needs Python 3.12 or newer.
  Every dependency is pinned exactly and `uv.lock` is committed (§11).
- **PostgreSQL 15 everywhere, tests included.** Double booking is prevented by database
  constraints and row locks, which SQLite cannot stand in for. 15 is what Debian bookworm
  installs in the sandbox, so the compose `db` image uses the same major.
- **No contrib applications.** The product gets its own user model, session store and
  admin console. Installing `auth` now would create `auth_user` tables before the custom
  user model exists. Task 02 revisits `INSTALLED_APPS` and `MIDDLEWARE`.
- **Environment-only settings.** `require_env` fails start-up naming the missing
  variable. `DEBUG` is on only when the value is `true`. Email uses Django 6.1 `MAILERS`
  because `EMAIL_HOST` and `EMAIL_PORT` are deprecated.
- **JSON renderer only, always JSON.** The browsable API needs templates and static
  files, which do not exist yet. `AlwaysJsonNegotiation` on the health view makes a
  browser's `Accept: text/html` still get JSON instead of 406.
- **mypy strict with the Django and DRF stubs**, one type checker, ruff for lint and format.
- **Containers for the developer machine.** `web` runs the development server as a
  non-root user with the source mounted and the virtual environment in `/opt/venv`; `db`
  has a named volume and health check and publishes no port; `mail` is `rnwood/smtp4dev`.
  Application and inbox bind `127.0.0.1` only. Image tags are pinned.
- **`make test` starts PostgreSQL when none answers.** Stages run in fresh shells, so a
  server started earlier may be gone. When one answers (compose) nothing is installed.

## Consequences

Container stack is unverified in the sandbox (no Docker); the host verifies it.
