# Review: /fhir writes for admin-managed records (task 26b3, item 3, slice 1)

Reviewer: second reader, on the diff `3b3da73...HEAD` (the run's base; the sandbox has no local `main`, and `3b3da73` is where `task/26b3-fhir-walk` points). Plan: `doc/plans/2026-11-23-fhir-access-writes-admin-records.md`.

Scope read: 6 files, +562 / -17. Product code: none changed. Specification: `drlibre-specs.md` unchanged. Test files and test data only, plus the plan and this review.

## Verdict

`approve`. No blocker. The slice the plan declared is held to; the 13 pending write pairs are not counted against the run.

## Plan of each changed block, in one sentence

- `test_support/fhir_access_rows.py:39-48`: `KnownDifference` gains `record` (default `""`), so a pair can hold for hospitals only. Confirmed at a glance. Entries at `:165-166`: admin Organization update and delete, row 200, product 405. Confirmed against ADR 0008 (hospital PUT and DELETE are 405 with `Allow: GET`).
- `scheduling/views/test_fhir_access_requests.py:53-64`: `_expected_answer(row, caller, record="")` returns the first matching pair whose `record` is `""` or equal to the case's kind, else the row. Confirmed at a glance: `in ("", record)` keeps a department case out of the hospital pair.
- `scheduling/views/test_fhir_access_walk.py`: the old `_expected` is deleted and the reads walk calls `_expected_answer`. Traced: the reads walk passes no record kind, so only pairs with `record=""` apply, which is the old behaviour. The reads walk is unchanged in effect.
- `scheduling/views/test_fhir_access_write_cases.py:45-146`: `WriteCase` table of 12 cases, `NOT_WALKED_YET` (13 pairs), the builders per caller. Traced: each case's `fresh` makes one record per call, so one per caller, except the CodeSystem case (`:145`), which is the one shared record. Stated in the plan and in the code comment (`:112-114`).
- `scheduling/views/test_fhir_access_writes.py:138-164` (`_attempt`): read the record as admin, read the audit pks and table pks, send as the caller, then compare the answer with `_expected_answer`, the audit and table change with the expected change, and the record with the read-back (accepted) or with the pre-read (refused). Traced the order: the audit and table snapshots sit before the send and the admin reads sit outside the audit diff (`:151`), so the walk's own reads do not skew the count.

Confirmed by trace (not by the chat): the write path reaches a refused answer before the body and `If-Match` (plan cites `scheduling/views/fhir/writes.py:40-55`, not re-read here). What forced a trace: the DELETE request shape and the hospital 405 order. Both match what the tests expect, and the walk passes.

## Checks in the order the brief gives

1. Plan per block: above. Every block states its purpose in one sentence.
2. Correctness and errors: no swallowed error in the new code; there is no `try` or `except` in the diff. `response.json()["id"]` (`test_fhir_access_writes.py:154`) can raise on a malformed 2xx; that is a test failure, which is the right outcome in a test. Not a defect.
3. Authorization, schema, logging: product code untouched, so no product authorization or schema is changed here. The walk sends only the caller's bearer token from `world.clients` (`test_fhir_access_world.py`, not changed), and role comes from the product. Nothing sensitive is logged or put in a URL.
4. Double booking: not in scope of this diff (no booking code touched). The Appointment write rows that would exercise it are in the pending set.
5. Tests: derived from the specification and the rows table, not from the implementation. Expected values come from `FHIR_ACCESS_ROWS` and `KNOWN_DIFFERENCES`. Two named behaviour tests, `returns_the_row_answer_and_the_record_state_when_each_caller_writes` (`test_fhir_access_writes.py:195`) and `returns_a_case_or_a_pending_entry_for_each_write_row_when_checked` (`:204`), follow the `returns_X_when_Y` convention. Proofs of failure are in the write notes of the plan (answer, record, audit, coverage, each reverted). I did not re-run the mutations. The prove commit `b696ea7` changed only `test_fhir_access_write_cases.py` (`:82-96`), a test helper, after the green (`9b5deae`): allowed.
6. Names and comments: names state roles (`WriteCase`, `NOT_WALKED_YET`, `ACCEPTED_ROWS_CHANGE`, `_attempt`, `_refused_problems`). Comments say why. Two docstring issues, see Later.
7. Proof trace: `git log` after `write` (`8725510`) is `check` (`9b5deae`, empty) then `prove` (`b696ea7`, one test-helper file). No product or migration line changed after green. No blocker.
8. Scope and contracts: no dependency added (`git diff --stat` shows none). No migration, no product file. The spec is not in the diff.

Gates run by me on the final HEAD (`b696ea7`, read-only commands):
- `make lint`: ruff check, ruff format, mypy strict: pass (mypy: 715 source files, no issues).
- `make gate`: comment cap, size cap, escape hatches: clean.
- `pytest` on `test_fhir_access_writes.py`, `test_fhir_access_walk.py`, `test_fhir_access_requests.py`, `test_fhir_access_world.py` with the Makefile's `SAFE_ENV`: 5 passed in 5.01 s on this shared sandbox (the number is not a budget measure).
- Not re-run by me: full `make test` (the check stage ran it: 5412 passed, 401 s, before the prove commit), `make mutate`, `make fhir-validate`.

## Findings

Severity: nit (no blocker in this review). File:line, risk, smallest fix.

1. `scheduling/views/test_fhir_access_writes.py:74-85` (`_send`, DELETE). The plan says a body-less DELETE with no Content-Type. Django's `client.delete` sends `application/octet-stream` with an empty body; the write notes disclose this. Risk: a client that sends no Content-Type is not exercised; the product reads a zero-length body as no body (`carries_body`), so no answer changes today. Smallest fix: send the DELETE through `client.generic("DELETE", path, headers=...)` with the content type omitted, if Django allows it, and re-run the walk. Later.

2. `scheduling/views/test_fhir_access_write_cases.py:1-2` (module docstring). It says "Each makes a fresh record per caller". The CodeSystem case (`:145`, `_specialty_list` at `:112-114`) is one shared record. Risk: a reader trusts the docstring and misses the shared record. Smallest fix: add "except the specialty list, one shared record (`_specialty_list`)". Later.

3. `scheduling/views/test_fhir_access_writes.py:1-2` (module docstring). It does not name the coverage test (`returns_a_case_or_a_pending_entry_for_each_write_row_when_checked`), though the plan asked for it. Risk: low. Smallest fix: one clause naming it. Later.

4. `scheduling/views/test_fhir_access_write_cases.py:100`, `:105`, `:107` (`# noqa: S101` on `assert`). The suppression names its code, so the gate accepts it. An `isinstance` guard that raises a named error would drop the suppression and read the same. Later.

5. `test_support/fhir_access_rows.py:57-58` (rows `Organization` update and delete, basis `15.4 admin; ADR 0008`). ADR 0008 is the decision that makes the hospital PUT and DELETE 405, so the cell cites the source of the difference as if it supported the row. The row's value (200) is what the specification says (15.4 admin). Risk: a reader takes ADR 0008 as the row's support. Smallest fix: the basis cell should read `15.4 admin` and the owner note (below) should carry ADR 0008. Left for the owner with the decision; not changed here.

6. Create bodies are builders, not a read of the record (`test_fhir_access_write_cases.py:84-96`, `department_body`, `room_body`, `service_body`). The brief asked for a body "built from a read of the record"; a create has no record to read. The plan discloses it. Risk: none for the answer; the create body shape is the builder's, so a builder bug would be shared by the test and the product. Smallest fix: accept, or read a template record. Later.

7. Timing: 4 FHIR access modules ran in 5.01 s here, on a machine shared with other runs. Not a budget finding. The orchestrator measures on a quiet machine. Later.

## Blocking

None.

## Later

- F1 (DELETE Content-Type, `test_fhir_access_writes.py:74-85`): see finding 1.
- F2 (`test_fhir_access_write_cases.py:1-2` docstring, shared specialty list): see finding 2.
- F3 (`test_fhir_access_writes.py:1-2` docstring, coverage test not named): see finding 3.
- F4 (`# noqa: S101` on asserts, `test_fhir_access_write_cases.py:100-107`): see finding 4.
- F5 (row basis cell, Organization update and delete): see finding 5.
- F6 (create bodies from builders, not a read): see finding 6.
- F7 (time measured here, 5.01 s for four modules): see finding 7.
- Process note: `tests-and-docs` was the run's process (no behaviour change). Accepted as the plan says.

## For the owner

1. Hospital Organization PUT and DELETE for an admin. The specification (`drlibre-specs.md` 15.4, the table row "`Organization` ... Create, update, delete: Admin") says the admin may write `Organization`. ADR 0008 (accepted 2026-11-22, `doc/adr/0008-fhir-admin-writes-organisation.md:16`) says a hospital's `Organization` is read-only: `PUT` and `DELETE` on a hospital's id are 405 with `Allow: GET`, and the product does so (`scheduling/views/test_fhir_organisation_writes.py:134` pins it, per the plan). The walk holds both answers: the row says 200 (`test_support/fhir_access_rows.py:57-58` and the entries at `:165-166`), the product says 405. The owner decides whether the specification or the product changes. This review changes neither. The walk will fail if the product moves to either side without the table changing.
2. Slot search (carried from the reads walk, flagged in the plan): the rows file keeps the Slot search cell at 200 with four `KNOWN_DIFFERENCES` entries (product 400). The reads plan's decision 1 said to correct the row and add none. Owner decides which is the specification's answer. Not changed in this run.

## Left for the orchestrator

From the run's `## Not in this run`, copied:
- Slice 2, the staff and patient write rows: 13 pairs in `NOT_WALKED_YET`, each with an other-user record for the refusals:
  - Practitioner update, delete.
  - PractitionerRole create, update, delete.
  - Schedule create, update, delete.
  - Patient update.
  - Appointment create, update.
  - AppointmentResponse create.
  - Communication update.
- Item 4 of task 26b3 (the access section of `doc/security-review.md`, the generator, the drift test). Not started.

Added by this review:
- The goal asked for all create, update and delete rows (23). This run walks 10 of them as 12 cases (123 requests). The orchestrator must accept that slice before the task is called done. The coverage test holds the other 13 as named pending pairs, so nothing passes unwalked.
- `make mutate` and `make fhir-validate` were not run by this reviewer. The backlog's done line names both.
- The backlog file `doc/backlog/26b3-access-table.md` and `doc/handover.md` are not updated by this run; the plan says the orchestrator does.
- The verify run: the squash must be verified from a clone of the run branch with the gates; the check stage's full-suite run predates the prove commit (`b696ea7`), so a full `make test` on the squashed tree is the orchestrator's to run.
