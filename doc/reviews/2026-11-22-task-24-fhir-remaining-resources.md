# Review: task 24, FHIR AppointmentResponse, Communication, AuditEvent (run 01M8184D89GV15NNN3XHGS3S2D)

Diff: 18 files, +1523. Gates (`make lint`, `make test`, `make gate`) passed in `check`. `make mutate` and
`make fhir-validate` were not run by the stages; not verified here either.
Proof commits: `verify_green..prove` (668e400..938372a) changed tests only. No product line left behind.

## What the diff does

The diff covers the read side of the three new types and two writes: accept offer (`fhir_response_reads.py:44`) and mark read
(`fhir_communication_reads.py:42`). Both call the existing use cases (`accept_offer`, `mark_read`), so the refusals are theirs.
The plan block for each is stateable in one sentence. The domain mappers are small and pure.

## Findings

### Blocker: most of the task is not in the diff
- `doc/plans/...-admin-writes.md` promises blocks 4 to 6, 8 to 12 and 14+. None exist. Missing: task items 7, 8, 9 (admin writes for
  Organization, Location, HealthcareService, CodeSystem, ValueSet, Practitioner, PractitionerRole, `notAvailable`, `If-Match` on
  delete and on console use cases), 10 (admin-write tests), 10a (Appointment samples + test that every declared type has a sample),
  10b (ADR 0007), 10c (tidy), 10d (`scripts/fhir_validate.sh` drop, collation note, split `fhir_slot_reads.py`, replace
  `views.py:98` `assert`), 11 (table-driven section 15 walk), 12 (ADR 0005 closure, README FHIR section; `README.md` does not exist).
  `fhir_declaration.py` has no write interactions on the admin types; `WRITE_SHAPES` has no entry for them.
- No ADR records declining, the hospital two-resources decision, or the specialty list.

### Blocker: promised tests missing
- `test_fhir_audit_event.py`: no 50 000-entry bounded-query and speed test (item 5), no demo-seed no-PII test (item 6).
  (`grep` for `50_000`, `seed` finds nothing.) `sort_columns={}` at `fhir_audit_reads.py:90` and no default sort: the plan
  promised newest-first ordering; pages come back by key order. No test states the order.
- No test that a change of a child row moves `versionId` (item 9); no `make fhir-validate` samples for the three new types
  (`samples.py` untouched).

### Important
- `fhir_audit_reads.py:70`: `_details` copies any metadata value into `valueString`. Safety rests wholly on `audit_metadata`
  typing; the seed test is what would prove it, and it is absent. Fix: write the seed test; consider an allowlist of keys.
- `fhir_response_reads.py:48-55`: the patient-versus-actor check runs before `accept_offer`, outside its transaction and
  before its authorization. A patient who names another patient as actor on an entry gets 400 vs 403 for a missing entry: tells
  a caller that an entry id exists and who owns it is not leaked, but the order differs by existence. Fix: authorize first
  (`accept_offer` already does) and compare the actor inside or after the forbidden check.
- `fhir_communication_reads.py:34`: `UUID(identifier)` after the `filter(pk=identifier)`; an unparsed id relies on the router
  having validated it. Confirm; same in `fhir_audit_reads.py:25`.
- `fhir_appointment_reads.py`: `starts_within` made public and imported by three modules from an Appointment-named file.
  Move to `fhir_reads.py` (second caller exists now).

### Nit
- `_stored_version` (`fhir_communication_reads.py:60`) re-parses the resource just built; take the version from the row.
- Dead code at `fhir_audit_reads.py:34-45`: four one-line filter wrappers could be one `_equals(column)` helper.

## Hard rules
No `Any`, `cast`, bare ignores introduced. No function > 100 lines. No swallowed error found. Writes call use cases that audit in
their own transaction (`accept_offer` audits `waitlist.accept`; `mark_read` audits). Authorization comes from the token user.

## Blocking
1. Items 7, 8, 9, 10, 10a to 10d, 11, 12 absent: admin writes, `notAvailable`, `If-Match` on delete, samples, ADRs 0005/0007, README.
2. Item 5 and 6 tests (50 000 entries, no personal data on the demo seed) missing; default newest-first order not implemented.
3. Item 9 child-row `versionId` test and `make fhir-validate` samples for new types missing.

## Later
- Authorize before the actor comparison in `create_response`.
- Move `starts_within` into `fhir_reads.py`.
- Replace one-line filter wrappers with one helper.
- Timing: not measured (`make test` 30 to 34 s in this sandbox, shared machine).

## Outcomes of the address stage

| # | Finding | Outcome |
|---|---------|---------|
| 1 | Items 7, 8, 9, 10, 10a to 10d, 11, 12 absent (admin writes, `notAvailable`, `If-Match` on delete, Appointment samples, ADRs 0005/0007, README, section-15 walk) | not fixed: a feature-sized body of work (about ten tasks of code, two ADRs, README), not a finding-sized fix. Needs its own task before the next layer. |
| 2a | 50 000-entry bounded-query and speed test missing | fixed: `test_fhir_audit_event.py::returns_a_page_in_bounded_queries_and_time_when_the_log_holds_50000_entries` (passed on first run: the page was already bounded; it guards it) |
| 2b | No-personal-data test on the demo seed missing | fixed: `test_fhir_audit_event.py::returns_no_personal_data_in_any_event_when_the_demo_seed_ran` (also passed on first run: no leak found) |
| 2c | Newest-first default order not implemented | fixed: `test_fhir_audit_event.py::returns_newest_entries_first_when_no_sort_is_given`, red before (ascending key order), green after `Part.newest_column` |
| 3a | `make fhir-validate` samples for the three new types | fixed as a guard: `test_samples.py::returns_a_staff_sample_for_every_declared_type_when_samples_are_built`. The sample loop already walks every declared type, so Communication and AuditEvent were sampled; the test now fails when a type has none. `make fhir-validate` itself was not run here. |
| 3b | Child-row `versionId` test (item 9) | not fixed: it belongs to the admin writes and `If-Match` of blocker 1; ADR 0003 states derived rows do not move the served `versionId`, so no existing resource has a child row to test. |

## Second reading, after the address stage (2026-11-22)

Re-read the diff at HEAD `931fc31`. The address stage added the 50 000-entry test, the demo-seed no-personal-data test, the
newest-first order and the sample guard test. Those three blockers (2a, 2b, 2c) are closed. `verify_green..prove` still
changed tests only.

Still open, and still blocking: items 7, 8, 9, 10, 10a (Appointment samples), 10b (ADR 0007 does not exist; `doc/adr` stops at
0006), 10c, 10d, 11 and 12 (`README.md` does not exist; ADR 0005 not closed). No admin write, no `notAvailable` update, no
`If-Match` on delete, no child-row `versionId` test, no section 15 walk test. The task's "done when" and the orchestrator's
checks (create and delete a hospital, record time off with a clinician token) cannot pass on this diff.

Hard rules: no escape hatch, no oversize function or file, no swallowed error, audits sit inside the use cases called.

Not run here: `make mutate`, `make fhir-validate`. Timing: `make test` took about 46 s in the `check` stage on a shared machine; the
orchestrator measures it quietly.

## Blocking
1. Items 7, 8, 9: admin writes, `notAvailable`, `If-Match` on update and delete, child-row `versionId` test.
2. Items 10, 10a to 10d: write tests per role, Appointment samples, ADR 0007, tidy, fhir-validate cleanup.
3. Items 11 and 12: section 15 walk test, ADR 0005 closure, README FHIR section.

## Later
- Authorize before the actor comparison in `create_response`.
- Move `starts_within` into `fhir_reads.py` (done in `fhir_reads.py` by the address stage; check imports).
- One `_equals(column)` helper for the audit filters.
- Split the remaining work into follow-up tasks if the orchestrator prefers: this diff stands as a sound read side.

## Outcomes of the second address stage

| # | Finding | Outcome |
|---|---------|---------|
| 1 | Items 7, 8, 9: admin writes, `notAvailable`, `If-Match` on update and delete, child-row `versionId` test | not fixed: feature-sized (writes for seven resource types through the task 17 to 19 use cases, new write shapes, failure-table tests). Not a finding-sized fix; needs its own task. |
| 2 | Items 10, 10a to 10d: per-role write tests, Appointment samples, ADR 0007, tidy, fhir-validate cleanup | not fixed: the write tests depend on blocker 1; ADR 0007 and the Appointment samples are separate, sizeable work. Own task. |
| 3 | Items 11 and 12: section 15 walk test, ADR 0005 closure, README FHIR section | not fixed: the walk asserts the admin writes of blocker 1, and the ADR and README would describe behaviour that does not exist yet. Own task after blocker 1. |

No product or test line changed in this stage. Proposed split: task 24b admin writes with `If-Match` and `notAvailable` (items 7 to 10);
task 24c Appointment samples, ADR 0007, tidy, validate cleanup (10a to 10d); task 24d section 15 walk, ADR 0005, README (11, 12).

## Round 3 re-check (HEAD f91fb0e)

Re-read the file list: still no admin-write views, no `doc/adr/0007-*`, no README, `scripts/fhir_validate.sh` still has no
cleanup of its throwaway database, no samples for the new types, no section 15 walk test. The blockers above stand unchanged.
`make test` runs 3979 tests; time not a blocker, not measured as a budget.

## Blocking
- Items 7, 8, 9: admin writes, `notAvailable`, `If-Match` on update and delete, child-row `versionId` test absent.
- Items 10, 10a to 10d: per-role write tests, Appointment samples, ADR 0007, tidy, `fhir-validate` cleanup absent.
- Items 11, 12: section 15 walk test, ADR 0005 closure, README FHIR section absent.
- Items 5, 6: 50 000-entry query-count test and demo-seed no-PII test absent.

## Later
- Authorize before the actor comparison in `fhir_response_reads.py:48-55`.
- Allowlist metadata keys in `fhir_audit_reads.py:70`.
- `starts_within` lives in an Appointment-named module used by three others.
