# Plan: access table for the /api/v1 routes (task 26b3, items 1 and 2)

Slice: items 1 and 2 only, for `/api/v1`. Item 3 (the walk that sends requests), item 4 (the
generated section of `doc/security-review.md`) and the `/fhir` rows are not in this run.

## Focal point

One data table of every `/api/v1` method and path in `drlibre/urls.py`, with the answer each of
four callers gets, and one test that fails when a route is missing from the table or a row names
a route that no longer exists. Behaviour changes: none. This run adds two files and no product code.

## Blocks

1. `scheduling/views/api_access_table.py` (new, data, not collected by pytest). A frozen
   dataclass `AccessRow(method, route, visitor, patient, clinician, admin)` with int status
   codes, and `API_ACCESS_ROWS`, a tuple of 27 rows in URL-configuration order. The module
   docstring states the columns, that a route naming a record gives the answer on the caller's
   own record, and that the walk checks another user's record separately (item 3). Route strings
   are Django's own pattern strings (`api/v1/appointments/<uuid:appointment_id>/cancel`), so a
   row reads like the URL file. Size about 150 lines.
2. `scheduling/views/test_api_access_table.py` (new, test). A helper walks
   `get_resolver().url_patterns`, keeps the patterns whose string starts with `api/v1/` or is the
   catch-all `^api/v1/`, and yields `(method, route)` for each declared handler (`get`, `post`,
   `put`, `patch`, `delete`); a view with no handler is keyed `ANY`, which is how the catch-all
   is written. Two tests (below). The helper and the tests stay under 60 lines.

## Files, in order

1. `scheduling/views/test_api_access_table.py`: the two tests and the walker. Written first; it
   imports the table, so it fails at import until block 1 exists. That is the red stage.
2. `scheduling/views/api_access_table.py`: the table.

## Files deliberately not touched

- `drlibre/urls.py`: the table is checked against it, not changed.
- `scheduling/views/test_api_bodyless_writes.py` has `_api_views`, but it drops the catch-all
  and filters the prefix, so it cannot serve. Importing a helper from one test module into
  another is avoided; the walker is written in the new file. This is a second copy of about
  ten lines. The owner may prefer extracting both to `scheduling/views/api_routes.py` in a
  later refactor; not this run.
- `drlibre-specs.md` (owner text). `doc/security-review.md` (item 4, not this run).
- `doc/handover.md`: no state change in this run unless a test recipe in it names the count of
  tests; check during implementation and update in the same commit if so.

## Tests (behaviour names, expected values from the specification)

- `returns_no_route_unlisted_when_the_url_configuration_is_walked`: the walked keys minus the
  table keys are empty. Expected: `[]`. Message names each missing key.
- `returns_no_row_for_a_removed_route_when_the_table_is_compared`: the table keys minus the
  walked keys are empty. Expected: `[]`.

Red proof, done in the red stage and restored: (a) delete the `POST api/v1/jobs/reminders` row,
the first test fails and names it; (b) add a row `GET api/v1/no-such-route`, the second test fails
and names it. Both before the restore. The table's cell values are not tested in this run: item 3
calls the routes; this run is data plus route coverage.

## The table (27 rows, one per method and path)

Cells: visitor / patient / clinician / admin. "Own" means the caller's own record in the state
the action applies to (an OFFERED waitlist entry, the caller's own appointment).

| Method | Route | Visitor | Patient | Clinician | Admin | Basis |
| --- | --- | --- | --- | --- | --- | --- |
| GET | api/v1/health | 200 | 200 | 200 | 200 | §14 Anyone; `HealthView` AllowAny |
| POST | api/v1/auth/login | 401 | 200 | 200 | 200 | §12.1; visitor has no account, wrong credentials give `unauthenticated` (`sign_in.py:58`); each caller sends its own password |
| POST | api/v1/auth/logout | 204 | 204 | 204 | 204 | §14 Anyone; `LogoutView` 204 |
| POST | api/v1/auth/link | 202 | 202 | 202 | 202 | §14 Anyone; `LinkView` 202 for every address |
| POST | api/v1/auth/link/verify | 200 | 200 | 400 | 400 | §7.3, §12.1; `use_link` refuses any token that is not a usable patient link with `invalid_input` (`sign_in_link.py:31`); clinicians and admins have no link |
| GET | api/v1/slots | 200 | 200 | 200 | 200 | §12.3 and §14 public |
| GET | api/v1/search/providers | 200 | 200 | 200 | 200 | §14 Anyone |
| GET | api/v1/search/hospitals | 200 | 200 | 200 | 200 | §14 Anyone |
| GET | api/v1/search/specialties | 200 | 200 | 200 | 200 | §14 Anyone |
| GET | api/v1/hospitals/<uuid:hospital_id> | 200 | 200 | 200 | 200 | §14 Anyone; active record (§4 `not_found` when inactive); no owner |
| GET | api/v1/providers/<uuid:provider_id> | 200 | 200 | 200 | 200 | as above |
| GET | api/v1/specialties/<uuid:specialty_id> | 200 | 200 | 200 | 200 | as above |
| POST | api/v1/booking/holds | 201 | 201 | 201 | 201 | §14 Anyone; `HoldsView` 201 |
| POST | api/v1/booking/holds/<uuid:hold_id>/resend | 200 | 200 | 200 | 200 | §14 Anyone; a hold has no owner, so the answer is the same for all; `ResendView` 200 |
| POST | api/v1/booking/holds/<uuid:hold_id>/verify | 201 | 201 | 201 | 201 | §7.1; `VerifyView` 201 and opens a session |
| GET | api/v1/appointments | 401 | 200 | 200 | 200 | §14 signed in; list limited to what the caller may see |
| POST | api/v1/appointments | 401 | 201 | 201 | 201 | §5.4: patient for self, clinician into own calendar with an active patient, admin for any; `AppointmentsView` 201 |
| POST | api/v1/appointments/<uuid:appointment_id>/cancel | 401 | 200 | 200 | 200 | §14 patient, clinician, admin; own appointment |
| POST | api/v1/appointments/<uuid:appointment_id>/reschedule | 401 | 200 | 200 | 200 | §14 patient, clinician, admin; own appointment |
| POST | api/v1/appointments/<uuid:appointment_id>/check-in | 401 | 403 | 200 | 200 | §14 clinician, admin; `roles(CLINICIAN, ADMIN)` refuses a patient with 403 |
| POST | api/v1/appointments/<uuid:appointment_id>/complete | 401 | 403 | 200 | 200 | as check-in |
| POST | api/v1/appointments/<uuid:appointment_id>/no-show | 401 | 403 | 200 | 200 | as check-in |
| POST | api/v1/waitlist | 401 | 201 | 403 | 201 | §5.8 join: patient for self, admin names a patient, clinicians cannot; `authorize_join` (`waitlist_rules.py:94`) |
| POST | api/v1/waitlist/<uuid:entry_id>/accept | 401 | 200 | 403 | 200 | §5.8 patient (own entry) or admin; `AcceptView` 200 |
| POST | api/v1/waitlist/<uuid:entry_id>/offer | 401 | 403 | 403 | 200 | §5.8 manual offer, admin; `offer_waitlist_entry` refuses non-admins (`waitlist.py:106`); **not in §14** |
| POST | api/v1/jobs/reminders | 401 | 403 | 403 | 200 | §14 admin; `roles(ADMIN)` |
| ANY | ^api/v1/ (catch-all) | 404 | 404 | 404 | 404 | `NotFoundView` public; an undeclared method is `MethodNotAllowed`, mapped to `not_found` (`failure_response.py:95`) |

The visitor gets 401 on every signed-in route because no session means `NotAuthenticated`
(`permission_denied` with no successful authenticator); a signed-in caller refused by role gets
403. Both mappings are in `failure_response.py:95-99` and `access.py`.

## Invariants that must not break

- No product behaviour changes. Double booking, audit, and the cross-origin refusal are untouched.
- The table is data: nothing reads it at runtime. It states answers the server already gives.
- Authorization stays server side: the table documents `permission_classes` and use-case guards,
  it does not add a check.

## Trust boundaries and blast radius

- None crossed by this run. The walker reads the URL configuration in memory; it sends no request.
- Blast radius: two new files under `scheduling/views/`. A failing row fails one test.

## Domain entities (CLAUDE.md §3 vocabulary)

Visitor, Patient, Clinician, Admin, Session, BookingHold, SignInLink, Appointment, WaitlistEntry,
AppointmentType, Hospital, Department, Specialty, ClinicianProfile, AvailabilityRule, TimeOff,
ApiClient is not used (no tokens in this run).

## What I will not do

- No token columns, no bearer-token rows (FHIR, §15, is another run).
- No request is sent, no xfail (item 3 owns the walk).
- No abstraction over DRF permissions, no shared helper module, no refactor of
  `test_api_bodyless_writes.py`.
- No edit to `drlibre-specs.md`.

## Costs and counts

- This run sends 0 requests; the suite time added is the import and one resolver walk (milliseconds).
- For item 3, to note here for the owner: 27 rows × 4 callers = 108 own-record requests, plus
  7 owned rows (cancel, reschedule, check-in, complete, no-show, accept, offer) × 2 other-user callers
  (patient, clinician) = 14, so about 122 requests, all sharing one set of users and sessions built once.

## Findings for "For the owner" in the review (not spec edits)

- §14 has no row for `POST /waitlist/{id}/offer`; §5.8 gives it to admins, and the code does the same.
- Undeclared methods on `/api/v1` routes answer 404 (`MethodNotAllowed` mapped to `not_found`);
  §4 does not say 404 or 405. The table lists declared methods only.
- No route read in this run answers differently from the specification.

## Risks

- A passwordless patient (§7.2) has no password; the login row assumes a patient with a password.
  Item 3 must build that caller with a password, or the row describes a different caller.
- The owned-row cells assume the record is in the state the action needs (OFFERED for accept).
  Item 3 must set that state, or the cell answers `invalid_transition` (409), not the table's answer.
- The duplicated walker (see Files not touched) is ten lines; fine until a third caller appears.

## Architect review

Read against `CLAUDE.md`, the backlog task 26b3, and the code the table cites. Verdict: approve.

What I checked:

- Route set: the 27 keys match `drlibre/urls.py`. Handler declarations match the table: each
  `get`/`post` in `scheduling/views/{health,auth,slots,search,public_details,booking,appointments,
  appointment_actions,waitlist,jobs}.py` is a row, and `NotFoundView` declares none, so it is the
  `ANY` key. I did not run the walker here; the test run will settle it.
- Status mapping: `failure_response.py:95-100` maps `NotAuthenticated` to `unauthenticated` (401)
  and `PermissionDenied` to `forbidden` (403). `ApiView` declares `SessionCookieAuthentication`,
  so a visitor on a signed-in route gets 401, not DRF's 403. The 401 status is in §4.
- Cited code: `sign_in.py:58` returns `unauthenticated`; `sign_in_link.py:31` is the
  `invalid_input` refusal; `waitlist_rules.py:94` is `authorize_join`; `waitlist.py:106` refuses
  non-admins on offer. Accept for a clinician returns `forbidden` through `guard_record`, as the
  table says.
- Scope: items 1 and 2 only, no product behaviour change, no request sent, no xfail. Coherent.
- Ladder: two new files, no helper module, no DRF abstraction. The duplicated walker is accepted
  and recorded.
- Security: no trust boundary is crossed. The walk reads the resolver in memory.
- First tests are named as behaviours with expected values (`[]` both ways). Red proof covers a
  missing row and a stale row.

Notes for the implementer, not reasons to revise:

1. Basis column: the 401 and 404 cells cite §14 and §12.1. Add §4 (the status table) and §12.3
   (`not_found` and `forbidden` rules) to the basis, since the goal names §4 and §12.3.
2. Cell semantics: the 201, 200 and 400 cells assume a valid body. The link and login cells assume
   the caller's own credentials or link. The docstring should say so in one sentence. The Risks
   section covers only the passwordless patient on login, not link/verify.
3. Location: the goal says "one table in the tests". The plan puts it in `scheduling/views/`, a
   product package. This is defensible (`probe_views.py` sets the precedent) and the file is not
   collected. If the orchestrator wants it under tests, move it next to `test_api_access_table.py`.
4. The `ANY` row: the markdown says `^api/v1/ (catch-all)`. The Python key must be the exact pattern
   string `^api/v1/`, with method `ANY`.
