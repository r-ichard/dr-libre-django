# Task 27c item 2: smoke steps, main(), `make smoke`, one README line

Slice: items 1 to 6 of the smoke test (the six steps, main, make target, README line). Nothing else.

Focal point: `scripts/smoke.py`. Six step functions take `(fetch, state)`; `make_steps` binds them
into `(name, callable)` pairs in order; `run_steps` (already there, unchanged) runs them and names
the first failing step. Steps raise `SmokeFailure(reason)` without the step name: `run_steps` adds it.

## Blocks and their one-sentence plans

- Types, `scripts/smoke.py`: `Reply(NamedTuple)` with `status: int`, `headers: dict[str, str]`
  (lower-case names), `body: bytes`; `Fetch = Callable[[str, str, Mapping[str, str], bytes | None], Reply]`
  (method, absolute URL, headers, body). `NO_ANSWER = 0` is the status of a reply that never came.
- Constants: `BASE_URL = "http://127.0.0.1:8000"`, `MAIL_URL = "http://127.0.0.1:8025"`,
  `TIMEOUT_SECONDS = 10`, `INBOX_ATTEMPTS = 10`, `INBOX_PAUSE_SECONDS = 1.0`,
  `SESSION_COOKIE = "drlibre_session"`, `CODE_PATTERN = re.compile(r"booking code is (\d{6})")`.
- Answer helpers (each under 15 lines): `_expect(reply, status)` raises `SmokeFailure("answered N")`,
  or `"no answer"` when status is `NO_ANSWER`; `_json(reply) -> dict[str, object]` decodes with
  `json.loads` into `object` and narrows with `isinstance(dict)`, raising `SmokeFailure("body is not JSON")`
  on `ValueError` or a non-object; `_field(body, key)` raises `SmokeFailure("body has no <key>")`.
  No `Any`, no `cast`: `json.loads` returns `Any`, so the result is assigned to an `object` variable.
- Step 1 `check_health(fetch)`: GET `BASE_URL/api/v1/health`, `_expect` 200.
- Step 2 `check_start_page(fetch, state)`: GET `BASE_URL/` is 200; regex `/providers/([0-9a-f-]{36})`
  on the HTML gives `state["provider_id"]` (no match: "no provider link"). GET
  `BASE_URL/api/v1/providers/<id>` is 200; `appointment_types[0].id` goes to `state["appointment_type_id"]`.
- Step 3 `hold_free_slot(fetch, state)`: GET `BASE_URL/api/v1/slots?appointment_type_id=..&from=<now UTC>&to=<now+28 days UTC>`
  (`urllib.parse.urlencode`, ISO with `Z`) is 200; the first of `slots` (none: "no free slot") gives
  `starts_at` and `clinician_ids[0]`. POST `BASE_URL/api/v1/booking/holds` with JSON
  `{appointment_type_id, clinician_id, starts_at, full_name: "Smoke Test", date_of_birth: "1980-01-01",
  email, terms_accepted: true}` is 201; `id` goes to `state["hold_id"]`. `email` is
  `smoke-<uuid4 hex>@example.test`, kept in `state["email"]`.
- Step 4 `read_booking_code(fetch, pause, state)`: up to `INBOX_ATTEMPTS` times: GET `MAIL_URL/api/messages`
  is 200; if `results` is non-empty, its first item's `id` is used for GET
  `MAIL_URL/api/messages/<id>/plaintext` (200); `CODE_PATTERN` on the text gives the code, stored in
  `state["code"]`, and the step returns. Otherwise `pause(INBOX_PAUSE_SECONDS)`. After the last attempt:
  `SmokeFailure("no booking code mail")`. The pause is a parameter so tests pass a no-op.
- Step 5 `confirm_and_list(fetch, state)`: POST `BASE_URL/api/v1/booking/holds/<hold>/verify` with
  `{"code": code}` is 201; the `set-cookie` header must start with `drlibre_session=`, its value (up to
  `;`) goes to `state["session"]`; body `id` goes to `state["appointment_id"]`. GET
  `BASE_URL/api/v1/appointments` with `Cookie: drlibre_session=<session>` is 200, and `results` holds an
  item with that `id` and `status` `BOOKED`.
- Step 6 `cancel_appointment(fetch, state)`: POST `BASE_URL/api/v1/appointments/<id>/cancel` with the
  cookie and `{"reason": "Smoke test"}` is 200; body `status` is `CANCELLED`.
- `make_steps(fetch: Fetch, pause: Callable[[float], None] = time.sleep) -> list[Step]`: creates
  `state: dict[str, str] = {}` and returns the six pairs in order, each a lambda over `fetch`, `state`
  and, for step 4, `pause`. Names: `health answers`, `start page finds a demo provider`,
  `visitor holds a free slot`, `code read from the inbox`, `code confirmed and appointment listed`,
  `patient cancels the appointment`.
- `_send(fetch, method, url, payload=None, session="") -> Reply`: JSON-encodes `payload` when given,
  sets `Content-Type: application/json` and `Cookie` when `session` is set. Sends no `Origin`: a non-browser
  client, which the cross-site check allows (`refuse_foreign_origin` refuses only a present foreign Origin).
- `_fetch_urllib` (the real `Fetch`): `urllib.request.Request` plus `urlopen(request, timeout=TIMEOUT_SECONDS)`.
  `HTTPError` becomes `Reply(error.code, ...)`. `OSError` and `http.client.HTTPException` (refused, reset,
  timeout, bad status line) become `Reply(NO_ANSWER, {}, b"")`, so no step ever sees a transport exception.
  Header names lower-cased. Redirects are not blocked: a redirect that ends in 200 passes (risk, see below).
  The one `urlopen` call gets `# noqa: S310 - constant loopback URL` only if ruff reports S310; the
  implementer checks `pyproject.toml` `select` first (not read in this planning pass).
- `main() -> int`: `steps = make_steps(_fetch_urllib)`; `exit_code = run_steps(steps)`; on 0 prints
  `Smoke passed: {len(steps)} steps` to stdout; returns the code. `if __name__ == "__main__": sys.exit(main())`.
- `Makefile`: add `smoke` to `.PHONY`; target `smoke:` runs `uv run python scripts/smoke.py`. Not referenced by
  `test`, `lint`, `gate`.
- `README.md`: one line after the `make audit` paragraph: run `make smoke` against a stack just started with
  `docker compose up --wait` and seeded with `seed_demo`; needs Docker; not part of `make test`.

## Files to touch, in order

1. `scripts/test_smoke.py`: red tests first (below). The four existing tests stay unchanged.
2. `scripts/smoke.py`: types, constants, helpers, six steps, `make_steps`, `_send`, `_fetch_urllib`, `main`.
   Under 300 lines; each function under 50.
3. `Makefile`: `smoke` target and `.PHONY`.
4. `README.md`: one line.

Not touched: the existing four tests, `run_steps`, `drlibre-specs.md`, `doc/backlog/*`, `doc/handover.md`,
`doc/backlog.md`, product code under `scheduling/` and `drlibre/`, `compose.yaml`, `pyproject.toml`, `uv.lock`,
`.github`, the `qa` workflow.

## Red tests (`scripts/test_smoke.py`)

Fake: `_stack_fetch(replaced: Mapping[tuple[str, str], Reply] = {})` returns a `Fetch`. It answers
`(method, path)` from a static table that matches the real stack: health 200; start page HTML with
`href="/providers/<uuid>"`; provider detail with one appointment type; slots with one slot and one
clinician; hold 201 with `id`; inbox list `{"results": [{"id": "m1"}]}`; plaintext
`Your DrLibre booking code is 123456.`; verify 201 with `set-cookie: drlibre_session=abc; Path=/` and an
appointment body (`id`, `status` `BOOKED`); appointments list holding that id; cancel 200 with status
`CANCELLED`. `replaced` overrides one answer. Unknown paths answer 404. Each test runs
`run_steps(make_steps(fake, pause=lambda seconds: None))` and asserts that stderr is one line starting with
`Smoke step failed: <step name>: `. Exact reason wording is not pinned.

1. `returns_zero_when_every_step_answers_as_the_stack_does`
2. `returns_health_step_name_when_health_answers_503`
3. `returns_health_step_name_when_stack_refuses_connection` (fake answers `NO_ANSWER`)
4. `returns_no_answer_status_when_connection_is_refused` (monkeypatch `urllib.request.urlopen` to raise
   `URLError`; `_fetch_urllib("GET", ...)` returns status `NO_ANSWER`)
5. `returns_start_page_step_name_when_start_page_lists_no_provider`
6. `returns_slots_step_name_when_body_is_not_json` (slots answers `<html>` with 200)
7. `returns_hold_step_name_when_no_slot_is_free` (slots `slots: []`)
8. `returns_hold_step_name_when_hold_answers_409`
9. `returns_inbox_step_name_when_no_booking_code_message_exists` (inbox `results: []` on every attempt)
10. `returns_verify_step_name_when_verify_answers_400` (wrong code)
11. `returns_verify_step_name_when_appointment_is_not_listed_for_the_patient` (list `results: []`)
12. `returns_cancel_step_name_when_cancel_answers_409`
13. `returns_cancel_step_name_when_status_is_not_CANCELLED`
14. `returns_loopback_urls_when_smoke_constants_are_read` (`BASE_URL` and `MAIL_URL` start with `http://127.0.0.1:`)

Each red test must fail first: before `make_steps` exists the import fails; after a stub the name assertion
fails. "Red for right reason" is judged by the reviewer.

## Invariants and blast radius

- Writes are the documented ones only: one hold, one verify (creates the appointment), one cancel. Nothing is
  seeded or deleted. Blast radius: one demo slot is held, then cancelled, on whatever stack `make smoke`
  points at. The run never starts the stack.
- No double booking from this client: it books only a slot the search reported free. A race gives 409 and
  the step fails, naming `visitor holds a free slot`.
- Authorization is the server's: the patient's rights come from the session cookie that verify issued, never
  from a client-sent field. Cross-site check untouched.
- Audit log stays append-only; the smoke only causes ordinary audit rows through the API.

## Trust boundaries crossed

- Stack responses are untrusted text: status checked, JSON decoded and shape checked, every failure a
  `SmokeFailure` that names the step. Transport and decode errors do not escape `run_steps`.
- Mail inbox responses: same treatment. The code matches six digits and is never printed or logged; it goes
  only into the verify body.
- Session cookie: held in process memory, sent only to `127.0.0.1:8000`, never printed.
- Client to stack: no credentials; the address is `example.test`.

## Domain entities (CLAUDE.md §3 vocabulary)

Visitor (hold, verify), Patient (the new patient who owns the appointment), BookingHold, VerificationCode (the
code read from the inbox), Appointment (BOOKED, then CANCELLED), Notification (the email), Clinician (the slot's
clinician), AppointmentType and Department/Hospital via the provider body only.

## What I will not do

- No new dependency, no `httpx`, no `requests`: `urllib.request`, `json`, `re`, `time`, `uuid`, `datetime`.
- No retry beyond the one bounded inbox poll; no config file; no CLI flags; no state file.
- No import from `scheduling/`; no mock of the product beyond the fake in the tests.
- No change to `run_steps` or its four tests; no README rewrite; no backlog or handover edit.

## Checked against code (this pass)

Routes in `drlibre/urls.py`: `api/v1/health`, `api/v1/slots`, `api/v1/providers/<uuid>`,
`api/v1/booking/holds`, `.../verify`, `api/v1/appointments`, `.../cancel`. Cookie `drlibre_session`
(`scheduling/views/session_cookie.py`). Hold body `id`; verify 201 with the appointment body and a
`Set-Cookie` (`scheduling/views/booking.py`). Slots body `slots[].clinician_ids` (`booking_schemas.py`). List body
`results` (`appointments.py`). Cancel 200 with the appointment body (`appointment_actions.py`). Provider detail
`appointment_types[].id` (`detail_schemas.py`). Email text `Your DrLibre booking code is <code>.`
(`scheduling/domain/email_content.py`). Start page list default `providers` (`search_page.py`,
`LIST_KINDS`); provider link `/providers/<id>` in `search/provider_result.html`. `refuse_foreign_origin`
(`api_view.py`) allows a request with no `Origin`.

## Unverified facts the orchestrator must check on the fresh stack

- smtp4dev 3.16.1 (`compose.yaml`): the list response is an object with `results`, each item with `id`, and
  `GET /api/messages/{id}/plaintext` returns the text. Not confirmed here (no network, no container). If it is
  wrong, `make smoke` fails at `code read from the inbox`; the fix is one line.
- The start page with an empty query lists at least one provider link. If not, step 2 fails naming its name.
- A free slot exists in the next 28 days after `seed_demo`; and the first provider's first appointment type is
  bookable online. Otherwise step 3 fails naming `visitor holds a free slot`.
- The code mail arrives within `INBOX_ATTEMPTS * INBOX_PAUSE_SECONDS` (10 s). A bounded poll, not a race-free wait.
- Rate limits on read and write endpoints do not trip on one run against a fresh stack.

## Risks

- urllib follows redirects, so a wrong 302 that ends in a 200 passes a step.
- Newest-message-first ordering of the inbox list is assumed, not checked; a fresh stack makes it safe.

## Architect reasons addressed (verdict `revise`, 2026-11-23)

1. Transport and decode errors: `_fetch_urllib` maps `OSError` and `HTTPException` to `NO_ANSWER`, `timeout=`
   set; `_json` turns decode failures into `SmokeFailure`. See blocks above; tests 3, 4, 6.
2. Red tests for those paths: tests 3, 4 and 6 (refused connection, refused mapping, non-JSON body).
3. Signature: `make_steps(fetch, pause: Callable[[float], None] = time.sleep)`; `INBOX_ATTEMPTS` and
   `INBOX_PAUSE_SECONDS` are named constants.
4. Test 11 renamed to `returns_loopback_urls_when_smoke_constants_are_read` (test 14 above).

## Done when (for this run)

`make lint`, `make test` (the smoke tests run there; `make smoke` does not), `make gate` pass; the fourteen new
red tests are proven red first and green after; the orchestrator runs `make smoke` against a fresh stack.

## Architect review

Verdict: `approve`. The four reasons of the previous `revise` are met in the plan and the test list.

- Ladder and scope: items 1 to 6 of backlog 27c item 2, nothing more. No new dependency, no abstraction with one
  caller, no change to `run_steps`. Product code and the README rewrite stay out.
- Routes and fields checked against code this pass: slots query `from`, `to`, `appointment_type_id`, `clinician_id`
  (tests in `scheduling/views/test_slots_follow_rules.py`); hold body `full_name`, `date_of_birth`, `email`,
  `terms_accepted` (`hold_schemas.py`); verify body `code` (`hold_schemas.py`); cancel body `reason`
  (`appointment_actions.py`, `booking_schemas.py`).
- Tests: fourteen named behaviours, expected values from the specification and the stack; transport, decode and
  status failures each have a red test. Test 14 checks a constant, a weak but accepted guard of "127.0.0.1 only".
- Security: status, JSON shape and every failure become `SmokeFailure` naming the step; the code is never printed;
  the session cookie stays in memory. Authorization stays server-side.
- Notes for the implementer, not reasons to revise:
  1. Ruff `select` includes `S`, so `urlopen` triggers S310: the `# noqa: S310 - ...` is required, not optional.
  2. Call `urllib.request.urlopen(...)` as an attribute access, not `from urllib.request import urlopen`, or test 4's
     monkeypatch does not take effect.
  3. `urllib.error.HTTPError` is a subclass of `URLError` and so of `OSError`: catch it before `OSError`.
  4. `scripts/` has no `__init__.py`; the existing `from scripts.smoke import` works and needs no change.
  5. Redirect following and the unverified smtp4dev and seed facts stay as the plan's stated risks; the orchestrator's
     fresh-stack run is the check.
