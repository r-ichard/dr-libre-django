Slice: write rows of the admin-managed types (Organization, Location, HealthcareService, CodeSystem): 10 of the 23 write rows, 12 write cases, 123 requests. The staff and patient write rows follow in the next run (`## Not in this run`).

## Focal point

`test_support/fhir_access_rows.py` lists the answer of every `/fhir` write interaction per caller. One walk, `scheduling/views/test_fhir_access_writes.py`, sends each case as each of four callers (visitor with no token, and a bearer token of a patient, a clinician and an admin). Each write goes to a record made for that caller. The walk reads the record back as admin before and after, and checks the answer, the record and the audit log against the row.

This revision answers the architect's reason 1: the hospital Organization PUT and DELETE pair is walked and listed in KNOWN_DIFFERENCES with both answers. `KnownDifference` gains a `record` field, so an entry can name the record kind it holds for.

## Blocks, in file order

1. **`test_support/fhir_access_rows.py`** (edit). Module docstring: read by the route-coverage test, the reads walk and the writes walk. `KnownDifference` gets `record: str = ""` (last field; `""` = every record, otherwise the record kind the pair holds for) and its docstring says so. Add two entries to `KNOWN_DIFFERENCES`: `KnownDifference("Organization", "update", Caller.ADMIN, 200, 405, record="hospital")` and the same for `"delete"`. The seven existing entries do not change. No row changes.

2. **`scheduling/views/test_fhir_access_requests.py`** (edit). Add `expected_answer(row, caller, record="")` (public), moved from `_expected` in the reads walk: returns the product answer of the first `KNOWN_DIFFERENCES` entry whose resource, interaction and caller match and whose `record` is `""` or equals `record`; else `row.answer_for(caller)`. Module docstring: add that it also gives the expected answer of a request. Nothing else changes.

3. **`scheduling/views/test_fhir_access_walk.py`** (edit). Delete `_expected`; call `expected_answer(row, caller)` (import from requests). Reads behaviour does not change.

4. **`scheduling/views/test_fhir_access_write_cases.py`** (new, about 110 lines). Module docstring: the records each write changes, made fresh per caller, the body each caller sends, and that a write without a case fails the walk. One frozen dataclass `WriteCase` per row or hospital variant: `resource`, `interaction`, `record` (`""` or `"hospital"`), `fresh(world, caller)` (makes the record; `None` for create), `path(target)`, `body(admin_client, target)` (an admin read with the change applied; `None` for delete and for create's support body), `accepted(world, target, created_id)` (the record state after an accepted write, as a bool). Each function under 15 lines. Builders reused: `department_body`, `room_body`, `service_body` (`scheduling/views/fhir_organisation_support.py:32,60,43`); `concept` (`scheduling/views/fhir_specialty_support.py:11`); `make("Hospital")`, `make("Department", hospital=...)`, `make("Room", department=...)`, `make("AppointmentType", department=...)` (`scheduling/models/builders.py:206`, defaults at 104-130).

5. **`scheduling/views/test_fhir_access_writes.py`** (new, about 110 lines). Module docstring: the walk of the 10 write rows as 12 cases, each caller's answer against its row (`expected_answer`), a refused write leaves the record and the audit log as they were, an accepted one changes them. Tests:
   - `returns_the_row_answer_and_the_record_state_when_each_caller_writes`
   - `returns_a_case_for_each_listed_write_row_when_the_walk_is_built` (the 10 `(resource, interaction)` pairs of this slice are in a tuple; each has a case; the next run extends the tuple).
   Helpers, each under 20 lines: `_state(client, path)` (admin GET: status, body, ETag); `_audit_count()` and `_table_count(model)` (ORM); `_write(client, method, path, body, etag)` (one request through the caller's `Client`, see below); `_mismatches(...)`.
   The walk sends through `world.clients[caller]` (`test_fhir_access_world.py`, built by `client_for(token)`): `client.post/put(path, data=json.dumps(body), content_type=FHIR_JSON, headers=...)`, `client.delete(path, headers=...)` with no body and no Content-Type, as a FHIR client sends a DELETE. `_says_not_json` takes CONTENT_LENGTH 0 as no body (`write_body.py:22`), so no 415.

No change to `test_fhir_access_world.py`: the world already holds the four caller clients, so `_clients` is not renamed.

## The 12 cases, the record each caller writes, and the requests

Each caller gets its own fresh record, so no write changes another's record. `world` is `_build_world()` (`test_fhir_access_world.py`), which holds a department (`world.room.department`), a hospital (`.hospital`), a room and an appointment type. The admin's read of the record supplies the body and `If-Match`; `If-Match` is the ETag of that read.

| # | Row (case) | Record each caller writes | Body each caller sends | Admin accepted answer and change |
| --- | --- | --- | --- | --- |
| 1 | Organization create | none; a new department under `world.room.department.hospital` | `department_body(hospital, "cardio-<caller>")` | 201; one more Department with that code; audit +1 |
| 2 | Location create | none; a new room under `world.room.department` | `room_body(department, "room-<caller>")` | 201; one more Room; audit +1 |
| 3 | HealthcareService create | none; a new appointment type under `world.room.department` | `service_body(department, "intake-<caller>")` | 201; one more AppointmentType; audit +1 |
| 4 | Organization update (department) | fresh Department D: `make("Department", hospital=world.room.department.hospital)` | admin read of D's Organization, `name` changed | 200; admin read shows the new name; audit +1 |
| 5 | Organization update (hospital, `record="hospital"`) | fresh Hospital H: `make("Hospital")` | admin read of H's Organization, `name` changed | 405 with `Allow: GET` for admin (KNOWN_DIFFERENCES); H unchanged; audit unchanged |
| 6 | Organization delete (department) | fresh Department D, no dependents | none; `If-Match` | 200; admin GET 404; Department row gone; audit +1 |
| 7 | Organization delete (hospital, `record="hospital"`) | fresh Hospital H | none; `If-Match` | 405 with `Allow: GET` for admin (KNOWN_DIFFERENCES); H unchanged; audit unchanged |
| 8 | Location update | fresh Room R: `make("Room", department=world.room.department)` | admin read of R's Location, `name` changed | 200; new name read back; audit +1 |
| 9 | Location delete | fresh Room R, unused | none; `If-Match` | 200; admin GET 404; Room row gone; audit +1 |
| 10 | HealthcareService update | fresh AppointmentType T: `make("AppointmentType", department=world.room.department)` | admin read of T's HealthcareService, `name` changed | 200; new name read back; audit +1 |
| 11 | HealthcareService delete | fresh AppointmentType T, unused | none; `If-Match` | 200; admin GET 404; row gone; audit +1 |
| 12 | CodeSystem update (`specialty`) | the specialty list, one record, not fresh | admin read of the list, `concept` gets one more entry (`concept("cardiology", "Cardiology")`), `count` recomputed | 200; list has `cardiology`; audit +1 |

Row 12 is the one shared record. Refused callers leave the list as it was, so every caller reads the same before-state; the admin is last in `Caller` order (visitor, patient, clinician, admin), so its accepted change comes after every refusal.

Requests (per caller, the same for each case):
- create (rows 1 to 3): one POST per caller, and for the admin's accepted write one GET of the new record (`id` from the 201 body). 4 + 1 = 5 per row, **15**.
- update and delete (rows 4 to 11): admin GET before (body and `If-Match` source), the caller's write, admin GET after. 3 per caller, 12 per case; 8 cases, **96**.
- CodeSystem (row 12): admin GET before, the write, admin GET after, 3 per caller, **12**.
- Total: 15 + 96 + 12 = **123 requests** through the test client, in process. Audit count and table counts are read with the ORM. The FHIR scope allows 600 per address (`scheduling/domain/rate_limit_rules.py:39`); 123 is under it, and the test is its own transaction.
- Cost: a few seconds. The reads walk sends 132.

## Expected answers

- Row cells from `FHIR_ACCESS_ROWS` for all 10 rows. For every case: visitor 401, patient 403, clinician 403, all answered before the body is read (`refusal_before_body`, `scheduling/use_cases/fhir_resources.py:145`; `is_read_only_here` runs after it, for PUT and DELETE, `writes.py:50-55`). For the hospital cases (5, 7) the visitor and patient/clinician cells are the row's; only admin differs.
- KNOWN_DIFFERENCES pairs: rows 5 and 7 only, admin 200 (row) and 405 (product). No other difference is expected for this slice; any other mismatch is a finding (the product answers differently), not a red to fix in this run.
- Refused write (any 4xx or 405): admin GET of the record before and after is identical (status, body, ETag); the AuditLogEntry count taken immediately before and after the write request is unchanged; for create, the table count is unchanged.
- Accepted write (2xx): the state in the table; audit count +1 around the write.

## Invariants and blast radius

- Server-side authorization: the walk sends the caller's bearer token only. Role, user and flags come from `resolve_token` in the product, never from the test.
- Tokens come from `token_of` through `world.clients`; the test stores none.
- The audit log is append-only; the test counts it and never deletes from it. Counts are read around the write only, so an audited read would not skew them. The walk checks reads write no audit entry; if one does, the plan's count rule still holds because no read sits between the two counts.
- Fresh records mean one write cannot change another's record. The CodeSystem list is the one shared record, handled by ordering.
- Blast radius: test modules, `test_support/fhir_access_rows.py` (one field, two entries, one docstring), and the reads walk's helper move. No product file. The product is not changed in this run.

## Trust boundaries crossed

- The FHIR door: bearer token, no cookie, no Origin, cross-site check enforced (`client_for`, `fhir_test_support.py:30`); `/fhir` is csrf-exempt by design (ADR 0005), so the walk sees what a real client sees.
- Body: sent as `application/fhir+json`. The product checks it against the write shape (`writes.py` `_checked_body`) and the URL's identity.
- `If-Match`: the ETag of the admin read, sent by the caller. The product checks it under the record's lock (ADR 0008). A refused caller's `If-Match` is valid, so the refusal is the caller's, not a stale version.
- Create bodies are support builders, not reads; codes are unique per caller so a taken code (400) cannot hide an answer.

## Domain entities (CLAUDE.md section 3)

Visitor, Patient, Clinician, Admin (callers); ApiClient (token); Hospital; Department (FHIR Organization of type `dept`); Room (Location `ro`); AppointmentType (HealthcareService); Specialty list (CodeSystem); AuditLogEntry.

## The hospital 405, and what the review says

The product answers a hospital's Organization PUT and DELETE with 405 and `Allow: GET` for an admin (ADR 0008; pinned by `test_fhir_organisation_writes.py:134`). The row says admin 200 and the specification (15.4) says admin. This is a finding: the walk holds the product's 405 in KNOWN_DIFFERENCES with the row's 200 beside it, and the review names both pairs under "For the owner" with the section (15.4). The owner decides whether the spec or the product changes. This run does not change the product or the spec.

## What I will not do

- No product code, no new dependency, no new abstraction beyond `WriteCase` and the public `expected_answer`.
- No xfail or skip on a walked case.
- No walk of the patient or staff write rows (next run).
- No change to `test_fhir_access_world.py` (no rename needed), to `doc/security-review.md` (item 4), `doc/handover.md`, or `doc/backlog/26b3-access-table.md` (the orchestrator updates the backlog).
- No change to the existing KNOWN_DIFFERENCES entries.

## Failing tests first, and proof they can fail

- Order: write `test_fhir_access_write_cases.py` and the walk; run the walk. A mismatch line names a case and a caller. A mismatch on rows 5 or 7 for the admin is expected to be absent, because the pairs are listed; if it appears, the product answer is not 405 and the entry is wrong.
- Proof the answer check fails: in a scratch edit, set one expectation wrong (Organization create as patient: 201 instead of 403); expect exactly one mismatch line naming it; revert.
- Proof the record check fails: in a scratch edit, expect the table count to grow on a refused create; expect a mismatch; revert.
- Proof the audit check fails: in a scratch edit, expect the audit count to stay the same on an accepted write; expect a mismatch; revert.
- Proof the coverage check fails: in a scratch edit, drop one case from the list; expect the coverage test to name the row; revert.

Behaviour names (`returns_X_when_Y`), expected values from the specification:
- `returns_the_row_answer_and_the_record_state_when_each_caller_writes`: each caller's answer equals its row, or its KNOWN_DIFFERENCES pair for the hospital cases (spec 15.4, ADR 0008); a refused write leaves the record and the audit log unchanged; an accepted write changes the record and adds one audit entry (CLAUDE.md, every write audited).
- `returns_a_case_for_each_listed_write_row_when_the_walk_is_built`: each of the 10 listed rows has a case, so no row is skipped silently.

## Domain fact checks (read in code)

- `create_record_resource`, `update_record_resource`, `delete_record_resource` (`scheduling/use_cases/fhir_resources.py`, through `fhir_record_writes`): admin only; missing record 404; stale version 412; dependents 409.
- `delete_record` is a hard delete with an audit entry, so an accepted delete reads back 404.
- `update_specialty_list` (`fhir_specialty_writes.py:38`): admin only; takes the list lock; stale version 412; one audit entry per changed specialty.
- Reads for these records carry an ETag (`views.py:136-138`), so `If-Match` is always available.

## Flags for the orchestrator (not blocking)

1. The rows file keeps the Slot search cell at 200 with four KNOWN_DIFFERENCES entries (product 400). The reads plan's decision 1 said to correct the row and add none. Not changed here; the owner decides.
2. The `Caller` StrEnum in the rows file has the same name as the use-case `Caller` (`scheduling/use_cases/fhir_caller.py`). Nit; not changed here.

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
- The review's "For the owner" lines for the hospital 405 pairs are written by the review stage, not by this run's walk.

## Architect review

Revised against the architect's reason 1 (hospital Organization PUT and DELETE). Reason 1 is met by a `record` discriminator on `KnownDifference`, two entries, one walked case per hospital pair (cases 5 and 7), and the request count (123, up from 99) with the record each case uses. The 405 is not argued away: it is in KNOWN_DIFFERENCES with the row's 200 beside it, and listed for the owner. Line references checked against `writes.py`, `fhir_resources.py`, `write_body.py:22`, `views.py:136-138`, `builders.py:104-130,206`.

## Architect review (round 2)

Reason 1 of round 1 is met: the hospital pairs are in KNOWN_DIFFERENCES with the row's 200 beside the product's 405, and ADR 0008 (accepted 2026-11-22) is the decision behind the 405. Verified in code: `writes.py:50-55` (405 with `Allow: GET` after `refusal_before_body`), `test_fhir_organisation_writes.py:134`, `fhir_resources.py:145`, `write_body.py` (`unsupported_media_type` returns None on no body), `builders.py:104-130,206`, the `department_body`/`room_body`/`service_body`/`concept` signatures. Request arithmetic checks: 15 + 96 + 12 = 123.

Reason 2 (new, blocking): the first test does not hold the invariant the plan states. The module docstring says "a write without a case fails the walk" and the plan says "no row is skipped silently", but `returns_a_case_for_each_listed_write_row_when_the_walk_is_built` only checks the 10-pair tuple against the cases. The 13 other write rows of `FHIR_ACCESS_ROWS` (Practitioner, PractitionerRole, Schedule, Patient, Appointment, AppointmentResponse, Communication) pass unwalked and nothing fails. Fix: the test compares every write row of `FHIR_ACCESS_ROWS` to the walked pairs plus a named `NOT_WALKED_YET` set in the walk's file that lists the 13 pairs, so an unlisted write row fails and the next run only shrinks the set.

Non-blocking:
- Slice is coherent: 10 of 23 write rows, 4 callers, 123 requests, tests only, no product file. The goal asked for all create, update and delete rows; the orchestrator decides whether the slice stands.
- Red stage: this changes no behaviour (tests the product already passes). Per CLAUDE.md it belongs on `fabro run tests-and-docs`, not the task workflow; the mutation proofs at the end of the plan carry the "can fail" evidence.
- Row 5/7 `basis` says "ADR 0008" for admin 200, but ADR 0008 says hospital PUT/DELETE are 405. The plan's KNOWN_DIFFERENCES handles it; the owner decides between spec 15.4 and ADR 0008. Name it under "For the owner".
- Row 12 ordering rationale ("admin last") is not needed: refusals return before the body, so each caller's before-read is independent. Harmless.
- `Caller` name collision with `scheduling/use_cases/fhir_caller.py` (already flagged, nit).

Verdict: revise. Reason 2 is the only blocker.
