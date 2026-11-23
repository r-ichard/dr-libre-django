# Review: per-test time gate (task 26c, item 11, gate only)

Scope: `git diff main...HEAD`, 5 files, 208 insertions, 1 deletion. Plan: `doc/plans/2026-11-23-per-test-time-gate.md`.
Commits after `verify_green` (08c5b47) up to `prove` (ec494d1) and after it: `prove` and `refactor` change `drlibre/test_time_gate.py` only. `check` (8ddbad8) changes nothing. No product line changed after `verify_green`. Nothing in `drlibre-specs.md` changed. No dependency added.

## Plan, block by block (§2.5)

- `drlibre/time_gate.py:1-10`: one sentence: a constant and a pure function returning a message or `None`. Read at a glance.
- `drlibre/test_time_gate.py`: the tests of that function. Read at a glance.
- `conftest.py:27-37`: a wrapper on `pytest_runtest_makereport` that turns a passing over-limit phase into a failure. Traced: `call.when` and `call.duration` are pytest's own values, and the `report.passed` guard leaves an earlier failure's message alone.
- `doc/handover.md:29`: one clause. Read at a glance.

I confirmed the hook fires in all three phases by running it, not by reading alone. I copied `HEAD` to a scratch directory outside the workspace, set the constant to 1 there, and added a probe test: slow setup and teardown through a fixture, and a slow call. Output under `-n 0`:

```
drlibre/test_probe_gate.py::...slow: setup took 2.0 s, over the 1 s limit (MAXIMUM_TEST_SECONDS)
drlibre/test_probe_gate.py::...slow: teardown took 2.0 s, over the 1 s limit (MAXIMUM_TEST_SECONDS)
drlibre/test_probe_gate.py::...call_is_slow: call took 2.0 s, over the 1 s limit (MAXIMUM_TEST_SECONDS)
1 failed, 2 errors in 6.07s
```

Same result under `-n 2`. The scratch copy is removed; the workspace is unchanged.

## Findings

Severity: nit or later. No important findings.

1. **nit** `drlibre/time_gate.py:4`: the parameter `nodeid` is a shortened word, which §3 forbids. The plan said "no shortened words". Smallest fix: name the parameter `test_identifier` and pass `item.nodeid` at `conftest.py:32`. Risk: none.
2. **nit** `doc/handover.md:29`: "a test whose setup, call or teardown passes `MAXIMUM_TEST_SECONDS` fails it" reads as "succeeds". Smallest fix: "takes longer than `MAXIMUM_TEST_SECONDS`". Risk: a reader misreads the gate.
3. **nit** `drlibre/test_time_gate.py:10`: the plan named three tests, one per phase. The code has one parametrized test for the three phases, plus two more (`:22`, `:28`). The behaviour names are correct and the assertions check the message (nodeid, phase, `61.5 s`, `60 s`), so none can pass forever. Only the plan differs from the code. No fix needed.
4. **later** The plan asked for the wiring proof and the largest setup to be recorded in green-stage notes. Neither is in the repo or the stage log I was given. The wiring proof I reproduced (see "Plan, block by block" above). The largest setup: the `verify_green` run (5267 passed, 195.04 s, 8 workers, shared machine) and the `check` run (5268 passed, 181.29 s) both passed the gate, so no phase in those runs exceeded 60 s, setup included. That is the rejection rule of the plan, met. The exact largest setup number was not recorded.
5. **later** `verify_red` ended in an xdist `INTERNALERROR` (`KeyError: <WorkerController gw0>` in `worker_workerfinished`), with `no tests ran`. The red gate counts that as red. The expected reason is `ModuleNotFoundError` for `drlibre.time_gate` during collection. The log I was given does not show that line. Red-for-right-reason is judged by reading (hand-applied gap 2); this one should be read, not assumed.
6. **later** `drlibre/time_gate.py:8-10`: the function returns `str | None`, a value in the contract. Nothing swallowed, nothing raised. No issue.
7. **later** The plan accepts that a skipped report is not checked (`report.passed` only). A slow setup ending in `pytest.skip` escapes the gate. Accepted in the plan; noted here so the orchestrator knows it is a hole, not an oversight.
8. **later** `doc/handover.md:28` still says "about 4900 tests, 40 to 65 seconds". The stage logs show 5267 and 5268 tests and 181 to 195 s under load. The number predates this change. Re-measure on a quiet machine, not in this review.

## Checks

- Authorization, sessions, schemas, audit, double booking: no trust boundary crossed; none applies to test tooling.
- Type escapes: none (no `Any`, `cast`, `# type: ignore`, `# noqa`). Lint and gate passed in the `check` stage.
- Swallowed errors: none. The gate never suppresses a phase that already failed.
- Size: functions under 50 lines, files under 300, line length under 100 (`pyproject.toml:38`).
- Comments: `drlibre/time_gate.py:5` says why (tests pass literal values instead of sleeping). `conftest.py:33` says why the `report.passed` guard is there. Both pass the litmus test.
- Scope: `drlibre/` is the product package, but `collection_guard.py` already sits there as test tooling. Same shape, so consistent.

## Blocking

None.

## Later

- Finding 1: rename `nodeid` (`drlibre/time_gate.py:4`).
- Finding 2: reword the handover clause (`doc/handover.md:29`).
- Finding 4: record the largest setup and the ten slowest tests from a quiet-machine measurement.
- Finding 5: read the red log of `verify_red` for the collection error that caused the crash.
- Finding 7: skipped setups escape the gate. Known, accepted.
- Finding 8: re-measure `doc/handover.md:28` on a quiet machine.

## For the owner

Nothing left open in the specification.

## Left for the orchestrator

From the plan's `## Not in this run`, not blockers:
- Why some teardowns wait 9 to 28 s at the end of a worker (`test_api_live_server.py` or open connections from race tests). Another run.
- Lowering `MAXIMUM_TEST_SECONDS` below 60. Another run, after the teardown waits are gone.
- Item 11's "bring those under it": the hostile-input test is 14 and 11 s, under 60. Nothing to do here.
- Items 11a, 12 to 20.

Unfinished from the slice, not in the diff:
- Record the largest setup (plan: "well under 60 s") and the ten slowest tests (item 11 asks for them) from a quiet-machine `make test --durations=10`. Not in the repo.
