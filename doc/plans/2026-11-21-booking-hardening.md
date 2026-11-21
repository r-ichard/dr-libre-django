# Task 08a: booking hardening

Focal point: `scheduling/use_cases/email_delivery.py` (items 2, 3) and `appointment_body` in
`scheduling/views/booking_schemas.py` (item 1). Five small independent fixes; no new abstraction.

## Plan per block (one sentence each)

1. **Reason (item 1).** `BookRequest` gets optional `reason`, `CharField(max_length=200,
   allow_blank=True, required=False)` (spec 3.1 caps it at 200; the DB column `Appointment.patient_reason`
   is `TextField`, so the serializer is the only bound and no migration is added).
   `PlacementCommand` gets `reason: str = ""`; `_write` stores it as `patient_reason` on create only.
   `reschedule` keeps the stored value untouched. `_record_booking` / `AuditMetadata` take no reason
   (the allow-list type has no field for it), `notify_patient` and `EmailSubject` stay as they are, and
   no log line gets it.
   **Where it is returned:** `appointment_body` adds `"reason"`. Every caller of that function is
   already a record-rule-scoped caller: `list_appointments._visible_to` (patient own, clinician own,
   admin all), `place_appointment` (authorize_booking: patient self, own clinician, admin), and cancel /
   reschedule / status actions (`guard_record`). So the patient, the appointment's clinician and an admin
   are the only readers; test proves it for the other patient and other clinician (403/empty list).
   The docstring that says "no reason" is rewritten: reason yes, clinical notes and cancellation text no.
2. **Total send (item 2).** `send_notification_email`: widen the `except (OSError, SMTPException)` to
   `except Exception` around building and sending the message; log with `logger.exception`
   (trace), `notification_id`, `correlation_id`; return False, row stays pending. `# noqa: BLE001` not
   needed if ruff does not select BLE; otherwise `# noqa: BLE001` with the code named. Also wrap
   `_send_in_context` so a failure in the lookup or lock (DB error) is logged and swallowed: nothing the
   `on_commit` callback raises may reach the client. `send_pending_emails` (command) keeps working: one bad
   row no longer stops the batch.
3. **Kinds (item 3).** Choice: **make the builder total**, not filter. `_message_of` no longer raises when
   `appointment is None`: `EmailSubject` fields `starts_at`, `hospital_name`, `provider_name` become
   optional and `patient_email` omits the When/Where/Provider lines whose value is absent, so
   WAITLIST_OFFERED, WAITLIST_BOOKED, APPOINTMENT_REMINDER notifications with only a `waitlist_entry` still
   mail title + sign-in link (spec 7.6, 11: every notification is mailed). Reason for the choice: a filter
   would leave the waitlist offer, the one email that needs a fast answer, unmailed. Task 09 may add richer
   text per kind later; it has a second caller then. `select_related` gains no new join.
4. **Size gate (item 4).** New `scripts/size_cap.py` (stdlib `ast`, run with `uv run python`, because
   host `python3` is 3.11 and cannot parse the PEP 695 generics in this repo): fails on a tracked
   `*.py` over 500 lines, or a function/method over 100 lines (`end_lineno - lineno + 1`), skipping
   `/migrations/`, with `--self-test` like the other gates. `make gate` calls it; `make gate`
   also runs its self-test. Constants `MAXIMUM_FILE_LINES = 500`, `MAXIMUM_FUNCTION_LINES = 100`
   at top. Only `test_appointment_actions.py` (719) is over 500; `test_placement.py` (426) and
   `test_version.py` (409) pass the hard limit and are not split (task wording: split the files that
   fail). No function is over 100 (checked with a 3.13 parse before writing; re-run at green).
   Split `test_appointment_actions.py` along what it tests: stays = cancel, reschedule, status actions
   (lines 1-495 + 601-720 room tests); new `test_appointment_emails.py` = email, commit timing, retry,
   batch (lines ~497-680, plus `MailServerDownBackend`, `_plant_free_text`). Shared helpers/fixtures
   (`_signed_in`, `_appointment`, `_post`, constants, autouse fixtures) move to `scheduling/views/conftest.py`
   (exists) or a plain `appointment_action_support.py` imported by both; pick conftest for fixtures and the
   support module for helper functions. Pure move; test names and bodies unchanged.
5. **Range (item 5).** One helper `refuse_empty_range(values)` in `booking_schemas.py`, returning
   `Failure.invalid_input([FieldMessage("to", "The end must be after the start.")])` when both `from` and
   `to` are present and `to <= from`. Called by `SlotsView.get` and `AppointmentsView.get` after schema
   validation, before any use case. Second caller exists, so the helper is justified.

## Files, in order
Tests first (red): `scheduling/views/test_appointments.py` (reason), `test_slots.py`,
`test_appointment_filters.py` (range), new `scheduling/use_cases/test_email_delivery.py` (items 2, 3),
`scripts/test_size_cap.py` (item 4). Then: `booking_schemas.py`, `placement.py`, `appointments.py`,
`slots.py`, `email_delivery.py`, `domain/email_content.py` (+ `test_email_content.py`), `scripts/size_cap.py`,
`Makefile`, the split. Move the split last, so the diff of the move stays pure.

Not touched: models and migrations, `audit_metadata.py`, `notifications.py`, `appointment_changes.py`,
`appointment_list.py`, `test_placement.py`, `test_version.py`, templates, demo seed, docs other than
`doc/backlog.md` status.

## Invariants and blast radius
- Double booking: `_write` change adds one column value only; locks, checks and exclusion constraints
  untouched. Existing placement/locking tests must stay green.
- Authorization stays server-side from the session; `reason` never decides access.
- Audit stays append-only; booking audit metadata gains nothing. Test: audit row for a booking with a
  planted reason contains no trace of it (metadata JSON, notification body/title, mail outbox, captured log).
- Blast radius: POST/GET `/appointments` response gains one key (`reason`, string, `""` when none);
  email text for appointment-less notifications; `make gate` can now fail on size.

## Failing tests first (`returns_X_when_Y`)
- `returns_201_and_reason_when_patient_books_with_reason`: body reason "knee pain" stored as
  `patient_reason`, echoed as `reason`.
- `returns_400_invalid_input_when_reason_is_201_characters`; `returns_201_when_reason_is_200_characters`;
  `returns_empty_reason_when_booking_without_one`.
- `returns_no_reason_in_audit_notification_email_or_log_when_booking_with_reason`.
- `returns_reason_to_patient_clinician_and_admin_only`: appointment's patient, its clinician, admin see
  it in the list; other patient and other clinician list is empty.
- `returns_reason_unchanged_when_appointment_is_rescheduled`.
- `returns_201_and_pending_notification_when_mail_backend_raises_runtime_error`: booking answers 201, row
  `email_pending` stays True, one log record with `exc_info`, no reason in it.
- `returns_pending_and_logged_trace_when_building_the_message_fails` (e.g. recipient lookup raises).
- `returns_other_rows_sent_when_one_pending_row_raises` (batch).
- `returns_email_with_title_and_sign_in_link_when_notification_has_no_appointment`, one per kind
  WAITLIST_OFFERED, WAITLIST_BOOKED, APPOINTMENT_REMINDER (parametrised); unit test in
  `test_email_content.py`: no When/Where/Provider lines when absent, no reason ever.
- `returns_400_invalid_input_when_slots_to_equals_from`, `..._is_before_from`; same two for
  `/appointments`; `returns_200_when_only_one_end_is_given` for appointments.
- Gate: `size_cap` returns violation for a 501-line file, none for 500; for a 101-line function, none for
  100; ignores migrations; real repo passes after the split.

## Trust boundaries
- Client body `reason`: validated by `StrictSerializer` (type, 200 max; unknown fields still refused),
  stored via ORM only, rendered as JSON only (never in HTML, mail, log).
- Query `from`/`to`: schema first (offset required), then ordering rule; actor scope unchanged.
- Mail server and DB errors in `on_commit`: crossed after commit; contained and logged without sensitive
  data (ids and class names only; the traceback is Django's own, message text may name the recipient
  address, so the logger is called with the exception but the `extra` carries ids only).

## Vocabulary
Patient, Clinician, Admin, Appointment (`patient_reason`), Notification (kinds of spec 11),
AuditLogEntry, WaitlistEntry (appointment-less notifications).

## Not doing
No model field or migration for the reason bound, no per-kind email templates, no retry scheduler, no
reason in the notification or email, no split of files under 500 lines, no new dependency, no change to
cancel reasons.

Open point for the architect: tracebacks may include the recipient email in an exception message
(`SMTPRecipientsRefused`). Logging with the trace is what the task asks; accept, or log `error_class`
only for SMTP errors and the trace for the rest.

## Architect review

Verdict: approve.

- Ladder: five small fixes, one helper with two callers, no dependency, no migration. Right layers (schema in views, storage in use case, content in domain).
- Item 1: `appointment_body` has only record-scoped callers (verified: `appointments.py`, `appointment_actions.py`); the 200-char cap matches spec 3.1. Audit, notification, email and log exclusion has a named test. Good.
- Item 2: widening to `except Exception` plus containing the lookup/lock failure covers "nothing raised may change the answer". `BLE` is not in ruff `select`, so no `noqa` needed.
- Item 3: total builder is a sound choice; spec 11 says every notification is mailed.
- Item 4: only one file exceeds 500 lines (719). Splitting only that one matches the 500/100 thresholds; the 426 and 409 line files pass the new gate. Keep the move pure and last.
- Item 5: one helper, two callers, `invalid_input` as a value.
- Open point (trace may contain a recipient address): condition for the build stage: log with `exc_info` as task requires, but `extra` carries ids and class only, and a test asserts the planted reason is absent from log output. If an SMTP error message holds the address, that sits in Django-level traceback text only; accept, note in the PR as a risk (spec 11 forbids emails in audit metadata, not operational logs, but note it).
- Check at green: the new email test file must keep the existing autouse fixtures it depends on after the split (shared helpers in conftest/support module).
