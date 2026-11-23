# Plan: task 26b3 item 3, record pages walk (49 record GET pages)

Slice: item 3 for the 49 record routes that answer a GET. Sign-out, the form-only pages and the other non-GET record routes stay for another run (`## Not in this run`).
Process: `tests-and-docs`. The new tests pass on the product as it stands, so the red gate cannot pass. Red is shown by the mutation proof below, recorded in the run log.

## Response to the architect's review

1. **Leg B covers the refused callers on admin-console routes.** Visitor, patient and clinician are walked on the 12 admin-console routes that name a user-owned record (`users` x4, `clinicians` x4, `appointments` x4): 36 GETs. The admin caller is not walked there (see Decisions). The other 18 admin-console routes have no owning user and are exempt, with the reason, in Decisions.
2. **Visitor on a sign-in row.** The expected answer is the sign-in redirect on the own, other and missing record. Basis: spec 12.3 (`drlibre-specs.md` 608-617): "Every other page needs a session; without one the user is sent to sign-in", and "a missing record gives not_found" applies only to a caller admitted by role. The walk checks this; see "For the orchestrator to confirm".
3. **Process.** `tests-and-docs`, with the mutation proof as red evidence (below).

## Focal point

`scheduling/views/pages/test_page_access_walk.py` walks only the GET routes that name no record. The 49 record routes that answer a GET have no walk. This run adds one test module for them, with its support code in a second module so each stays under 300 lines.

## Reading (done)

- `CLAUDE.md`; backlog `doc/backlog/26b3-access-table.md` item 3; spec 12.3 (608-617).
- Rows: `test_page_access_rows.py` (`Row`, `Answer`, 8 record rows), `_patient.py` (7), `_clinician.py` (11), `_admin.py` (23), `_admin_operations.py` (12). Total 61 record rows. 12 answer no GET (form-only, see `Not in this run`), so 49 are walked.
- Walk and helpers: `test_page_access_walk.py` (`_answers_get`, `KNOWN_DIFFERENCES`, `_walked_rows`), `page_walk_support.py` (`make_world`, `client_for_role`, `path_of`, `_record_ids`), `browser_support.py:18-28` (`browser_client`, `browser_post`), `booking_pages_support.py:18` (`FORM`), `:34` (`details_path`).
- Ownership and refusal: `patient_appointments.py:67-73` (`appointment_or_refusal`: 404 missing, 403 other) and `scheduling/use_cases/patient_appointments.py:25-27` (`own_appointment`); `clinician_support.py:41-46` (`appointment_or_refusal`, `refusal_of`: 404 missing, 403 "not yours", nothing of the record) and `clinician_appointment.py:12-24`; `clinician_availability.py:180-190` (rule and time off: 404 missing, 403 other).
- Hold ownership: `booking_code.py:42,49,106` (`made_this_hold`, a cookie set when the hold is made, `booking_details.py:93`). A missing or foreign hold gets 404 (`booking_code.py:77-78`).
- Models: `scheduling/models/availability.py:41` (`AvailabilityRule`), `:76` (`TimeOff`), `access.py:102` (`BookingHold`), `builders.py:18-19`, `:62-73` (appointment defaults: BOOKED, 2030-01-07 10:00 UTC), `:155` (time off defaults), `:232-266` (`make_clinic`, `add_clinician`, which makes a rule).
- Introspection, no file written: the 61 record rows minus the 12 that answer no GET = 49. The 12: `admin-console/appointments/<appointment_id>/check-in`, `/complete`, `/no-show`; `admin-console/waitlist/<entry_id>/accept`, `/offer`; `book/holds/<hold_id>/resend`; `clinician/appointments/<appointment_id>/check-in`, `/complete`, `/no-show`, `/notes`; `patient/notifications/<notification_id>/read`; `patient/waitlist/<entry_id>/accept`.

## Blocks and files, in order

1. **`scheduling/views/pages/page_walk_support.py`**: extract `fill_route(route: str, ids: Mapping[str, UUID]) -> str` from the `re.sub` at the end of `path_of`. It replaces each `<uuid:name>` with `ids[name]`. `path_of` keeps its behaviour and calls it. Needed because leg B and leg C choose ids per caller and per leg, not from `make_world` alone.
2. **`scheduling/views/pages/test_page_access_walk.py`** (rename only, plus one skip):
   - make `_answer_of`, `_wanted`, `_expected_answer`, `_clients`, `_page_callbacks`, `_answers_get` public (`answer_of`, `wanted_answer`, `expected_answer`, `clients_by_caller`, `page_callbacks`, `answers_get`), because the new module imports them;
   - `returns_product_answer_when_pair_is_known_difference`: skip `names_record` rows. Its `path_of` fills no record id, so a record pair would be checked on the wrong page; leg A of the new module checks those pairs;
   - module docstring: one added sentence that record routes are walked in `test_page_access_records.py`.
3. **`scheduling/views/pages/record_walk_support.py`** (new, about 150 lines; no `test_` prefix, so pytest does not collect it). Its docstring says what the record walk relies on: the records, the ids per route, the accepted answers per leg, and the leak check.
   - `Records` (frozen dataclass): `world`, `appointment`, `other_appointment`, `rule`, `other_rule`, `time_off`, `other_time_off`, `other_patient`, `other_clinician`, `other_hold`, `holds: dict[Caller, UUID]`.
   - `records_of(world, clients) -> Records`: builds the others (below) and makes each caller's hold with `browser_post(clients[caller], details_path(world.clinic), FORM)`; the hold id comes from the `Location`. `other_hold` is made by a fresh `Client()`.
   - `ids_for(route, leg, caller, records) -> dict[str, UUID]`: the id for each `<uuid:name>` in the route, from the record table below; leg C gives `uuid4()`.
   - `accepted_answers(leg, row, caller) -> frozenset[str]`: leg A `{wanted_answer(row, caller)}`. Leg B: if the caller is admitted (row answer OK), `{FORBIDDEN, NOT_FOUND}`, else `{wanted}`. Leg C: if admitted, `{NOT_FOUND}`, else `{wanted}`.
   - `leaks(body: str, marks: Iterable[str]) -> bool`: true when any mark appears in the body. Marks are the other record's pk as text and the other owner's email (appointment: both the other patient's and the other clinician's; rule and time off: the other clinician's; hold: pk only; users: that user's email; clinicians: that clinician's email).
4. **`scheduling/views/pages/test_page_access_records.py`** (new, under 200 lines). Module docstring says what the tests hold: for each record page, each caller gets its row's answer on its own record (leg A); a refused or foreign record gets a refusal with nothing of the record in the response (leg B); a missing record gets 404 when admitted, the row's answer when refused (leg C); and the walked record routes equal the record GET routes the resolver serves. Tests:
   - `returns_row_answer_when_caller_gets_own_record_page` (leg A, 49 x 4 = 196 GETs);
   - `returns_refusal_without_trace_when_caller_gets_other_users_record_page` (leg B, 88 GETs);
   - `returns_404_or_row_answer_when_caller_gets_missing_record` (leg C, 196 GETs);
   - `returns_every_record_get_route_in_walk_when_resolver_lists_it` (the resolver's record routes that answer a GET equal the walked record routes; the 12 non-GET routes are absent from both).
   Each walk test builds `world = make_world()`, `clients = clients_by_caller(world)`, `records = records_of(world, clients)`, loops rows and callers, collects mismatches as `caller route: want X got Y` lines, and asserts the list is empty.

### Other records (built in `records_of`)

- `other_patient`: a User built the way `make_clinic` builds the patient.
- `other_clinician = add_clinician(world.clinic.department)`; it makes its own rule.
- `other_appointment = make("Appointment", patient=other_patient, clinician=other_clinician, appointment_type=world.clinic.appointment_type)`. Builder defaults: BOOKED, 2030-01-07 10:00 UTC. The other clinician avoids a clash with the world's appointment.
- `rule` = the rule of `world.clinic.clinician`; `other_rule` = the rule `add_clinician` made. Fetched with `.filter(clinician=...).first()` and an isinstance assert, as `make_world` does.
- `time_off = make("TimeOff", clinician=world.clinic.clinician)`; `other_time_off = make("TimeOff", clinician=other_clinician)`.

## Record per route and caller

Leg A = the caller's own record; B = the other record; C = a uuid4. A refused caller uses the same record as an owner would, so its refusal is judged on a real record.

| Family (routes) | Leg A record (all four callers) | Leg B record (visitor, patient, clinician, admin) | Leg C |
|---|---|---|---|
| Patient appointments (5): `patient/appointments/<appointment_id>/cancel`, `/reschedule`, `/reschedule/review`; `appointments/<appointment_id>/confirmation`, `/calendar.ics` | `world.appointment` | `other_appointment` | uuid4 |
| Clinician appointments (4): `clinician/appointments/<appointment_id>`, `/cancel`, `/reschedule`, `/reschedule/review` | `world.appointment` | `other_appointment` | uuid4 |
| Clinician availability (2): `clinician/availability/<rule_id>/edit`, `/delete` | `rule` | `other_rule` | uuid4 |
| Clinician time off (1): `clinician/time-off/<time_off_id>/delete` | `time_off` | `other_time_off` | uuid4 |
| Booking hold (1): `book/holds/<hold_id>/code` | the caller's own hold, made by the caller's client | `other_hold` (fresh browser) | uuid4 |
| Admin users (4): `admin-console/users/<record_id>`, `/edit`, `/delete`, `/deactivate` | `world.clinic.patient` | `other_patient` (admin not walked) | uuid4 |
| Admin clinicians (4): `admin-console/clinicians/<record_id>`, `/edit`, `/delete`, `/calendar` | `world.clinic.clinician` | `other_clinician` (admin not walked) | uuid4 |
| Admin appointments (4): `admin-console/appointments/<appointment_id>`, `/cancel`, `/reschedule`, `/reschedule/review` | `world.appointment` | `other_appointment` (admin not walked) | uuid4 |
| Admin managed lists, no owner (18): hospitals (3), specialties (3), departments (3), rooms (3), appointment types (3), `appointments/new/<appointment_type_id>/provider`, `/times`, `/review` (3) | `world.clinic.department.hospital_id`, `world.clinic.clinician.specialty_id`, `world.clinic.department.pk`, `world.room_id`, `world.clinic.appointment_type.pk` | none (exempt) | uuid4 |
| Public (6): `providers/<provider_id>`, `hospitals/<hospital_id>`, `specialties/<specialty_id>`, `book/<appointment_type_id>`, `/provider`, `/details` | the same record for all callers | none (no owner) | uuid4 |

Leg B row counts: 13 owned routes x 4 callers (52) plus 12 admin-console routes x 3 callers (36) = 88 GETs. Leg A 196, leg C 196, total 480 GETs. Each leg B on a row that refuses the caller accepts the row's answer, with the same leak check.

Per caller, on the owned families:
- Visitor: sign-in redirect on all three legs (refused by session).
- Patient: patient appointment families are admitted on its own appointment (200); on another's, 403 or 404. Clinician families: 403 by role on A, B and C.
- Clinician: clinician families are admitted on its own (200); on another's, 403 or 404. Patient families: 403 by role.
- Admin: 403 by role on the owned families; admin-console families admitted on A and C (200 and 404).

## Failing tests to write first (behaviour names, `returns_X_when_Y`)

The four tests above. Expected values, from the specification (12.3): a caller with a session on another user's record gets 403 (the walk also accepts 404, as the backlog allows) with nothing of that record; a caller without a session is sent to sign-in; a missing record is not_found for an admitted caller.

Expected to pass on the product as it stands. Red is shown by the mutation proof.

## Red and green proof

- **Mutation proof (red), in a working copy, reverted before commit:**
  1. in `test_page_access_rows_patient.py`, flip `patient/appointments/<uuid:appointment_id>/cancel` for the patient from OK to FORBIDDEN. Leg A must fail and name the caller and route;
  2. in `record_walk_support.py`, set `other_appointment.patient = world.clinic.patient`. Leg B for the patient must fail on the 200;
  3. drop `clinician/time-off/<uuid:time_off_id>/delete` from the walked set. The coverage test must fail.
- **Green:** `make test` passes for the two modules and the walk; `make lint` and `make gate` pass.
- The orchestrator judges "red for the right reason" from the three mutation results (no red gate runs for this process).

## Invariants and blast radius

- No product code, no row changes, no spec text, no `doc/security-review.md`, no `mutation-equivalents.txt`.
- Authorization is the product's: session cookie, role guard in `PageView`, ownership in the use cases, `made_this_hold`. The walk checks, it does not change them.
- Only GETs are walked. The setup POSTs (sign-in per signed-in caller, five hold POSTs) create test rows in the test database. Test data only.
- Blast radius: the suite; `page_walk_support.py` (`path_of` unchanged); `test_page_access_walk.py` (renames, one skip).

## Trust boundaries

- Browser to page: session cookie and role guard on the server; the walk sends GETs with the cookie a browser would send. Hold POSTs use `browser_post` (CSRF token and `Origin`).
- Path uuid (untrusted): a missing or foreign id gets 404 or 403 with nothing of the record; legs B and C check it.
- Hold cookie: `made_this_hold` decides the hold code page; a foreign hold gets 404.

## Domain entities (`CLAUDE.md` §3)

Visitor (no session; holds through a cookie), Patient (User), Clinician (ClinicianProfile and its User), Admin (User, role admin), Appointment (BOOKED), AvailabilityRule, TimeOff, BookingHold, Hospital, Department, Room, AppointmentType, Specialty. Not touched: WaitlistEntry, Notification, VerificationCode, SignInLink, AuditLogEntry, Session.

## Requests and cost

- 480 GETs (above) and about 3 sign-ins plus 5 hold POSTs per test, 3 tests, one `make_world` per test.
- Cost not measured in this stage. The green stage reports the wall time of the new module; if it is over 30 seconds, the slice stops and the orchestrator decides whether to share the world across the three walks.

## What I will not do

- No new abstraction beyond `fill_route`, `Records`, `records_of`, `ids_for`, `accepted_answers`, `leaks`.
- No change to the row tables or `KNOWN_DIFFERENCES` except a leg A pair the product gives differently (none expected from reading).
- No change to `make mutate` scope or the Makefile.

## Decisions I took (orchestrator: confirm or redirect)

- **Admin is not walked on leg B.** CLAUDE.md's Admin entity manages every hospital, so no admin-console record is another user's for the admin. Its leg A and leg C cover those routes.
- **18 admin-console routes are exempt from leg B.** Hospitals, specialties, departments, rooms, appointment types and the `appointments/new` steps belong to no user. There is no "another user's record" to test; their refusal by role is covered by leg A and leg C.
- **Public pages (6) have no leg B.** Spec 12.3: search and public pages need no session, and no user owns them.
- **Leg B and C mismatches never go into `KNOWN_DIFFERENCES`.** A leg B or C mismatch fails the test and goes into the review under "For the owner" with both answers. `KNOWN_DIFFERENCES` stays leg A only.
- **A leg A mismatch goes into `KNOWN_DIFFERENCES`** with both answers, and the row stays. None expected: the walk's appointment is BOOKED, and `patient_refusal.py:39-57` refuses only the cases its options block.
- **403 or 404 accepted on another's record.** Spec 12.3 says forbidden; the backlog accepts 404 as well.

## For the orchestrator to confirm in writing

- Visitor on a sign-in row gets the sign-in redirect on the own, other and missing record (spec 12.3 supports it). The walk proves it; this is not a product check yet.
- Process: `tests-and-docs`, mutation proof as red evidence.
- A signed-in caller's hold POST (`browser_post` to the details page) must create a hold. I have not verified it; if it does not, the green stage stops and reports rather than changing the caller.

## Files, deliberately not touched

Rows files (`test_page_access_rows*.py`), `test_page_access_table.py`, `drlibre-specs.md`, `doc/security-review.md`, `doc/backlog/*`, `doc/handover.md`, `mutation-equivalents.txt`, product code.

## Not in this run

- Sign-out (`sign-out`), the sign-in form pages (`sign-in/email-link`), `patient/notifications/read-all`, `admin-console/appointments/export`, `admin-console/settings/reminders`: form-only or non-GET; another run.
- The 12 record routes that answer no GET (listed in Reading): form-only; another run.
- Item 4 of the backlog (access section in `doc/security-review.md`, generated by a Makefile command and checked by a test): another run.

## Architect review

Second reading, against `CLAUDE.md`. Verdict: approve. The previous review's revision reason is met: leg B now walks visitor, patient and clinician on the 12 admin-console user-owned routes (36 GETs), and the 18 owner-less routes are exempt with a reason.

Checked against the repository:
- Row counts: 61 `names_record=True` rows across the five `test_page_access_rows*.py` files; 49 walked (13 owned + 12 admin-console owned + 18 owner-less admin lists + 6 public). Leg B: 13 x 4 + 12 x 3 = 88. Matches.
- Names used exist: `make_world`, `World.room_id`, `make_clinic` (`clinician`, `patient`), `add_clinician(department, rule_fields, **profile_fields)` (makes the rule), `KNOWN_DIFFERENCES`, `_answers_get`, `_page_callbacks`, `_answer_of`, `_wanted`, `_clients`, `path_of`, `_record_ids`. `path_of` maps unknown ids to `ZERO_UUID`, so `fill_route` must keep that; the plan's leg A ids replace it for record routes, which the plan does.
- Spec 12.3 (`drlibre-specs.md` 608-617) supports sign-in for a session-less visitor on every leg. It does not say the "missing record gives not_found" line applies only to role-admitted callers; the plan reads that in. Expected answers for refused callers stay as written, so the plan's reading holds for the walk, but the orchestrator confirms it (below).

Findings (none is a revision reason):
1. Coverage test source. `page_routes()` drops `NOT_HTML` (`appointments/<uuid:appointment_id>/calendar.ics`). The record coverage test must take resolver routes from `_page_callbacks()` filtered by `_answers_get`, not from `page_routes()`, or `calendar.ics` looks uncovered. Say so in the green stage; the mutation proof 3 would then also depend on it.
2. Admin on another user's admin-console record is not walked on leg B. The backlog says "must answer 403 or 404" for another user's record, but admin manages every hospital (CLAUDE.md), so the product answers 200 there by design. The exemption is the right call; the orchestrator confirms it in writing because it narrows the literal backlog text.
3. Leg C wanted answer for admitted callers is `NOT_FOUND` only. On public pages (`providers/`, `hospitals/`, `specialties/`, `book/<type>`) the walk assumes 404 for a missing id. The green stage reports any other answer; that is a finding, not a plan defect.
4. The 12 non-GET record routes are listed by introspection, not re-derived in this review. The coverage test (`returns_every_record_get_route_in_walk_when_resolver_lists_it`) is what proves the split; it must run before any leg test is trusted.
5. Cost: 480 GETs plus about 15 setup POSTs per test, not measured. The plan's 30-second stop rule is adequate for this slice.
6. Renaming `_answer_of` and siblings to public names so a second test module can import them is acceptable for a slice this size. A later run could move them to `page_walk_support.py` instead of importing from a test module.

Scope: one slice (item 3, record pages), with sign-out and form-only pages under `## Not in this run`. Process `tests-and-docs` fits: no product behaviour changes, and the mutation proof is the red evidence. Layers: test-only; no product code, rows, specs or ADRs touched. No new trust boundary beyond those listed; hold POSTs carry CSRF and `Origin` through `browser_post`.

For the orchestrator to confirm in writing: (a) visitor on a sign-in row gets the sign-in redirect on own, other and missing records; (b) admin is not walked on leg B for admin-console user-owned routes; (c) `tests-and-docs` with the mutation proof as red evidence; (d) a signed-in caller's hold POST creates a hold (unverified; the green stage stops and reports if not).

## Left for the orchestrator (green stage)

Product answers that differ from the table, recorded as `KNOWN_DIFFERENCES` pairs (leg A checks them on the own record; the row stays). Each is a question for the owner under "For the owner":
- `book/<uuid:appointment_type_id>/details`, clinician and admin: table OK, product 403. `scheduling/views/pages/booking_details.py:70-72` (`_refuse_staff`) refuses staff; spec 7.2 has bookings for visitors and patients.
- `admin-console/appointments/new/<uuid:appointment_type_id>/provider`, `/times`, `/review`, admin: table OK, product 302 to `/admin-console/appointments/new` without wizard state. Same pattern as the existing `new/service` pair.

Deviations from this plan, found while writing:
- Holds: a staff caller cannot make a hold in its own browser (403 above), and a signed-in patient's details POST books an appointment. So each caller's hold is made in a fresh visitor browser and its `drlibre_hold` cookie is copied to the caller's client. `made_this_hold` reads only that cookie. The hold POST answers 303.
- Slot query: a booking details page and a reschedule review answer 404 without `provider` and `starts_at`. The walk adds `provider` and `starts_at=2030-01-14T10:00:00Z` (a free Monday) to those routes only.
- Helper names: `conftest.py` fails a public non-test function in a test module, so the walk helpers keep their private names and the two new modules import them. A later run can move them to `page_walk_support.py`.
- Leak check marks: all other-record ids and both other owners' emails, for every leg B row (a superset of the per-family marks in the plan).
- Mutation proof, run in the working copy and reverted: (1) patient own cancel row OK to FORBIDDEN: leg A fails for the patient on own and missing legs; (2) other appointment owned by the world's patient at a free time: patient gets 200 on another's cancel page, leg B fails; (a first try at the same patient and time hit the no-overlap constraint in setup, so it was red for the wrong reason); (3) time-off delete dropped from the walk: `returns_every_record_get_route_in_walk_when_resolver_lists_it` fails.
- Gates: `make lint`, `make gate`, `make test` (5411 passed, 172 s) pass. The record module takes about 2 to 5 s.
