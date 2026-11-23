# Second-reader re-review: task 27c item 2, smoke steps, `main()`, `make smoke`, one README line

Reviewed: the run's diff against its base `bbd76f9` (the sandbox has no local `main`; `bbd76f9` is the tip of `task/27c-smoke`, the commit the run forked from). Head `553e35a`. Files: `scripts/smoke.py` (230 lines), `scripts/test_smoke.py` (500 lines), `Makefile`, `README.md`, `doc/plans/2026-11-23-smoke-steps.md`, and the two earlier review documents of this run. No product code, no `drlibre-specs.md`, no dependency change.

Verdict: `revise`. One blocker: the smoke picks the earliest free slot from now, and that slot is refused by the hold or the cancel rule, so the flow fails on a fresh stack by construction. The earlier blockers (transport errors, missing red tests) are fixed in the current code.

## Plan per block (§2.5)

- Types and constants (`scripts/smoke.py:13-53`): one sentence each; read at a glance. No `Any`, no `cast`, no bare `# type: ignore`. The two `noqa` lines name a code (`S310`, `N818`).
- `run_steps` (`scripts/smoke.py:56-67`): unchanged from base. Catches `SmokeFailure` only and prints the step name. Confirmed by diff.
- `make_fetch` (`scripts/smoke.py:71-89`): traced. The open and both reads sit under `except (OSError, HTTPException)`, so transport and body-read errors become `SmokeFailure`. `HTTPError` is caught first, so a refusal still returns its status. Confirmed by trace; the happy path is not tested (Later).
- Answer helpers (`scripts/smoke.py:90-118`): one sentence each; each raises `SmokeFailure` with a step label; JSON lands in an `object` variable first.
- `health_step` (`:122`), `start_page_step` (`:128`): one sentence each; routes and keys match the stack (`drlibre/urls.py:92`, `scheduling/views/health.py`, `scheduling/views/pages`, `/providers/` link from `detail_context.py:25`).
- `_first_free_start` (`:141-152`): traced, because it decides the slot the hold and the cancel use. Its `from` is `now` (`:145`). That is the blocker below.
- `hold_step` (`:155`), `code_step` (`:176`), `confirm_step`, `cancel_step`: one sentence each. Routes and fields match the stack: `api/v1/booking/holds` (`drlibre/urls.py:104`), `holds/<id>/verify` (`:106`, body `code`, 201 with the appointment body, `scheduling/views/booking.py:66`), `appointments` list with `results` (`scheduling/views/appointments.py:40`), `appointments/<id>/cancel` (`drlibre/urls.py:108`, status `CANCELLED`, `scheduling/domain/vocabulary.py:11`). Booking-code wording matches `scheduling/domain/email_content.py:45`.
- `make_steps` (`:213-223`) and `main` (`:225-226`): one sentence each. `main` is `return run_steps(make_steps(make_fetch()))`.
- Makefile `smoke` (`Makefile:47-48`) and the README line (`README.md:7`): read at a glance; see Later.

## Findings

### Blocking

**B1. The slot search starts at now, so the flow fails on a fresh stack.** `scripts/smoke.py:145`, with `:141-152` and the hold at `:155`. The window's `from` is `now`, so the smoke books the earliest free slot. Two rules in `scheduling/domain/booking_rules.py` refuse that slot:
- The hold is a patient booking (an anonymous visitor's `actor_role` is `Role.PATIENT`, `scheduling/use_cases/placement.py:150`). A start less than `LEAD_TIME`, 120 minutes away, is refused as `lead_time_too_short` (`booking_rules.py:11`, `:61`, `:96`; `drlibre-specs.md:201`).
- The cancel is a patient action. A start less than `CANCELLATION_WINDOW`, 24 hours away, is refused as `cancellation_window_closed` (`booking_rules.py:12`, `:63-64`, `:102`; `drlibre-specs.md:202`, `:242`).

So `make smoke` fails at `hold` when the earliest free slot is under two hours away, and at `cancel` when it is under 24 hours away. A seeded schedule has availability starting soon after now, so the slot is often inside 24 hours. The unit tests cannot see this: `FakeStack` answers any slot, and the test at `scripts/test_smoke.py:312-321` checks only the window length, not where it starts.
- Risk: the backlog's "the patient cancels it" step fails on most runs, and the orchestrator's live run cannot pass. The plan's unverified-facts list missed it.
- Smallest fix: start the window at `now + 24 h`. Add a named constant with a why-comment, for example `SLOT_NOTICE = timedelta(hours=24)  # the patient's cancel window, booking_rules.py:12`, because the smoke is standard-library only and cannot import `scheduling`. Then `"from": _instant(now + SLOT_NOTICE)` and `"to": _instant(now + SLOT_NOTICE + timedelta(days=SEARCH_DAYS))`. Keep `SEARCH_DAYS` inside 31 days.
- Red test: in `scripts/test_smoke.py`, extend `returns_utc_search_window_of_search_days_when_holding` (`:312`). Capture `before = datetime.now(UTC)` before `hold_step`, then assert the parsed `from` is at least `before + timedelta(hours=24)`. Against the current code `from` equals `now`, so the assertion fails first. Mind the naive `strptime` result: compare with `before.replace(tzinfo=None)`.

### Later

**L1. Makefile interpreter, `Makefile:48`.** `python3 scripts/smoke.py` runs the host interpreter. Here it is Python 3.11.2; the project pins 3.13 and every other target uses `uv run`. `smoke.py:6` imports `datetime.UTC`, which needs 3.11 or later. The plan said `uv run python scripts/smoke.py`. Fix: use that. Not a blocker class; §9 "pin everything" applies.

**L2. README line, `README.md:7`.** "or after a deploy" misleads: the smoke talks only to 127.0.0.1, so it checks a local stack. Also state the requirement that `DEBUG` is on. With `DEBUG` off, `cookie_secure()` makes the session cookie `Secure` (`scheduling/views/session_cookie.py:15-18`), `CookieJar` drops it over `http://127.0.0.1`, and `confirm` fails with "not listed", which hides the cause. Reword and name `DEBUG`.

**L3. Cookie round trip is untested, `scripts/smoke.py:73`.** The plan asked for an explicit `Cookie: drlibre_session=` header; the code uses `CookieJar`. No test checks that the cookie from verify is sent on the appointments request. Only the live run does. Add a test against a local `http.server` if the live run does not settle it.

**L4. Weak assertion, `scripts/test_smoke.py:214`.** `assert "Traceback" not in str(failure.value)` is always true; `pytest.raises(SmokeFailure)` already proves no other exception escaped. Replace it with `match="no answer from"`.

**L5. Name, `scripts/smoke.py:183`.** `text` holds a `Reply`, so `plaintext` states the role (§3). Also `found` (`:185`, `:132`) is a regex match; `match` reads better. Nits.

**L6. Stale comment, `scripts/smoke.py:53`.** "main() binds the journey into each one" is wrong: `make_steps` does. Fix the words.

**L7. The real fetch's success path is untested, `scripts/smoke.py:82-83`.** Tests cover refusal, garbage and a body that cannot be read, not a 200 reply that reads back. A mistake there shows only in the live run.

**L8. Fragile fake, `scripts/test_smoke.py:448-458`.** The start-page row's fragment `http://127.0.0.1:8000/` matches any GET under `BASE_URL`, so the row order in `_stack_of` decides which answer a GET gets. Works today; a new GET under `BASE_URL` would be answered with the start page.

**L9. Silent filter, `scripts/smoke.py:108-111`.** `_objects_under` drops non-object items without a word. Malformed data then reads as "no slots" or "not listed". Acceptable; note it.

**L10. Plan drift.** The plan describes `Reply(status, headers, body)`, `NO_ANSWER`, `make_steps(fetch, pause)`, `_send`, `_fetch_urllib`, a bounded inbox poll, `Smoke passed: N steps` on stdout, and the step names `health answers` and so on. The code has `Reply(status, body)`, `Journey`, `make_fetch`, no poll, no success line, and short step names. The code is smaller and the poll is safe because the hold sends the code mail synchronously. Record the change in the plan or an ADR so the next reader does not chase `make_steps(fetch, pause)`.

**L11. Smoke does not check the recipient, `scripts/smoke.py:176-183`.** `code_step` reads the newest message whatever its `to`. Fine on a fresh stack; check `to` if the sink is ever shared.

**L12. Redirects are followed, `scripts/smoke.py:71-89`.** A wrong 302 that ends in 200 passes a step (plan risk, unchanged).

**L13. Size.** `scripts/test_smoke.py` is 500 lines, exactly the gate cap (`make gate` passes; §5 says under 300). `scripts/smoke.py` is 230. Not a blocker. If the test file grows, split it by step.

**L14. Handover.** `doc/handover.md` does not mention `make smoke`. CLAUDE.md asks that the state doc be kept current in the commit that changes the state. Add one line in the commit that lands this work, or say why not.

**L15. Hold omits `clinician_id`, `scripts/smoke.py:156-174`.** The server assigns one round-robin. Harmless for the smoke; noted so the plan drift in L10 covers it.

## Proof trace (§13)

- `7101144` verify_green: no file change.
- `2423d97` prove: `scripts/test_smoke.py` only (92 insertions, 19 deletions). No product or migration line.
- `57b9ed0` refactor: empty.
- `621e1b7`, `189c8c9` address: changed `scripts/smoke.py` and `scripts/test_smoke.py`. Those are fixes to review findings, after review and before `check`, which is the address stage's job.
- Product code and migrations: no change in the run.

## Checks run

- `git diff bbd76f9 HEAD --stat`: seven files, all expected. No `drlibre-specs.md`, `pyproject.toml`, `uv.lock` or product code change.
- `uv run --env-file .env.example pytest -q -p no:cacheprovider scripts/test_smoke.py`: 40 passed in 0.09 s. Run here, on this sandbox.
- Routes, body keys and status codes of the stack checked by reading `drlibre/urls.py`, `scheduling/views/booking.py`, `appointments.py`, `booking_schemas.py`, `detail_schemas.py`, `email_content.py`, and the rules in `booking_rules.py` and `placement.py`.
- I started `make test` to run the full suite and stopped it after two minutes; the full suite is not measured here. The `check` stage on `553e35a` reports `make lint`, `make test` (5316 passed) and `make gate` clean.
- Not run: `make smoke` against a live stack (the orchestrator's step); `make mutate`; `make fhir-validate`.

## For the owner

Nothing in the diff changes `drlibre-specs.md`. The smoke's slot window is a test-tool choice (24 hours of notice, so the cancel can pass), not a product decision. No open decision for the owner.

## Blocking

- `scripts/smoke.py:145` (`_first_free_start` window starts at now): a hold under 120 minutes and a patient cancel under 24 hours are refused (`booking_rules.py:61`, `:63-64`, `:102`), so `make smoke` fails on a fresh stack. Start the window at now + 24 h via a named constant, and add the red assertion to `returns_utc_search_window_of_search_days_when_holding` (`scripts/test_smoke.py:312`).

## Later

- L1 `Makefile:48`: `uv run python scripts/smoke.py`, as the plan says.
- L2 `README.md:7`: drop "after a deploy"; say `DEBUG` must be on.
- L3 cookie round trip untested (`scripts/smoke.py:73`).
- L4 `scripts/test_smoke.py:214`: replace the always-true `Traceback` check with `match=`.
- L5 `scripts/smoke.py:183`: rename `text` to `plaintext`.
- L6 `scripts/smoke.py:53`: the comment names `main()`; it is `make_steps`.
- L7 success path of `make_fetch` untested.
- L8 `_stack_of` row order decides answers (`scripts/test_smoke.py:448-458`).
- L9 `_objects_under` drops non-object items silently.
- L10 plan drift: record `Journey`, no poll, no success line, step names, `Cookie` via `CookieJar`.
- L11 recipient of the newest mail not checked (`scripts/smoke.py:176-183`).
- L12 redirects followed.
- L13 `scripts/test_smoke.py` at 500 lines, §5 says under 300.
- L14 `doc/handover.md` should mention `make smoke`.
- L15 `clinician_id` not sent in the hold.

## Left for the orchestrator

- After the B1 fix, run `make smoke` against a fresh `docker compose up --wait` and `seed_demo` stack. The checks this review could not make: smtp4dev routes `/api/Messages?skip=0&take=1` and `/api/Messages/<id>/plaintext` return `results` with `id` and the text; newest first; a free slot starts at least 24 hours out within 14 days after the window start; the first provider's first appointment type is bookable online; the hold's per-visitor rate limit does not trip on repeated runs.
- Backlog 27c item 2 is done when that live run passes. The README rewrite is item 1, a separate run.
- Run `make setup && make lint && make test && make gate && make mutate` and `make fhir-validate` from a fresh clone. Not run here.
