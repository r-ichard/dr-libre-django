Slice: write rows of the admin-managed types (Organization, Location, HealthcareService, CodeSystem): 10 of the 23 write rows, 99 requests. The staff and patient write rows follow in the next run (`## Not in this run`).

## Focal point

`test_support/fhir_access_rows.py` lists the answer of every `/fhir` write interaction per caller. One walk, `scheduling/views/test_fhir_access_writes.py`, sends each of the 10 rows as each of four callers (visitor with no token, and a bearer token of a patient, a clinician and an admin). Each write goes to a record made for that write. The walk reads the record back as admin before and after, and checks the answer, the record and the audit log against the row.

## Blocks, in file order

1. **`test_support/fhir_access_rows.py`** (edit, lines 1-3, module docstring). Say the rows are read by the route-coverage test, the reads walk and the writes walk. No row changes in this run.

2. **`scheduling/views/test_fhir_access_walk.py`** (edit, lines 42-50 `_expected`). Move `_expected` to `test_fhir_access_requests.py` as `expected_answer` (public), so the writes walk uses the same KNOWN_DIFFERENCES rule. Update the one import in the reads walk (lines 10-17). Behaviour of the reads walk does not change.

3. **`scheduling/views/test_fhir_access_world.py`** (edit, line 98 `_clients`). Rename to `clients_for` (public). Its caller-to-client map is what the writes walk needs.

4. **`scheduling/views/test_fhir_access_write_cases.py`** (new, about 110 lines). Module docstring: the record each write changes, made fresh per write, and the body each caller sends. One `WriteCase` per row: `fresh_record(world)` (make a record, or nothing for create), `body(record, token)` (built from an admin read of the record, or the support builder for create), `path(record)`, and `accepted(...)` (what the record looks like after an accepted write). Each function under 15 lines.
   - Builders reused: `department_body`, `room_body`, `service_body` (`scheduling/views/fhir_organisation_support.py:32,60,43`); `with_concepts`, `concepts_of`, `concept` (`scheduling/views/fhir_specialty_support.py:36,30,11`); `make_clinic` (`scheduling/models/builders.py:245`) for the hospital and department; `make("Department", hospital=...)`, `make("Room", department=...)`, `make("AppointmentType", department=...)` for the fresh records.

5. **`scheduling/views/test_fhir_access_writes.py`** (new, about 100 lines). Module docstring: the walk of the 10 write rows of this slice; a refused write leaves the record and the audit log as they were; an accepted one changes them. One test: `returns_the_row_answer_and_the_record_state_when_each_caller_writes`. Helpers: `_state(record_path)` (admin GET status, body, ETag; AuditLogEntry count; table count), `_write(...)` (one request through `send` from `fhir_test_support.py:40`), `_mismatches(...)`.

## The 10 rows and the record each uses

Every caller gets its own fresh record (make per write), so no write changes another write's record. Admin reads use `token_of(role="ADMIN")`.

| Row | Record each caller writes | Body each caller sends | Admin (accepted) answer and change |
| --- | --- | --- | --- |
| Organization create | none; a new department of the clinic's hospital | `department_body(hospital, code)`, code `cardio-<caller>` | 201; one Department more, with that name; audit +1 |
| Organization update | fresh Department D (`make("Department", hospital=H)`) | admin read of D's Organization, `name` changed; `If-Match` = that read's ETag | 200; admin read shows the new name; audit +1 |
| Organization delete | fresh Department D, no dependents | none; `If-Match` = admin read's ETag | 200; admin read 404; Department row gone; audit +1 |
| Location create | none; a new room of the clinic's department | `room_body(department, code)`, code `room-<caller>` | 201; one Room more; audit +1 |
| Location update | fresh Room R | admin read of R's Location, `name` changed; `If-Match` | 200; new name read back; audit +1 |
| Location delete | fresh Room R, unused | none; `If-Match` | 200; admin read 404; audit +1 |
| HealthcareService create | none; a new appointment type of the clinic's department | `service_body(department, code)`, code `intake-<caller>` | 201; one AppointmentType more; audit +1 |
| HealthcareService update | fresh AppointmentType T | admin read of T's HealthcareService, `name` changed; `If-Match` | 200; new name read back; audit +1 |
| HealthcareService delete | fresh AppointmentType T, unused | none; `If-Match` | 200; admin read 404; audit +1 |
| CodeSystem update | the specialty list (`/fhir/CodeSystem/specialty`), one record, not fresh; callers run in enum order, so the admin writes last | admin read of the list with one concept appended (`concept("cardiology", "Cardiology")`); `If-Match` | 200; list has the new concept; audit +1 |

Decision on CodeSystem: the list is a singleton and cannot be fresh per write. Refused callers leave it unchanged, so each caller's before-read is the same list; the admin's accepted write is last.

## Requests

Per row and caller:
- create: one POST; for an accepted (admin) write one read-back GET of the new record. 4 + 1 = 5 per row, 15 for three rows.
- update and delete: admin GET before (the body and `If-Match` source), the write, admin GET after. 3 per caller, 12 per row. Update rows 3 x 12 = 36, delete rows 3 x 12 = 36, CodeSystem 12.
- Total: 15 + 36 + 36 + 12 = **99 requests**, in process. The audit log and the table counts are read with the ORM, not requests. Limit: the FHIR scope allows 600 per address (`scheduling/domain/rate_limit_rules.py:39`); one test sends 99, and rate-limit hits roll back per test.
- Cost: a few seconds (the reads walk sends 132).

## Expected answers

- Row cells as written in `FHIR_ACCESS_ROWS` for the 10 rows. Visitor 401, patient 403, clinician 403 (ADR 0008: admin only; no token 401; non-admin 403, answered before the body is read: `write_refusal`, `fhir_record_writes.py:44`).
- KNOWN_DIFFERENCES predicted for these rows: none. Reading the code, each admin write answers its row (`update_record`, `create_record`, `delete_record` through `admin_records.py`, `fhir_record_writes.py:53-110`). If the build finds one, it goes into KNOWN_DIFFERENCES with both answers and a "For the owner" line in the review.
- Refused write (any 4xx): admin read of the record before and after is identical (body and ETag); AuditLogEntry count unchanged; table count unchanged for create.
- Accepted write (2xx): the state in the table of the rows above; audit count +1 (CLAUDE.md: every write audited).

## Not walked here, and why

- A hospital's Organization: PUT and DELETE answer 405 with `Allow: GET` for every caller with a token (ADR 0008; `writes.py` `is_read_only_here`, pinned by `test_fhir_organisation_writes.py:134`). The row says "admin 200", and the walk uses a department, which is what the row names. The hospital case is a second answer for the same row and cannot be keyed in `KnownDifference` (no record field). Owner decision: keep it pinned by its own test (already there), and list it under "For the owner" in the review. This plan does not add it to KNOWN_DIFFERENCES.
- Hospital (Location) create, update and delete: the site writes are covered by `test_fhir_organisation_writes.py` (site body, 409 for a site with departments). The walk uses rooms.

## Invariants and blast radius

- Server-side authorization: the walk sends the caller's token and nothing else. Role, user and flags come from the product's `resolve_token`, never from the test.
- Tokens from `token_of` (`fhir_test_support.py:25`, the `issue_token` use case); no token stored by the test.
- Audit log is append-only; the test reads it and never deletes from it.
- Fresh records mean one write cannot change another's record; the CodeSystem singleton is the one exception, handled by ordering.
- Blast radius: test modules and one docstring. No product file. If the walk finds a product answer that differs, the product is not changed in this run.

## Trust boundaries crossed

- The FHIR door: bearer token, no cookie, no Origin, cross-site check enforced (`client_for`, `fhir_test_support.py:30`); `/fhir` is csrf-exempt by design (ADR 0005), so the walk sees what a real client sees.
- Body: sent as `application/fhir+json` (`FHIR_JSON`, `send`). The product checks it against the write shape (`writes.py` `_checked_body`) and the identity of the URL.
- `If-Match`: sent as the ETag of the admin read (`views.py:136-138` sets it on reads). The product checks it under the record's lock (ADR 0008).
- Input for create is a support body, not a read; codes are unique per write so a taken code (400) cannot hide an answer.

## Domain entities (CLAUDE.md section 3)

Visitor, Patient, Clinician, Admin (callers); ApiClient (token); Hospital; Department (FHIR Organization of type `dept`); Room (Location `ro`); AppointmentType (HealthcareService); Specialty list (CodeSystem); AuditLogEntry.

## What I will not do

- No product code, no new dependency, no new abstraction beyond `WriteCase` and the moved `expected_answer`.
- No xfail or skip on a walked row.
- No walk of the patient or staff rows (next run).
- No change to `doc/security-review.md` (item 4), `doc/handover.md`, `doc/backlog/26b3-access-table.md` (the orchestrator updates the backlog).
- No change to the rows or to the Slot search row (see "Flags").

## Failing tests first, and proof they can fail

- Order: write `test_fhir_access_write_cases.py` and the walk; run the walk. Any mismatch is a finding (the product answers differently), not a red to fix in this run. An import error is not the red; the red for the right reason is a mismatch on a named row.
- Proof the answer check fails: in the walk, set one expectation wrong in a scratch edit (Organization create as patient: 201 instead of 403); expect exactly one mismatch line naming it; revert.
- Proof the record check fails: in the scratch edit, expect the table count to grow on a refused create; expect a mismatch; revert.
- Proof the audit check fails: expect the audit count to stay the same on an accepted write; expect a mismatch; revert.

Behaviour name (`returns_X_when_Y`), expected values from the specification:
- `returns_the_row_answer_and_the_record_state_when_each_caller_writes`: each caller's answer equals its row (spec 15.4, ADR 0008); a refused write leaves the record and the audit log unchanged; an accepted write changes the record and adds an audit entry (CLAUDE.md, every write audited).

## Domain fact checks (read in code)

- `update_record_resource`, `delete_record_resource`, `create_record_resource` (`fhir_record_writes.py:53,74,100`): admin only (`admin_of`, line 112); missing record 404; stale version 412; dependents 409 (`delete_record`, `admin_records.py:80-105`).
- `delete_record` is a hard delete (`row.delete()`, line 97) with an audit entry (line 104): an accepted delete reads back 404.
- `update_specialty_list` (`fhir_specialty_writes.py:38`): admin only; takes the list lock; stale version 412.

## Flags for the orchestrator (not blocking)

1. Current branch state: the rows file keeps the Slot search cell at 200 and lists four KNOWN_DIFFERENCES (product 400). The reads plan's decision 1 said to correct the row to 400 and add no entry. The reads run took the other route. This run does not change it; the owner decides.
2. Hospital Organization 405 is not in the rows (see "Not walked").
3. The `Caller` StrEnum in the rows file has the same name as the use-case `Caller` (`scheduling/use_cases/fhir_caller.py`). Nit; not changed here.

## Not in this run

- Slice 2, the staff and patient write rows (13 rows, each with an other-user record for the refusals):
  - Practitioner update, delete: admin only; other clinician's user record for the 403s.
  - PractitionerRole create, update, delete: clinician updates own role (`notAvailable`); admin any; patient and clinician refused on create and delete.
  - Schedule create, update, delete: owning clinician only; admin 403.
  - Patient update: own patient (patient 200), another patient (403).
  - Appointment create: patient, clinician, admin each book a fresh free slot (201).
  - Appointment update: body-level status change to cancelled, fresh appointment per caller.
  - AppointmentResponse create: fresh waitlist offer per caller; clinician 403.
  - Communication update: recipient only (200); clinician and admin 403.
- Item 4 of task 26b3 (the access section of `doc/security-review.md`, the generator and the drift test).

## Architect review

Reviewed against CLAUDE.md and the task goal, and against the cited code (`test_fhir_access_walk.py:42-50`, `test_fhir_access_world.py:98`, `fhir_organisation_support.py`, `fhir_specialty_support.py`, `builders.py:245`, `fhir_test_support.py:30-44`, `views.py:136-138`, `test_fhir_organisation_writes.py:134`, ADR 0008). Line references and the 99-request count check out: 15 (create) + 36 + 36 (update and delete on three rows) + 12 (CodeSystem) = 99.

**Revise, reason 1: a product answer that differs from its row is left out of KNOWN_DIFFERENCES.** The task says a pair the product answers differently goes into KNOWN_DIFFERENCES with both answers. The plan, under "Not walked here", declines this for hospital `Organization` PUT and DELETE: the row says admin 200, the product answers 405 with `Allow: GET` (ADR 0008; pinned by `test_fhir_organisation_writes.py:134`). The stated reason is that `KnownDifference` has no record field. That is a reason to extend the key, not to drop the pair. Required: either add an optional record discriminator to `KnownDifference` (hospital or department) and list both pairs, or walk a hospital record for Organization update and delete and key the 405 answer to it. The plan must then state the new request count and the record each case uses. Owner decision on the 405 itself stays as a "For the owner" line in the review.

**Notes, not reasons to revise:**
- Slice: 10 of 23 write rows, the other 13 under `## Not in this run`. Coherent, and the product stays whole. Task 26b3 item 3 is not complete after this run; the orchestrator should keep it open in `doc/backlog/26b3-access-table.md`.
- CodeSystem row: the admin's accepted write appends `cardiology`. Each caller's before-read is the same list, and the admin writes last. Ordering is stated; fine. The plan should say the test rolls back so the list is unchanged for the next test.
- Fresh records per write, and the record each row uses, are stated for all 10 rows. Ownership of each record is clear.
- Red: the plan defines red as a named-row mismatch, with scratch-edit proofs for the answer, record and audit checks. Adequate. The first failing test is named as a behaviour with values from spec 15.4 and ADR 0008.
- Security: authorization comes from the bearer token only (`token_of`, `client_for`); no cookie or Origin; the cross-site check is enforced; `If-Match` is the admin read's ETag. Product side: `update_record_resource`, `delete_record_resource`, `create_record_resource` are admin-only; the audit log is append-only and only read. Adequate.
- Size: the test function sends 99 requests and must stay under 50 lines. Helpers `_state`, `_write`, `_mismatches` carry it. Keep `WriteCase` functions under 15 lines as planned.
- Entities use the CLAUDE.md vocabulary (Department, Room, AppointmentType, Specialty list, AuditLogEntry, ApiClient, Admin and the other callers).

Verdict written to `scratch/plan.verdict`: `revise`.
