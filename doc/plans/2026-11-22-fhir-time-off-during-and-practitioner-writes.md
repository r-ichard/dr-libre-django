Slice: items 1, 2, 3 and the item 5 duties of the writes that exist (PractitionerRole, time off). Item 4 (`Practitioner` writes) is the next run, under `## Not in this run`.

# Plan: task 24c2, `notAvailable.during`, two survivors, time off proved end to end

Focal point: `scheduling/domain/fhir_role_write.py`, the one place that reads `notAvailable[i].period`. The read side is `fhir_practitioner_role.py:90`.

## Blocks

1. **Element name** (`fhir_practitioner_role.py`, `fhir_role_write.py`): serve `during`, read `during`; `period` is no longer in `ROLE_SHAPE`, so `exact_elements` refuses it like any unknown element, naming `PractitionerRole.notAvailable[i].period`.
2. **Samples** (`samples_records.py:23` `NOT_AVAILABLE_SAMPLE`): `period` becomes `during`; clears the 3 failing validator samples.
3. **Test helper** (`fhir_role_support.py:42` `period()`): emits `during`. Existing time-off tests keep their names and follow the helper.
4. **Survivors** (`test_fhir_code_identifier.py`, beside `fhir_record_write._coding_code`): tests that kill `x__coding_code__mutmut_9` and `_11`. Read the two mutants with `mutmut show` first; they are most likely the `{}` fallback of `first` and the `"coding"` key / empty-list guard. Pin: a concept with no `coding`, with `coding: []`, with a non-dict concept and with a coding without `code` each give `""`; a concept with two codings gives the first one. A line in `mutation-equivalents.txt` only if `mutmut show` proves a mutant cannot change behaviour, with the reason.
5. **End-to-end time off** (new `scheduling/views/test_fhir_time_off_journey.py`): one test, clinician's own token as a FHIR client sends it (bearer, no cookie, no `Origin`): `PUT` role with a new `during` -> 200; `GET` shows the entry with `id`, `during`, `description`; `GET /api/v1/slots` lacks the slots inside the period; `/fhir/Slot` shows them `busy-unavailable`; `PUT` without the entry -> removed; both lists show the slots again. Refusals as separate tests, one `returns_X_when_Y` each (see below).
6. **ADR 0009**: a line "Checked against R4 `PractitionerRole`" listing: `active`, `practitioner`, `organization`, `specialty`, `location`, `healthcareService`, `availableTime` (`daysOfWeek`, `availableStartTime`, `availableEndTime`), `notAvailable` (`description`, `during`; `id` is the element id). Only `during` was wrong (`period`). The two extensions `role-bio` and `role-round-robin-weight` are ours and carry our URLs. Fix the ADR's own text, which says `period`. The validator (`make fhir-validate`) is the proof.
7. **Item 5 for existing writes**: audit the tests of `PractitionerRole` writes for the matrix {admin, clinician own, clinician other, patient, no token} x {POST, PUT, DELETE}; add the missing cells. Hostile-input test already lists the role paths and the `notAvailable` bodies; add one body with `during` of wrong types (`"during": []`, `{"start": 5}`). Samples and CapabilityStatement already list `PractitionerRole` create/update/delete; add a test that every interaction in the statement answers (not 404/405) if none exists (grep `interaction` in tests first).

## Failing tests first (expected values from spec 15.2, 15.4 and ADR 0009)

- `returns_200_and_serves_during_when_a_clinician_reads_a_role_with_time_off`: entry has key `during` with `start`/`end` as instants and no key `period`.
- `returns_400_naming_period_when_a_body_still_sends_period`: `notAvailable[0].period` unknown element, nothing stored.
- `returns_200_and_records_time_off_when_the_standard_request_with_during_is_put`: `{"description": "Dentist", "during": {...}}` stores one `TimeOff` with reason "Dentist".
- `returns_the_slots_back_when_the_period_is_removed` (inside the journey test).
- Refusals: `returns_400_when_a_stored_period_is_changed_in_place` (ADR: 400 naming `notAvailable[i]`); `returns_409_or_400_when_an_identical_period_is_added_twice` (state the status the console gives: unique constraint 0012, mapped by `_as_not_available`; read before asserting); `returns_400_when_the_end_is_before_the_start`; `returns_403_when_a_clinician_puts_another_clinicians_role`; `returns_400_naming_PractitionerRole.notAvailable_when_an_admin_changes_time_off`.
- Survivor tests of block 4, each named `returns_empty_code_when_...`.
- Each must be seen red for the right reason (before block 1: key `during` refused as unknown; before block 4: the two mutants survive).

## Files, in order
tests (3-5, 7) -> `fhir_role_support.py` -> `fhir_role_write.py` -> `fhir_practitioner_role.py` -> `samples_records.py` -> `mutation-equivalents.txt` (only if proven) -> ADR 0009.

Not touched: `Practitioner` code, models, migrations, `admin_*` use cases, `fhir_declaration.py` (no new interaction), the console time off pages, `scripts/`.

## Invariants and boundaries
- Authorization stays server-side from the token (`role_write_refusal`, before the body is read); nothing about who may write changes.
- Time off write stays one transaction with audit entries (ids only, no reason text); a refused step rolls back all.
- Slots: no double booking path touched. Search of free slots reads `TimeOff` as before.
- Trust boundary: the JSON body from the FHIR client; shape-checked by `exact_elements`, instants need a time zone (existing test), end > start by the console rule.
- Blast radius: the `notAvailable` wire name only. A client that sent `period` gets 400 (intended, spec says R4 name). Domain entities: Clinician, ClinicianProfile, TimeOff, AvailabilityRule, Appointment (slots), ApiClient, AuditLogEntry.

## Will not do
No alias accepting both names, no new abstraction, no dependency, no refactor of `fhir_role_write.py`. Files stay under the size caps (check `make gate`).

## Not in this run (task 24c3)
- `PUT /fhir/Practitioner/{id}` for an admin token via `update_user`, `deactivate_user`, `update_profile`; a phone that differs is 400; own-account and last-admin refusals come from those use cases.
- `DELETE /fhir/Practitioner/{id}` via `delete_user` (409 while the profile exists; 409 with appointments or audit entries).
- No `POST /fhir/Practitioner`: reason in ADR 0009 already (the console needs a temporary password, not a FHIR element).
- Version: `Practitioner.versionId` is `user.version` only, so a title change (profile row) does not move it. Plan: migration with a trigger bumping the user's version when a profile's title changes, as the child-row triggers do for the role (ADR 0003 rejects summing in the mapper). `If-Match` old -> 412.
- Write matrix, samples, hostile paths and CapabilityStatement `update`/`delete` for `Practitioner`.

## Architect review

Verdict: approve.

- Ladder: smallest fix in the right place (one wire name, one helper, samples, two tests, ADR). No alias, no new dependency. Good.
- Slice: items 1, 2, 3 and the item 5 duties for existing writes are coherent and leave the product whole. Item 4 moves to 24c3 with its decisions listed. The slice means the goal's "Done when" for item 4 is not met in this run: the hand-off must say so plainly.
- Tests first: named as behaviours with spec-derived values; red reasons stated. Good.
- Conditions for the writer:
  1. The admin refusal status for `notAvailable` is asserted as "400 naming `PractitionerRole.notAvailable`", but `grep` of ADR 0009 for admin + time off found no matching line. Read the ADR and `role_write_refusal` first, assert what they fix, and state it in the ADR if missing.
  2. `fhir_role_write.py:32` (`ROLE_SHAPE`) and `_period_of` (line 142) are the places to change. Check the file stays under the size cap.
  3. Run `mutmut show` for both survivors before writing the tests; confirm each fails before the fix.
