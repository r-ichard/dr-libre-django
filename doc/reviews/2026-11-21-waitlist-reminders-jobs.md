# Review: task 09, waitlist, reminders and scheduled jobs

Scope: `git diff main...HEAD` (50 files). Commits after `verify_green` up to `prove` touch tests only
(`test_waitlist_rules.py`, `test_purge.py`, `test_waitlist.py`); no product or migration line moved. No
migration in the diff, no dependency added (one ruff per-file ignore removed, as asked).

## Confirmed at a glance
- `domain/waitlist_rules.py`: pure matching, offerable-slot, join authorization, expiry decision. No I/O or clock.
- `use_cases/waitlist.py`: join, auto offer inside the cancel transaction (`appointment_changes.py:58`), manual
  offer, accept through `place_appointment`. Entry locked, audit and notification in the same transaction.
- `use_cases/reminders.py`: `skip_locked` plus the existing unique constraint (`models/booking.py:170`) for
  overlap; the IntegrityError is matched on the constraint name and anything else re-raised (no swallow).
- Views thin; `signed_in()` and `roles(ADMIN)` permissions; actor from session; patient/admin rule in the domain.
- Offer body and offer email read the freed slot's time, provider and hospital only; the notification links
  `appointment` only when it is the patient's own (`notifications.py:48-58`). No other patient's reason leaks.
- Helper rename to `test_appointment_support.py`; per-file ruff ignore removed.
- No `Any`, `cast`, bare `noqa`/`type: ignore` in product code. The two suppressions in `test_runner.py` name codes.

## Findings

### Low: offer release/expiry runs under the worker with actor `None`
`use_cases/waitlist_expiry.py:34`. Audit actor is `None` for system changes; consistent with reminders and purge.
No fix needed; noted so the audit reader knows system rows have no actor.

### Low: `_is_taken` checks clinician overlap only
`use_cases/waitlist_expiry.py:46`. An offer whose room or the patient's own slot became unavailable stays
`OFFERED` until accept answers `conflict`. Acceptable (accept re-checks everything); the entry is never booked
wrongly. Fix if wanted: reuse the placement checks.

### Low: manual offer scans all future cancelled slots of the type
`use_cases/waitlist.py:_first_free_cancelled_slot` loads every future cancelled appointment of the type into
memory and probes clinician freeness one by one. Fine at demo scale; bound the query by the entry window.

### Low: worker schedule state is in memory
`jobs/worker.py:run_due_jobs`. Restart runs every job at once; documented as safe because jobs are idempotent.
A failed run counts as run (commented). Two worker replicas would double-run; reminders and emails are
guarded by locks and constraints, expiry and purge are idempotent.

### Low: broad `except Exception` in `run_job`
`jobs/runner.py:31`. Required by the task (failing job must not stop the worker); logged with `logger.exception`
and returns `None`, so not swallowed. The JSON formatter must not print exception values with secrets; a test
(`SECRET` planted) covers it.

### Low: `notify_waitlist_patient` resolves its own appointment with a query per notification
`notifications.py:55`. One extra query per offer or accept. Negligible.

## Blocking
None.

## Later
- Make `_is_taken` also consider room and patient conflicts (or document that accept is the authority).
- Bound the manual-offer candidate query by the entry window.
- Persist job last-run times if the worker ever runs as more than one replica.
