# Plan: task 08, appointment changes, notifications and email

Spec: sections 4, 5.2, 5.3, 5.6, 7.6, 11, 14. Builds on task 07 (`use_cases/placement.py`).

## Focal point

`use_cases/appointment_changes.py`: one locked, audited, notifying transaction per change.
Everything else feeds it or exposes it.

## Blocks, one sentence each

1. `domain/email_content.py` (new, pure, mutated): builds subject and body from title, start,
   hospital zone, hospital name, provider name and sign-in URL. Its inputs have no field for a
   reason or note, so they cannot leak; the time reads `2030-01-07 at 09:30 (Europe/Paris)`.
2. `domain/placement_rules.py`: rename `booked_notification_text` to `time_notification_text`
   (same text, used by every event); update its caller and test.
3. `models/booking.py` + migration `0006`: `Notification.email_pending` (bool, default False,
   partial index where true). Pending = created and not yet mailed. A bool, not a sent-at
   timestamp, because the version trigger (0004) refuses a backfill that does not bump the
   version, and old rows must never be mailed. Regenerate `doc/data-model.md` with
   `render_data_model`.
4. `use_cases/notifications.py` (new): `notify_patient(appointment, event)`. It holds the
   section 11 table (kind, title), creates the row with `email_pending=True` in the caller's
   transaction, and registers `transaction.on_commit` to send that row. Task 07's booked
   notification moves onto it.
5. `use_cases/email_delivery.py` (new): `send_pending_emails(limit)` and the per-row send.
   Each row: `atomic`, `select_for_update(skip_locked=True)` where pending, send with
   `django.core.mail`, clear the flag, audit `notification.email_sent` (ids and field name
   only, actor empty). Failure of the mail server is caught, logged (notification id,
   correlation id, error class; no address), and the row stays pending.
6. `management/commands/send_pending_emails.py` (new): calls block 5, prints the count sent.
7. `use_cases/placement.py` (+ `placement_locks.py`, `placement_checks.py`,
   `schedule_loading.py`): make `_place` take an optional appointment to replace. With it:
   conflicts, busy rooms and free-slot loading ignore that appointment's id; booking rules
   run as `RESCHEDULE` with the current start (lead time, 24 h window, online type, free
   slot; the open-bookings rule stays book-only); the room choice passes the current room as
   the preferred default; the final step updates start, end and room instead of creating,
   with the same `IntegrityError` to `conflict` translation. Lock helpers move to
   `placement_locks.py` to keep files under 300 lines.
8. `use_cases/appointment_changes.py` (new): `cancel_appointment`, `reschedule_appointment`,
   `change_status` (check in, complete, no-show). Shared steps: lock the appointment row
   (`select_for_update`, with hospital relations), `guard_record` for not_found/forbidden
   (clinician: `clinician.user_id == actor.pk`; patient: `patient_id == actor.pk`;
   `may_change_status` decides), then `can_transition` (`invalid_transition` with the current
   status), then for a patient cancel `violated_rules(CANCEL)` with the request clock, then
   write (`cancelled_at = context.now`, reason, status; save raises the version), audit
   inside the transaction, notify.
9. `views/appointment_actions.py` + `booking_schemas.py` + `drlibre/urls.py`: five thin
   `ApiView` classes at `appointments/<uuid>/cancel|reschedule|check-in|complete|no-show`.
   Cancel and reschedule: `signed_in()`. Status actions: `roles(CLINICIAN, ADMIN)`.
   Schemas: `CancelRequest{reason}` (required, trimmed, not blank, at most 1000 characters;
   the limit is mine, the spec names none), `RescheduleRequest{starts_at}` (offset required),
   status actions an empty strict schema. Response 200 with `appointment_body` (no reason).
10. Settings: `EMAIL_SENDER` and `PUBLIC_BASE_URL` read from the environment (`.env.example`,
    `compose.yaml`, `test_settings.py`). The sign-in link is `PUBLIC_BASE_URL + /sign-in`.

## Mail server down

The change commits first and is never undone or slowed by mail: the on-commit send catches
the failure and logs it. The notification stays `email_pending`. The next run of
`manage.py send_pending_emails` (task 09 schedules it) sends it. Delivery is at least once:
a crash after SMTP accepted and before the flag commit sends twice; losing mail is the worse
failure. Two runners at once do not double-send (`skip_locked`). The SMTP client uses a
timeout so a hung server cannot hold the request.

## Files, in order

`doc/plans` (this), `domain/email_content.py` + test, `placement_rules.py` + test,
`models/booking.py`, migration 0006, `doc/data-model.md`, `use_cases/notifications.py`,
`use_cases/email_delivery.py`, `placement*.py`, `schedule_loading.py`,
`appointment_changes.py`, `booking_schemas.py`, `appointment_actions.py`, `urls.py`,
settings and env files, the command. Tests beside each.

Not touched: waitlist matching (task 09), screens, reminders job, FHIR, sign-in and
verification emails, `domain/appointment_status.py` and `booking_rules.py` (already hold the
table and the rules; reuse), `mutation-equivalents.txt` unless a survivor is real.

## Invariants and blast radius

- No double booking: reschedule still ends at the exclusion constraints; ignoring the
  appointment itself never ignores any other.
- Authorization from the session user, never the body; record rule ordering fixed.
- Audit append-only, written in the change's transaction; metadata holds ids, statuses and
  field names, never the reason.
- No reason, note, name or address in in-app text, audit metadata or email.
- Blast radius: task 07 booking (notification path and `_place` signature), `Notification`
  table, settings. The existing placement tests must stay green unchanged except the rename.
- Lock order: appointment row first, then clinician, patient, rooms (task 07's order).
  Placement only inserts appointments, so there is no cycle.

## Failing tests first (`returns_X_when_Y`)

Use cases (`use_cases/test_appointment_changes.py`, request clock bound):
- `returns_success_when_patient_cancels_own_appointment_25_hours_ahead`: status CANCELLED,
  `cancelled_at` equals the clock, reason stored, version up by one, one audit entry,
  one `APPOINTMENT_CANCELLED` "Appointment cancelled" notification.
- `returns_rule_violation_cancellation_window_closed_when_patient_cancels_23h59m_ahead`;
  `returns_success_at_exactly_24_hours` (boundary is 24 h or more); staff cancel inside 24 h.
- `returns_forbidden_when_patient_cancels_someone_elses_appointment`; clinician other than
  the appointment's: forbidden; admin: success; unknown id: `not_found`.
- `returns_forbidden_when_patient_checks_in`; clinician own check-in succeeds, other
  clinician forbidden, admin any; no notification created for status actions.
- `returns_invalid_transition_with_current_status` for each refused pair: complete from
  BOOKED, check in from CHECKED_IN, no-show from CHECKED_IN, cancel from COMPLETED, CANCELLED
  and NO_SHOW, reschedule from CHECKED_IN.
- `returns_invalid_input_when_reason_blank` (API schema level).
- `audit_metadata_never_holds_the_reason`: planted reason absent from every audit row.
- Reschedule: `returns_success_and_keeps_clinician_type_and_room_when_moved_to_free_slot`;
  `returns_success_when_new_slot_overlaps_the_old_one` (self ignored);
  `returns_conflict_when_new_slot_is_taken_by_another_appointment`;
  `returns_rule_violation_outside_availability`; patient `lead_time_too_short` and
  `cancellation_window_closed`; room reassigned when the current room is busy at the new
  time; one "Appointment rescheduled" `SCHEDULE_CHANGED` notification; a failed reschedule
  changes nothing and creates nothing.
- `returns_forbidden_...` and lock: a second change on the same row sees the first's status
  (test with `select_for_update` ordering as in `test_placement_locking.py`).
- Booking still creates "Appointment booked" through `notify_patient`.

Email (`use_cases/test_email_delivery.py`, `domain/test_email_content.py`):
- `sends_one_email_after_commit` (capture on-commit callbacks); body holds the local time
  with the zone name, hospital name, provider name, and the `/sign-in` URL, and no URL with a
  token or query.
- `sends_no_email_when_the_transaction_rolls_back`: no mail, no notification row.
- A planted `patient_reason`, planted `clinical_notes` and planted cancellation reason appear
  in no email subject or body, and the in-app body has no name, reason or address.
- `leaves_notification_pending_when_the_mail_server_is_down`, change still committed;
  `retry_sends_once`: second `send_pending_emails` after a failed first sends exactly one
  mail, third sends none.
- Sender is `EMAIL_SENDER`. Command test: `send_pending_emails` prints the count.

API (`views/test_appointment_actions.py`): per action, 401 signed out, 403 for the wrong
role, 404, 400 unknown field, 409 `invalid_transition` carrying `current_status`, 422 with
`violated_rules`, 409 `conflict`, 200 body without reason; correlation id on every response.

Model: migration check that `email_pending` defaults False and `makemigrations --check` is
clean; data-model document test stays green.

## Trust boundaries

HTTP body and path id: strict schema, UUID path converter, UTC instant with offset, reason
trimmed and bounded. Actor only from `signed_in_user`. Patient identity never from the body.
Outbound mail: content built from a typed value without reason or note; sender and base URL
from the environment; the mail server is outside the transaction. Logs carry ids only.

## Domain entities

Appointment, AppointmentType, Patient, Clinician (public "provider"), ClinicianProfile,
Hospital (time zone), Room, Notification, AuditLogEntry, Admin, User.

## Will not do

No waitlist matching, no scheduler, no outbox table or queue library, no template engine for
email (plain-text body built in the domain function), no HTML email, no new dependency, no
generic abstraction beyond `notify_patient`, no screens, no change to reminder or sign-in
mail. Open question for the reviewer: pytest capture of mail under Django 6.1 `MAILERS`
(`mail.outbox`) is unverified; the red stage proves it first.

## Skipped or unchecked

Reason length limit and SMTP timeout value are my choices. At-least-once delivery accepted.

## Architect review

Verdict: approve.

- Ladder: no new dependency, no outbox table, no template engine. `notify_patient` has two callers (booking, changes), so it earns its place. Reusing `_place` with an optional appointment honours "not a copy".
- Knowledge: every block states one purpose; vocabulary matches CLAUDE.md.
- Tests first: behaviours named with spec values (24 h boundary, each refused transition, planted reason and note, rollback, failed send then retry sends once). Edge and error paths covered.
- Security: strict schemas, actor from session, reason kept out of audit, in-app text and email; sign-in link carries no token; sender and base URL from environment.
- Architecture: thin views, pure email content, one transaction per change with audit inside, expected errors as values, mail after commit.
- Scope: all nine task items covered, including migration, data-model regeneration and the mail-down paragraph.

Notes for implementation, not blockers:
- `email_pending` plus a failed on-commit send relies on the command to retry; make sure the on-commit send never raises into the request (catch all `OSError`/`SMTPException`, not only one class).
- Set the SMTP timeout via settings (`EMAIL_TIMEOUT`) and test the setting exists.
- Check the pending-send audit row (`notification.email_sent`) does not break the "audit written for every write" test counts in task 07 tests.
- Keep `placement.py` under 300 lines after the change (plan already splits locks).
