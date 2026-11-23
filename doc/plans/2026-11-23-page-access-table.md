# Page access table: every page route has a row

Slice: items 1 and 2 of task 26b3, page routes only (no `/api/v1`, no `/fhir`). Item 3's walk, item 4's review section and item 5's timing are later runs; no route is requested here.

## Focal point

One table in the tests, one row per page route of `drlibre.urls.urlpatterns`, giving the answer each caller gets, by `drlibre-specs.md` 12.3, 14 and 16. Coverage tests fail when a page route has no row or a row names a route that does not exist. No production code changes. One document is added: a proposed ADR that records every spec reading the table encodes.

## Blocks and files, in order

1. `doc/adr/0012-page-access-readings.md` (new, status Proposed). The readings listed under "For the owner" below, and the record-existence conflict. CLAUDE.md requires open decisions in an ADR; the review's "For the owner" section follows in item 4's run.
2. `scheduling/views/pages/test_page_access_rows.py` (new). Types `Answer` (StrEnum: `OK`, `SIGN_IN`, `FORBIDDEN`, `NOT_FOUND`), frozen dataclass `Row`, and the no-session rows (18) plus `style` (debug only).
3. `scheduling/views/pages/test_page_access_rows_patient.py` (new). Patient area (12 routes under `patient/`), `appointments/<id>/confirmation`, `appointments/<id>/calendar.ics`, `account/password`: 15 rows.
4. `scheduling/views/pages/test_page_access_rows_clinician.py` (new). `clinician/` and its 18 children, including `clinician/type-colours.css`: 19 rows.
5. `scheduling/views/pages/test_page_access_rows_admin.py` (new). `admin-console/` and the record families (hospitals, specialties, departments, rooms, appointment types, users, clinicians, each with list, new, show, edit, delete), plus `users/<id>/deactivate` and `clinicians/<id>/calendar`: 38 rows.
6. `scheduling/views/pages/test_page_access_rows_admin_operations.py` (new). `admin-console/appointments` and its 13 children (export, the booking steps, reschedule), `audit`, `settings`, `settings/reminders`, `waitlist` and its 3 children, and `admin-console/type-colours.css`: 22 rows. The split keeps the two admin files short for the line-by-line review.
7. `scheduling/views/pages/test_page_access_table.py` (new). Builds the route list from `drlibre.urls.urlpatterns`, joins the row files, holds the coverage tests.

Not touched: `drlibre/urls.py`, every view, every template, `drlibre-specs.md`, `doc/security-review.md`, `Makefile`, `mutation-equivalents.txt`, and the existing tests `scheduling/views/pages/test_admin_access.py`, `test_form_only_pages.py`, `test_public_route_limits.py`, `scheduling/views/test_api_bodyless_writes.py`. They overlap with the new table (they already walk `get_resolver()` or check the console's 403/redirect); whether any becomes redundant is decided in item 3's plan, not here.

## Row shape

`Row(route, visitor, patient, clinician, admin, names_record=False, debug_only=False)`. Every cell is an `Answer`.

- `route`: the pattern as `str(pattern.pattern)` prints it, without a leading `^` (the three regex entries are excluded, see Coverage). Example: `clinician/appointments/<uuid:appointment_id>/notes`. Home is `""`.
- Cells, in caller order (visitor, patient, clinician, admin): the answer for that caller when it is not refused by session or area.
  - `OK`: the route's own answer for an allowed caller. For most routes a 200. For `favicon.ico` a 302 to `/static/favicon.svg`. For `sign-out` (POST only, no page guard) a 302 to `/sign-in` with the session cookie cleared, for every caller; item 3 must check the cleared cookie, because the redirect alone looks like `SIGN_IN`.
  - `SIGN_IN`: a 302 to `/sign-in?next=...` (the page guard's redirect).
  - `FORBIDDEN`: the 403 page.
  - `NOT_FOUND`: the 404 page. No cell carries it; it is reached through `names_record` (below).
- `names_record`: the route carries a record id. `True` on every route with a `<uuid:...>` segment, including catalogue ids (types, hospitals, specialties, rooms, departments) that have no owner; item 3 applies the other-record rule only where the record has an owner (Appointment, BookingHold, Notification, WaitlistEntry, AvailabilityRule, TimeOff, Clinician, Patient). The rule the table encodes, from 12.3:
  - a missing record gives `NOT_FOUND` for every caller whose area admits the route;
  - another user's owned record gives `FORBIDDEN` for every caller except Admin, whose console reads every hospital (17.2);
  - the caller's own record gives the cell's `OK`.
  The flag does not change a cell. A caller whose area refuses the route gets its cell (`SIGN_IN` or `FORBIDDEN`) whatever the record.
- `debug_only`: the route exists only when `settings.DEBUG` is on (`style`).

Order of checks the table encodes (12.3, and `scheduling/views/pages/page_view.py` `_guarded_dispatch`): session first (no session gives `SIGN_IN` on a session route), then the caller's area (another role's area gives `FORBIDDEN`), then the record (owned by someone else gives `FORBIDDEN`, missing gives `NOT_FOUND`). A visitor never gets `FORBIDDEN` or `NOT_FOUND` on a session route.

Method, decided here so item 3 does not inherit a guess: the table has no method column. Item 3 sends a `GET` when the view class defines `get` and a `POST` otherwise, read from the view's `http_method_names`. A route whose method is refused by `http_method_names` answers 405, which the spec does not name (For the owner, item 9); the table says nothing about 405. Method checks in `PageView._guarded_dispatch` run after the session and area checks, so a wrong role gets 403 even on a POST-only route.

## Coverage, what the tests hold

Route set of the URL configuration (`drlibre.urls.urlpatterns`, walked through `get_resolver()` so `admin_*_routes()` helpers are already flattened):

- Keep an entry whose `str(pattern.pattern)` does not start with `api/`, `fhir`, `static/` after an optional leading `^` is stripped. The excluded entries are `^api/v1/`, `fhir` (a plain `path`), `^fhir/`, and `^static/(?P<path>.*)$`. Without the strip, the regex entries would be taken as page routes.
- Expected rows: every row whose `debug_only` is false, plus those with `debug_only` true only when `settings.DEBUG` is on. Test runs keep `DEBUG` off (`Makefile`: start-up refuses the published development key otherwise), so `style` is not expected there.

Tests (names `returns_X_when_Y`, expected values in words):

- `returns_no_failure_when_every_page_route_has_a_row`: the set of configured page routes equals the set of expected rows. Failure message prints both set differences: `missing_rows` (route without row) and `stale_rows` (row without route).
- `returns_one_row_per_route_when_table_read`: no route string appears in two rows.
- `returns_no_debug_row_expected_when_debug_is_off`: with `settings.DEBUG` false, no row with `debug_only` is in the expected set. This is the branch `make test` runs. The on-branch (`style` expected) is covered by the same comparison under `DEBUG` on, which no test run makes; say so in the test docstring.

The tests import the URL configuration and compare strings. No `django_db` mark, no requests, no clock.

Red proof, in the run log (not in the diff): (a) write the tests before the row files exist; the first test fails with every route missing. (b) After the rows pass, delete one row and add a row for `page/that-is-gone`; each change must fail the first test on its own.

## Answer rules, by family

Spec gaps are decided here and listed in "For the owner" below. `names_record` is true on every row with an id, as the rule above says.

| Family | Routes | Visitor | Patient | Clinician | Admin |
| --- | --- | --- | --- | --- | --- |
| No-session pages and booking steps | `""`, `favicon.ico`, `providers/<id>`, `hospitals/<id>`, `specialties/<id>`, `terms`, `privacy`, `sign-in`, `sign-in/email-link`, `sign-in/check-email`, `sign-in/link`, `sign-out`, `book`, `book/<type>`, `book/<type>/provider`, `book/<type>/details`, `book/holds/<id>/code`, `book/holds/<id>/resend` (18) | OK | OK | OK | OK |
| `style` (debug only) | 1 | OK | OK | OK | OK |
| Patient area and shared appointment pages | `patient/` and its 11 children, `appointments/<id>/confirmation`, `appointments/<id>/calendar.ics` (14) | SIGN_IN | OK | FORBIDDEN | FORBIDDEN |
| Password, any signed-in staff | `account/password` (1) | SIGN_IN | FORBIDDEN | OK | OK |
| Clinician area | `clinician/` and its 18 children, including `clinician/type-colours.css` (19) | SIGN_IN | FORBIDDEN | OK | FORBIDDEN |
| Admin console | `admin-console/` and its 59 children, including `admin-console/type-colours.css` (60) | SIGN_IN | FORBIDDEN | FORBIDDEN | OK |

Count: 18 + 1 + 14 + 1 + 19 + 60 = 113 page rows with `DEBUG` on, 112 with it off. Verified on this branch by importing the URL configuration with `DEBUG` on: 142 entries, of which 29 are excluded: 26 under `api/v1` (25 paths and the `^api/v1/` regex), 2 `fhir` (the plain path and `^fhir/`), 1 `^static/`. That leaves 113 page routes. Of those, 19 start `clinician`, 60 `admin-console`, 12 `patient/` (plus the 2 appointment pages in the patient family). Route strings are copied from that import when writing the rows, not typed from memory.

Hold routes: the visitor reaches `book/holds/<id>/code` and `resend` by the hold cookie. The hold rule is a visitor's own hold: OK. Another visitor's hold: FORBIDDEN per 12.3 (see For the owner, item 5).

## Invariants and blast radius

- No runtime behaviour changes. The only new code runs in the test suite and in one document.
- Double booking, server-side authorization and the append-only audit log are untouched; none is read or written.
- A wrong row has no runtime effect in this run. It can make item 3 check a wrong answer; it cannot make the product answer differently.

## Trust boundaries and domain

No trust boundary is crossed in this run (no request, no input). Domain entities named in the rows, from CLAUDE.md §3 vocabulary: Visitor, Patient, Clinician, Admin, Hospital, Department, Room, Specialty, AppointmentType, Appointment, WaitlistEntry, Notification, AvailabilityRule, TimeOff, User, BookingHold.

## Style and gates

- Module docstrings say what the file holds, for example "Section 12.3: who may open each clinician page." No task numbers, no item numbers.
- Names: `Row`, `Answer`, `OK`, `SIGN_IN`, `FORBIDDEN`, `NOT_FOUND`; full words; constants not magic strings. Rows one line each where ruff's 100-column limit allows, otherwise wrapped the way ruff formats.
- Types: strict mypy, no `Any`, no `cast`, no bare suppressions. `route` is `str`.
- Each file well under 300 lines; each function under 50 lines.
- `make gate` comment cap respected; no comment narrates a row.

## ADR 0012 content (proposed, this run)

Status: Proposed. Decision: the table encodes these readings until the owner changes the specification. Record: the nine readings under "For the owner" and the record-existence conflict. Linked from `test_page_access_table.py` by its number only.

## Not in this run

- Item 3, the walk: every caller sends every route's request as its real client sends it, with own-record and other-record cases. Derived method per "Row shape". Risk for item 3: `PageView.read_scope` rate limits can answer 429 on repeated `GET`s; item 3 must read which pages set it and reset or spread its requests.
- Item 1 for `/api/v1` and `/fhir` (tokens, 401, the API rows). A separate slice.
- Item 4: the access section in `doc/security-review.md`, its generator command, its test, and the "For the owner" section of the review.
- Item 5: request count and timing of the walk. Item 3's plan counts them from the table.
- The reference files `test_api_access_rows.py` and `test_api_access_table.py` named in the goal: not on `main` or this branch (`git ls-files`). This plan follows the shape they describe; the orchestrator says whether to rename once they merge.

## For the owner (spec silent or in conflict; the table states these readings)

1. **Record existence (conflict).** The goal says a caller on another user's record "never tells whether the record exists". Spec 12.3 says another's record gives `forbidden` and a missing one `not_found`; those two answers reveal existence. The table follows 12.3, because the backlog says to write the table as the specification has it so a divergent route fails. Divergence already in the code: `scheduling/views/pages/booking_code.py` `_expired` answers `not_found` for a hold made by another visitor (`not made_this_hold`), so item 3 fails on `book/holds/<id>/code` for the other-visitor case. The owner picks one reading; `not_found` for both removes the leak and changes 12.3.
2. Signed-in staff on no-session pages (booking steps, public pages, sign-in): 12.3 says these "need no session"; read as OK for every caller, not forbidden for a signed-in clinician or admin.
3. Appointment confirmation and calendar file: patient-only reading; clinician and admin get `FORBIDDEN`. The spec names no area for them.
4. `account/password`: patient gets `FORBIDDEN`, staff OK. Matches the code's `allowed_roles`; the spec does not name it.
5. `sign-out`: OK for every caller including a visitor. Read from 14 ("Anyone" for logout), not from 12.3. The wire answer is a redirect to sign-in for all callers (see Row shape).
6. `favicon.ico` redirects to a static file without a session check; the row is OK for every caller.
7. `style` exists only with `DEBUG` on. Spec silent; the row is debug-only.
8. `/static/` is not a page and has no row.
9. A method the view does not accept answers 405. The spec does not name 405; the table says nothing about it.
10. Passwordless patients and `book/holds/<id>` reads: the hold cookie, not the session, is the caller's identity on the hold routes. Spec 12.3 gives no rule for it.

These go to ADR 0012 in this run and to the review's "For the owner" in item 4. This run does not edit `drlibre-specs.md`.

## Failing tests to write first

Written before any row file exists:

- `returns_no_failure_when_every_page_route_has_a_row`: fails with every route listed as missing.
- `returns_one_row_per_route_when_table_read`: passes on an empty table.
- `returns_no_debug_row_expected_when_debug_is_off`: passes on an empty table.

After the rows exist, the first must pass on the real URL configuration; then the red proof described under "Coverage".

## What I will not do

- No new abstraction, generator or Makefile command here (item 4).
- No change to the URL configuration or to any view to make a row fit.
- No read of `api/v1` or `fhir` routes.
- No request to any page.
- No edit of `drlibre-specs.md` or of the existing tests named above.

## Revision notes (architect `revise`, scratch/plan.verdict)

1. Record existence: named as a conflict, reading chosen (spec 12.3), listed as For the owner item 1, and recorded in ADR 0012. Divergence with `booking_code.py` stated.
2. Decisions recorded now: ADR 0012 is in this run, not in item 4.
3. Coverage filter: strip `^`, exclude `api/`, `fhir`, `static/`; `fhir` is a plain path. Stated under Coverage.
4. `OK` defined: the route's own answer for an allowed caller; `favicon.ico` and `sign-out` redirects spelled out.
5. Method: derived by item 3 from the view's `http_method_names` (GET if `get`, else POST); stated under Row shape.
6. Overlapping tests: named, left alone, decided in item 3.
7. DEBUG-on branch: not run by `make test`; the debug row is expected only when `settings.DEBUG` is on, and the on-branch is stated as unrun.
8. Reference style files: still absent on this branch; names kept.

## Architect review

Verdict: approve (scratch/plan.verdict).

1. Ladder: one test module, four row files, one ADR, no production change, no new abstraction. Smallest slice that proves items 1 and 2 for page routes.
2. Purpose per block: stated in one sentence each (ADR, Answer/Row types, four row files by family, coverage module). Vocabulary matches CLAUDE.md §3.
3. Tests first: three named behaviours with expected values; red proof (empty table, then delete-one-row and add-stale-row) is specified.
4. Security: no trust boundary crossed; the plan states it. Access rules themselves are the subject, and the record-existence leak is named, not hidden.
5. Architecture: test-only; no wire or storage change.
6. Scope: slice coherent. Items 3, 4, 5 and the `/api` and `/fhir` parts are named under "Not in this run".

Reasons the earlier `revise` no longer holds: the record-existence conflict is named and the spec reading is chosen; the coverage filter, `OK`, method derivation and DEBUG branch are stated; ADR 0012 is in this run.

Residual, not a reason to revise:
- The route counts (113 with `style`, 112 without) were not re-derived by the architect: the import probe was blocked by settings (`SECRET_KEY` and `DEBUG` refusal). The red run must confirm the count by import before the rows are typed.
- Rows for `appointments/<id>/confirmation` and `account/password`, and the `sign-out` cell for visitors, are readings with no spec row; ADR 0012 must list them (it does, under For the owner items 3 to 5).
- Item 3 must not merge with the existing overlapping tests without a decision; the plan defers that correctly.
