# Review: task 27c item 2, smoke step runner (2026-11-23)

Branch `fabro/run/01M83YQSNPV33EHCPPC27YT003` against local `main`. Diff: `doc/plans/2026-11-23-27c-smoke-runner.md` (new), `scripts/smoke.py` (new, 19 lines), `scripts/test_smoke.py` (new, 62 lines). Nothing else changed. `drlibre-specs.md`, `Makefile`, `scheduling/`, `drlibre/` untouched.

## Scope note

The run goal names item 2 with one red test: the step runner stops at a failing step and names it. The plan's slice is wider (runner, `fetch`, health step, start-page step, `main`, `make smoke` target, tests 4 to 10). This review holds the run to the goal, which says "nothing else of that file". The unfinished plan items are listed under `## Left for the orchestrator`, not as blockers. The orchestrator must decide whether the plan's slice or the goal stands; the two disagree.

## Plan and block check (§2.5)

- `SmokeFailure` (`scripts/smoke.py:8`): exception type. Confirmed at a glance.
- `run_steps` (`scripts/smoke.py:12-19`): plan in one sentence: run steps in order, stop at the first `SmokeFailure`, print the step name to stderr, return 1; else return 0. Confirmed at a glance. No trace needed.
- `Step` alias (`scripts/smoke.py:5`): zero-argument closures. This resolves plan open point 1. The plan's Focal point still says steps "take a fetch callable"; the code and the comment at line 4 say they take none. Stale plan text, see Later.

## Findings

Ordered by the review checklist. None is a blocker.

### 1. Correctness and error handling: pass

- `scripts/smoke.py:14-16` catches only `SmokeFailure`. Any other exception propagates. That is the §9 rule: an unexpected exception is a broken invariant, not a step failure. Test `raises_unexpected_error_without_reporting_a_step` (`scripts/test_smoke.py:52-62`) pins it.
- No swallowed error: the failure is printed to stderr and the function returns 1.
- Exit contract is an int from the function. No `sys.exit` in the runner.

### 2. Trust boundaries, auth, sensitive data: not applicable

No I/O, no request, no payload, no ORM, no clock. The failure text is whatever the step passes in. No secrets, no URLs.

### 3. Double booking: not applicable

### 4. Tests: derived from behaviour, pass-capable

- Exact stderr equality (`scripts/test_smoke.py:34`, `:49`) fails on any change of the message or of the step name. Good.
- Red proof recorded: `verify_red` ran 4 failures on the stub, including the RuntimeError test. The stub-driven red is for the right reason (the stub returns 0 or does not raise), not an import error.
- Later-steps test (`scripts/test_smoke.py:37-49`) asserts `later_calls == []` and the stderr text, but discards the return value. The exit code 1 is never asserted there. See Later 3.

### 5. Names and comments (§3, §4): pass with nits

- Names state roles: `run_steps`, `step_name`, `failure`, `later_calls`. No abbreviations.
- Comment `scripts/smoke.py:4` says `main()` binds the fetch callable. `main()` does not exist in this diff. See Later 1.
- Comment on `scripts/smoke.py:8` is a `noqa` note, not narration. Under 255 characters.

### 6. Proof left no trace (§2.3, checklist 7)

Commits after `verify_green` (330e6ec) up to `prove` (bdf1d25):

- `330e6ec` verify_green: empty commit message only, no file change.
- `bdf1d25` prove: no file change.

`refactor` (8aa79f4) changed `scripts/smoke.py` and `scripts/test_smoke.py`. It is after `prove`, so the rule above does not cover it, and it is the designed refactor step. The change moved `Step` from the test file into `smoke.py`. Read it: it is a pure move plus the new `Step` alias. No behaviour change.

`check` (03fa928): no file change.

Green (53dc169) changed only `scripts/smoke.py`. No mutation left behind.

### 7. Hard rules (§5, §7, §9, §11): pass

- Escape hatches: `scripts/smoke.py:8` `# noqa: N818 - ...`. Named code, passes `scripts/escape_hatches.sh`. No `Any`, `cast`, bare `type: ignore`, bare `noqa`.
- Function sizes: `run_steps` is 8 lines. File is 19 lines. Under caps.
- Types: `Step`, `Callable[[], None]`, typed test helpers. Mypy strict covers `scripts/` (only `comment_cap.py` excluded, `pyproject.toml:50`).
- Lint: ruff selects `N`, so the `noqa: N818` is live and used. Without it the lint would fail.

### 8. Scope and dependencies: pass

- No dependency added. Only the standard library (`sys`, `collections.abc`) and the existing pytest.
- No `drlibre-specs.md` change.
- No unrequested file. The plan doc is the run's own artifact under `doc/plans/`, as the process expects.
- No contract across layers (no API, no schema) in this slice.

## Measured

- Not re-run here. The sandbox numbers are in the verify logs: `verify_green` 5280 passed in 201.69 s, `check` (lint, test, gate) 5280 passed in 241.81 s. Time figures are the sandbox's shared-machine numbers, not a budget finding. The orchestrator measures on a quiet machine.

## Blocking

None.

## Later

1. `scripts/smoke.py:4`: the comment names `main()`, which the diff does not define. It is correct only after the `main()` step lands. Smallest fix: reword to the rule alone ("Steps take no arguments.") or leave it until `main()` is written.
2. `scripts/smoke.py:8`: `SmokeFailure` triggers N818 (name should end in `Error`). Smallest fix: rename to `SmokeFailureError` and drop the `noqa`. The plan names `SmokeFailure`, so a rename touches the plan too. The current `noqa` reason ("the test suite imports this name") is a weak reason; the rename is cleaner.
3. `scripts/test_smoke.py:46`: `run_steps(steps)` result is not checked in `returns_one_without_running_later_steps_when_a_step_fails`. Smallest fix: `assert run_steps(steps) == 1` before the `later_calls` assert.
4. `scripts/smoke.py:17`: a `SmokeFailure()` with no reason prints `Smoke step failed: one: ` with a trailing separator. Only steps raise it, and the plan requires a reason, so the risk is low. Smallest fix: keep the rule in the step code, or assert non-empty reasons in the step tests when they land.
5. `doc/plans/2026-11-23-27c-smoke-runner.md`, Focal point: says steps "take a fetch callable". The implementation uses zero-argument closures (see Step alias). Smallest fix: update the plan sentence when the orchestrator next edits the plan.
6. Test names: plan's names (`stops_at_first_failing_step_and_names_it`, `returns_one_when_first_step_fails`) differ from the file. The file's names follow `returns_X_when_Y` and `raises_*` (pytest config, `pyproject.toml:33`). The file's names are the ones collected and run. No action unless the plan is kept as the record.

## Left for the orchestrator

From the plan's slice, not finished in this run:

- `scripts/smoke.py`: `fetch(path) -> tuple[int, str]` with `urllib.request`, 10 s timeout, `OSError` to `SmokeFailure` without a body echo.
- `scripts/smoke.py`: `health_step(fetch)`: 200 and JSON `{"status": "ok"}`.
- `scripts/smoke.py`: `start_page_step(fetch)`: 200 and a `/providers/<uuid>` link. Markup verified at `scheduling/views/pages/search_context.py:141`.
- `scripts/smoke.py`: `main()`, `BASE_URL = "http://127.0.0.1:8000"`, `if __name__ == "__main__"`. Today `python3 scripts/smoke.py` does nothing.
- `Makefile`: `smoke` target (`python3 scripts/smoke.py`), `.PHONY` entry. Not a dependency of `test`.
- `scripts/test_smoke.py`: plan tests 4 to 10 (health, start page, refused connection).
- The goal's live check: `make smoke` against a running seeded stack. Sandbox has no Docker. The orchestrator runs it on the host.

From the plan's `## Not in this run` (never a blocker):

- Item 2 step 3: visitor holds a free slot through `/api/v1`.
- Item 2 step 4: read the verification code from the smtp4dev API on 127.0.0.1:8025. Confirm against `rnwood/smtp4dev:3.16.1`.
- Item 2 step 5: verify hold, list appointments, cancel.
- Item 1 (README) and the orchestrator's `make smoke` run against a fresh stack.

## For the owner

Nothing in this diff leaves a specification decision open.
