# Task 09: waitlist, reminders and scheduled jobs

Focal point: new use cases `scheduling/use_cases/waitlist.py` (join, offer, accept) and the pure rules
`scheduling/domain/waitlist_rules.py`. Everything else is a thin caller: the cancel hook, four API views,
the job runner and the worker command. The existing placing use case is called, not changed.

## Blocks (one sentence each)

1. **Domain `waitlist_rules.py` (pure, mutation-gated).** `entry_matches_slot`, `best_match` (oldest `created_at`,
   ties lowest id, among entries whose preferred clinician is empty or the freed one and whose
   `earliest_at <= slot.start` and `slot.end <= latest_at`, slot start in the future), `first_offerable_slot`
   (earliest start, ties lowest id, same type and window, future, not already held), `authorize_join`
   (patient: self only, naming another patient is `forbidden`; admin: must name a patient; clinician: `forbidden`),
   `expiry_decision` (see policy), `is_reminder_due` (`BOOKED`/`CONFIRMED`, `now < starts_at <= now + 24 h`).
   Types are plain dataclasses of ids and instants; no ORM.
2. **Domain `job_schedule.py`.** `is_due(last_run_at | None, interval, now)`; the worker's only decision.
3. **Vocabulary.** `WaitlistStatus` becomes a `StrEnum` in `domain/vocabulary.py` (audit statuses need one); the model
   uses `choices_of(...)` like `Appointment`. Same values, so at most a generated choices migration.
4. **Use case `waitlist.py`.**
   - `join_waitlist(command, actor)`: `authorize_join`, active type (`active_appointment_type`), active preferred clinician
     of the type's department, active patient, window with `earliest < latest` and `latest > now`, else `not_found` /
     `invalid_input`. Creates `WAITING` entry, audit `waitlist.join`. No notification (table 11 has none).
   - `offer_freed_slot(appointment)`: called from `cancel_appointment` after its notify, same transaction. Locks
     candidate `WAITING` entries (`select_for_update`), `best_match`, sets `OFFERED` + `offered_appointment`, audit
     `waitlist.offer`, notifies. The partial unique index "one offer per appointment" stays the last line.
   - `offer_waitlist_entry(entry_id, actor)` (admin): locks entry (`WAITING` else `invalid_transition`), loads
     cancelled future appointments of the type inside the window (and of the preferred clinician if named) that no
     `OFFERED` entry holds, picks with `first_offerable_slot`, checks the clinician is free then with the free-slot
     computation of placement (`_free_clinician_ids` in `placement.py` loses its underscore; second caller), then
     offers as above. Nothing found: `no_clinician_available` (409; no new code in the contract, spec silent).
   - `accept_offer(entry_id, actor)`: lock entry, `guard_record` (own patient or admin), `OFFERED` else
     `invalid_transition`; `place_appointment` for offered clinician, type, start (patient id = entry's), so
     conflict and booking rules apply, a failure is returned as is and the entry stays `OFFERED`. On success: entry
     `BOOKED` (save, version bumps), then appointment `waitlist_entry = entry`, `inherited_version = entry.version`
     (final, ADR 0003), save. Audit `waitlist.accept`, notify `WAITLIST_BOOKED`. `PlacementCommand` unchanged.
5. **Notifications.** `notifications.py` gains `notify_waitlist_offer(entry)`. The `WAITLIST_OFFERED` row links
   `waitlist_entry` only, never the freed appointment (it is another patient's record, reason included); body is the
   time only. `email_delivery._message_of` reads the offered appointment through the entry for time, provider,
   hospital. Accept sends `WAITLIST_BOOKED` linked to the new appointment and entry. Note: placing also sends the
   usual "Appointment booked" (5.2 step 6), so an accept yields two notifications; both are required by 5.2 and
   table 11, accepted.
6. **Reminders `use_cases/reminders.py`.** `send_reminders(actor | None) -> int`: select `BOOKED`/`CONFIRMED`
   appointments starting in the window with no reminder (`~Exists`), `select_for_update(skip_locked=True)`; per
   appointment a nested `atomic` + `notify_patient(APPOINTMENT_REMINDER, "Appointment reminder")`. Overlap safety:
   skip_locked covers runs that overlap in time, the unique constraint `notification_one_reminder_per_appointment`
   covers a run whose snapshot predates the other's commit (`IntegrityError` on that constraint is skipped, any
   other re-raised). One audit entry `reminder.run`, `reminder_count`, only when count > 0; actor is the admin or None.
7. **Housekeeping.** `expire_waitlist()` and `purge_expired()` in `use_cases/waitlist_expiry.py` and
   `use_cases/purge.py`. Policy below. Purge deletes `Session.expires_at < now` and `SignInFailure.failed_at <
   lockout_rules.window_start(now)`, audit `housekeeping.purge` with `session_count`, `sign_in_failure_count` when any.
8. **Jobs `scheduling/jobs/runner.py`.** `run_job(job, now)`: fresh `uuid4().hex` correlation id, binds a
   `RequestContext(now)`, runs the job in `transaction.atomic()`, logs one JSON line `{job, counts}` via logger
   `scheduling.jobs`; any `Exception` is logged (`logger.exception`, formatter already drops messages) and swallowed.
   `JsonFormatter` allowlist gets `job` and `counts`. Exception: the email job runs without an outer transaction,
   because task 08 sends per notification inside its own transaction; an outer one would roll back "sent" flags
   after mail left and resend.
9. **Commands.** `send_reminders`, `expire_waitlist`, `purge_expired` and the existing `send_pending_emails`
   (moved onto `run_job`) each print their counts; `run_worker` loops: every second, for each job where `is_due`,
   `run_job`; first tick runs all. Clock read (`datetime.now(UTC)`) lives in the command, not use cases.
10. **Compose.** Service `worker`: same image as `web` (`image:` tag on both, `build: .` on web), same env via a YAML
    anchor, `command: python manage.py run_worker`, `depends_on` web healthy (migrations done), db, mail.
11. **API** `views/waitlist.py`, `views/jobs.py`, schemas in `booking_schemas.py`/new `waitlist_schemas.py`, routes in
    `drlibre/urls.py` before the `api/v1/` catch-all: `POST /waitlist` (201; patient, admin; clinician 403),
    `POST /waitlist/{id}/accept` and `/offer` (empty body), `POST /jobs/reminders` (admin; `{"reminder_count": n}`).
    Strict bodies, unknown fields rejected, actor from session. Body of an entry: id, status, type id, preferred
    clinician id, window, and for `OFFERED` an `offer` of start, end, time zone, provider name, hospital name. Never
    `patient_reason`, never the freed appointment's id or patient.
12. **Carried from 08a.** `git mv scheduling/views/appointment_action_support.py scheduling/views/test_appointment_support.py`,
    fix four imports, delete the per-file `S101` line in `pyproject.toml`. `appointment_body` untouched.

## Policy: offers that go stale (spec silent)

Run by `expire_waitlist` every run, per entry, via `expiry_decision`:
- `WAITING`, `latest_at < now` -> `EXPIRED`.
- `OFFERED`, offered slot start `<= now` (passed), or an active appointment of the offered clinician now overlaps
  the offered window (taken): if `latest_at < now` -> `EXPIRED`, else back to `WAITING` with the offer cleared, so a later
  cancellation can match it again. Accept on a taken slot still answers `conflict` and changes nothing.
One audit entry per changed entry (`waitlist.expire`, `waitlist.release`).

## Schedule (worker tick 1 s)

reminders every 10 min (24 h window, so at most 10 min late); waitlist expiry every 5 min; pending emails every
1 min (retry and offer latency; batch 100); purge every 60 min.

## Files in order

`domain/vocabulary.py`, `domain/waitlist_rules.py`, `domain/job_schedule.py`, `models/booking.py` (enum), `use_cases/placement.py`
(rename only), `notifications.py`, `email_delivery.py`, `waitlist.py`, `reminders.py`, `waitlist_expiry.py`, `purge.py`,
`appointment_changes.py` (one call), `jobs/runner.py`, `json_logging.py`, commands, views, schemas, `urls.py`,
`compose.yaml`, rename + `pyproject.toml`, `doc/data-model.md` if rendering requires, `mutation-equivalents.txt` only for
explained survivors.
**Not touched:** `PlacementCommand`, `appointment_body`, models/migrations beyond a generated no-op, screens, FHIR,
audit writer, `place_appointment` logic.

## Invariants and blast radius

No double booking (accept goes through placement; exclusion constraints stay). Authorization server-side from session
(`guard_record`, `roles`). Audit entry in the same transaction as each write; metadata ids/counts/statuses only. Entry
`BOOKED` implies linked appointment and matching `inherited_version`. Cancel now also matches the waitlist: a failure
there rolls back the cancel (accepted, one transaction). Reads of `Notification.appointment` stay unchanged.

## Failing tests first (`returns_X_when_Y`)

Domain: `returns_oldest_entry_when_two_match`; `returns_lowest_id_when_created_at_ties`; `returns_none_when_preferred_clinician_is_another`;
`returns_entry_when_preferred_clinician_empty`; `returns_none_when_slot_ends_after_latest_at`; `returns_entry_when_slot_fits_window_exactly`;
`returns_earliest_slot_when_several_cancelled`; `returns_none_when_slot_past`; `returns_forbidden_when_clinician_joins`;
`returns_forbidden_when_patient_names_other_patient`; `returns_expired_when_waiting_latest_passed`; `returns_waiting_when_offered_slot_passed_and_window_open`;
`returns_expired_when_offered_slot_taken_and_window_closed`; `returns_due_when_never_run`; `returns_not_due_when_interval_not_elapsed`;
`returns_due_when_interval_exactly_elapsed`; reminder window edges (exactly 24 h in, 24 h + 1 s out, status `CANCELLED` out).
Use cases / API: `returns_201_when_patient_joins`; `returns_403_when_clinician_joins`; `returns_not_found_when_type_inactive`;
`returns_not_found_when_preferred_clinician_inactive`; `returns_400_when_unknown_field`; cancel turns the oldest matching entry
`OFFERED`, linked, patient notified with an email, other entries stay `WAITING`; no match leaves cancel unchanged; failure after
matching rolls the cancel back; manual offer `returns_offered_when_slot_free`, `returns_no_clinician_available_when_clinician_booked`,
`returns_invalid_transition_when_not_waiting`, `returns_403_when_patient_offers`, skips a slot another entry holds; accept
`returns_booked_when_patient_accepts`, appointment linked, `inherited_version` equals entry version, `returns_409_conflict_when_slot_taken`
(entry still `OFFERED`), `returns_rule_violation_when_lead_time_short`, `returns_403_when_other_patient_accepts`, admin may accept;
offer body `returns_no_reason_when_offer_shown` (another patient's `patient_reason` string absent from body, notification, email);
reminders create one per qualifying appointment, none for `CANCELLED`, past, beyond 24 h, twice-run reminds once, two overlapping runs
(threads, `transaction=True`) give one reminder, one audit entry with `reminder_count`, none when zero, admin API `403` for patient;
expiry and purge counts, purge keeps fresh rows and rows inside the lockout window; runner: failing job logged and the next job
still runs, one JSON line with counts and correlation id, distinct correlation ids per run; each command runs alone and prints counts;
worker loop with injected clock runs due jobs only. Rename: the lint config no longer has the `S101` line, `make lint` passes.

## Trust boundaries

HTTP body -> `StrictSerializer` (ids, aware instants, unknown fields rejected); actor = session user; role gates by `roles(...)`;
record rule by `guard_record`; patient id from body honoured only for admin. Worker: no input, actor None, audit actor null.
Management commands: no arguments.

## Vocabulary

Patient, Admin, Clinician, WaitlistEntry, Appointment (freed, new), AppointmentType, ClinicianProfile, Notification, AuditLogEntry,
Session, sign-in failure rows.

## Will not do

No new dependency (no Celery, no cron), no new failure code, no reservation of an offered slot, no change to placement or
`appointment_body`, no waitlist screens, no duplicate-join rule, no settings for intervals, no test for `compose.yaml`
(sandbox has no Docker; orchestrator runs the worker on the host).

## Architect review

Verdict: approve.

- Ladder: no new dependency, placement reused, one rename (`_free_clinician_ids`) justified by a second caller. `job_schedule.is_due` is small and is the worker's only decision, so it is acceptable.
- Layering: matching, ranking, expiry, reminder-due and schedule decisions are pure and mutation-gated. Use cases own the transaction and audit. Views are thin.
- Security: the freed appointment's `patient_reason` is kept out of the notification link, the email and the API body, and `returns_no_reason_when_offer_shown` tests it. Actor comes from the session. Patient id in the body is honoured only for an admin.
- Reminder overlap: `skip_locked` plus the unique constraint is sound. Make sure the overlap test hits the constraint path, where the second run's snapshot predates the first's commit, and not only the lock path.
- Email job outside an outer transaction is correctly reasoned.
- Spec-silent points are stated: stale `OFFERED` goes back to `WAITING` or to `EXPIRED`, and `no_clinician_available` is reused for a manual offer with no slot.

Watch items for the implementer, not blockers:
1. Accept: the `place_appointment` failure must leave the entry `OFFERED` with nothing written, so run the entry save and the appointment link inside the same transaction as placement.
2. The first-tick-runs-all rule means a worker restart re-runs every job. All jobs are idempotent, so this is fine.
3. Add a test that a cancel with a matching entry still audits both the cancel and `waitlist.offer`.
4. The purge test should cover the lockout-window boundary exactly.
