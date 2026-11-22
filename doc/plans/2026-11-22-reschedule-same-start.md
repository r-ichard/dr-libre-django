# Reschedule to the current start changes nothing (task 27b, item 9, issue #39)

Slice: item 9 only. Nothing else of `doc/backlog/27b-qa-round-3-pages.md`.

## Focal point

`scheduling/use_cases/appointment_changes.py`, `reschedule_appointment`. Every surface
(clinician, admin and patient pages; `/api/v1` `RescheduleView`; FHIR `update_appointment`
through `reschedule_appointment`) ends in this one function. Today a same-start call
reaches `replace_placement`, which excludes the appointment from its own conflict check,
so it passes, rewrites the same row, writes an `appointment.reschedule` audit entry and
queues a `SCHEDULE_CHANGED` notification. That is the defect.

## Answer: quiet success, not refusal

- `/fhir` already answers a same-start update with `NoChange` (`decode_update`,
  `fhir_appointment_writes._unchanged`): 200, the stored resource, no write. A refusal on
  the API and pages would make the four surfaces disagree.
- Section 5.6 names no refusal for this case. Section 4's failure table has no code that
  fits without inventing one; `invalid_transition` would be a lie.
- A double submit or second tab then lands on the same success and changes nothing.
- Owner risk: the pages redirect with the "rescheduled" notice for a no-op. Accepted here;
  see Risks.

## Blocks

1. `reschedule_appointment`, after the status check and before `replace_placement`: if
   `starts_at == appointment.starts_at`, return `Success(appointment)`. One comparison, no
   new domain function, no new dependency. Placed after `_lock_for_change` so authorization
   and the record rule still answer first (a non-owner gets the same refusal as before),
   and after the status check so a `CHECKED_IN` or `CANCELLED` appointment still answers
   `invalid_transition`. Python aware-datetime `==` compares instants, so UTC from the
   request and from the database match. No comment: the code states it.
2. New `scheduling/use_cases/test_appointment_changes.py` (file first used here): the
   behaviour tests below, written first.
3. Surface tests appended to existing files, one each, asserting the answer and that no
   audit row and no notification row appear:
   - `/api/v1`: `scheduling/views/test_appointment_actions.py`
   - `/fhir`: `scheduling/views/test_fhir_appointment.py`
   - page: `scheduling/views/pages/test_clinician_qa_round_two.py`, POST sent as a browser
     sends it (CSRF token, `Origin` header), per CLAUDE.md "Page forms".

No change to `placement.py`, the domain, models, templates or migrations.

## Files, in order

1. `scheduling/use_cases/test_appointment_changes.py` (new): red tests.
2. `scheduling/use_cases/appointment_changes.py`: green, the comparison in block 1.
3. The three surface test files: add one test each, red then green with block 2.

Not touched: `placement.py`, `fhir_appointment_writes.py`, `appointment_actions.py`,
the page views (their POST already passes `starts_at` through), `drlibre-specs.md`,
`doc/backlog/27b-*.md` (the orchestrator updates the backlog file).

## Failing tests first

Expected values from the specification: §5.6 (a reschedule keeps the status and moves the
start), §4 (every write audited; one transaction per change). A no-op writes nothing, so
the audit count and notification count stay where they were.

- `returns_unchanged_appointment_and_no_audit_or_notification_when_rescheduled_to_current_start`
  Expected: `starts_at`, `ends_at`, `room_id`, `version` as before; `appointment.reschedule`
  rows = 0; `SCHEDULE_CHANGED` notifications = 0. Red today: one audit row, one notification.
- `returns_success_when_rescheduled_twice_to_the_same_start`
  Expected: both calls return `Success`; audit rows for `appointment.reschedule` = 1 (the
  first call only, that one moved the start). Use a second, different start for the first
  call so the second is the real no-op.
- `returns_invalid_transition_when_checked_in_appointment_rescheduled_to_current_start`
  Expected: `Failure` with code `invalid_transition`; no audit row. Guards the ordering.
- `returns_not_found_when_other_patient_reschedules_to_current_start`
  Expected: same answer as a reschedule to a new start by that patient (the record rule
  wins before the comparison). No audit row.
- Surface, API: `returns_200_without_audit_entry_when_api_reschedules_to_current_start`
  (`/api/v1/appointments/<id>/reschedule`, signed in as the clinician, Origin and cookie).
- Surface, FHIR: `returns_200_without_audit_entry_when_fhir_put_keeps_start` (passes
  already; the test guards the path after the change).
- Surface, page: `returns_303_without_notification_when_clinician_review_posts_current_start`
  (form POST with CSRF and Origin, as a browser).

Red proof: the first use-case test must fail on the current code with a count of one
audit row, and the failure output goes into the run log.

## Invariants and blast radius

- Double booking: unaffected. The no-op runs before `replace_placement`, so no conflict,
  room or clinician check is re-run for a start that is already held.
- Server-side authorization: unchanged. `_lock_for_change` (record rule, status table,
  version) runs first, as before.
- Audit log append-only: unchanged; the change only avoids a write.
- Concurrency: the comparison runs under the row lock taken in `_lock_for_change`, so two
  tabs cannot both see a stale start.
- Blast radius: every reschedule caller (three pages, API, FHIR, `demo_seed`
  `test_survives_use.py`). Only same-start calls change behaviour.
- Version: a no-op does not save, so `version` does not move.

## Trust boundaries

- `starts_at` from the request (page query, API JSON, FHIR `start`): validated by the
  existing parsers before the use case, unchanged.
- Identity and authorization: taken from the session or token in the view, checked
  server-side in `_lock_for_change`. The new check adds no input.

## Domain entities (CLAUDE.md §3)

Appointment (status BOOKED or CONFIRMED, starts_at, ends_at, room), User (actor), Patient
(notified), AuditLogEntry (not written), Notification (kind `SCHEDULE_CHANGED`, not
written).

## Not doing

- No refusal code, no new `FailureCode`, no change to `Failure`.
- No change to the page copy or the success notice on a no-op (owner decision, see Risks).
- No dedupe of the notification elsewhere, no FHIR change (already correct).
- No abstraction, dependency or refactor of `placement.py`.

## Not in this run

- Items 1 to 8 and 10 of task 27b (other findings).
- A notice that reads "nothing changed" on the pages. Needs an owner decision on copy.

## Risks

- `make mutate` covers `scheduling/domain` only. The new comparison sits in a use case, so
  the mutation gate does not cover it; the tests above are the guard.
- The page still shows "Rescheduled" after a no-op. The owner may want different copy.
- If the owner prefers a refusal, block 1 changes to return a `Failure` and the tests on
  the three surfaces change from 200/303 to a refusal. The plan is cheap to flip.
- The no-op returns before `replace_placement`, so it also skips the booking rules for the
  same start (patient lead time, start now in the past, availability changed since
  booking). A same-start call then succeeds quietly where it would have been refused. No
  row is written, so no invariant breaks; name it in the run log.

## Architect review

Verdict: approve.

- Ladder: one comparison in the use case, no new domain function, dependency or refactor.
  Right layer: the use case owns the transaction, the lock and the write, and all four
  surfaces end there.
- Ordering checked against `appointment_changes.py`: `_lock_for_change` (record rule,
  status table, stale version) runs first, then the status check, then the no-op. A
  non-owner, a stale version and a `CHECKED_IN` appointment keep their answers. The comparison
  sits under the `select_for_update` row lock.
- Test-first: the four use-case tests name behaviours and give expected values from §5.6
  and §4 (audit and notification counts). The red proof is stated. Edge paths (second call,
  non-owner, wrong status) are covered, not only the happy path.
- Surfaces: `/api/v1` (`appointment_actions.py`), page (`clinician_reschedule.py`,
  `patient_reschedule.py`, `admin_appointment_reschedule.py`) and FHIR all end in
  `reschedule_appointment`. The page test sends CSRF and `Origin`, as the rule requires.
- Corrections to the focal point, not blocking: FHIR does not reach block 1 for a same-start
  update. `decode_update` returns `NoChange` first (`scheduling/domain/fhir_appointment_write.py`),
  so its test guards that path, and block 1 is not what makes FHIR correct. Also, today's
  same-start call re-chooses a room (`room_id` is None in `replace_placement`), so the red
  test on `room_id` may fail for a second reason. The expected value stays right.
- Security: no new input. Authorization stays server-side in `_lock_for_change`. Audit stays
  append-only; the change only avoids a write. Nothing sensitive is logged.
- Scope: covers the four surfaces and the blast radius (including `demo_seed`
  `test_survives_use.py`). Items 1 to 8 and 10 are named as out of this run. The
  "rescheduled" copy on a no-op is an owner question, named.
- Open for the run: the lead-time and booking-rule bypass in Risks; the mutation gate does not
  cover the use case.
