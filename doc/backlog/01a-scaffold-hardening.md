Task 01a: scaffold hardening.

Close the defects the orchestrator found on the host and the reviewer's "Later" list of
task 01 (`doc/reviews/2026-11-21-scaffold-stack-binding-second-pass.md`) before the
domain model is built on the scaffold. No new feature.

1. `docker compose exec web make test` fails on
   `drlibre/test_settings.py::returns_environment_values_when_settings_are_loaded`. The
   test asserts the values of `.env.example` (`localhost`, `1025`); inside the `web`
   container the environment says `mail` and `25`. Make the test prove that settings
   follow the environment whatever its values, so the suite passes both in the sandbox
   and in the container.
2. A function in a `test_*.py` file whose name matches no `python_functions` pattern
   (`returns_*`, `raises_*`) is never collected: a test named `rejects_...` looks written
   and never runs. Add `rejects_*` to the patterns, and make silent non-collection
   impossible: a top-level function in a test file that is not collected and is not
   named as a private helper fails the suite or the lint. Show the guard failing on an
   example in the red stage.
3. The mail inbox is published on port 5000. On macOS the AirPlay receiver listens there
   and `http://localhost:5000` answers 403 from AirPlay instead of the inbox. Publish the
   inbox on `127.0.0.1:8025` and update `CLAUDE.md`.
4. `scripts/ensure_database.py`: a missing variable gives a bare `KeyError`, so name the
   variable as the settings do; a quote in the role, database or password breaks the
   `\set` lines, so refuse such a value with a clear message; the cluster version `15`
   and the cluster name `main` are literals, so name them.
5. `compose.yaml` repeats the database name, user and password that `.env.example`
   already holds. Keep one source of truth.

The sandbox cannot run Docker; the orchestrator verifies items 1, 3 and 5 on the host.

Done when `make setup && make lint && make test && make gate` pass from a fresh clone.
