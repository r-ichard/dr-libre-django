# Second-reader review: task 27c item 2, smoke steps, `main()`, `make smoke`, one README line

Reviewed: `git diff bbd76f9..HEAD` on `fabro/run/01M841HZ1QJ337VX3CHJZDW04J` (head `222c221`). The sandbox has no local `main`; `bbd76f9` is the base the run forked from (the tip of `task/27c-smoke`, the same history `main` carries here). Six files: `Makefile`, `README.md`, `doc/plans/2026-11-23-smoke-steps.md`, `doc/reviews/2026-11-23-smoke-steps.md`, `scripts/smoke.py` (227 lines), `scripts/test_smoke.py` (422 lines).

Verdict: `revise`. Two blockers: a transport error can still escape `run_steps` as a traceback with no step name (`scripts/smoke.py:84`), and the red tests do not cover the full run, the step names, or `main()`, all of which the plan and the task promise.

## Plan per block (§2.5), what was confirmed at a glance, what forced a trace

- Types and constants (`scripts/smoke.py:14-58`): one sentence each. Read at a glance. `Journey` holds what later steps read; `Fetch` and `Step` are the seams the tests use.
- `run_steps` (`scripts/smoke.py:61-68`): unchanged from base. Confirmed by diff; catches `SmokeFailure` only and names the step.
- `make_fetch` (`scripts/smoke.py:71-88`): traced line by line. The `OSError, HTTPException` guard covers the open and the 200 body read; the 4xx body read at line 84 is outside it. That is the defect under Blocking.
- Answer helpers (`scripts/smoke.py:91-118`): one sentence each; each raises `SmokeFailure` with a step label. `json.loads` lands in an `object` variable, so no `Any` escapes.
- Steps 1 to 6 (`scripts/smoke.py:121-209`): traced against the stack. Routes, bodies and fields checked: health `status: ok` (`scheduling/views/health.py:12`); start-page link (`PROVIDER_LINK`, line 25); hold body, `clinician_id` optional (`scheduling/views/hold_schemas.py:33-41`); verify 201 with the appointment body (`scheduling/views/booking.py:66`); cancel status `CANCELLED` (`scheduling/domain/vocabulary.py:11`); list `results` (`scheduling/views/appointments.py:40`). API auth is a cookie with no CSRF check (`scheduling/views/api_view.py:23`, `authentication.py:13-21`), so a cookie POST with no `Origin` passes `refuse_foreign_origin` (`api_view.py:56-64`). Traced: the inbox read is safe without a poll, because the hold sends the code mail synchronously before its 201 (`scheduling/use_cases/booking_holds.py:81` calls `issue_code`, `scheduling/use_cases/booking_codes.py:51-66` calls `message.send()` in the request).
- `main` (`scripts/smoke.py:212-223`): one sentence: builds the six steps inline and runs them. Not tested (see Blocking 2).
- Makefile `smoke` and README line: read at a glance; see Later.

## Findings

### Blocking

1. **`scripts/smoke.py:83-84`, important.** The `except HTTPError` handler calls `refusal.read()`. An exception raised inside an `except` handler is not caught by a sibling `except` clause, so the guard at line 85 does not cover it. A 4xx or 5xx answer whose body read fails (`http.client.IncompleteRead`, `ConnectionResetError`) escapes `fetch` as a traceback with no step name. The plan promised the opposite ("no step ever sees a transport exception", plan line 122), and the backlog requires failures to name the step.
   - Risk: a broken stack that answers 4xx/5xx and drops the connection mid-body fails `make smoke` with a traceback and no `Smoke step failed: <name>` line.
   - Smallest fix: nest the open and both reads under the guard:
     ```python
     try:
         try:
             with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as answer:
                 return Reply(answer.status, answer.read().decode(errors="replace"))
         except HTTPError as refusal:
             return Reply(refusal.code, refusal.read().decode(errors="replace"))
     except (OSError, HTTPException) as failure:
         raise SmokeFailure(f"no answer from {url}: {failure}") from None
     ```
   - Red test: `raises_smoke_failure_when_refusal_body_cannot_be_read` in `scripts/test_smoke.py`. Monkeypatch `scripts.smoke.build_opener` with an opener whose `open` raises `HTTPError(url, 500, "x", {}, fp)`, where `fp.read` raises `IncompleteRead(b"")`. Expect `SmokeFailure` matching `no answer from`.
   - Outcome: fixed. The open and both reads sit under the `OSError, HTTPException` guard (`scripts/smoke.py:80-87`); `raises_smoke_failure_when_refusal_body_cannot_be_read` was seen red (`IncompleteRead` escaped), then green.

2. **`scripts/test_smoke.py` (whole file) and `scripts/smoke.py:212-223`, important.** The promised red tests are not all here, and the task's own requirement, "fails with the step's name when the answer is wrong", is not tested for any step.
   - Plan test 1, `returns_zero_when_every_step_answers_as_the_stack_does` (plan line 89), is absent. No test runs the six steps in order against a fake that answers as the stack does. The plan's fake (plan lines 79-85) was never written; `FakeStack` answers per test, so no test sees the full run.
   - No test asserts the step name. `run_steps` is tested with dummy steps only (`scripts/test_smoke.py:116-163`). The per-step tests (lines 166-422) assert the `SmokeFailure` reason text, not `Smoke step failed: <name>:`.
   - Plan test 6, slots body not JSON (plan line 95), is absent. The only non-JSON test is for health (`scripts/test_smoke.py:188-192`).
   - `main()` and the step list are untested: the names live inside `main()` (`scripts/smoke.py:216-221`), so nothing checks them.
   - Smallest fix: move the six-pair list out of `main` into `make_steps(fetch: Fetch) -> list[Step]`, which builds `Journey(fetch=fetch)` and returns the pairs in order. Then `main` is `return run_steps(make_steps(make_fetch()))`. Add:
     - `returns_zero_when_every_step_answers_as_the_stack_does`: one `FakeStack` with keys for all ten endpoints, run through `run_steps(make_steps(stack))`. Order the keys so that `("POST", "/verify")` and `("POST", "/cancel")` come before `("POST", "/api/v1/booking/holds")` and `("GET", "/api/v1/appointments")`: `FakeStack` takes the first fragment that matches, and the verify, cancel and appointment URLs also contain the broader fragments.
     - A parametrized test over the six step names: replace one answer with a wrong one, assert `capsys` stderr starts with `Smoke step failed: <name>: `.
     - `raises_smoke_failure_when_slot_listing_is_not_json`: slots answers `<html>` with 200; expect `SmokeFailure` matching `slots body is not JSON`.
   - Outcome: fixed. `make_steps(fetch)` extracted; `main()` is now `return run_steps(make_steps(make_fetch()))`. Tests: `returns_zero_and_prints_nothing_when_every_step_answers_as_the_stack_does`; `returns_one_naming_the_step_when_its_answer_is_wrong` (six cases, one per step, asserting the `Smoke step failed: <name>: ` prefix); `raises_smoke_failure_when_slot_listing_is_not_json`. Seen red first on the missing `make_steps` import. `main()`'s own line is not run by a test: the only path to it goes through the network in `make_fetch`.

### Later

- **L1, plan drift, nit.** The code departs from the approved plan in ways the plan does not record: `Journey` instead of the state dict; no `make_steps(fetch, pause)`; the inbox is read once, no bounded poll (plan lines 32-36; safe per the synchronous send above); `Reply` has no `headers`; cookies come from `CookieJar` (`scripts/smoke.py:73`) instead of an explicit `Cookie` header; the hold omits `clinician_id` (`scripts/smoke.py:162-169`, optional per `hold_schemas.py:35`); no success line on stdout (plan line 59); step names are short (`health`, `hold`, `code`) not the plan's names (plan lines 46-48). Fix: record these in the plan or an ADR so the next reader does not reconstruct the design.
- **L2, Makefile:45-46, important for reproducibility, not a blocker.** `python3 scripts/smoke.py` runs the host interpreter (3.11.2 on this sandbox). The project pins 3.13 (`.python-version`) and the plan said `uv run python scripts/smoke.py`. The code runs on 3.11, but "pin everything" (§9) is not met. Fix: `uv run python scripts/smoke.py`.
- **L3, README line, nit.** "after a deploy" is misleading: the smoke talks only to `127.0.0.1`, so it checks only a stack on this machine. Reword to "after the local stack is up and seeded" or drop the clause.
- **L4, cookie path (`scripts/smoke.py:73`), nit.** `cookie_secure()` makes the session cookie `Secure` whenever `DEBUG` is off or `HTTPS_ONLY` is on (`scheduling/views/session_cookie.py:15-18`). `CookieJar` then drops it over `http://127.0.0.1`, and `confirm` fails with "the new patient's appointment is not listed", which hides the cause. Fine while `DEBUG` is on, which `seed_demo` needs. Note it in the plan or the README.
- **L5, mail route and ordering, unverified.** `/api/Messages?skip=0&take=1`, `results`, `id`, `/plaintext` (`scripts/smoke.py:176-182`) and newest-first ordering are assumptions about smtp4dev 3.16.1. The plan lists them as unverified (plan lines 155-157). The fresh-stack run is the check.
- **L6, naming, nit.** `text` at `scripts/smoke.py:182` holds a `Reply`; `plaintext` states the role. `found` at lines 130 and 184 is a regex match; `match` or the captured name reads better.
- **L7, redirects followed.** `urllib` follows 3xx (plan risk, unchanged). A wrong 302 that ends in 200 passes a step.
- **L8, test weakness, nit.** `returns_loopback_urls_when_smoke_constants_are_read` (`scripts/test_smoke.py:224-226`) checks a prefix only. Accepted by the architect; it guards nothing beyond the constant's spelling.
- **L9, size, nit.** `scripts/test_smoke.py` is 422 lines; §5 says files under 300. The gate cap is 500 and passes, so this is not a blocker.
- **L10, uncaught non-`SmokeFailure`.** A programming error in a step still tracebacks. The test at `scripts/test_smoke.py:153-163` pins this on purpose, which is right.

## Checks run

- Diff scope: six files, all expected. `drlibre-specs.md`, `doc/backlog*`, `doc/handover.md`, `pyproject.toml`, `uv.lock`, product code under `scheduling/` and `drlibre/`: untouched. No dependency added. The README change is one line.
- Proof trace (§13): commits after `verify_green` (`7101144`) up to `prove` (`2423d97`): `7101144` and `57b9ed0` (refactor) carry no file change; `2423d97` changes `scripts/test_smoke.py` only. No product line moved after the gate. The `address` commit (`621e1b7`) changed `scripts/smoke.py`, which is the address stage's job, after review.
- Not run here: this stage reads the diff and does not run tests. The `check` stage on `222c221` reported `make lint`, `make test` (5307 passed) and `make gate` clean.
- Not run: `make smoke` (needs a live stack; the orchestrator runs it).

## For the owner

None. The diff changes no `drlibre-specs.md` text and leaves no product decision open.

## Blocking

- `scripts/smoke.py:84`: `refusal.read()` sits outside the transport guard, so a failing error-body read escapes as a traceback with no step name. Nest the open and both reads under `except (OSError, HTTPException)`; add `raises_smoke_failure_when_refusal_body_cannot_be_read`. Outcome: fixed, see finding 1 above.
- `scripts/test_smoke.py` and `scripts/smoke.py:212-223`: plan test 1 (full run returns zero against a stack-like fake) is absent; no test asserts the step name for any step; plan test 6 (slots body not JSON) is absent; `main()` is untested. Extract `make_steps(fetch)` from `main`; add the full-run test, the parametrized step-name test and the slots-not-JSON test. Outcome: fixed, see finding 2 above; the plan's test 1 is now `returns_zero_and_prints_nothing_when_every_step_answers_as_the_stack_does`.

## Later

- L1 plan drift: record `Journey`, the dropped `make_steps`/poll, `CookieJar`, the omitted `clinician_id`, the missing success line and the step names in the plan or an ADR.
- L2 `Makefile:45-46`: `uv run python scripts/smoke.py`, as the plan says, so the interpreter is pinned to 3.13.
- L3 README: drop "after a deploy" or reword; the smoke checks only `127.0.0.1`.
- L4 `Secure` session cookie outside `DEBUG`: the smoke fails with a misleading message. Document "DEBUG on only" or name the cause.
- L5 smtp4dev 3.16.1 routes, `results`/`id`/`plaintext` and newest-first order: verify on the fresh stack.
- L6 rename `text` to `plaintext` (`scripts/smoke.py:182`); name the regex matches.
- L7 redirects followed (plan risk, unchanged).
- L8 loopback test checks a prefix only (`scripts/test_smoke.py:224-226`); accepted.
- L9 `scripts/test_smoke.py` is 422 lines, over the 300 guideline in §5; under the 500 gate.

## Left for the orchestrator

- Run `make smoke` against a fresh `docker compose up --wait` and `seed_demo` stack. The steps that depend on the live stack (L4, L5, the start page listing a provider, a free slot in the next 14 days) are checked only there.
- Backlog 27c item 2 is done when that live run passes; item 1 (the README rewrite) is a separate run and is not in this diff.
- The plan's "Unverified facts" list (plan lines 153-162) stays open until the live run.
- `make mutate`, `make fhir-validate`, and `make setup && make lint && make test && make gate` from a fresh clone: not run in this stage.
