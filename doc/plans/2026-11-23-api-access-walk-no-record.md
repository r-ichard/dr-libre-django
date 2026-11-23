Slice: task 26b3 item 3, part one: the walk over the 14 `/api/v1` rows that name no record. Tests and test data only; no product file changes. 62 HTTP requests.

## Focal point

`scheduling/views/test_api_access_walk.py`: one test sends each of the 14 no-record requests as each of four callers and compares the status with the row. The rows already exist in `scheduling/views/test_api_access_rows.py`.

## Selection of rows

A row is walked when its route has no `<` (no `<uuid:...>`) and does not start with `api/v1/booking/holds`. That leaves 14 rows: health, auth login, logout, link, link verify, slots, search providers, search hospitals, search specialties, GET appointments, POST appointments, POST waitlist, jobs reminders, and the catch-all `^api/v1/`.

## Request count

- Walk: 14 rows x 4 callers = **56 requests**.
- Setup: 3 sign-ins for the shared patient, clinician and admin clients, plus 3 sign-ins for the logout clients (one per signed-in caller): **6 requests**.
- Stored sign-in links (verify rows) are rows written directly, not requests.
- Total: **62 HTTP requests**, in process through the Django test client.
- Cost: the test settings hash passwords with MD5 (`conftest.py:47`), so sign-ins are cheap. The build reports the walk's duration from `make test`; expect a few seconds.
- Rate limits, from `scheduling/domain/rate_limit_rules.py`: link 3 per email per hour (the walk asks once for the patient's address); link 10 per address (4 used); search 120 per address (about 16 used); failed sign-in lockout at 10 (one failure). All well inside.

## Blocks, in file order

1. **`scheduling/views/test_api_access_rows.py`** (edit). Docstring rewritten to say what the rows hold: the access answer of each `/api/v1` route; the route-coverage test and the no-record walk read them; record routes and hold routes are not walked yet. No task number. Add:
   - `class Caller(StrEnum)`: visitor, patient, clinician, admin.
   - `@dataclass(frozen=True) class KnownDifference`: `caller: Caller`, `method: str`, `route: str`, `row_answer: int`, `product_answer: int`.
   - `KNOWN_DIFFERENCES: tuple[KnownDifference, ...] = ()`.
   Rows and cells are not changed. The tuple starts empty; the build adds an entry only where the product answers differently, with both answers.
2. **`scheduling/views/test_api_access_table.py`** (edit, docstring only). Drop the "Task 26b3 item 2:" prefix; the docstring says what the test holds.
3. **`scheduling/views/test_api_access_world.py`** (new). `World` dataclass: the patient with a password (P1), a passwordless patient (P2, the waitlist target and the visitor's verify target), one clinician with profile and an availability rule covering the frozen day, one admin, one hospital with one department and one bookable appointment type, three free slots (A, B, C) for the three booking callers, a waitlist window, the signed-in clients for patient, clinician and admin, and a logout client for each of them. Builders come from `scheduling/models/builders.py` (`make_clinic`, `add_clinician`; signatures read in the build). Functions:
   - `build_world() -> World`
   - `sign_in(email, password) -> Client`: POST `/api/v1/auth/login` with `browser_api_client()`, so the cookie comes from the product's response.
   - `new_link(patient) -> str`: creates a `SignInLink` directly (`token_hash=hash_token(token)` from `scheduling/use_cases/session.py`, `expires_at` now plus `LINK_LIFETIME` from `scheduling/domain/sign_in_link_rules.py`) and returns the token. It does not import the private `_stored_link` of `test_sign_in_link_support.py`.
4. **`scheduling/views/test_api_access_requests.py`** (new). One sender per walked row, keyed by `(row.method, row.route)` so that `GET` and `POST api/v1/appointments` do not collide. `Sender = Callable[[World, Caller], Response]`. Each sender picks its client (visitor: a fresh `browser_api_client()` per request; others: their `World` client) and sends the route's request with a body built only from fields the serializer accepts (`StrictSerializer` refuses unknown keys). Bodies:
   - login: own email and password; visitor sends an unknown address and a wrong password.
   - logout: `{}` from the caller's logout client.
   - link: `{"email"}` of the caller; visitor sends an unknown address.
   - link verify: visitor sends `new_link(P2)`; patient sends `new_link(P1)`; clinician and admin send a random token no link holds (`secrets.token_urlsafe`). The link is created inside the sender, at send time, not in the world (see the hazard below).
   - slots: `appointment_type_id`, `from`, `to` (window as in `test_slots.py`).
   - search rows: no query. Health: no body.
   - GET appointments: no query.
   - POST appointments: type plus `starts_at` of the caller's slot (patient: A for self; clinician: B with `patient_id` P2; admin: C with `patient_id` P1; visitor: a body, answered 401 before any booking).
   - POST waitlist: type and window; admin adds `patient_id` P2; others send no `patient_id`.
   - POST jobs/reminders: `{}`.
   - catch-all: `GET /api/v1/no-such-route` (row method is ANY; the walk sends GET).
   `SENDERS: dict[tuple[str, str], Sender]`. Each sender is 3 to 8 lines.
5. **`scheduling/views/test_api_access_walk.py`** (new). Module docstring says what the walk holds: each caller's status for each no-record route against the access row. One test: `returns_the_row_answer_for_each_caller_when_the_walk_sends_each_request`. It freezes the clock (`monkeypatch.setattr(clock, "now_utc", ...)`, as the other API tests do), builds the world, and for each walked row (in table order) and each caller (visitor, patient, clinician, admin) sends the request and records a mismatch when the status differs from the expected one. Expected = the `KNOWN_DIFFERENCES` product answer for that caller, method and route, else the row's answer. A helper checks each `KNOWN_DIFFERENCES` entry both ways: its `row_answer` must equal the row's cell, and its `product_answer` must differ from it; otherwise the walk reports the entry. Mismatch text: `POST api/v1/waitlist as clinician: expected 403, got 201`. Helpers keep every function under 50 lines. The test ends with `assert mismatches == []`.

No production file is touched. Files: 3 new, 2 edited, all under 300 lines.

## Ordering hazard (why the verify links are made at send time)

`ask_for_link` (`scheduling/use_cases/sign_in_link.py`) cancels every open unused link for the same email before it issues a new one. The walk sends the patient's link request (row 4) before its verify request (row 5). A link stored in the world at build time would be cancelled by row 4 and the verify would answer 400, a false mismatch. So `new_link` runs inside the verify sender. The visitor's verify uses P2 (a link for an address that has no other link), and the patient's verify uses P1 (its own identity), so the patient's shared session is never swapped for another person's. A verify swaps the patient's cookie for a new session of the same user; the test client keeps the new cookie. `use_link` does not revoke other sessions (`open_session` adds one).

## Callers (how each one sends)

- **Visitor**: a fresh `browser_api_client()` per request. It holds the `csrftoken` cookie and the `Origin` header, and no session. A visitor verify turns only that fresh client into a session.
- **Patient, clinician, admin**: one client each, signed in once through the product's login, reused for every row. Each login row or verify row may replace the cookie with a new session of the same user. The test client keeps the latest cookie.
- **Logout**: logout ends the session, so each signed-in caller logs out from its own second client, signed in for that row. The shared clients stay signed in.
- **Enforcement**: `browser_api_client()` sets `enforce_csrf_checks=True`, an `Origin` header and `X-CSRFToken`, as a browser sends them.

## Expected answers (the rows, copied from `test_api_access_rows.py`)

| Row | Visitor | Patient | Clinician | Admin |
| --- | --- | --- | --- | --- |
| GET health | 200 | 200 | 200 | 200 |
| POST auth/login | 401 | 200 | 200 | 200 |
| POST auth/logout | 204 | 204 | 204 | 204 |
| POST auth/link | 202 | 202 | 202 | 202 |
| POST auth/link/verify | 200 | 200 | 400 | 400 |
| GET slots | 200 | 200 | 200 | 200 |
| GET search providers, hospitals, specialties | 200 | 200 | 200 | 200 |
| GET appointments | 401 | 200 | 200 | 200 |
| POST appointments | 401 | 201 | 201 | 201 |
| POST waitlist | 401 | 201 | 403 | 201 |
| POST jobs/reminders | 401 | 403 | 403 | 200 |
| catch-all `^api/v1/` | 404 | 404 | 404 | 404 |

The product's answers are not known until the build runs the walk. Any different answer goes into `KNOWN_DIFFERENCES` with both answers and the section of `drlibre-specs.md`. Nothing is xfailed or skipped.

## Invariants and blast radius

- **Double booking**: three distinct slots (A, B, C) for the three booking callers; the visitor's 401 comes before any booking.
- **Server-side authorization**: the walk asserts the product's answers and bypasses nothing. Every request crosses the browser checks (Origin, CSRF cookie, session from the product's login).
- **Audit log**: written only by the product through its own requests. The test does not disable or truncate it. The module uses the default transactional fixture, so no `committed_rows`.
- **Mail**: no mail is asserted. `send_after_commit` uses `transaction.on_commit`, which does not run inside the default test transaction, so the walk sends no mail to `mail.outbox`, and the walk does not depend on it.
- **Clock**: frozen, so slot times and windows are stable.
- **Blast radius**: test files and test data only. A mistake can fail the walk; it cannot change what the product answers.

## Trust boundaries

- Each request crosses the browser boundary (Origin on writes, the CSRF cookie, the session cookie from the product's login). The product validates all of it; the walk checks status codes only.
- Bodies come from the test's own fixtures: no untrusted input. Response bodies are not asserted here; the per-route test modules own those.

## Domain entities (CLAUDE.md, section 3)

Visitor, Patient, Clinician (public word: provider), Admin (callers); Session and SignInLink (verify rows); Hospital, Department, ClinicianProfile, AvailabilityRule, AppointmentType, Appointment, WaitlistEntry (booking and waitlist rows); Specialty and Clinician (search rows, no query).

## Failing tests first (red), and proof that the walk can fail

- Red: the walk test fails first, because `test_api_access_requests.py` and `test_api_access_world.py` do not exist yet (import error), and then with a missing `SENDERS` key until every walked row has a sender. Missing senders raise `KeyError`, which is a broken invariant, so they are not caught.
- Proof that the walk checks answers: in the working tree, change one row cell (waitlist clinician 403 to 201), run the walk, expect exactly one mismatch naming that cell, then revert. The build stage records the run and the revert.
- Proof of `KNOWN_DIFFERENCES` both ways, recorded in the build: a listed pair whose product answer changes fails; a listed pair that now matches its row fails; an unlisted mismatch fails.

## Not in this run

- The record-naming rows (`hospitals/{id}`, `providers/{id}`, `specialties/{id}`, `appointments/{id}/...`, `waitlist/{id}/...`) and the hold routes (`booking/holds...`): the next run.
- The `/fhir` rows: the owner scoped this run to `/api/v1`.
- Item 4: the access section of `doc/security-review.md`, the generator command, and the drift test.
- Method mismatches (for example `GET /api/v1/auth/login`): not rows, not walked.
- Any product fix. A mismatch goes into `KNOWN_DIFFERENCES`, not into code.
- Documentation: `doc/handover.md` is unchanged, since no product state changes.

## Not doing

- No xfail, no skip, no new dependency, no abstraction beyond `Caller`, `KnownDifference`, `World` and the sender table.
- No import of private helpers (`_stored_link`, `_signed_in`); the world signs in through the product's login route.
- No change to row values and no change to any existing test beyond the two docstrings.

## Open points for the build stage

- Builder signatures (`make_clinic`, `add_clinician`, passwords) and the slot constants are read in the build, not here.
- The review (a later stage) lists every `KNOWN_DIFFERENCES` entry under "For the owner" with both answers and the section.

## Changes from the previous draft (architect `revise`)

1. Sender key is `(method, route)`, not `route`.
2. The module docstrings are rewritten to say what each module holds (the rows' docstring no longer says "nothing reads it").
3. The domain list uses "Clinician (public word: provider)".
4. Each verify link is named: visitor to P2, patient to P1, created at send time (see the ordering hazard).
5. Found while checking: the patient's link row cancels open links for the same email, so the verify links cannot be stored up front.
6. Found while checking: the walk sends no mail to `mail.outbox`; the earlier draft said one did.
7. The private `_stored_link` helper is not imported; the world writes its own link.

## Architect review

Verdict: **approve**.

Checked against the plan and the code:

- **Ladder (§1):** test and test data only; no product file, no dependency. `Caller`, `KnownDifference`, `World` and `SENDERS` each have a real user in the walk.
- **Plan knowledge (§2.5):** each block states its purpose in one sentence. Entities use CLAUDE.md §3 names (Visitor, Patient, Clinician, Admin, Session, SignInLink).
- **Test-first (§10):** red is named (import error, then `KeyError` per missing sender). The walk covers edge and error paths: visitor 401 on signed-in routes, clinician and admin verify 400 on a random token, catch-all 404, logout of each signed-in caller.
- **Security (§11):** every request crosses the Origin check, the CSRF cookie and the product's own login session. Bodies are test fixtures. No mail is asserted.
- **Architecture (§8):** no product layer touched; tests sit beside the code they cover.
- **Facts checked in code:**
  - `ask_for_link` cancels open links for the same email (`sign_in_link.py:47-51`). Verify links must be made at send time, as planned.
  - `sign_out` deletes only the current session (`session.py:67-75`). Shared clients stay signed in after a row's logout.
  - Rate limits: link 3 per email and 10 per address; search 120 per address (`rate_limit_rules.py`). Counters are database rows, rolled back per test. The walk's 4 link requests and 16 search requests fit.
  - Named helpers exist: `browser_api_client` (`api_clients.py:11`), `make_clinic` and `add_clinician` (`builders.py:245`, `260`), `hash_token` (`session.py:35`), `LINK_LIFETIME` (`sign_in_link_rules.py:5`), `now_utc` (`clock.py:4`), `StrictSerializer` (`schemas.py:60`). Its refusal of unknown keys is not checked here; the build confirms it.
- **Request count:** 14 rows x 4 callers = 56 walk requests, plus 6 sign-ins (3 shared, 3 logout) = 62 HTTP requests. Verify-link creation is a direct write, not a request.
- **Earlier revise reasons:** all four are addressed in the text above.

For the build, not blocking:

- The world must give the clinician and the admin a password the product accepts at `auth/login`. The builder signature is read in the build.
- A product answer that differs from its row (for example the catch-all, or a visitor's answer on a route) goes into `KNOWN_DIFFERENCES` with both answers. It is not xfailed.
- The admin's `jobs/reminders` call returns 200 and may run a job. No mail is asserted, so this does not affect the walk.
