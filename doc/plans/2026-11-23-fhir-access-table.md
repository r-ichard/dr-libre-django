# Plan: access table for the /fhir declaration (task 26b3, items 1 and 2)

Slice: items 1 and 2 only, for `/fhir`. Item 3 (the walk that sends requests), item 4 (the generated
section of `doc/security-review.md`) and any change to the `/api` table are not in this run.

## Focal point

One data table with one row per (resource type, interaction) of `FHIR_RESOURCES` in
`scheduling/domain/fhir_declaration.py`: 51 rows over 14 types (read and search-type are declared
per type; the rest are the writes the declaration names). Each row gives the status that a visitor
(no token), a patient, a clinician and an admin get. Two tests fail when a declared interaction has
no row, or a row names an interaction the declaration does not have. A third fails on a duplicate
row. No route is called. Behaviour changes: none.

## Ladder

Rung taken: an explicit data table beside the `/api` table, same style, same two-test shape, plus a
duplicate check.

Rungs rejected:
- Deriving the cells from `scheduling/views/fhir_spec_tables.py`. That file holds roles and ADR
  differences, not status codes; deriving would move the rules into the test, where a reader cannot
  see them.
- Any change to the declaration or the routes. The declaration is read, not edited.

## Cell rules (one place; every row follows them)

1. **Who may call** follows the letter of `drlibre-specs.md` 15.4. Where the letter names a caller
   and an ADR the letter does not contradict gives the status (401, 403, 201, 200), the ADR fills in.
2. **Precedence.** Where an ADR's answer on who may call differs from the letter of 15.4, the
   letter prevails and the difference goes under "For the owner". The spec is the owner's text and
   the brief is to write the table as the specification has it, so the test fails on a product that
   answers otherwise. This rule applies to every row, Communication and AppointmentResponse included.
3. **Scope of a cell.** A cell is the answer for the caller's own record, or for the collection where
   no record is named, for a body the caller may send. Other users' records, absent ids, inactive
   records, method-on-record outcomes (for example 405 on a hospital's `Organization` id, ADR 0008),
   and body refusals (400, 409, 412, 422) are not in cells. The walk (item 3) sends them.
4. **Visitor.** No token. A type the letter opens to anyone gives 200. A type with no public answer
   gives 401 (ADR 0006 "No token is 401"). Any write without a token is 401 (ADR 0006 "Writes", ADR
   0008, ADR 0009).
5. **Writes by a caller the letter does not name** are 403, answered before the body is read (ADR
   0008, ADR 0009).
6. **Success codes**: create 201, update 200, delete 200 (ADR 0006 "Writes").

## Blocks

1. `scheduling/views/fhir_access_rows.py` (new, data only). Frozen dataclass `FhirAccessRow`
   (`resource`, `interaction`, `visitor`, `patient`, `clinician`, `admin`, `basis`) and the tuple
   `FHIR_ACCESS_ROWS`, one line per row, within the 100-column limit. The `basis` is a short
   reference to the letter of 15.4 and, where used, the ADR. The file name has no `test_` prefix,
   so pytest does not collect it. Expected size about 70 lines, far under the cap.
2. `scheduling/views/test_fhir_access_table.py` (new, tests). Builds the set of declared pairs from
   `FHIR_RESOURCES` (each type's `interactions`) and the set of row pairs from `FHIR_ACCESS_ROWS`,
   compares them both ways, and counts duplicates.

## Files, in order

1. `scheduling/views/test_fhir_access_table.py`: the three tests (red first, see below).
2. `scheduling/views/fhir_access_rows.py`: the table. Red stage: an empty tuple, so the first test
   fails on the 51 unlisted pairs. Green stage: the 51 rows.
3. Proof that the tests guard: remove one row locally, the first test fails; add a row for
   `("ValueSet", "create")`, the second fails; duplicate a row, the third fails. Revert all three
   before the commit.
4. `make lint`, `make test`, `make gate`.

Files deliberately not touched: `scheduling/domain/fhir_declaration.py`, `scheduling/views/fhir_spec_tables.py`,
`scheduling/views/test_fhir_surface.py`, `scheduling/views/test_api_access_rows.py`,
`scheduling/views/test_api_access_table.py`, `drlibre-specs.md`, `doc/adr/*`, `doc/security-review.md`,
`Makefile`, `doc/backlog/*`.

## Tests (behaviour names, expected values from the specification)

- `returns_no_interaction_unlisted_when_the_declaration_is_read`: every (type, interaction) the
  declaration names has a row. Fails on an empty table.
- `returns_no_row_for_a_removed_interaction_when_the_declaration_is_read`: every row names a
  (type, interaction) the declaration has. Fails on a row for an interaction it does not have.
- `returns_one_row_per_interaction_when_the_table_is_read`: no (type, interaction) appears twice.

No test checks a cell here. Cells are the answer the specification gives; whether the product gives
it is the walk's question. A product that answers differently is a finding, so cells are not tuned
to what the code does today.

Module docstrings state what the tests hold (the table lists each declared interaction once, and
nothing else), with no task number.

## The table

Interactions as the declaration names them: `read`, `search-type`, `create`, `update`, `delete`.
A method the declaration does not name is not a row; it is a 405 (ADR 0005), a route question for
item 3.

Rows (resource, interaction: visitor / patient / clinician / admin), with the short basis. The file
holds the same rows, each with its full basis.

| Resource | Interaction | Visitor | Patient | Clinician | Admin | Basis (short) |
| --- | --- | --- | --- | --- | --- | --- |
| Organization | read | 200 | 200 | 200 | 200 | 15.4 anyone, active only |
| Organization | search-type | 200 | 200 | 200 | 200 | 15.4 anyone, active only |
| Organization | create | 401 | 403 | 403 | 201 | 15.4 admin; ADR 0008 |
| Organization | update | 401 | 403 | 403 | 200 | 15.4 admin; ADR 0008 |
| Organization | delete | 401 | 403 | 403 | 200 | 15.4 admin; ADR 0008 |
| Location | read | 200 | 200 | 200 | 200 | 15.4 anyone, active only |
| Location | search-type | 200 | 200 | 200 | 200 | 15.4 anyone, active only |
| Location | create | 401 | 403 | 403 | 201 | 15.4 admin |
| Location | update | 401 | 403 | 403 | 200 | 15.4 admin |
| Location | delete | 401 | 403 | 403 | 200 | 15.4 admin |
| HealthcareService | read | 200 | 200 | 200 | 200 | 15.4 anyone, active only |
| HealthcareService | search-type | 200 | 200 | 200 | 200 | 15.4 anyone, active only |
| HealthcareService | create | 401 | 403 | 403 | 201 | 15.4 admin |
| HealthcareService | update | 401 | 403 | 403 | 200 | 15.4 admin |
| HealthcareService | delete | 401 | 403 | 403 | 200 | 15.4 admin |
| CodeSystem | read | 200 | 200 | 200 | 200 | 15.4 anyone, active only |
| CodeSystem | search-type | 200 | 200 | 200 | 200 | 15.4 anyone, active only |
| CodeSystem | update | 401 | 403 | 403 | 200 | 15.4 admin; ADR 0008 |
| ValueSet | read | 200 | 200 | 200 | 200 | 15.4 anyone, active only |
| ValueSet | search-type | 200 | 200 | 200 | 200 | 15.4 anyone, active only |
| Practitioner | read | 200 | 200 | 200 | 200 | 15.4 anyone, public fields; staff all |
| Practitioner | search-type | 200 | 200 | 200 | 200 | 15.4 anyone, public fields; staff all |
| Practitioner | update | 401 | 403 | 403 | 200 | 15.4 admin; ADR 0006 clinician may not |
| Practitioner | delete | 401 | 403 | 403 | 200 | 15.4 admin |
| PractitionerRole | read | 200 | 200 | 200 | 200 | 15.4 anyone, public fields; staff all |
| PractitionerRole | search-type | 200 | 200 | 200 | 200 | 15.4 anyone, public fields; staff all |
| PractitionerRole | create | 401 | 403 | 403 | 201 | 15.4 admin; ADR 0009 |
| PractitionerRole | update | 401 | 403 | 200 | 200 | 15.4 clinician own notAvailable; ADR 0009 |
| PractitionerRole | delete | 401 | 403 | 403 | 200 | 15.4 admin; ADR 0009 |
| Schedule | read | 200 | 200 | 200 | 200 | 15.4 anyone |
| Schedule | search-type | 200 | 200 | 200 | 200 | 15.4 anyone |
| Schedule | create | 401 | 403 | 201 | 403 | 15.4 owning clinician; ADR 0006 |
| Schedule | update | 401 | 403 | 200 | 403 | 15.4 owning clinician; ADR 0006 |
| Schedule | delete | 401 | 403 | 200 | 403 | 15.4 owning clinician; ADR 0006 |
| Slot | read | 200 | 200 | 200 | 200 | 15.4 anyone, free slots only |
| Slot | search-type | 200 | 200 | 200 | 200 | 15.4 anyone, free slots only |
| Patient | read | 401 | 200 | 200 | 200 | 15.4 patient, clinician, admin; ADR 0006 |
| Patient | search-type | 401 | 200 | 200 | 200 | 15.4 patient, clinician, admin; ADR 0006 |
| Patient | update | 401 | 200 | 403 | 200 | 15.4 patient, admin; ADR 0006 |
| Appointment | read | 401 | 200 | 200 | 200 | 15.4 patient, clinician, admin |
| Appointment | search-type | 401 | 200 | 200 | 200 | 15.4 patient, clinician, admin |
| Appointment | create | 401 | 201 | 201 | 201 | 15.4 and 5.4 |
| Appointment | update | 401 | 200 | 200 | 200 | 15.4 and 5.6; body-level (walk) |
| AppointmentResponse | read | 401 | 200 | 403 | 200 | 15.4 patient own, admin |
| AppointmentResponse | search-type | 401 | 200 | 403 | 200 | 15.4 patient own, admin; ADR 0007 owner |
| AppointmentResponse | create | 401 | 201 | 403 | 201 | 15.4 patient own offer, admin; ADR 0007 owner |
| Communication | read | 401 | 200 | 403 | 403 | 15.4 recipient; ADR 0005 owner |
| Communication | search-type | 401 | 200 | 403 | 403 | 15.4 recipient; ADR 0005 owner |
| Communication | update | 401 | 200 | 403 | 403 | 15.4 recipient; ADR 0005 owner |
| AuditEvent | read | 401 | 403 | 403 | 200 | 15.4 admin; ADR 0007 |
| AuditEvent | search-type | 401 | 403 | 403 | 200 | 15.4 admin; ADR 0007 |

Cell notes that a reader would otherwise guess:

- Own-record scope (rule 3): clinician `Patient` read is own patients (one with an appointment with
  them, ADR 0006); clinician `Appointment` read and update is own calendar; clinician `Schedule`
  writes and `PractitionerRole` update are the owning clinician's; patient `Appointment` create is
  self only (5.4); patient `Communication` and `Patient` answers are own record.
- `Appointment` update, patient 200 means a body the patient may send: cancel or move (5.6). Staff-only
  status changes (check-in, complete, no-show) from a patient are a body-level 403 for the walk.
- `Practitioner` update, clinician 403: §15.4 gives a clinician only `notAvailable`, which lives on
  `PractitionerRole`; ADR 0006 "A clinician may not update".
- `Schedule` writes, admin 403: §15.4 names "the owning clinician" only; ADR 0006 says any other token,
  an admin's too, is 403.
- `Patient` update, clinician 403: §15.4 names the patient and admin; ADR 0006.
- `Organization`, `CodeSystem` update and delete: admin 200 holds for a department and the code list.
  A hospital's id is 405 (ADR 0008), a walk case, not in the cell.
- `AuditEvent`, visitor 401: the type has no public answer (rule 4).

## Owner decisions (conflicts; the table follows the letter, the test does not change if the owner
rules otherwise, only the row)

1. `Communication` admin 403. §15.4 names "the recipient" only; ADR 0005 says a clinician's or an
   admin's token sees "every record". Letter applied. Owner: accept, or grant admin read.
2. `Communication` clinician 403. Notifications go to the patient only (§11), so a clinician is never
   the recipient. ADR 0005's "every record" would give 200. Letter applied. Owner decides.
3. `AppointmentResponse` search, clinician 403. §15.4 names the patient (own) and admin. ADR 0007
   gives a clinician an empty search, 200 total 0. Letter applied; ADR 0007's answer is the owner's
   to keep or change.
4. `AppointmentResponse` create, admin 201. §15.4 names "the patient (own offer), admin"; ADR 0007
   says "Only the offered patient may accept". Letter applied; the walk will show the refusal if the
   owner keeps ADR 0007's wording. Owner decides.
Each goes into `doc/security-review.md` under "For the owner" when the review is written, with its
section number. The spec is not edited.

## Invariants that must not break

- No product behaviour changes. The declaration and routes are read, not edited.
- The table is the specification's answer, written out. It does not follow the code.
- The table and the declaration agree in both directions and once per pair.

Blast radius: two new files under `scheduling/views/`. No product code imports them. The test
imports `FHIR_RESOURCES` read-only.

## Trust boundaries crossed

None. No request, no token, no input is read. Tokens and sessions are not created.

## Domain entities (CLAUDE.md §3 vocabulary)

Visitor (no token), Patient, Clinician, Admin, ApiClient (a bearer token, one user's rights),
Organization (a Hospital or a Department, ADR 0005), Location (a Room, or a Hospital), Schedule
(AvailabilityRule), Slot, Appointment, AppointmentResponse (the accept of a WaitlistEntry offer),
Communication (Notification), AuditEvent (AuditLogEntry), Practitioner and PractitionerRole
(ClinicianProfile), HealthcareService (AppointmentType), CodeSystem and ValueSet (Specialty list).

## Costs and counts

Zero requests, zero database access (no `django_db` mark). A pure comparison of 51 rows with 51
declared pairs in memory: well under a millisecond. The walk's request count is item 3's plan.

## What I will not do

- No route call, no client, no token issued in the test.
- No Makefile target and no generated document (item 4).
- No shared base or abstraction with the `/api` table. Two small files in the same style.
- No change to `fhir_spec_tables.py` or its surface test.
- No task number in any module docstring.
- No rename of `scheduling/views/test_api_access_rows.py`. Its name and its task-number docstring are
  the review's finding for the `/api` table; a separate change.

## Risks

- Two copies of the role matrix: `fhir_spec_tables.py` (roles and ADR differences) and this table
  (status codes). They agree on every row checked. A later run may derive one from the other; this
  run does not.
- Cells follow the letter of 15.4 and the rules above. Where the product answers differently, the walk
  reports it; this run does not fail on a cell.
- Cells cover access only. A rule refusal (400, 409, 412, 422) is not in a cell.
- Owner decisions 1 to 4 may move a row. The test checks pairs, so a changed row still passes this run.

## Architect review (addressed)

Verdict `revise` on the previous draft. Each reason, and the change:

1. Row count. The declaration has 51 pairs (Organization, Location, HealthcareService 5 each;
   PractitionerRole, Schedule 5 each; Practitioner, Appointment 4 each; CodeSystem, Patient,
   AppointmentResponse, Communication 3 each; ValueSet, Slot, AuditEvent 2 each). The focal point, the
   red and green steps now say 51.
2. Communication. Now the letter: recipient only. Notifications go to patients (§11), so the clinician
   is 403. Admin 403. Both are owner decisions 1 and 2.
3. Precedence. Stated once in cell rule 2, applied to every row (Communication, AppointmentResponse
   included).
4. Cell scope. Stated once in cell rule 3, with the own-record cases listed under the table.
5. AppointmentResponse create, admin. Letter 201 kept; owner decision 4.
6. Basis. Drafted per row, short, citing 15.4 and the ADR. ADR 0010 is proposed and is cited nowhere
   here.
7. Kept: rows outside these reasons agree with 15.4 and `fhir_spec_tables.py`.

## Architect review

Verdict `approve`. The previous `revise` reasons are addressed: the row count is 51 (declaration
pairs per type: 5, 5, 5, 3, 2, 4, 5, 5, 2, 3, 4, 3, 3, 2; the table has the same per-type counts);
precedence is one rule (cell rule 2) applied to every row; cell scope is one rule (cell rule 3);
Communication follows the letter and is listed as owner decisions 1 and 2; AppointmentResponse
create admin 201 follows the letter and is owner decision 4.

Non-blocking, to fix in the green stage:
1. Practitioner update, clinician 403. The basis cites "ADR 0006 clinician may not". That sentence
   (ADR 0006, "Patient" paragraph) concerns Patient update. The basis for this row is 15.4 alone:
   the clinician's update right is own `notAvailable` on PractitionerRole, not Practitioner.
2. The duplicate-pair test is a third test beyond the two the task asks for. Keep it: it is cheap
   and backs the "once per pair" invariant.
3. `fhir_access_rows.py` has no `test_` prefix, unlike the `/api` precedent
   `test_api_access_rows.py`. The reason (pytest must not collect a data module) is sound. Say it
   in the module docstring so a reader does not take the naming as an accident.

Checked, no finding: `FHIR_RESOURCES` interactions match the table's rows for all 14 types; the
Organization, Location, HealthcareService, CodeSystem, ValueSet, Schedule, Slot, Patient rows
match 15.4 and ADRs 0006 and 0008; the PractitionerRole and Communication rows match 15.4 and ADR
0009 and ADR 0005. Size is far under the caps; no product code is touched; no request is made.
