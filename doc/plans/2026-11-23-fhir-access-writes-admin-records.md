Slice: write rows of the admin-managed types (Organization, Location, HealthcareService, CodeSystem): 10 of the 23 write rows, 12 write cases, 123 requests. The staff and patient write rows follow in the next run (`## Not in this run`).

Process: `tests-and-docs` (no behaviour change; the task workflow's red gate cannot pass for it, 27a3). Architect round 2 said the same.

## Focal point

`test_support/fhir_access_rows.py` lists the answer of every `/fhir` write interaction per caller. One walk, `scheduling/views/test_fhir_access_writes.py`, sends each case as each of four callers (visitor with no token, and a bearer token of a patient, a clinician and an admin). Each caller writes its own fresh record. The walk reads the record back as admin before and after, reads the audit log back around the write, and checks the answer, the record and the audit log against the row.

A second test holds the coverage invariant for all 23 write rows: every write row is either walked by a case or listed as pending in `NOT_WALKED_YET`. This answers round 2's reason 2: no write row passes unwalked without a name.

## Blocks, in file order

1. **`test_support/fhir_access_rows.py`** (edit, 3 lines plus 2 entries). Module docstring: read by the route-coverage test, the reads walk and the writes walk. `KnownDifference` gets `record: str = ""` as its last field. `""` means every record of that resource and interaction; otherwise it is the record kind the pair holds for (`"hospital"`). Its docstring says so. Add two entries to `KNOWN_DIFFERENCES`: `KnownDifference("Organization", "update", Caller.ADMIN, 200, 405, record="hospital")` and the same with `"delete"`. The seven existing entries do not change (they take the default `record`). No row changes.

2. **`scheduling/views/test_fhir_access_requests.py`** (edit). Add public `expected_answer(row, caller, record="")`, moved from `_expected` in the reads walk. It returns the product answer of the first `KNOWN_DIFFERENCES` entry whose resource, interaction and caller match and whose `record` is in `("", record)`; otherwise `row.answer_for(caller)`. So a department case (`record=""`) never picks up the hospital pair, and a hospital case (`record="hospital"`) does. Module docstring: add that it also gives the expected answer of a request. Nothing else changes.

3. **`scheduling/views/test_fhir_access_walk.py`** (edit). Delete `_expected` (line 42); call `expected_answer(row, caller)` imported from requests. Reads behaviour does not change.

4. **`scheduling/views/test_fhir_access_write_cases.py`** (new, about 120 lines). Module docstring: the records each write changes, made fresh per caller, the body each caller sends, the pending set, and that a write row with neither a case nor a pending entry fails the coverage test. Contents:
   - One frozen dataclass `WriteCase` per row or hospital variant: `resource`, `interaction`, `record` (`""` or `"hospital"`), `fresh(world, caller)` (makes the record; `None` for create), `path(target)`, `body(admin_client, target)` (an admin read with the change applied; `None` for delete), `accepted(world, target, created_id)` (the record state after an accepted write, as a bool). Each function under 15 lines.
   - `WRITE_INTERACTIONS = ("create", "update", "delete")`.
   - `NOT_WALKED_YET: frozenset[tuple[str, str]]`: the 13 write pairs of the next run, listed in full (below). Its docstring: the next run removes entries as it adds cases; an entry that gets a case fails the test.
   Builders reused: `department_body` (`scheduling/views/fhir_organisation_support.py:32`), `room_body` (`:60`), `service_body` (`:43`), `concept` (`scheduling/views/fhir_specialty_support.py:11`), `make` (`scheduling/models/builders.py:206`, defaults around 104-130).

5. **`scheduling/views/test_fhir_access_writes.py`** (new, about 120 lines). Module docstring: the walk of the 10 walked write rows as 12 cases, each caller's answer against its row (`expected_answer`), a refused write leaves the record and the audit log as they were, an accepted one changes them, and every write row is walked or pending. Tests:
   - `returns_the_row_answer_and_the_record_state_when_each_caller_writes`
   - `returns_a_case_or_a_pending_entry_for_each_write_row_when_checked`
   Helpers, each under 20 lines: `_state(client, path)` (admin GET: status, body, ETag); `_audit_ids()` (ORM: list of `AuditLogEntry` pks, ordered); `_table_ids(model)` (ORM: pks); `_write(client, method, path, body, etag)` (one request through the caller's client, below); `_mismatches(...)`.
   The walk sends through `world.clients[caller]` (`test_fhir_access_world.py:98`, built in `_build_world` at `:107`): `client.post/put(path, data=json.dumps(body), content_type=FHIR_JSON, headers=...)` for POST and PUT, `client.delete(path, headers=...)` with no body and no Content-Type, as a FHIR client sends a DELETE. A PUT or POST carries `If-Match` only on PUT and DELETE; POST has none.

No change to `test_fhir_access_world.py`: it already holds the four caller clients.

## The 12 cases, the record each caller writes, and the requests

Each caller gets its own fresh record for each case (`fresh(world, caller)`), so no write changes another's record. The one exception is row 12, the specialty list (see `## Records`). `world` is `_build_world()`, which holds a department (`world.room.department`), its hospital (`.hospital`), a room and an appointment type. The admin's read of the record supplies the body and the `If-Match` value (the read's ETag).

| # | Row (case) | Record each caller writes | Body each caller sends | Accepted answer for admin, and change |
| --- | --- | --- | --- | --- |
| 1 | Organization create | none; a new department under `world.room.department.hospital` | `department_body(hospital, "cardio-<caller>")` | 201; one more Department with that code; audit +1 |
| 2 | Location create | none; a new room under `world.room.department` | `room_body(department, "room-<caller>")` | 201; one more Room; audit +1 |
| 3 | HealthcareService create | none; a new appointment type under `world.room.department` | `service_body(department, "intake-<caller>")` | 201; one more AppointmentType; audit +1 |
| 4 | Organization update (department) | fresh Department D: `make("Department", hospital=world.room.department.hospital)` | admin read of D's Organization, `name` changed | 200; admin read shows new name; audit +1 |
| 5 | Organization update (hospital, `record="hospital"`) | fresh Hospital H: `make("Hospital")` | admin read of H's Organization, `name` changed | 405 with `Allow: GET` (KNOWN_DIFFERENCES); H unchanged; audit unchanged |
| 6 | Organization delete (department) | fresh Department D, no dependents | none; `If-Match` | 200; admin GET 404; Department row gone; audit +1 |
| 7 | Organization delete (hospital, `record="hospital"`) | fresh Hospital H | none; `If-Match` | 405 with `Allow: GET` (KNOWN_DIFFERENCES); H unchanged; audit unchanged |
| 8 | Location update | fresh Room R: `make("Room", department=world.room.department)` | admin read of R's Location, `name` changed | 200; new name read back; audit +1 |
| 9 | Location delete | fresh Room R, unused | none; `If-Match` | 200; admin GET 404; Room row gone; audit +1 |
| 10 | HealthcareService update | fresh AppointmentType T: `make("AppointmentType", department=world.room.department)` | admin read of T's HealthcareService, `name` changed | 200; new name read back; audit +1 |
| 11 | HealthcareService delete | fresh AppointmentType T, unused | none; `If-Match` | 200; admin GET 404; row gone; audit +1 |
| 12 | CodeSystem update (`specialty`) | the specialty list, one record, not fresh | admin read of the list, one more concept (`concept("cardiology", "Cardiology")`), `count` recomputed | 200; list has `cardiology`; audit +1 |

Requests (the same per caller in every case):
- create (rows 1 to 3): one POST per caller, plus for the admin's accepted write one GET of the new record (`id` from the 201 body). 4 + 1 = 5 per row: **15**.
- update and delete (rows 4 to 11): per caller, admin GET before (body and `If-Match` source), the caller's write, admin GET after: 3 per caller, 12 per case, 8 cases: **96**.
- CodeSystem (row 12): the same 3 per caller: **12**.
- Total: 15 + 96 + 12 = **123 requests**, in process through the test client. Audit ids and table ids are read with the ORM, not through requests. The FHIR scope allows 600 per address (`scheduling/domain/rate_limit_rules.py:39`); 123 is under it.
- Cost: a few seconds. The reads walk sends 132.

Pending rows (not walked, no request sent in this run): 13 write pairs in `NOT_WALKED_YET`: Practitioner update, Practitioner delete, PractitionerRole create, PractitionerRole update, PractitionerRole delete, Schedule create, Schedule update, Schedule delete, Patient update, Appointment create, Appointment update, AppointmentResponse create, Communication update. 2+3+3+1+2+1+1 = 13.

## Records

- Fresh per caller: rows 1 to 11. The create rows (1 to 3) make nothing before the write; the creates add rows that no other case reads, and each caller's create uses a code of its own.
- Shared: row 12. The specialty list is one record (`CodeSystem` is the whole list); no fresh copy can be made. Only the admin's accepted write changes it, and refused callers return before the body is read (`refusal_before_body`), so the list is unchanged when the admin writes it. Each caller reads its own before-state, so no ordering is needed. The admin's write is the only accepted one, so no other row reads a changed list.
- Orchestrator: this is the one place the goal's "fresh record per write" does not hold, and why.

## Read-back rule

- Refused write (any 4xx or 405): the admin GET of the record before and after is identical (status, body, ETag); the audit ids (ORM list of pks) read immediately before and immediately after the caller's write request are identical; for create, the table ids are identical.
- Accepted write (2xx): the record reads back as the case's `accepted` says; the audit ids read around the write grow by exactly one new pk.
- The walk decides refused or accepted from the response status it got, not from the row. A product 405 on a hospital pair is refused.
- Admin GETs and the ORM reads sit outside the two audit reads, so their own effects cannot skew the count.

## Expected answers

- Row cells from `FHIR_ACCESS_ROWS` for all 10 walked rows. For every case: visitor 401, patient 403, clinician 403, all answered before the body is read (`refusal_before_body`, `scheduling/use_cases/fhir_resources.py:145`). `is_read_only_here` runs after it, for PUT and DELETE (`scheduling/views/fhir/writes.py:40-55`). For the hospital cases (5, 7) only admin differs.
- KNOWN_DIFFERENCES pairs: rows 5 and 7 only, admin 200 (row) and 405 (product). No other difference is expected for this slice. Any other mismatch is a finding (the product answers differently), not a red to fix in this run.

## Invariants and blast radius

- Server-side authorization: the walk sends the caller's bearer token only. Role, user and flags come from `resolve_token` in the product, never from the test.
- Tokens come from `token_of` through `world.clients`; the test stores none.
- The audit log is append-only; the test reads its pks and never deletes from it.
- Fresh records mean one write cannot change another's record. The CodeSystem list is the one shared record, handled above.
- Blast radius: test modules, `test_support/fhir_access_rows.py` (one field, two entries, one docstring), and the reads walk's helper move. No product file. No change in this run to the product or the specification.

## Trust boundaries crossed

- The FHIR door: bearer token, no cookie, no Origin, cross-site check enforced (`client_for`, `scheduling/views/fhir_test_support.py:30`). `/fhir` is csrf-exempt by design (ADR 0005), so the walk sees what a real client sees.
- Body: sent as `application/fhir+json`. The product checks it against the write shape (`_checked_body`, `scheduling/views/fhir/writes.py`) and the URL's identity. A body-less DELETE is not a 415 (`scheduling/domain/write_body.py`, `carries_body`).
- `If-Match`: the ETag of the admin read, sent by the caller. The product checks it under the record's lock (ADR 0008). A refused caller's `If-Match` is valid, so the refusal is the caller's, not a stale version.
- Create bodies are support builders, not reads; codes are unique per caller so a taken code (400) cannot hide an answer.

## Domain entities (CLAUDE.md section 3)

Visitor, Patient, Clinician, Admin (callers); ApiClient (token); Hospital; Department (FHIR Organization of type `dept`); Room (Location `ro`); AppointmentType (HealthcareService); Specialty list (CodeSystem); AuditLogEntry.

## The hospital 405, for the owner

The product answers a hospital's Organization PUT and DELETE with 405 and `Allow: GET` for an admin (ADR 0008; pinned by `scheduling/views/test_fhir_organisation_writes.py:134`). The row says admin 200, and the specification (15.4) says admin may write. The row's `basis` cell cites ADR 0008 but ADR 0008 says hospital writes are 405, so the cell is wrong as a citation. This is a finding: the walk holds the product's 405 in KNOWN_DIFFERENCES with the row's 200 beside it, and the review names both pairs under "For the owner" with section 15.4 and ADR 0008. The owner decides whether the spec or the product changes. This run changes neither.

## What I will not do

- No product code, no new dependency, no new abstraction beyond `WriteCase`, `NOT_WALKED_YET` and the public `expected_answer`.
- No xfail or skip on a walked case, and no skip on a pending row.
- No walk of the patient or staff write rows (next run).
- No change to `test_fhir_access_world.py`, to `doc/security-review.md` (item 4), `doc/handover.md`, or `doc/backlog/26b3-access-table.md` (the orchestrator updates the backlog).
- No change to the existing KNOWN_DIFFERENCES entries.

## Failing tests first, and proof they can fail

- Order: write `test_fhir_access_write_cases.py` and the walk; run them. A mismatch line names a case and a caller. A mismatch on rows 5 or 7 for the admin is expected to be absent, because the pairs are listed; if it appears, the product answer is not 405 and the entry is wrong.
- Proof the answer check fails: in a scratch edit, expect Organization create as patient to be 201 instead of 403; expect exactly one mismatch line naming it; revert.
- Proof the record check fails: in a scratch edit, expect the table ids to grow on a refused create; expect a mismatch; revert.
- Proof the audit check fails: in a scratch edit, expect the audit ids to stay the same on an accepted write; expect a mismatch; revert.
- Proof the coverage check fails, both ways: (a) in a scratch edit, drop one case from the list; expect the coverage test to name that row; revert. (b) remove one pair from `NOT_WALKED_YET`; expect the coverage test to name that pair as unlisted; revert.

Behaviour names (`returns_X_when_Y`), expected values from the specification:
- `returns_the_row_answer_and_the_record_state_when_each_caller_writes`: each caller's answer equals its row, or its KNOWN_DIFFERENCES pair for the hospital cases (spec 15.4, ADR 0008); a refused write leaves the record and the audit log unchanged; an accepted write changes the record and adds one audit entry (CLAUDE.md: every write audited).
- `returns_a_case_or_a_pending_entry_for_each_write_row_when_checked`: the set of write rows of `FHIR_ACCESS_ROWS` equals the walked (resource, interaction) pairs plus `NOT_WALKED_YET`, and the two do not overlap. So an unlisted write row fails, a pending entry that gets a case fails, and a case for a removed row fails.

## Domain fact checks (read in code)

- `create_record_resource`, `update_record_resource`, `delete_record_resource` (`scheduling/use_cases/fhir_resources.py`, through `fhir_record_writes.py`): admin only; missing record 404; stale version 412; dependents 409.
- `delete_record` is a hard delete with an audit entry, so an accepted delete reads back 404.
- `update_specialty_list` (`scheduling/use_cases/fhir_specialty_writes.py`): admin only; takes the list lock; stale version 412; one audit entry per changed specialty.
- Reads for these records carry an ETag (`scheduling/views/fhir/views.py:131-138`), so `If-Match` is always available.
- Refusal order in the write path (`scheduling/views/fhir/writes.py:40-55`): refusal before body; then the hospital 405 (PUT and DELETE); then `If-Match`; then DELETE; then body. So a hospital admin PUT gets 405 before `If-Match` or body are checked.

## Flags for the orchestrator (not blocking)

1. The rows file keeps the Slot search cell at 200 with four KNOWN_DIFFERENCES entries (product 400). The reads plan's decision 1 said to correct the row and add none. Not changed here; the owner decides.
2. The `Caller` StrEnum in the rows file has the same name as the use-case `Caller` (`scheduling/use_cases/fhir_caller.py`). Nit; not changed here.
3. Process: this run changes no behaviour; run it on `fabro run tests-and-docs`, not the task workflow (the red gate cannot pass, 27a3).

## Not in this run

- Slice 2, the staff and patient write rows (13 pairs in `NOT_WALKED_YET`, each with an other-user record for the refusals):
  - Practitioner update, delete: admin only; another clinician's user record for the 403s.
  - PractitionerRole create, update, delete: clinician updates own role (`notAvailable`); admin any; patient and clinician refused on create and delete.
  - Schedule create, update, delete: owning clinician only; admin 403.
  - Patient update: own patient (patient 200), another patient (403).
  - Appointment create: patient, clinician, admin each book a fresh free slot (201).
  - Appointment update: body-level status change to cancelled, fresh appointment per caller.
  - AppointmentResponse create: fresh waitlist offer per caller; clinician 403.
  - Communication update: recipient only (200); clinician and admin 403.
- Item 4 of task 26b3 (the access section of `doc/security-review.md`, the generator and the drift test).
- The review's "For the owner" lines for the hospital 405 pairs are written by the review stage, not by this run's walk.

## Revision history

- Round 1 (architect): the hospital Organization PUT and DELETE pair was walked but not listed. Addressed: `record` discriminator on `KnownDifference`, two entries, one case per hospital pair.
- Round 2 (architect, verdict `revise`): the coverage test checked only the 10 walked pairs, so the 13 unlisted write rows passed unwalked. Addressed in this revision: `NOT_WALKED_YET` names the 13 pairs; the coverage test requires the write rows to equal walked plus pending, with no overlap; two proofs of that test. Also: the cited paths corrected to their real files; the read-back rule now reads audit pks, not only a count; `expected_answer` matches a record with `record in ("", record)`; the CodeSystem sharing and the `tests-and-docs` process are stated as decisions.
- Non-blocking round 2 notes taken: the owner note on the hospital 405 (section above); the `Caller` nit (flag 2); the admin-last ordering is dropped because refusals return before the body.
- Round 3 (architect, verdict `approve`): the round-2 reason is met. The 13 pending pairs are named in `NOT_WALKED_YET`, and the coverage test holds write rows = walked + pending with no overlap.

## Architect review

Verdict: `approve` (`scratch/plan.verdict`). Read against the code: `test_support/fhir_access_rows.py` (23 write rows; the 10 walked pairs plus 13 pending give 23), `scheduling/views/test_fhir_access_walk.py` (`_expected`, `_difference_problems`), `scheduling/views/test_fhir_access_requests.py`, `scheduling/views/test_fhir_access_world.py` (`_clients` :98, `_build_world` :107), `scheduling/views/fhir/writes.py` (refusal order, `_checked_body` :102), `scheduling/use_cases/fhir_record_writes.py`, `scheduling/use_cases/fhir_specialty_writes.py`, `scheduling/views/fhir_organisation_support.py` (builders :32, :43, :60), `scheduling/views/fhir_specialty_support.py` (`concept` :11), `scheduling/models/builders.py` (`make` :206, defaults), `drlibre-specs.md` 15.4, ADR 0008.

1. Ladder: no product change, no dependency. New abstractions are `WriteCase`, `NOT_WALKED_YET` and public `expected_answer`, all named in the plan. Each has a second caller within this run (the reads walk and the writes walk use `expected_answer`). Ok.
2. Plan knowledge: each block states its purpose in one sentence. Vocabulary matches CLAUDE.md §3 (Department, Room, AppointmentType, Specialty list, Hospital). Ok.
3. Test first: two named behaviour tests, expected values from spec 15.4 and the rows table. Proofs that the answer, record, audit and coverage checks each fail are listed. Ok.
4. Security: the walk sends only the caller's bearer token or none; role comes from `resolve_token`. Refusals are checked before the body (`refusal_before_body`). Audit log is read and never deleted. Ok. The staff and patient rows, where the IDOR threat lives, are deferred and named.
5. Architecture: test-only change, no product layer touched. Ok.
6. Scope: the goal asked for all create, update and delete rows (23). The plan walks 10 rows as 12 cases and names the 13 others in `NOT_WALKED_YET` and `## Not in this run`. A coherent slice: the admin-only resources, one shared-record exception (CodeSystem) stated with its reason. Accepted; the orchestrator must confirm the slice.

Non-blocking findings for the orchestrator:
- Creates (rows 1 to 3) build bodies with `department_body`, `room_body`, `service_body`, not from a read of the record (no record exists yet). The goal asked for a read. The plan discloses this; accept or ask for a read-of-a-template.
- Rate limit basis is wrong. `scheduling/domain/rate_limit_rules.py:39` sets the FHIR cap to 600 per address, but `scheduling/views/fhir/views.py:89-91` takes a hit only on GET, so writes are not counted. The walk sends 75 GETs and 48 writes. "123 is under it" holds, but the stated basis should be the 75 GETs. Fix the sentence in the run.
- `scheduling/views/test_fhir_access_writes.py` plus `test_fhir_access_write_cases.py` at 12 cases with four callables each is near the 300-line cap; the orchestrator reads the diff line by line, so prefer one-line lambdas only where they stay readable.
- The owner note on the hospital 405 (spec 15.4 says admin writes Organization; ADR 0008 says a hospital's Organization is 405; row basis cites ADR 0008 wrongly) stays as the plan says: name both pairs under "For the owner" in the review.
- Process: `tests-and-docs`, as the plan says, since no behaviour changes.

## Write stage notes

Written as planned, with these differences, each forced by the code or the tests:

- `expected_answer` is named `_expected_answer`. The conftest collects only `test_*` functions and rejects a public function in a `test_*.py` module; the reads walk already imports `_send` and `_path_of` the same way.
- `WriteCase` has `reads_back` (default `("name",)`, `("concept",)` for the specialty list) instead of a per-case `accepted` function. The server adds fields to a read (`meta`, coding `display`), and returns the concepts sorted by code, so the walk compares only the fields the case changes, with lists compared as sets.
- Delete cases name their `table` too, so an accepted delete must remove exactly one row. Create cases check one row added; refused writes check no row and no audit change.
- The test client always sends `Content-Type: application/octet-stream` on DELETE (Django's default). Not "no Content-Type" as the plan says. The product reads a zero-length body as no body (`carries_body`), so the answer is the same; a real FHIR client that sends no Content-Type is not exercised.
- Request count checked by a counting wrapper on the test client: 123 `/fhir` requests, no failures, the walk's records as in the table above.
- Proofs run (temporary edits, all reverted): a row changed from 403 to 201 gave `create Organization as patient: expected 201, got 403`; an audit line removed in `scheduling/use_cases/admin_records.py:76` gave 4 audit problems (the first `update Organization as admin`); a refused create made a Department first gave `the table changed by (1, 0), expected (0, 0)`; dropping a case or a pending pair, or listing a walked pair as pending, named the pair in the coverage test.
