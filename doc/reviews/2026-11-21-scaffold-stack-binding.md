# Review: task 01 scaffold and stack binding

Scope: `git diff main...HEAD` (14 files). Gates (`make lint`, `make test`, `make gate`) pass per the check stage. The diff covers only part of the task.

## Findings

1. **Blocker, task items 7, 9, 10 absent.** The diff has no `Dockerfile`, `compose.yaml`, `.dockerignore`, `.gitignore` change, `CLAUDE.md` change (Stack line, fresh checkout order, test placement, layer paths) or `doc/adr/0001-stack.md`. "Done when" requires the container files. Risk: the orchestrator cannot verify the stack and later runs have no bound conventions. Fix: add them as the task describes.
2. **Blocker, task item 2 not met, `drlibre/settings.py:6`.** `os.environ["SECRET_KEY"]` (and `:14-18`, `scripts/ensure_database.py:22-23`) raise a bare `KeyError`, not a clear start-up message. The planned `drlibre/environment.py` `require_env` and its test exist only as `scratch/test_environment.py.pending`, so they are not in the repo. Fix: add `require_env` raising `ImproperlyConfigured`, move the pending test beside it, and use it in settings.
3. **Blocker, task item 2 not met, `drlibre/settings.py:7-8`.** `DEBUG = False` is hard-coded, so the environment cannot turn it on. `ALLOWED_HOSTS` is hard-coded and ignores the `ALLOWED_HOSTS` in `.env.example`, so a `web` container reached under another host name gives 400. Fix: read both from the environment (`DEBUG` default off).
4. **Blocker, task items 3 and 7, `drlibre/settings.py`, `.env.example:9-10`.** `EMAIL_HOST` and `EMAIL_PORT` are in `.env.example` but never read, so Django mail does not point at `mail`. Fix: set both from the environment.
5. **Later, `scripts/ensure_database.py:63`.** Values are interpolated inside single quotes in `\set`. A password or name containing `'` breaks the script. It is safe only because the values are dev-only. Fix: reject or escape quotes.
6. **Later, `scripts/ensure_database.py:50`.** Cluster version `15` and `main` are hard-coded. Fine for the pinned sandbox image; name a constant.
7. **Later, `drlibre/settings.py:9-10`.** `INSTALLED_APPS` and `MIDDLEWARE` are minimal, and the plan's per-contrib-app justification is moot. Task 02 must revisit them (sessions, auth, admin).
8. **Later, `scheduling/views/health.py:11-20`.** `AlwaysJsonNegotiation` goes beyond the task. It is covered by the second test and takes about 10 lines. Acceptable; record why in the ADR.
9. **Later, `pyproject.toml:21`.** `python_functions = ["returns_*", "raises_*"]` fits the §3 naming rule.

## One-sentence plans

`health.py`, `urls.py` and `test_health.py` I could state at a glance. Tracing `ensure_database.py`'s `local_and_root` branching took effort. The tests derive from the specification (status, body, content type) and failed without the view in the red stage.

## Blocking

- Missing `Dockerfile`, `compose.yaml`, `.dockerignore`, `.gitignore` extension (task items 7, 9) **Outcome: fixed, `returns_200_when_health_endpoint_is_requested` unchanged; files added, container stack unverified (no Docker).**
- Missing `CLAUDE.md` binding and `doc/adr/0001-stack.md` (task item 10) **Outcome: fixed, docs only, no test.**
- Missing-variable start-up error is a `KeyError`; `require_env` and its test not in the repo (`settings.py:6`) **Outcome: fixed, `raises_improperly_configured_naming_variable_when_required_value_is_missing`.**
- `DEBUG` and `ALLOWED_HOSTS` not read from the environment (`settings.py:7-8`) **Outcome: fixed, `returns_true_only_when_flag_variable_is_true`, `returns_environment_values_when_settings_are_loaded`.**
- Email settings not wired (`settings.py`) **Outcome: fixed, `returns_environment_values_when_settings_are_loaded` (Django 6.1 `MAILERS`).**

## Later

- `ensure_database.py` quote handling and constants (findings 5, 6)
- Revisit contrib apps in task 02 (finding 7)
- Note the negotiation class in the ADR (finding 8)
