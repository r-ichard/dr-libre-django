# Per-test time gate (task 26c, item 11, gate only)

Slice: item 11, the gate only. Items 11a, 12 to 20 and the teardown waits are not in this run (see `## Not in this run`).

## Focal point

`make test` fails when one test's setup, call or teardown runs longer than `MAXIMUM_TEST_SECONDS`
(60). The failure names the test, the phase, the seconds and the limit. The number lives in one
place.

`MAXIMUM_TEST_SECONDS` is a ceiling against a test that runs away, not a budget. It does not ask
any test to get faster, and a test under it is not thereby fast. Measured phases it must clear:
call up to 11.5 s, teardown 9 to 28 s under load (the teardown waits stay in place; another run
removes them).

## Ladder

- Rung 1, existing pytest: `--durations` prints slow phases but never fails. Rejected.
- Rung 2, `pytest-timeout`: a new dependency, not in `pyproject.toml`. It kills a test; it does not
  say which phase took how many seconds, and it is not a measured-duration check. Rejected.
- Rung 3, chosen: a pure function in `drlibre/` (same shape as `drlibre/collection_guard.py`, which
  the root `conftest.py` already uses) and a wrapper hook in the root `conftest.py` that reads
  `call.duration` and `call.when`, which pytest already provides.

## Blocks and files, in order

1. `drlibre/time_gate.py` (new, about 15 lines). `MAXIMUM_TEST_SECONDS = 60`. Pure function
   `over_limit_message(nodeid: str, phase: str, seconds: float, limit: float) -> str | None`:
   returns `None` when `seconds <= limit`, else
   `f"{nodeid}: {phase} took {seconds:.1f} s, over the {limit:g} s limit (MAXIMUM_TEST_SECONDS)"`.
   No I/O, no clock, no pytest import. The limit is a parameter, so tests pass literal values and do
   not sleep.
2. `drlibre/test_time_gate.py` (new, about 40 lines). Four tests, listed under `## Failing tests`.
3. `conftest.py` (root, existing, about 12 lines added). A wrapper hook
   `pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None])` with
   `Generator[None, pytest.TestReport, pytest.TestReport]` as return type (same as the existing
   `pytest_make_collect_report` wrapper). After `report = yield`: compute
   `over_limit_message(item.nodeid, call.when, call.duration, MAXIMUM_TEST_SECONDS)`. If it is not
   `None` and `report.passed`, set `report.outcome = "failed"` and `report.longrepr = message`.
   A phase that already failed keeps its own failure; the gate does not overwrite it.
4. `doc/handover.md` line 28 describes what `make test` does: add one clause that it fails a test
   over `MAXIMUM_TEST_SECONDS`. One line, same commit.

The orchestrator owns `doc/backlog.md` and `doc/retro.md`; this run does not touch them.

## Files deliberately not touched

- `Makefile`, `pyproject.toml`: no new flag, no new dependency. `make test` already runs pytest with
  `-n auto`; the hook runs inside each worker and xdist carries the failed report back.
- Any `scheduling/**` file, including `test_api_live_server.py` and the hostile-input test. No test is
  changed in this run.
- `drlibre/collection_guard.py`, `drlibre/test_collection_guard.py`: unchanged.
- `mutation-equivalents.txt`, `doc/backlog/26c-gates-that-hold.md`: unchanged here.

## Invariants and blast radius

- No product behaviour changes. No user-visible text, no route, no model, no migration.
- Blast radius is every test run by `make test` (about 4591 items). The hook adds one float comparison per
  phase; no measurable cost.
- Authorization, audit log, double booking: not touched.
- The one real risk: pytest-django creates the test database in a session fixture, and that cost is
  charged to the setup phase of whichever test first asks for it. A cold database with migrations
  could exceed 60 s and fail a good test. Green stage must measure it: one `make test` run with
  `--durations=10`, and the largest setup must be well under 60 s. If it is not, the plan is
  rejected, not the limit raised silently.
- A timed-out phase that already failed (an assertion) keeps its own message; the gate is silent
  for it. The suite is red either way.
- A skipped report is not checked (`report.passed` only). A slow setup that ends in `pytest.skip`
  escapes the gate. Accepted; no test does this today.

## Naming and style

- Constant `MAXIMUM_TEST_SECONDS` (named, one place). Function `over_limit_message`. Parameters
  `nodeid`, `phase`, `seconds`, `limit`: no shortened words.
- Comments only where the why is not obvious (one in `time_gate.py` on the parameter, one in
  `conftest.py` on the `report.passed` check). Under 255 characters per block.
- Functions under 50 lines; files under 300.

## Failing tests (written first, behaviour names, expected values from the task)

In `drlibre/test_time_gate.py`:

- `returns_message_naming_test_phase_seconds_and_limit_when_setup_takes_over_limit`:
  nodeid `scheduling/domain/test_x.py::returns_y`, phase `setup`, 61.5 s, limit 60. The message
  contains the nodeid, the word `setup`, `61.5 s` and `60 s`.
- `returns_message_naming_test_phase_seconds_and_limit_when_call_takes_over_limit`: same, phase
  `call`, 61.5 s.
- `returns_message_naming_test_phase_seconds_and_limit_when_teardown_takes_over_limit`: same,
  phase `teardown`, 61.5 s, limit 60.
- `returns_none_when_call_takes_under_limit`: phase `call`, 11.5 s, limit 60 returns `None`.

Each must fail before `time_gate.py` exists (module not found), then pass.

Wiring proof (not committed): the hook cannot be unit-tested without a minute of sleep. Green stage
runs a temporary probe: a scratch test file under `drlibre/` whose setup, call and teardown each
sleep 2 s, with `MAXIMUM_TEST_SECONDS` edited to 1 for the run. `pytest` on the probe must fail
three times, one per phase, with messages naming the probe test. Then the constant is restored to 60
and the probe deleted. The output is pasted into the green-stage notes.

## Trust boundaries and entities

- No trust boundary is crossed. The gate reads pytest's own measured durations inside the
  developer's test run. No request, no user input, no external service.
- Domain entities: none. Vocabulary from CLAUDE.md is not used; this is test tooling.

## Not in this run

- Why some teardowns wait 9 to 28 s at the end of a worker (`test_api_live_server.py` or open
  connections from race tests). Another run finds and removes the wait.
- Lowering `MAXIMUM_TEST_SECONDS` below 60. Another run decides after the teardown waits are gone.
- Item 11's "bring those under it": the hostile-input test is already 14 and 11 s, under 60. Nothing
  to bring under.
- Items 11a, 12 to 20.

## Done for this slice

`make lint`, `make test` (green, with the largest setup recorded), `make gate` pass. Wiring proof
output recorded. Mutation gate: not run here (`make mutate` covers `scheduling/domain` only and this
change is in `drlibre/`).

## Architect review

Verdict: approve. Read against CLAUDE.md and the backlog item 11 (gate part only).

1. Ladder: right rung. `--durations` never fails; `pytest-timeout` is a new dependency and kills
   rather than measures. A pure function plus one wrapper hook on `pytest_runtest_makereport`, the
   same shape as the existing `pytest_make_collect_report` wrapper and `drlibre/collection_guard.py`,
   is the smallest change. No speculative abstraction.
2. Blocks: each block's purpose is one sentence (constant; pure message function; four tests; hook
   that fails an over-limit passing phase; one clause in the handover). Vocabulary: test tooling, so
   no domain entities, as stated.
3. Test first: four named behaviours with values from the task (61.5 s over 60 s in setup, call and
   teardown; 11.5 s under 60 s). Each fails first because `time_gate.py` does not exist. Gap, not
   blocking: no test pins the boundary (exactly 60 s passes, per `<=`). Add one case in green if cheap.
4. Security: no trust boundary crossed; plan says so. Nothing to validate; no secrets, no logs.
5. Architecture: test tooling in the root `conftest.py` and `drlibre/`, consistent with the
   existing collection guard. Not a product layer, so §8 layering does not apply.
6. Scope: slice is coherent. The gate covers setup, call and teardown; the teardown waits, the
   number's reduction and item 11a/12 to 20 are explicitly deferred. The product stays whole: no
   test is changed, so no existing test can newly fail except through a real over-limit phase.
   Risk named and handled: DB creation charged to the first setup (measured in green, with rejection
   rule). The plan does not restate the ten slowest tests from a fresh measurement as item 11 asks;
   the orchestrator measurement is cited instead. Acceptable for a gate-only slice; record the
   ten-slowest list in the green-stage notes.
7. Accuracy of references (checked): `conftest.py` wrapper pattern, `drlibre/collection_guard.py`,
   `python_functions` pattern (`returns_*` matches the planned test names), `doc/handover.md` line 28
   (the `make test` sentence to extend). Nit: the plan says about 4591 items; `doc/handover.md`
   says about 4900. Use the number the green run prints.
8. Hook correctness: `call.when` and `call.duration` are pytest's own; setup, call and teardown each
   pass through `pytest_runtest_makereport`; a string `longrepr` on a runtest report is accepted.
   Skipped reports are not checked; accepted in the plan.
