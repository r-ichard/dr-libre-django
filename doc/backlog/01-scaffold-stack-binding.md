Task 01: scaffold and stack binding.

Draft. The stack choices below are proposals; the owner confirms or edits them before the
run.

Create the smallest Django project that the rest of the backlog can build on, and bind
the Makefile targets every later run depends on. No domain model, no feature code.

1. Project: a uv project (`pyproject.toml`, committed `uv.lock`, exact versions) with the
   current Django LTS release and a supported Python version. Check each version exists
   on PyPI before pinning (§11). One Django project package and one empty application for
   the domain. Settings read every secret and every environment-specific value from the
   environment, with a committed `.env.example`; `DEBUG` off by default.
2. Database: SQLite for now, through the Django ORM only, so runs need no database
   service in the sandbox. Record the choice and its limits as an open point for task 02.
3. `make test`: pytest with pytest-django. Write the first failing test before any
   scaffold code: `returns_200_when_health_endpoint_is_requested`, for a `/healthz` view
   that returns status 200 and the body `ok`.
4. `make lint`: ruff (lint and format check) and one strict type checker with Django
   stubs, configured in `pyproject.toml`. Lint must pass with no suppression.
5. `make setup` already installs uv and runs `uv sync --locked`; keep it working from a
   fresh clone.
6. `make mutate`: leave unbound, with its `not configured` message. Task 05 binds it.
7. Extend `.gitignore` for the files the stack generates.
8. Record the binding in `CLAUDE.md`: the Stack line, the Fresh checkout order, the Test
   placement rule (tests beside the code they cover) and the paths of the domain,
   use-case and view layers (§8).

Do not add: a front-end build, Docker files, continuous integration, authentication, an
admin site customisation, any dependency not named above.

Done when `make setup && make lint && make test && make gate` pass from a fresh clone.
