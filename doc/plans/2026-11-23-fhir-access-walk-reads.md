Slice: task 26b3 item 3 for `/fhir`, reads and searches only (28 rows, 132 requests). Tests and test data; no product file changes. Writes (create, update, delete) are the next run.

## Focal point

`test_support/fhir_access_rows.py` lists the access of every `/fhir` interaction. One test, `scheduling/views/test_fhir_access_walk.py`, sends each read and each parameterless search as each of four callers (visitor with no token, and a bearer token of a patient, a clinician and an admin) and compares the status with the row. For the five personal types it also reads a record of another user.

## Blocks, in file order

1. **`test_support/fhir_access_rows.py`** (edit).
   - Lines 1-7 (module docstring): say what the rows hold: the access answer per `/fhir` interaction for each caller, read by the route-coverage test and the reads-and-searches walk; `KNOWN_DIFFERENCES` lists where the product answers otherwise. Drop "own record only" (the walk now reads own and other records).
   - Lines 10-18 (`FhirAccessRow`): add `answer_for(caller) -> int`, mirroring `AccessRow.answer_for` in `scheduling/views/test_api_access_rows.py`.
   - New `class Caller(StrEnum)`: visitor, patient, clinician, admin.
   - New `@dataclass(frozen=True) class KnownDifference`: `resource`, `interaction`, `caller: Caller`, `row_answer`, `product_answer`. Docstring: both answers; the walk asserts the product's.
   - New `KNOWN_DIFFERENCES` (predicted, confirmed by the build run, see "Known differences" below).
   - Lines 80-81 (Slot read and search rows): see decision 1. The Slot search row changes from 200 to 400 for all four callers, basis "15.5 start range required".
   - Write rows (lines 22-79 create/update/delete, and 82-120 except the read and search rows) are not touched.

2. **`scheduling/views/test_fhir_access_world.py`** (new, about 80 lines). Module docstring: the records the reads and searches are walked on. `World` dataclass with the records below, and `clients: dict[Caller, Client]` (visitor: `client_for(None)`; others `client_for(token)`), built once per test (share sessions and tokens, plan item 5). `build_world() -> World` uses existing builders: `make_clinic` (line 245 of `scheduling/models/builders.py`) for hospital, department, bookable online type and clinician C; `add_clinician` (line 260) for clinician C2; `make("Room")`, `make("Appointment")` (direct, `waitlist_entry` unset), `make("WaitlistEntry", status="BOOKED")` plus an `Appointment` with `waitlist_entry` set (see decision 2), `make("Notification")` (line 171 defaults); tokens with `token_of(user)` from `scheduling/views/fhir_test_support.py` (line 25; it calls `issue_token`, the use case the management command calls). The rule of C is read with `AvailabilityRule.objects.get(clinician=C)`.
   Records, all with user ids from the builders:
   - P: patient with appointment AP_P (P, C, 10:00 on 2030-01-07), waitlist entry W (P, booked) with its appointment, notification N_P.
   - Q: other patient, appointment AP_R (Q, C2), waitlist entry W_Q (Q, booked), notification N_Q.
   - A: admin. C: clinician with a bookable online type. C2: second clinician, same department.
   - Token holders: P, C, A.
   - FREE: `slot_id(rule.pk, type.pk, 11:00 on 2030-01-07)` (`scheduling/domain/fhir_slot_id.py:15`), free because AP_P is 10:00-10:30.
   - Audit entries: the three `issue_token` calls write `api_client.issue` entries. E1 and E2 are two of them (AuditEvent reads).

3. **`scheduling/views/test_fhir_access_requests.py`** (new, about 90 lines). Module docstring: the request each `/fhir` read or search receives from each caller, sent as a FHIR client sends it: bearer token or none, no cookie, no `Origin` (`client_for`, `scheduling/views/fhir_test_support.py:30`).
   - `PATHS: dict[tuple[str, str], Callable[[World], str]]` for the 28 read and search rows: the path of the record each row reads (table below).
   - `OTHER_USER_PATHS: dict[str, Callable[[World], str]]` for the five personal types: the path of the other user's record.
   - `def send(world, caller, path) -> HttpResponse` (one line through `world.clients`).
   Each function under 15 lines.

4. **`scheduling/views/test_fhir_access_walk.py`** (new, about 80 lines). Module docstring: the walk of reads and searches: each caller's status for each row against its answer, and the other-user rule for personal reads (no token 401, a token 403, or the admin's own answer where admin may read the record).
   - `returns_the_row_answer_for_each_caller_when_the_walk_reads_and_searches`: for each of the 28 rows in table order and each caller, sends the row's path and collects mismatches `GET /fhir/Slot as patient: expected 200, got 400`. Expected = `KNOWN_DIFFERENCES` product answer for that (resource, interaction, caller), else `answer_for`.
   - `returns_401_or_403_when_a_caller_reads_another_users_record`: for each personal type and each caller, sends the other-user path. Expected: visitor 401; patient and clinician 403; admin: the row's answer (admin reads every record). Other-user reads are not overridable by `KNOWN_DIFFERENCES`: a difference there is a finding, and the test fails.
   - `returns_the_row_cell_and_a_product_answer_that_differs_when_a_difference_is_listed`: each `KNOWN_DIFFERENCES` entry has `row_answer` equal to the row's cell and `product_answer` different from it (the api walk's check, `test_api_access_walk.py:43-57`).
   - Clock frozen with `monkeypatch.setattr(clock, "now_utc", ...)` as in `test_fhir_patient.py:21-24`.

5. **`scheduling/views/test_fhir_access_table.py`**: unchanged (route coverage; already names the row set).

## Request count and records

Requests per type: public types (Organization, Location, HealthcareService, CodeSystem, ValueSet, Practitioner, PractitionerRole, Schedule, Slot): read 4 + search 4 = 8 each, 72 total. Personal types (Patient, Appointment, AppointmentResponse, Communication, AuditEvent): read 8 (each caller reads its may-use record and the other record) + search 4 = 12 each, 60 total. **132 requests**, in process through the Django test client. No sign-ins: tokens are issued by `issue_token` (DB writes, not requests). Cost: a few seconds (the api walk of 56 requests is the reference). FHIR read limit is 600 per address and user (`rate_limit_rules.py:39`); the walk sends at most about 33 per caller. No bad tokens, so no failure counter is touched.

Record each row reads (may-use record; the other record is listed for personal types):

| Row | Record read by the read | Search |
| --- | --- | --- |
| Organization read, search | hospital H (`Organization/<H>`) | no params |
| Location read, search | room R | no params |
| HealthcareService read, search | appointment type T (online) | no params |
| CodeSystem read, search | `CodeSystem/specialty` | no params |
| ValueSet read, search | `ValueSet/specialty` | no params |
| Practitioner read, search | user C (`Practitioner/<user id of C>`) | no params |
| PractitionerRole read, search | profile C | no params |
| Schedule read, search | availability rule of C | no params |
| Slot read, search | FREE (11:00 on 2030-01-07) | no params (400, see decision 1) |
| Patient read | P (own for patient; own patient of C; any for admin); other: Q | no params |
| Appointment read | AP_P (own; own calendar of C; any for admin); other: AP_R | no params |
| AppointmentResponse read | W (own for patient; admin any; clinician has none, same record); other: W_Q | no params |
| Communication read | N_P (recipient P); other: N_Q | no params |
| AuditEvent read | E1 (admin any; patient and clinician refused); other: E2 | no params |

## Expected answers

Read and search rows: the rows in `test_support/fhir_access_rows.py`, with the Slot search row corrected (decision 1). Other-user reads: visitor 401, patient 403, clinician 403, admin the row's answer (200 on Patient, Appointment, AppointmentResponse and AuditEvent; 403 on Communication).

## Known differences (predicted by reading the code; the build run confirms each)

Each entry: row answer, product answer, source.

1. Communication search, clinician: row 403, product 200 with total 0 (`fhir_communication_reads.py:38-41`: the search runs over the caller's own notifications, and a clinician has none).
2. Communication search, admin: row 403, product 200 with total 0 (same code path).
3. AppointmentResponse search, clinician: row 403, product 200 with total 0 (`fhir_response_reads.py:_part`, `booked.none()`; ADR 0007 says a clinician's search is an empty set).

No other differences are predicted. Any differing answer the build finds goes into `KNOWN_DIFFERENCES` with both answers, and the review's "For the owner" section cites the spec section.

## Decisions taken (the reader may reject)

1. **Slot search row changes 200 to 400.** Spec 15.5 says a start range of at most 31 days "is required"; `search_slots` answers 400 (`fhir_slot_reads.py:112-114`) for a search without one. The row was wrong against the spec, the product matches the spec, so the row is corrected and no `KNOWN_DIFFERENCES` entry is added. This is not a row changed to match the product against the spec: the spec gives 400. Alternative: keep 200 and list four differences. Rejected because the backlog says the table is written as the specification has it.
2. **AppointmentResponse uses one waitlist-booked record, built as data.** An AppointmentResponse exists only for a booked waitlist entry (ADR 0007, `fhir_response_reads.py` `_part`), so no direct booking can be read as one. The record is `WaitlistEntry(status=BOOKED)` with an `Appointment` whose `waitlist_entry` is set; its FHIR id is the entry id (ADR 0003). Only this row uses a waitlist record; the Appointment rows use direct bookings, so their model id is the FHIR id (ADR 0007).
3. **Admin's other-user read is 200 where the row says so.** Admin may read every record, so "a token 403 or 404" cannot hold for admin on the four types it may read. The rule is applied to the patient and clinician tokens; admin's expected answer is the row's.
4. **Other-user answers are not overridable by `KNOWN_DIFFERENCES`.** The owner's rule is a fixed answer, so a product difference there fails the test and becomes a finding.
5. **Clinician's may-use read of AppointmentResponse goes to W.** A clinician has no offer of its own; the same record gives the 403 the row states.

## Files touched, in order

1. `test_support/fhir_access_rows.py` (edit, blocks 1).
2. `scheduling/views/test_fhir_access_world.py` (new).
3. `scheduling/views/test_fhir_access_requests.py` (new).
4. `scheduling/views/test_fhir_access_walk.py` (new).

Not touched: any product file (`scheduling/`, `drlibre-specs.md`, ADRs); `test_fhir_access_table.py`; the write rows; `doc/security-review.md` (item 4); `doc/handover.md` (no product state changes); `doc/backlog/26b3-access-table.md` (the orchestrator updates it).

## Invariants and blast radius

- Server-side authorization: the walk uses the product's `resolve_token`, the product's routes and the product's use cases. It never sets a user, a role or a flag in the test to get an answer.
- Tokens come from `issue_token` (the command's use case); no token is hashed or stored by the test.
- Audit log: append-only; the walk reads it, the product writes its entries. The test does not truncate it.
- Double booking: AP_P and AP_R are different slots; FREE is an unbooked time.
- Blast radius: test data and tests only. A wrong expectation fails the walk; no product answer changes.

## Trust boundaries crossed

- The FHIR door: bearer token, no cookie, no `Origin`, with `enforce_csrf_checks=True` (`client_for`); `/fhir` is csrf-exempt by design (ADR 0005), so the walk checks the same thing a real client sees.
- Token resolution (`resolve_token`): unknown tokens are not sent; each caller's token is the one `issue_token` returned.
- Input: the walk sends no body (reads and searches only), and no query parameters except none at all. Response bodies are not asserted; the per-type test modules own them.

## Domain entities (CLAUDE.md section 3)

Visitor, Patient, Clinician, Admin (callers); ApiClient (token); Hospital, Room (Location), AppointmentType (HealthcareService), Department, ClinicianProfile (PractitionerRole), User (Practitioner), AvailabilityRule (Schedule), Slot (computed, FREE); Appointment, WaitlistEntry (AppointmentResponse), Notification (Communication), AuditLogEntry (AuditEvent).

## Failing tests first (red), and proof they can fail

- Red: the walk and other-user tests fail first with an import error (the new modules do not exist). Once the modules exist, the walk fails on the Slot search rows if block 1's correction is not yet in place (product 400, row 200): that is the red for the right reason.
- Proof the walk checks answers: change one row cell (e.g. Organization read anonymous to 404), run the walk, expect exactly one mismatch naming that cell, then revert.
- Proof of `KNOWN_DIFFERENCES` both ways, in the build: an entry whose product answer changes fails; an entry matching its row fails; an unlisted mismatch fails.
- Proof of the other-user rule: set a patient's expected other-user answer to 200 in a scratch copy, expect the test to fail; revert.

Behaviour names (`returns_X_when_Y`), expected values from the specification:
- `returns_the_row_answer_for_each_caller_when_the_walk_reads_and_searches`: each caller's status equals its row (spec 15.4), with Slot search 400 (spec 15.5).
- `returns_401_or_403_when_a_caller_reads_another_users_record`: no token 401; a patient or a clinician token 403 (spec 12.3: "a record that exists but belongs to someone else gives forbidden").
- `returns_the_row_cell_and_a_product_answer_that_differs_when_a_difference_is_listed`: every entry is a walked pair whose product answer differs from its row cell.

## Domain fact checks (read in code)

- `read_patient` (`fhir_patient_reads.py`): clinician sees patients with an appointment of its own; a missing or not-readable one is 403 for non-admins.
- `read_appointment` (`fhir_appointment_reads.py:36-42`): patient, clinician, admin scopes; 403 otherwise.
- `read_response` (`fhir_response_reads.py`): patient sees own booked entries; clinician and other patient get 403.
- `read_communication` (`fhir_communication_reads.py:29-35`): recipient only; 403 otherwise.
- `_refusal` (`fhir_audit_reads.py:36-39`): admin only; 401 without a user, 403 otherwise.
- Public parts (`fhir_reads.py`): `SERVICE`, `PRACTITIONER`, `ROLE`, `SCHEDULE` visible through `bookable_types` and `listable_profiles`; `PRACTITIONER` and `ROLE` ids are the user id and profile id.
- `read_slot` (`fhir_slot_reads.py:142-167`): a free slot is found from the rule, the type and the start.

## What I will not do

- No product code, no new dependency, no abstraction beyond `Caller`, `KnownDifference`, `World`, and the path tables.
- No xfail, skip or mark on a walked row.
- No login round trip: tokens come from `issue_token`, not from a request.
- No write rows, no `doc/security-review.md`, no generator, no drift test (item 4).
- No change to `test_fhir_access_table.py`.

## Not in this run

- Writes (create, update, delete) of every `/fhir` type: the next run, item 3 for writes.
- Item 4: the access section of `doc/security-review.md`, the Makefile generator and the drift test.
- Admin-specific records (an appointment or a patient only admin sees): not needed; admin's may-use record is the same set of records the patient and clinician use.

## Open points for the build

- Builder defaults are read in the build: the rule's weekday (`builders.py:149`, weekday 1 per the make_clinic docstring "Mondays") must include 11:00 on 2030-01-07; the online type default is `is_bookable_online` True (`builders.py:145`).
- The review (a later stage) lists every `KNOWN_DIFFERENCES` entry under "For the owner" with both answers and the section.
