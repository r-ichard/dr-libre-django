# Review: task 27c item 2, smoke steps, `main()`, `make smoke`, one README line

Reviewed: `git diff 680f030 HEAD` (base is the run's start commit `680f030`; the sandbox has no local `main`).
Files: `scripts/smoke.py`, `scripts/test_smoke.py`, `Makefile`, `README.md`, `doc/plans/2026-11-23-smoke-steps.md`.
No product code, no `drlibre-specs.md`, no dependency change. Commits after `verify_green` (`7101144`) that
touch files: `2423d97 prove` changes `scripts/test_smoke.py` only; `57b9ed0 refactor` is empty. Proof left no
product trace.

Verdict: `revise`. One defect breaks the stated contract (a failure must name its step), and one promised
test is absent.

## Plan per block (§2.5), what was confirmed at a glance, what forced a trace

- Types and constants (`smoke.py:13-53`): one sentence each. Read at glance. `Reply`, `Journey`, `Fetch`,
  `Step` are typed; no `Any`, `cast`, bare `# type: ignore`, or bare `# noqa` (the two `noqa` lines name codes).
- `run_steps` (`smoke.py:60-67`): unchanged from base. Confirmed by diff.
- `make_fetch` (`smoke.py:70-87`): traced. Its exception mapping is the defect below.
- Answer helpers (`smoke.py:90-117`): one sentence each; each raises `SmokeFailure` with a step label.
- Steps 1 to 6 (`smoke.py:120-208`): each traced against the stack. Health key `status` = `ok` matches
  `scheduling/views/health.py:12`. Booking-code wording matches `scheduling/domain/email_content.py:45`.
  Slot, hold, verify, list and cancel routes and fields match the plan's checks.
- `main` (`smoke.py:211-222`): one sentence. Sends steps to `run_steps`; no `print` on success (the plan
  said it would print `Smoke passed`; see Later).
- Makefile `smoke` and README line: read at glance; see Later on the interpreter.

## Findings

### Blocking

**B1. Transport and decode errors escape as tracebacks, without a step name.** `scripts/smoke.py:79-85`,
`except (URLError, TimeoutError)`. Only those two are mapped. `http.client.HTTPException` (bad status line,
truncated body) and other `OSError` (reset during `read()`) pass through `run_steps`, which only catches
`SmokeFailure`. Checked by running `make_fetch()` against a local socket that sends `NOT HTTP` (raises
`http.client.BadStatusLine`) and against a truncated body (raises `http.client.IncompleteRead`). Both
escaped uncaught. Backlog 27c requires "fails with a message that names the step when one step fails",
and the architect's revise reason 1 required this mapping. Risk: a stack that answers garbage makes `make
smoke` print a traceback and no `Smoke step failed: <name>` line. Smallest fix: add `from http.client import
HTTPException`, and change line 84 to `except (OSError, HTTPException) as failure:`. `URLError` and
`TimeoutError` are `OSError` subclasses; `HTTPError` stays first, so it is still caught at line 82. The
`read()` at line 81 sits inside the same `try`, so it is covered. Red test: add one test to
`scripts/test_smoke.py` that monkeypatches the opener's `open` to raise `http.client.BadStatusLine` and
asserts `SmokeFailure`. Expected fail first: it raises `BadStatusLine` today.

**Outcome: fixed.** Red test `raises_smoke_failure_when_stack_answers_with_garbage` failed with
`http.client.BadStatusLine: NOT HTTP` escaping `make_fetch`. Fix: `except (OSError, HTTPException)` at
`scripts/smoke.py:84`, `URLError` import replaced by `HTTPException`. Green; `make test` 5307 passed.

**B2. Promised test missing.** Plan test 14, `returns_loopback_urls_when_smoke_constants_are_read`, is not in
`scripts/test_smoke.py` (no test name or assertion mentions the loopback URLs). The plan lists it as accepted
and weak. Smallest fix: one test asserting `BASE_URL.startswith("http://127.0.0.1:")` and the same for
`MAIL_BASE_URL`, both imported from `scripts.smoke`.

**Outcome: fixed.** Test `returns_loopback_urls_when_smoke_constants_are_read` added to
`scripts/test_smoke.py`. Note: it passes on the existing constants, so it has no red step; it guards the
loopback values, which the code already holds (no behaviour change, as the plan asked).

### Later

**L1. Plan drift, the plan no longer describes the code.** The plan's `Reply(status, headers, body)`,
`NO_ANSWER`, `make_steps(fetch, pause)`, `_fetch_urllib`, `_send`, and the 14 test names do not exist. The code
has `Reply(status, body)`, `Journey`, `make_fetch`, and steps that take no arguments. Record the change in the
plan or an ADR so the next reader does not chase a missing `make_steps`. Not a blocker: the code is the
artifact and it is smaller.

**L2. Hold body drops `clinician_id`.** `scripts/smoke.py:161-168`. The plan sends the clinician the slot
listed (`clinician_ids[0]`); the code sends none, so the server assigns one (round robin,
`scheduling/use_cases/booking_holds.py:66`). `scripts/test_smoke.py:251-268` pins the shorter body, so the
test encodes the drift. Smoke still holds a free slot; it just no longer holds the clinician the search showed.
Fix: carry `clinician_ids[0]` from `_first_free_start` and send it as `clinician_id`; update the test.

**L3. No inbox poll.** Plan promised up to `INBOX_ATTEMPTS` polls with a pause (`smoke.py:174-186` makes one
request). The code is safe without it: `scheduling/use_cases/booking_codes.py:58` sends the code mail
synchronously before the hold's 201, so it is in the inbox. Record the change in the plan. The inbox read
also does not check the recipient (`to`) of the newest message; on a shared mail sink another mail could be
read. Fine for a fresh stack; check `to` if the sink is ever shared.

**L4. Cookie round trip untested.** `smoke.py:72` uses `CookieJar`, which carries the session from verify to
the appointment list. No red test covers it; only the live `make smoke` exercises it. Add one test against a
local `http.server` that sets `drlibre_session` and checks the next request sends it, if the orchestrator's
live run is not enough.

**L5. Interpreter in the Makefile.** `Makefile` target `smoke` runs `python3 scripts/smoke.py`; the plan said
`uv run python scripts/smoke.py`, which every other target uses. `smoke.py:6` imports `datetime.UTC`, which
needs Python 3.11 or later. A host `python3` older than that fails at import. Fix: `uv run python scripts/smoke.py`.

**L6. Name.** `scripts/smoke.py:181` binds a `Reply` to `text`. Rename `plaintext`.

**L7. Redirects.** `urllib` follows redirects (plan risk, unchanged). A 302 that ends in a 200 passes a step.
Left as the plan states.

**L8. `refusal.read()` at `smoke.py:83`** runs inside the `except HTTPError` handler, so B1's wider `except`
does not cover it. It can raise `http.client.IncompleteRead` on a truncated error reply. Wrap it in the same
change as B1.

**L9. Success message.** The plan said `main` prints `Smoke passed: N steps`. The code prints nothing on
success. Harmless; the orchestrator's run shows exit 0.

**L10. Not measured here.** No time budget is in this task. The sandbox runs `make test` at 307 s (verify_green)
and 167 s (check); not a budget, so not a finding.

## Checks run

- `git diff 680f030 HEAD --stat`: five files, all in scope. Confirmed no `drlibre-specs.md`, `pyproject.toml`
  or `uv.lock` change.
- Prove commit `2423d97`: test file only, strengthens assertions (`match=`, window check, body check).
- Probe of `make_fetch` against a raw socket server (not committed; run from `/tmp`, deleted): B1 confirmed.
- Not run: `make test`, `make lint`, `make gate` (the check stage already ran them; `check` succeeded at
  `4607d02`). `make smoke` against a live stack: the orchestrator's step.

## For the owner

Nothing in the diff changes the specification, and no decision is left open for it.

## Blocking

- B1 (`scripts/smoke.py:84`): catch `OSError` and `HTTPException` in `make_fetch`, so every transport failure names its step; add the red test for `BadStatusLine`. **Outcome: fixed**, `raises_smoke_failure_when_stack_answers_with_garbage`.
- B2 (`scripts/test_smoke.py`): add the promised loopback constants test (plan test 14). **Outcome: fixed**, `returns_loopback_urls_when_smoke_constants_are_read`.

## Later

- L1 plan drift: record `Journey`, `make_fetch` and the dropped `make_steps`/poll in the plan or an ADR.
- L2 send `clinician_id` from the slot listed; update `test_smoke.py:251-268`.
- L3 inbox poll dropped (sync mail makes it safe); note in plan; match the newest message by `to` if the sink is shared.
- L4 test the cookie round trip against a local server.
- L5 Makefile `smoke`: `uv run python scripts/smoke.py`.
- L6 rename `text` to `plaintext` at `scripts/smoke.py:181`.
- L7 redirects followed (plan risk, unchanged).
- L8 wrap `refusal.read()` at `scripts/smoke.py:83` in the same change as B1.
- L9 success message not printed (plan said it would be).

## Left for the orchestrator

- Run `make smoke` against a fresh `docker compose up --wait` and `seed_demo` stack. Facts the run could not
  check (from the plan): smtp4dev list route `/api/Messages?skip=0&take=1` returns `results` newest first;
  plaintext route `/api/Messages/<id>/plaintext` returns the text; a free slot within 14 days exists after
  `seed_demo`; the first provider's first appointment type is bookable online.
- The backlog's item 2 is done when the live run passes. The README line is in; item 1 (the README rewrite)
  is a separate run.
- The Makefile target was not run in the sandbox (no stack).
