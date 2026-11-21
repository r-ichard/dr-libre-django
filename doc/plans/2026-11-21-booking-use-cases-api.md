# Plan: booking use cases and API (task 07)

Spec: `drlibre-specs.md` 5.1, 5.2, 5.3, 5.4, 5.5, 4, 7.1 (holds count), 11, 14. Model plan "Waits for
its use case" rows: same department, roles behind `patient`/`clinician`, active room, room of the
clinician's department, end = start + duration. No migration, no new dependency, no model change.

## Focal point

`place_appointment` in `scheduling/use_cases/placement.py`: its lock order. A wrong order double
books or deadlocks. Everything else is reads, small pure tables and thin views.

## Locks (the answer to "what, in which order")

One `transaction.atomic()`. Inside it, `SELECT ... FOR UPDATE` in one global order, always by kind
first, then by id ascending within a kind:

1. **ClinicianProfile rows.** Named clinician: that one. First available: every active clinician of
   the type's department with weight > 0, one ordered statement (`order_by("id")`). This also
   serialises round-robin ranking and the `last_assigned_at` write.
2. **Patient `User` row.** Serialises one patient's bookings: patient overlap and the "fewer than 3
   open online bookings" count (5.3).
3. **Room rows.** Named room: that row. Room needed and not named: every active room of the
   clinician's department, one ordered statement. Serialises room choice, so two clinicians sharing
   a default room both win, with different rooms.

Every placement takes the same kinds in the same order, ids ascending inside a kind, so no cycle,
so no deadlock. Reads after the locks see committed rows (READ COMMITTED, new snapshot per
statement). Checks run only after all locks are held.

Last line: the three exclusion constraints. The insert runs in a nested `atomic()` savepoint; an
`IntegrityError` whose cause is an exclusion violation (`psycopg.errors.ExclusionViolation`, name
from `diag.constraint_name`: `appointment_no_overlap_for_<clinician|patient|room>`) becomes
`Failure.conflict([resource])`. Any other `IntegrityError` re-raises (broken invariant, 500).

## Blocks, one sentence each

Domain (pure, no ORM/clock; tests beside code; covered by `make mutate`):

1. `scheduling/domain/placement_rules.py`:
   - `authorize_booking(actor_role, actor_clinician_id, named: NamedParties) -> Failure | BookingParties`:
     5.4 as a table, returning `forbidden` or `invalid_input` fields as values.
   - `choose_room(needs_room, named_room_id, default_room_id, rooms_in_code_order, busy_room_ids) -> RoomChoice`:
     step 5 exactly.
   - `booked_notification_text(starts_at, time_zone)`: the time and nothing else.

Use cases (own transaction and authorization; callers above callees):

2. `scheduling/use_cases/schedule_loading.py`: `load_schedules(clinician_ids, appointment_type, window, now)
   -> dict[UUID, ClinicianSchedule]` in four queries total, whatever the clinician count: rules
   (`clinician_id__in`), time off overlapping the window, active appointments overlapping the window
   widened by the type's buffer, unexpired holds (`expires_at > now`, same widening) mapped to
   `ExistingAppointment(status=BOOKED)` so they block exactly like appointments, buffer included. Used
   by both the slot query and placement, so the two cannot disagree on what is free.
3. `scheduling/use_cases/free_slots_query.py`: `find_free_slots(type_id, clinician_id | None, window)
   -> Result[FoundSlots]`: type active, clinician active and in the type's department, else
   `not_found`; no clinician = one query for the department's active clinicians, then
   `free_slots_by_start`; `QueryTooWide` becomes `invalid_input` on field `to`. Returns offers plus
   the hospital time zone.
4. `scheduling/use_cases/placement.py`: `place_appointment(command: PlacementCommand, actor: User)
   -> Result[Appointment]`. Order: (0) 5.4 authorization and patient identity from `actor` only, patient
   must be active with role PATIENT else `not_found`; (1) type active, clinician and its user active,
   same department else `not_found`; (2) named room active and in the clinician's department else
   `not_found` (judgement: 5.2 names no code, section 4 defines `not_found` as "no such record, or it
   is inactive"); (3) overlaps for clinician, patient, named room, all listed in one `conflict`;
   (4) `violated_rules` with real counts and `slot_is_free` from `load_schedules` over
   [start, start+duration] -> `rule_violation`; (5) `choose_room` -> `no_room_available`; (6) create
   `BOOKED`, `ends_at = starts_at + duration`, audit, notification. `now` from `current_request_context()`.
5. `scheduling/use_cases/placement_checks.py`: steps 0-5 as small functions each returning a value or a
   `Failure`, so `placement.py` stays under the size caps (§5).
6. First available (5.5), inside `place_appointment` when a patient names no clinician: after step-1 locks,
   candidates = locked clinicians with a free slot at that start (from `load_schedules`), `first_available`
   ranks them, the winner goes through steps 1-6, `source=ROUND_ROBIN`, `last_assigned_at = now` saved in the
   same transaction with its own audit entry (`clinician.round_robin_assigned`, changed field
   `last_assigned_at`). None gives `no_clinician_available`. Source is derived (patient + clinician named =
   `ONLINE`, patient without = `ROUND_ROBIN`, staff = `STAFF`), never read from the caller.
7. Audit/notification: `record_audit(AuditEvent("appointment.book", "Appointment", id, AuditMetadata(ids:
   appointment_id, patient_id, clinician_id, appointment_type_id, room_id if any; statuses:
   appointment_status, source_status)), actor)`; `Notification(kind=SCHEDULE_CHANGED, title="Appointment
   booked", body=booked_notification_text(...), appointment=...)`. No names, emails, reasons.

Views (thin, format only; screens later):

8. `scheduling/views/booking_schemas.py`: `SlotsQuery`, `AppointmentsQuery`, `BookRequest` as
   `StrictSerializer` (unknown fields refused; times must carry an offset; naive is `invalid_input`),
   plus response mappers: instants as UTC ISO 8601 `Z`, `time_zone` beside them.
9. `scheduling/views/slots.py`: `GET /api/v1/slots`, `public()`; query `appointment_type_id`,
   `clinician_id?`, `from`, `to`. Body `{"time_zone", "slots": [{"starts_at", "ends_at", "clinician_ids"}]}`.
10. `scheduling/views/appointments.py`: `GET` (`signed_in()`; filters `patient_id`, `clinician_id`, `status`,
    `from`, `to`, `page`, `page_size` <= 100, default 20; queryset scoped first by role: patient = own, clinician =
    own calendar, admin = all; a filter naming someone else yields an empty page, never a leak; order
    `starts_at`, `id`; response `{count, page, page_size, results}`) and `POST` (`signed_in()`; body
    `appointment_type_id`, `starts_at`, `clinician_id?`, `patient_id?`, `room_id?`; 201 with the appointment).
    Appointment JSON: ids, `starts_at`, `ends_at`, `time_zone`, `status`, `source`; no reason or notes.
11. `drlibre/urls.py`: two routes above the `NotFoundView` catch-all.

## Files, in order

New: `domain/placement_rules.py`, `domain/test_placement_rules.py`, `use_cases/schedule_loading.py`,
`use_cases/free_slots_query.py`, `use_cases/placement_checks.py`, `use_cases/placement.py`, their
`test_*.py`, `views/booking_schemas.py`, `views/slots.py`, `views/appointments.py`, `views/test_slots.py`,
`views/test_appointments.py`; edit `drlibre/urls.py`. Builders in `models/builders.py` may get a small
helper only if three tests need it.

Deliberately untouched: models, migrations, existing domain modules (engine stays as task 06 left it),
audit writer, request middleware, sessions, auth views, page views, templates, seed. Not done: cancel,
reschedule, status change (08), waitlist (09), hold creation or removal (12), email (08), patient reason,
search endpoints, FHIR.

## Invariants and blast radius

- No double booking: locks above plus constraints; `conflict` never a 500.
- Authorization server-side from the session user; body never names the actor; `patient_id` or `room_id`
  from a patient, `clinician_id` of another clinician from a clinician: `forbidden`. Admin without a clinician
  or staff without a patient: `invalid_input`.
- Audit append-only: entry written through `record_audit` inside the placing transaction; failing audit
  rolls back the appointment.
- Blast radius: new code only plus two URL lines. Task 12 must delete its own `BookingHold` inside the
  transaction before calling placement (a hold blocks 5.3 "slot is free" for everyone, its owner too). Said
  here so it is not a surprise there.

## Failing tests first (`returns_X_when_Y`)

Domain (`test_placement_rules.py`): `returns_forbidden_when_patient_names_a_patient`, `..._names_a_room`;
`returns_forbidden_when_clinician_names_another_clinician`; `returns_own_calendar_when_clinician_names_nobody`;
`returns_invalid_input_when_admin_names_no_clinician`; `returns_default_room_when_free`;
`returns_first_free_active_room_in_code_order_when_default_is_busy`; `returns_no_room_available_when_all_busy`;
`returns_no_room_when_type_needs_none`; `returns_named_room_when_staff_names_one`;
`returns_text_with_local_time_only_when_booked` (no names; hospital zone).

Slot query (use case, database): `returns_union_one_entry_per_start_when_no_clinician_named`;
`returns_no_slot_when_unexpired_hold_covers_it`; `returns_slot_when_hold_expired`;
`returns_not_found_when_type_inactive`, `..._clinician_in_other_department`, `..._clinician_user_inactive`;
`returns_invalid_input_when_range_over_31_days`; `runs_constant_queries_when_ten_clinicians` (`assertNumQueries`
equal for 2 and 10 clinicians).

Placement, one per step and code: `returns_booked_appointment_with_end_start_plus_duration_when_patient_books`
(end never from caller; schema refuses `ends_at`); `returns_not_found_when_type_inactive`;
`..._clinician_in_other_department`; `..._patient_inactive`; `..._patient_is_not_role_patient`;
`..._room_inactive`; `..._room_in_other_department`; `returns_conflict_naming_clinician_when_clinician_busy`;
`..._patient`, `..._room`, `returns_conflict_naming_all_three_when_all_three_overlap`;
`returns_conflict_not_error_when_constraint_catches_what_the_check_missed` (check patched to see nothing);
`returns_rule_violation_lead_time_too_short_when_patient_books_in_119_minutes` and the other four rules
(staff exempt except availability); `returns_no_room_available_when_type_needs_room_and_none_free`;
`returns_audit_entry_and_notification_in_same_transaction` and `returns_no_appointment_when_audit_write_fails`;
notification title "Appointment booked", kind SCHEDULE_CHANGED, body time only; steps stop at the first failure
(`returns_not_found_not_conflict_when_type_inactive_and_slot_taken`).
First available: `returns_never_assigned_clinician_first`; `returns_largest_idle_times_weight_next`;
`returns_source_round_robin_and_sets_last_assigned_at_to_now`; `returns_no_clinician_available_when_none_free`;
`returns_weight_zero_clinician_never`.

Races (two real threads, two connections, `Barrier`, committed data, `django_db(transaction=True)`):
`returns_exactly_one_booking_when_two_race_for_same_clinician`, `..._same_patient`, `..._same_named_room`;
`returns_both_booked_with_different_rooms_when_two_clinicians_share_a_default_room` (proves room lock, the
constraint alone would give a conflict); `returns_one_booking_when_patient_with_two_open_races_two_more`
(proves patient lock); `returns_both_booked_with_different_clinicians_when_two_patients_race_first_available`
(proves clinician lock). Run each 20 times. Trap: `transaction=True` teardown TRUNCATEs the append-only audit
table and the trigger refuses it (comment in `use_cases/test_audit.py`). The race module owns a fixture that
disables the audit trigger (`ALTER TABLE scheduling_auditlogentry DISABLE TRIGGER USER`) before the flush and
re-enables it after, ordered so re-enable runs after Django's flush. If that cannot be made reliable, fall back
to a separate throwaway database created by the module; the implementer reports which. Nothing else uses
`transaction=True`.

API: slots `returns_200_without_session`, `returns_400_when_range_over_31_days`, `..._naive_time`,
`..._unknown_parameter`, `returns_utc_z_times_with_hospital_zone_named`; appointments `returns_401_without_session`
(list and book), `returns_only_own_when_patient_lists`, `returns_empty_page_when_patient_filters_by_other_patient`,
`returns_only_own_calendar_when_clinician_lists`, `returns_all_when_admin_lists`, `returns_page_of_20_with_count`,
filters by status and range; `returns_201_when_patient_books`, `returns_403_when_patient_names_patient`,
`returns_400_when_body_has_ends_at`, `returns_409_conflict_with_resources_list`, `returns_422_rule_violation`,
`returns_409_no_clinician_available`, `returns_403_when_origin_foreign` (existing guard).

Prove tests can fail: remove each lock and each check once, see the matching test go red; delete the constraint
translation, see the patched-check test raise 500.

## Trust boundaries

HTTP body and query: `StrictSerializer`, ids as UUID, aware datetimes only, enums checked, sizes bounded.
Actor: only `request.user` through `signed_in_user`. Resource ownership (patient sees own, clinician own
calendar): checked in the query scope, server-side. Database: parameterized ORM only. Logs and audit: ids,
statuses only.

## Vocabulary used

Visitor (public slots), Patient, Clinician (`ClinicianProfile`), Admin, Hospital (time zone), Department,
AppointmentType, AvailabilityRule, TimeOff, Appointment, Notification, AuditLogEntry, BookingHold (read only),
Room, Session (identity).

## Will not do

No abstraction beyond the two shared helpers that already have two callers (schedule loader, placement
checks used by one use case but split for size caps only). No advisory locks, no serializable isolation, no new
index or migration (measure first), no retry loop on conflict, no change to the engine.

## Architect review

Verdict: approve.

- Ladder: no migration, dependency or model change. Two shared helpers each have two callers (schedule loader: slots and placement); `placement_checks.py` is a size-cap split, acknowledged in "Will not do". Fine.
- Locking: single global order (clinicians by id, patient user, rooms by id), checks after locks, constraints as last line with `IntegrityError` translated by constraint name. Answers the task's "what, in which order". Each lock has a race test that proves it (room lock, patient lock, clinician lock).
- Spec fit: steps 1-6 order matches 5.2; 5.4 table matches; 5.5 matches; codes and statuses match section 4 (409 conflict, 422 rule_violation). `not_found` for a named room that is inactive or in another department is a stated judgement based on section 4; acceptable.
- Security: identity from session only, strict schemas, list scoped by role before filters, audit ids and statuses only, no reason or notes in output.
- Tests: first tests are behaviour-named with spec values (119 minutes, 20 per page, 31 days), cover error paths and stop-at-first-failure.
- Non-blocking notes for the implementer:
  1. Races: the audit trigger fixture for `transaction=True` is the riskiest part; implementer must report which fallback was used.
  2. `rule_violation` should list every violated rule from the engine's `violated_rules`, not only the first; test it.
  3. Round robin: re-verify candidate freeness after the clinician locks, as planned, not before.
  4. The patient-with-two-open-races test needs the 3-open-bookings count read after the patient lock; keep the count query inside the atomic block.
  5. `make mutate` must still report: new domain module `placement_rules.py` will need survivors killed or listed in `mutation-equivalents.txt`.
