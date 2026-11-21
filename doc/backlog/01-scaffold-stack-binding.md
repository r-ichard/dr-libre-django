Task 01: scaffold and stack binding.

Create the smallest Django project the rest of the backlog can build on, runnable in
containers, and bind the Makefile targets every later run depends on. No domain model, no
feature code. The stack choices below are the owner's decisions; do not reopen them.

1. Project: a uv project (`pyproject.toml`, committed `uv.lock`, exact versions) with the
   latest stable Django and the latest stable Django REST Framework that support each
   other, on a Python version both support. Check on PyPI that each version exists and
   read each project's supported versions before pinning (§11); put what you found in the
   plan. One Django project package and one empty application for the domain. Keep only
   the contrib applications the product needs and justify each one in the plan: the
   product gets its own user model, session store and admin console later. Do not create
   or commit a migration; the custom user model arrives in task 02 and must be in the
   first one.
2. Settings: every secret and every environment-specific value comes from the
   environment, with a committed `.env.example` holding development-only values. `DEBUG`
   is off unless the environment turns it on. Start-up fails with a clear message when a
   required value is missing. Time zone UTC, time-zone-aware datetimes.
3. Database: PostgreSQL everywhere, tests included, because double booking will be
   prevented by database constraints and row locks. Same major version in the sandbox
   and in the container stack.
4. `make setup` leaves a fresh clone ready for `make lint` and `make test`. The fabro
   sandbox is Debian bookworm, running as root, with no Docker daemon. Measured there:
   `apt-get install postgresql` gives PostgreSQL 15 in 9 seconds and
   `pg_ctlcluster 15 main start` starts it. So in the sandbox `make setup` installs and
   starts PostgreSQL and creates the role and database the tests use.
5. `make test` runs pytest with pytest-django against PostgreSQL. Before the tests it
   makes sure a server answers at the configured database address, and starts the local
   one when none does: stages run in fresh shells and a server started by an earlier
   stage may be gone. When a server already answers, as in the container stack, it
   installs and starts nothing. Write the first failing test before any scaffold code:
   `returns_200_when_health_endpoint_is_requested`, for `GET /api/v1/health`
   (`drlibre-specs.md` section 14) answering status 200 with the JSON body
   `{"status": "ok"}`.
6. `make lint`: ruff (lint and format check) and one strict type checker with the Django
   and Django REST Framework stubs, configured in `pyproject.toml`. Lint passes with no
   suppression.
7. Containers, for the developer's machine: a `Dockerfile` for the application and a
   `compose.yaml` with three services. `web`: the Django development server with reload,
   the source mounted, running as a non-root user. `db`: PostgreSQL with a named volume
   and a health check. `mail`: `rnwood/smtp4dev`, which receives every email the
   application sends and shows it in a web inbox. Django's email settings point at `mail`
   through the environment. Pin every image tag (§11). Publish ports on `127.0.0.1` only:
   the application and the mail inbox; the database publishes none. `docker compose up`
   from a fresh clone must serve `/api/v1/health`. The sandbox cannot run Docker, so say
   in your reply that the container stack is unverified; the orchestrator verifies it on
   the host.
8. `make mutate`: leave unbound, with its `not configured` message. Task 06 binds it.
9. Extend `.gitignore` and add a `.dockerignore` for the files the stack generates.
10. Record the binding in `CLAUDE.md`: the Stack line with the pinned versions, the Fresh
    checkout order for the sandbox and for the containers, the Test placement rule (tests
    beside the code they cover) and the paths of the domain, use-case and view layers
    (§8). Record the decisions and their reasons in `doc/adr/0001-stack.md`.

Dependencies allowed: Django, Django REST Framework, the PostgreSQL driver, pytest,
pytest-django, ruff, the type checker and its stubs. Anything else needs its reason in the
plan.

Do not add: a front-end build, continuous integration, authentication, any model or
migration, a README (it comes with the hand-over task).

Done when `make setup && make lint && make test && make gate` pass from a fresh clone in
the sandbox image, and the container files are present.
