# Review: task 08, appointment changes, notifications and email

Diff: `main...HEAD`, 22 files. Commit order checked: `prove` (053377d) touched only
`test_email_content.py` and `test_appointment_actions.py`. No product or migration line changed
between `verify_green` and `prove`. Gate, lint and tests were green in the `check` stage.

## What I confirmed at a glance
- `appointment_changes.py`: three use cases, each lock, record rule, transition table, write,
  audit and notify in one `transaction.atomic()`. Actor comes from `signed_in_user(request)`, never the body.
- `notifications.py`: one row per event, `on_commit` send. Body is time only.
- `email_content.py`: input type has no field for reason or note, so none can reach a message.
- `placement.py`: reschedule goes through `_place` with `replacing`, not a copy. Ignored id is
  passed to the clinician schedule, conflict and room queries.

## What forced me to trace
- Reschedule lock order. The appointment is locked first, then clinicians, patient, rooms. Booking
  never locks an existing appointment row, so no cycle with the global order of 5.2.
- `RESCHEDULE` rules for a patient. Lead time and 24 h window use the old start. The open-bookings
  limit applies to `BOOK` only, so a patient at the limit can still move an appointment. Correct.
- Room preference: `current_room_id or clinician.default_room_id`, tested both ways.

## Findings

### Later 1 (low): SMTP call inside the request
`email_delivery.py:35`, `notifications.py:36`. The `on_commit` callback sends synchronously, so the
HTTP response waits up to the 10 s mail timeout when the server hangs. The change is safe (already
committed, row stays pending), but the "must not block" wording is only met for the transaction,
not the response. Fix: leave the send to the job (task 09) and keep `on_commit` as best effort, or
accept it and say so in the ADR.

### Later 2 (low): non-mail exceptions escape `on_commit`
`email_delivery.py:38`. Only `OSError` and `SMTPException` are caught. Any other error in the
callback (`ValueError` at line 70 when an appointment is missing, a template or encoding error)
propagates after commit and the client sees a 500 for a change that happened. The row stays pending
so nothing is lost. Fix: in `_send_in_context`, log and keep the row pending for the broader failure.
Never swallow silently.

### Later 3 (low): row lock held across the SMTP call
`email_delivery.py:30-47`. `select_for_update(skip_locked=True)` is held while sending. This is
what gives send-once under concurrency, and it only locks the notification row. A slow server holds
that row up to 10 s. Fine at this scale; revisit with the scheduler.

### Later 4 (low): patient reschedule of a type not bookable online
`placement_checks.py` reuses `type_bookable_online`, so a patient cannot reschedule a staff-booked
appointment of an in-person-only type. Check against 5.3 and decide. Not a security issue.

### Later 5 (nit): `_audit` and `_record_booking` build metadata separately
`appointment_changes.py:121`, `placement.py` `_record_booking`. Two similar id dicts. Merge on a
third caller.

## Checks 3 to 8
- Authorization: record rule on every use case. Route access declared (`signed_in`, `roles`).
  Missing appointment gives `not_found` before role, except a patient on a status action, who gets
  403 from the route (tested at line 682).
- Schemas: `StrictSerializer` on all five bodies. Reason max length 1000 is ours and commented.
- Logs: ids and exception class only; no reason, email address or body.
- Double booking: conflict check and room check inside the transaction after row locks. The DB
  exclusion constraints stay as backstop, `IntegrityError` mapped to `conflict`.
- Tests: spec-derived. Boundary 24 h exact and 23h59m, planted reason and note, rollback, retry-once,
  mail-down and room preference are all present. Guard tests came from breaking the implementation.
- Names and comments fine. No escape hatch added (`# type: ignore[attr-defined]` in tests names its code).
- Scope: migration `0007`, data-model regenerated, two env vars in `.env.example` and settings. No
  dependency added.
- Plan states the mail-down behaviour (plan lines 57-64).

## Blocking
None.

## Later
1. Synchronous SMTP in the response path.
2. Catch and log non-mail exceptions in the `on_commit` send.
3. Row lock held across SMTP call.
4. Patient reschedule of in-person-only type: confirm against 5.3.
5. Merge duplicate audit metadata builders on a third caller.
