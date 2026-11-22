# Review: task 23a, FHIR Appointment and booking

Base `cd48726`, head `3da0c9f`. Diff read: 22 files, +2208 lines.

## What I confirmed

- Proof left no trace. Commits after `verify_green` up to `prove` touch tests and `mutation-equivalents.txt` only (`git diff 99273b8 8aa91f6 --stat`).
- Reads: visible rows are built from the caller first (`scheduling/use_cases/fhir_appointment_reads.py:54-111`), so a search only narrows them. Clinical note is loaded only for the viewer's own appointments (`fhir_appointment_loading.py:27-32`).
- Writes call the existing use cases (`place_appointment`, `join_waitlist`, `cancel_appointment`, `reschedule_appointment`, `change_status`), so locks and audit entries are shared (`fhir_appointment_writes.py`). `expected_version` is checked inside the lock (`appointment_changes.py:129-133`).
- Item 13 done: `fhir_bundle.py:41-46` and `fhir_search.py` drop `_sort` where the type has no `name`; `test_fhir_paging.py` follows `next`.
- No `Any`, `cast` or suppression found in the new files; sizes within caps.

## Findings

### Blocker: ClinicalNote declaration and data model not corrected (item 3)
`scheduling/models/booking.py:114` still declares `fhir_not_exposed`; `doc/data-model.md:233-237` still says "FHIR: not exposed". The note is now served as `Appointment.comment`, so the declaration and the generated doc are false. The plan promised this (plan point 14). Fix: `fhir_resources = ("Appointment",)`, regenerate `doc/data-model.md`.

### Blocker: items 14, 15, 16 not implemented
The diff does not touch `fhir_body.py` (`if_match_version` still returns 0 for `W/"0"`, `fhir_body.py:50-57`), `fhir_patient_writes.py`, `admin_users.py` (`update_user`, line 53) or `admin_clinicians.py` (`update_profile`, line 58), and `fhir_patient.py` still names the phone `phone` rather than `Patient.telecom`. No hostile-input test for a mismatched `resourceType` or `id` exists for Patient, Schedule or Appointment. The plan (points 5, 6, 90, 172, 213) says these are covered; they are not. Fix: do each as the task states.

### Blocker: item 12 parity tests missing
`scheduling/views/test_fhir_appointment.py` contains no assertion on `AuditLogEntry`, `Notification`, `mail.outbox` or the portal row for a booking, a reschedule or a cancellation. The task requires each asserted. Without them, "indistinguishable from the screens" is unproven.

### Blocker: item 9 race not tested with two transactions
`returns_201_for_the_first_and_409_for_the_second_when_the_same_slot_is_booked_twice` (`test_fhir_appointment.py:257`) is two sequential requests. It proves the conflict check, not the lock. Task 08's tests use two transactions; do the same.

### Later
- Plan promised `doc/adr/0007-fhir-appointment-and-booking.md`; none written (latest is 0006).
- Item 11: no test found for each named booking rule (`lead_time_too_short`, `cancellation_window_closed`, `too_many_open_bookings`, `type_not_bookable_online`, `outside_availability`) reaching the client as `OperationOutcome` over FHIR. Check coverage; add if absent.
- `fhir_appointment_writes.py:57-62` queries `Appointment` twice (read, then row lookup) per update; fold into one lookup.
- `read_appointment` builds `UUID(identifier)` itself; safe only because the view runs `parse_id` first (`views.py:113`). A direct caller with a bad id raises.

## Blocking
1. `ClinicalNote.fhir_not_exposed` and `doc/data-model.md` still say not exposed (item 3).
   **fixed**: `ClinicalNote.fhir_resources = ("Appointment",)`, `doc/data-model.md` regenerated;
   guarded by `test_data_model_document.py` (stale copy fails).
2. Items 14, 15 and 16 absent from the diff though the plan says covered.
   **fixed**: 14 by `returns_no_condition_when_if_match_names_version_zero`,
   `returns_stale_version_and_keeps_the_record_when_the_expected_version_is_old`,
   `returns_stale_version_when_the_expected_version_is_old`,
   `returns_412_when_admin_put_has_a_stale_if_match` (`update_user` and `update_profile` take
   `expected_version`; the FHIR layer no longer maps conflicts); 15 by
   `returns_the_fhir_path_when_a_phone_is_refused`; 16 by
   `returns_400_naming_the_element_when_a_write_body_differs_from_the_address` (Schedule, Patient,
   Appointment) and Appointment added to `returns_outcome_and_no_500_when_fhir_gets_hostile_write_bodies`.
3. Item 12 parity tests (audit, notification, email, portal) absent.
   **fixed**: `test_fhir_appointment_parity.py`, `returns_the_same_trace_when_a_booking_is_made_over_fhir_and_on_the_screen`,
   `..._a_reschedule_...`, `..._a_cancellation_...`.
4. Item 9 race test is sequential, not two transactions.
   **fixed**: `returns_201_for_one_and_409_for_the_other_when_two_clients_book_the_same_slot_together`
   (`test_fhir_appointment_race.py`, two threads, two connections, 10 attempts).

## Later
1. ADR 0007 not written.
2. Item 11 per-rule tests over FHIR unverified.
3. Double lookup in `update_appointment`.
4. `read_appointment` relies on the view for id validation.
5. Test time: I did not run `make test`. The stage logs show 72.49s (`verify_green`, 3669 tests) and 79.83s (`check`, 3773 tests) on a shared host, over the 45s target. The orchestrator measures it on a quiet machine. Not blocking.

---

# Second pass, head `ef64ce0`

Re-read after `address`. Base `cd48726`. Four first-pass blockers are fixed and I confirmed each in code, not in the note above.

## Confirmed

- Proof left no trace: `git diff 99273b8 8aa91f6 --stat` touches tests and `mutation-equivalents.txt` only. Product edits come after `prove` (refactor, address), which the rule allows.
- Item 3: `scheduling/models/booking.py:114` now `fhir_resources = ("Appointment",)`; `doc/data-model.md` says "FHIR: Appointment".
- Items 14 to 16: `update_user` (`admin_users.py:54-63`) and `cancel/reschedule/change_status` take `expected_version` and answer `stale_version()` inside the lock (`appointment_changes.py:129-133`). `if_match_version` treats `0` as absent (`fhir_body.py:51-59`). `_named_by_fhir_path` (`fhir_patient_writes.py:71-93`) maps field names to FHIR paths.
- Item 9: `test_fhir_appointment_race.py` runs two threads, two connections, behind a barrier, 10 attempts.
- Item 12: `test_fhir_appointment_parity.py` compares audit, notification, mail and portal for booking, reschedule, cancellation.
- Reads: visible rows built from caller first (`fhir_appointment_reads.py:56-100`); the clinical note is loaded only where `row.clinician.user_id == viewer_id` (`fhir_appointment_loading.py:27-32`), and an `_include` only builds Patient, Practitioner, Location.
- Writes call `place_appointment`, `join_waitlist`, `cancel_appointment`, `reschedule_appointment`, `change_status`; audit stays inside their transactions. No `Any`, `cast`, bare ignore or bare noqa added; files under 300 lines.

## Findings

### Blocker: item 11 has no test over FHIR
`scheduling/views/test_fhir_appointment.py` (all 24 tests listed by `grep "def returns"`) never provokes `lead_time_too_short`, `cancellation_window_closed`, `too_many_open_bookings`, `type_not_bookable_online`, `outside_availability`, `no_room_available` or `no_clinician_available` through `POST`/`PUT /fhir/Appointment`. A grep of `scheduling/views/test_fhir*.py` for those names finds nothing. The use cases are tested on their own; nothing proves the `OperationOutcome` carries the rule name for a booking. Fix: one parametrized view test, one case per name, asserting status, `issue.code` and the rule name in `issue.details` or `expression`.

### Blocker: item 6 and 7 booking paths untested over FHIR
No view test books by `slot` reference, books "first available" (no practitioner, patient token, and the 403 for a clinician or admin without one), books as a clinician into the own calendar, or as an admin for a named clinician and an active patient. `_clinician_of` (`fhir_appointment_writes.py:136-157`) and its slot/practitioner disagreement branch (`Appointment.slot` refusal) are exercised only through the patient-with-practitioner case. Item 7's 403 is tested for one case (`returns_403_and_no_appointment_when_patient_books_for_another_patient`). Fix: add the missing cases; each is a short request against existing helpers.

## Later
1. `doc/adr/0007-fhir-appointment-and-booking.md` promised by the plan, not written (latest is 0006).
2. `fhir_appointment_writes.py:57-62` looks up `Appointment` twice per update (once via `read_appointment`, once for the row); fold into one.
3. `read_appointment` calls `UUID(identifier)` itself (`fhir_appointment_reads.py:46`); safe only while the view runs `parse_id` first.
4. `test_fhir_appointment_race.py:28-48` types fixtures as `object` and silences `attr-defined` per line; a typed clinic fixture would remove the suppressions.
5. `make test` was 72 to 80 s on a shared host (stage logs), over the 45 s target; the orchestrator measures on a quiet machine. Not run by me.

## Blocking
1. Item 11: no FHIR test of each booking rule, `no_room_available` and `no_clinician_available` reaching the client as `OperationOutcome`.
2. Items 6 and 7: no FHIR test of booking by `slot`, "first available", clinician booking, or admin booking.

## Outcomes, third pass

1. Item 11: no FHIR test of each booking rule.
   **fixed**: the rule names did not reach the client at all (the OperationOutcome carried only
   `rule_violation`). `failure_outcome` now adds one `violated-rule` extension per rule and one
   `conflicting-resource` per conflict (not for a stale version). Domain tests in
   `test_fhir_outcome.py` (`returns_one_rule_extension_per_violated_rule_when_a_rule_is_violated`,
   `returns_one_conflict_extension_per_resource_when_a_slot_is_in_conflict`,
   `returns_no_conflict_extension_when_the_conflict_is_a_stale_version`); view tests in
   `test_fhir_appointment_booking.py`, one per name: `returns_422_naming_lead_time_too_short_...`,
   `..._too_many_open_bookings_...`, `..._type_not_bookable_online_...`, `..._outside_availability_...`,
   `..._cancellation_window_closed_...`, `returns_409_naming_the_clinician_...`,
   `..._no_room_available_...`, `..._no_clinician_available_...`.
2. Items 6 and 7: booking paths untested over FHIR.
   **fixed**: same file: `returns_201_with_the_slots_clinician_when_patient_books_by_slot_reference`,
   `returns_400_and_no_appointment_when_slot_and_practitioner_name_different_clinicians` (answers 400
   naming `Appointment.slot`), `returns_201_with_an_assigned_practitioner_when_patient_books_first_available`,
   `returns_no_appointment_when_admin_books_without_a_practitioner`,
   `returns_201_in_the_own_calendar_when_clinician_books_without_naming_a_practitioner`,
   `returns_201_when_clinician_books_into_the_own_calendar_for_a_patient`,
   `returns_403_and_no_appointment_when_clinician_books_into_another_calendar`,
   `returns_201_when_admin_books_a_named_clinician_for_an_active_patient`,
   `returns_no_appointment_when_admin_books_for_an_inactive_patient`.

---

# Fourth pass, head `59b3b5d`

Base `cd48726`. Re-read after the third `address`. I re-ran `make lint` and `make gate` (clean) and the 76 new FHIR tests (all pass). I did not run the full `make test`.

## Confirmed

- Proof left no trace: `git diff 99273b8 8aa91f6 --stat` touches tests and `mutation-equivalents.txt` only. The product edit after `prove` is `fhir_outcome.py`, which the rule allows.
- Item 11: `failure_outcome` (`scheduling/domain/fhir_outcome.py:36-56`) adds one `violated-rule` and one `conflicting-resource` extension. The values are fixed vocabulary from `Failure.details`, never client input, and a stale version gets none. `test_fhir_appointment_booking.py` has one view test per rule name, including `no_room_available` (line 239) and `no_clinician_available` (line 249).
- Items 6 and 7: slot, first available, clinician and admin bookings each have a view test, and so does the 403.
- Clinical note: `fhir_appointment_loading.py:26-31` loads it only for rows where the viewer is the clinician. `test_fhir_appointment.py:161` plants a note and proves its absence for patient, admin and another clinician in a read and in a search with `_include`.
- Authorization comes from `caller.user`, never the body (`fhir_appointment_writes.py:38-60`). Every write goes through `place_appointment`, `join_waitlist`, `reschedule_appointment`, `cancel_appointment` or `change_status`, so audit entries stay inside their transactions.
- No `Any`, `cast` or bare suppression added; files and functions inside the caps.

## Findings

None blocking.

## Blocking

None.

## Later

1. `doc/adr/0007-fhir-appointment-and-booking.md` promised by the plan, not written (latest is 0006).
2. `fhir_appointment_writes.py:57-62` looks up `Appointment` twice per update (via `read_appointment`, then for the row); fold into one.
3. `read_appointment` calls `UUID(identifier)` itself (`fhir_appointment_reads.py:46`); safe only while the view runs `parse_id` first.
4. `test_fhir_appointment_race.py:28-48` types fixtures as `object` and silences `attr-defined` per line; a typed clinic fixture would remove the suppressions.
5. `make test` was 64 to 80 s on a shared host (stage logs), over the 45 s target. The orchestrator measures it on a quiet machine; a miss there is a defect to fix before merge.
