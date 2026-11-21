# Plan: task 03a, fast test suite

## Measured (sandbox, 18 CPUs, `make test`, before)

414 passed in 100–103 s. `pytest --durations=25` (all `call`, top of table):

| seconds | test |
|---|---|
| 5.95 | test_writer::returns_same_row_counts_when_command_runs_on_a_later_day |
| 4.26 | test_seed_demo_command::returns_new_hash_only_when_password_in_environment_changed |
| 2.89 | test_seed_demo_command::returns_one_new_audit_entry_when_command_runs_again |
| 2.65 | test_seed_demo_command::returns_unchanged_manual_row_when_seed_runs_again |
| 2.62 | test_writer::returns_same_row_counts_when_command_runs_twice_on_one_day |
| 2.60 | test_writer::returns_reminder_only_once_per_appointment_when_seeded |
| 2.04 | test_seed_demo_command::returns_no_seeded_name_email_or_phone_when_audit_metadata_is_serialised |
| 1.55–1.79 | the other 17 of the top 25: every test that runs `seed_demo` (test_writer, test_seed_demo_command) |

Every top-25 test runs the seed. Nothing outside the seed tests is above 0.21 s.

**Cause (measured, not guessed):** `writer.py:159` calls `set_password` for the demo
accounts; Django's default hasher (PBKDF2, hundreds of thousands of iterations) costs
~1.5 s per seed. Probe: autouse `settings.PASSWORD_HASHERS = [MD5PasswordHasher]` in
`conftest.py` alone gives 414 passed in **2.8 s** (probe reverted, nothing committed).

## Focal point

`conftest.py` (root): one autouse fixture. Everything else is wiring.

## Blocks

1. `conftest.py`: autouse fixture `fast_password_hasher` sets
   `settings.PASSWORD_HASHERS` to `MD5PasswordHasher` for every test. Test-only; product
   settings untouched.
2. `drlibre/test_settings.py`: add test proving product settings keep Django's default
   slow hasher (reads the `drlibre.settings` module, not the overridden `django.conf`).
3. `pyproject.toml` + `uv.lock`: add `pytest-xdist==<current stable, pin exact>` to the
   `dev` group; `uv lock`, verify the hash in `uv.lock` (§11).
4. `Makefile` `test`: `DB_NAME=drlibre_run_$$$$ uv run --env-file .env.example pytest -n auto --maxprocesses=4`
   (cap: startup per worker is migrations; measure at green, keep the value that is fastest).
   `ensure_database.py` still runs first with the plain `DB_NAME`.
5. `doc/engineering-conventions.md` / `CLAUDE.md`: not touched (orchestrator owns them);
   report the new `make test` behaviour in the reply.

## Collision on `test_drlibre`

pytest-django names each worker database `test_<DB_NAME>_gw<N>`. `make test` sets
`DB_NAME` to `drlibre_run_<shell pid>` (real environment wins over `.env.example`, per
CLAUDE.md), so two concurrent runs get `test_drlibre_run_<pidA>_gw0` and
`..._<pidB>_gw0`: disjoint. Django creates test databases through the `postgres`
maintenance database, so the per-run `DB_NAME` need not exist. pytest-django drops its
test databases at session end; a killed run can leak a database, never collide. Plain
`pytest` without `-n` still uses `test_drlibre` (single run, as today). Proven at red:
a test-free shell check, two `make test` in parallel both green (verified by hand at
green, reported in reply).

## Guards under xdist (each proven, not assumed)

- Collection guard: `pytest_collectstart` runs in each worker. Risk: a worker-side
  `UsageError` may not abort the controller with non-zero exit. Red test (below) pins it.
- Pending-migration and data-model-document tests: no change; they run in whichever
  worker gets them. Verify by `pytest -n 2 --collect-only -q` listing and a green run
  counting 414 + new tests.
- Failing test fails `make test`: red test runs `pytest -n 2` on a failing test and
  expects non-zero exit.

## Failing tests first (`returns_X_when_Y`)

- `drlibre/test_settings.py::returns_default_pbkdf2_hasher_when_product_settings_are_loaded`:
  `drlibre.settings` defines no `PASSWORD_HASHERS`, and Django's default first entry is
  `PBKDF2PasswordHasher`. (Passes at once on current code; it is a guard, not red. Prove
  it can fail by adding `PASSWORD_HASHERS` to settings temporarily.)
- `drlibre/test_parallel_run.py::returns_nonzero_exit_and_names_function_when_parallel_run_meets_uncollected_test`:
  subprocess `pytest -n 2` over a tmp module with `def checks_x(): ...`; expect non-zero
  exit and `checks_x` in output. Loads the root conftest via `-p conftest`.
- `drlibre/test_parallel_run.py::returns_nonzero_exit_when_parallel_run_has_failing_test`:
  subprocess `pytest -n 2` over a tmp module with one `returns_x` that asserts False;
  expect non-zero exit and `1 failed`.
- `drlibre/test_parallel_run.py::returns_hasher_md5_when_test_runs`: asserts
  `make_password("x")` starts with `md5$`. Red now (value is `pbkdf2_sha256$`).
- Both subprocess tests must stay fast (< 3 s each); if xdist startup dominates, use
  `-n 2` only there.

## Not touched

Product code (`scheduling/`, `drlibre/settings.py`, the seed writer), migrations, test
bodies of existing tests, `compose.yaml`, `scripts/`, `.fabro/`.

## Not doing

- Seed once per module: seed is 0.1–0.2 s with a fast hasher; module-scoped state would
  need a hand-held outer transaction and couples tests. Rejected by the numbers.
- `-n auto` in `addopts`: would slow single-test runs and the red gate. `make test` only.
- `--reuse-db`, `--nomigrations`: would skip the migration path the suite guards.
- No new abstraction, no refactor.

## Invariants and blast radius

Double booking, authorization, append-only audit log: untouched; no product code
changes. The audit table's append-only trigger keeps working per worker database
because each worker migrates its own. Blast radius: test run only. Risk: MD5 hasher
hides a bug only reproducible with PBKDF2; the one product-settings test and
production never use MD5.

## Trust boundaries / entities

None crossed. Entities: User (hash of demo accounts), AuditLogEntry (seed tests).

## Done check

`make setup && make lint && make test && make gate` from a fresh clone; `make test`
under 30 s (expected ~5 s); two concurrent `make test` both green; report before
(100–103 s) and after.

## Architect review

Verdict: approve.

- Ladder: one autouse fixture fixes the measured cause (PBKDF2 in the seed, 2.8 s probe). xdist is the dependency the task names. Seed-once-per-module is rejected by the numbers. No speculative abstraction.
- Task coverage: hasher fix, product-settings guard, pinned xdist, per-run database name, three guard checks, before/after report. Nothing dropped.
- Collision: `DB_NAME=drlibre_run_$$$$` gives disjoint `test_..._gwN` names per run, which holds.
- Tests: all named `returns_X_when_Y`. The two subprocess tests are the right way to prove the guards under `-n`.
- Security and architecture: no trust boundary crossed, no product code touched.

Watch at green (not blocking):
1. The inner `pytest -n 2` subprocess inherits `DB_NAME`. If the tmp module uses no `db` fixture it creates no database. If it ever does, it would collide with the outer `test_<DB_NAME>_gw0`. Keep those modules database-free, or give the subprocess its own `DB_NAME`.
2. Check that the collection-guard `UsageError` raised in a worker really gives a non-zero exit on the controller. The red test covers this. If it fails, fix the guard hook, not the test.
3. `$$$$` in the Makefile must reach the shell as `$$`. Check with `make -n test`.
4. Fabro's red/green gate scripts may call `pytest` directly or parse `make test` output. Check that the `-n` output format still works with them.
