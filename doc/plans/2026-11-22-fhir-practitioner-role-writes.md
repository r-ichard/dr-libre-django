# Plan: task 24c, FHIR `PractitionerRole` writes and time off

Slice: items 2, 3, 4, 6 and the `PractitionerRole` half of 5. Item 1 (`Practitioner` update and
delete, the `Practitioner` half of item 5) is `## Not in this run`; its decisions are written into
the ADR now so the next run only builds them.

## Focal point

One new use-case module, `scheduling/use_cases/fhir_role_writes.py`. It turns a checked FHIR body
into calls of `admin_clinicians` (admin) or `time_off` (the owning clinician) and rebuilds the answer
with the existing `fhir_loading.practitioner_roles*` builders. The console's checks, refusals,
audit entries and versions are reused. This task adds no rule.

## Decisions (new ADR 0009, `doc/adr/0009-fhir-practitioner-writes-and-time-off.md`)

- **Who writes what.** Admin: create, update, delete of a role, through `attach_profile`,
  `update_profile`, `delete_profile`. Clinician: update of the own role, `notAvailable` only. No
  token 401. Patient token 403. Clinician `POST`, `DELETE`, or `PUT` of another clinician's role:
  403 (roles are public, so 403 leaks nothing; 15.4 says "own"). Refusals come before the body is
  read (`refusal_before_body` gains the method, because a clinician may `PUT` but not `POST`).
- **Admin and `notAvailable`.** No use case lets an admin record time off (`locked_profile` wants
  the clinician), and 15.4 gives it to the clinician. An admin `PUT` whose `notAvailable` differs from
  the stored one is 400 naming `PractitionerRole.notAvailable`; one that repeats it is fine, so
  GET then PUT works.
- **Mapping on a write.** `practitioner` (reference, required on create, must equal the stored one on
  update: a profile never changes user), `organization` (department), `specialty` (coding code of
  the managed list), `location` (default room, optional), extensions `role-bio` and
  `role-round-robin-weight`. `active` and `healthcareService` are derived: they round-trip, a
  difference is 400 naming the element. `title` is the `Practitioner`'s qualification, so a role
  create does not send one (the next run's `Practitioner` `PUT` sets it).
- **Console refusals pass through with FHIR names:** room of another department
  (`PractitionerRole.location`), unknown or inactive specialty (`.specialty`), department move with
  upcoming appointments, rules or a kept room (`.organization`), user not an active clinician without
  a profile (`.practitioner`), delete with dependents 409 `has_dependents` with the console's counts.
- **`notAvailable` on read.** New element on the staff build only (owner clinician and admin; public
  never sees time off, as for busy slots): one entry per `TimeOff`, `id` = the time off id,
  `period` start and end, `description` = the reason ("Time off" when it is empty). Public build
  unchanged.
- **`notAvailable` on write, by entry id.** An entry without `id` = add (`create_time_off`). A stored
  id missing from the body = remove (`delete_time_off`). An entry whose `id` is stored but whose
  period or description differs = 400 naming `PractitionerRole.notAvailable[i]` ("time off is
  recorded and removed, not edited"). An unknown `id` = 400, named. Any other element that differs
  from the stored role = 400, named (the same derived-difference check, now over every element).
- **`availableTime`** round-trips and may not differ: 400 naming `PractitionerRole.availableTime`
  ("change the Schedule resources").
- **One transaction.** The whole `PUT` runs in one `transaction.atomic`: lock the profile, compare
  `If-Match` with its version (stale: 412), apply removals then additions, then (admin) the profile
  edit; the first refusal calls `set_rollback`, so no earlier step or audit entry stays.
  The use cases' own `version` argument is fed the version read under that lock (they compare it to
  the row; the FHIR `If-Match` is the only client check).
- **Versions (ADR 0003).** Already guaranteed by DB triggers (`models/test_version.py`): a time off or
  rule row moves the profile's version. New view-level tests prove it through FHIR.
- **Practitioner (next run, decided now).** `POST /fhir/Practitioner` is not offered: the console's
  create needs a temporary password, which is not a FHIR element, and a user without a profile is
  not a readable `Practitioner` (reads list by profile). Users are created in the console; their id is
  then the `practitioner` of a role create. `PUT` (name, email, `active`, title via the profile) and
  `DELETE` (409 while the profile exists) go through `update_user`, `deactivate_user`,
  `update_profile`, `delete_user`. A phone differing is 400 (the console cannot edit it). The
  password appears in no FHIR element, answer, log or audit entry.

## Files, in order

1. `scheduling/domain/fhir_practitioner_role.py`: `RoleSource.time_off: tuple[TimeOffSource, ...] | None`;
   `practitioner_role` adds `notAvailable` when not None. Same file: `ROLE_SHAPE`.
2. `scheduling/domain/fhir_role_write.py` (pure, new): `role_values(body)` returns `Values | element`;
   `time_off_changes(body_entries, stored_entries)` returns adds, removed ids or an element name;
   `role_difference(body, stored, *, free: set[str])` names the first differing element outside
   `free`. Reuses helpers of `fhir_record_write.py` (`_reference_id`, `_extension_value`,
   `_coding_code`) by moving them to `fhir_common` only if they are needed by both; else import.
3. `scheduling/use_cases/fhir_loading.py`: `_roles(..., with_time_off)`; staff build passes True.
4. `scheduling/use_cases/fhir_role_writes.py` (new, focal): `create_role`, `update_role`,
   `delete_role`, `role_write_refusal(method, caller)`; specialty code to id lookup; renames console
   fields to elements.
5. `scheduling/use_cases/fhir_resources.py`: route `PractitionerRole` in `create`, `update`,
   `delete`; `refusal_before_body(resource_type, caller, method)`.
6. `scheduling/views/fhir/writes.py`: pass the method to the refusal (one line).
7. `scheduling/domain/fhir_write_shapes.py`, `fhir_declaration.py`: shape; role interactions
   `(*READ_ONLY, "create", "update", "delete")`. Routes, `Allow` and CapabilityStatement follow.
8. `scheduling/views/fhir/samples_records.py` (or a new `samples_role.py` if it passes 300 lines):
   role create, update, delete, a `notAvailable` add update, a refusal. `samples.py` registers them.
9. `scheduling/views/test_hostile_input.py`: role paths and bodies (`notAvailable` with a huge
   list, wrong types, bad ids).
10. `doc/adr/0009-...md`.

Not touched: `admin_clinicians.py`, `time_off.py`, models, migrations, console pages, `fhir_reads.py`
(Part definitions already serve roles), `doc/backlog.md` (orchestrator).

## Invariants and blast radius

- Authorization from the token's user, never the body; the use cases re-check admin / own profile.
  Every write is tested with admin, own clinician, other clinician, patient, no token.
- One transaction per request, audit inside it (use cases' entries: `clinician.*`,
  `time_off.create|delete`); a no-op `PUT` leaves version and audit unchanged. Audit stays
  append-only; time off audit keeps ids only (reason is free text, never logged).
- Booked appointments untouched by time off (the use case's rule); double booking unaffected.
- Blast radius: staff `PractitionerRole` reads gain `notAvailable` (samples and whole-resource
  comparisons for staff change); `refusal_before_body` signature.
- Trust boundary: JSON body. Layers: `exact_elements` against `ROLE_SHAPE`, then pure
  `role_values` / `time_off_changes`, then the use cases' checks. Sizes capped by
  `request_limits`; `notAvailable` count is bounded by the body cap.

## Failing tests first (`returns_X_when_Y`)

View tests with `fhir_client(token)` (bearer, no cookie, no `Origin`):
- `returns_201_with_location_and_etag_when_admin_posts_a_role`: row exists with department,
  specialty, room, bio, weight 3; audit `clinician.create` by the admin; ETag `W/"1"`.
- `returns_400_naming_location_when_the_room_belongs_to_another_department`;
  `returns_400_naming_organization_when_moving_a_clinician_with_upcoming_appointments`;
  `returns_400_naming_specialty_when_the_specialty_is_inactive`;
  `returns_400_naming_practitioner_when_the_user_has_a_profile`.
- `returns_200_with_new_etag_when_admin_puts_a_changed_bio_with_current_if_match`; audit names `bio` only.
- `returns_200_and_keeps_version_when_put_changes_nothing`.
- `returns_409_has_dependents_when_deleting_a_role_with_appointments`;
  `returns_200_outcome_when_deleting_an_unused_role`.
- `returns_200_and_records_time_off_when_the_clinician_puts_a_new_period`: row exists with the
  reason, audit `time_off.create`, answer lists the period with the new id.
- `returns_200_and_deletes_time_off_when_the_clinician_puts_without_a_stored_period`.
- `returns_400_naming_not_available_entry_when_a_stored_period_is_changed_in_place`;
  `returns_400_naming_not_available_when_an_unknown_time_off_id_is_sent`.
- `returns_400_naming_the_element_when_a_clinician_changes_bio_or_organization_or_weight` (one case
  each) and nothing was written, not even the time off in the same body (atomic).
- `returns_400_naming_available_time_when_the_body_changes_it` for clinician and admin.
- `returns_400_naming_not_available_when_an_admin_changes_it`; admin PUT repeating it is 200.
- `returns_403_when_a_clinician_puts_another_clinicians_role`; `returns_403_when_a_clinician_posts_or_deletes`;
  `returns_403_when_a_patient_writes`; `returns_401_when_no_token_writes` (POST, PUT, DELETE).
- Versions: `returns_412_when_if_match_is_the_version_before_a_time_off_was_added` (clinician records a
  period; the old `If-Match` on the next PUT is 412; same for an availability rule added through
  `Schedule`; `ETag` moved by one per change); stale `If-Match` 412 on admin update and delete.
- `returns_the_same_fields_as_the_console_when_fhir_and_console_attach_the_same_profile` (row and
  audit metadata).
- `returns_notAvailable_to_the_owner_and_admin_and_not_to_the_public_when_a_role_is_read`.
- CapabilityStatement lists create, update, delete for `PractitionerRole`; `Practitioner` still
  read and search only (POST 405 with `Allow`).
- Domain tests (mutated by `make mutate`): `role_values`, `time_off_changes`, `role_difference`.
- `test_samples.py`: role samples exist and validate in `make fhir-validate`; hostile-input includes them.

## Domain entities

ClinicianProfile (as PractitionerRole), TimeOff, AvailabilityRule (read-only mirror), Department,
Room, Specialty, Admin, Clinician, ApiClient, AuditLogEntry.

## Not doing

No new rule, use case or model, no console change, no `notAvailable` write for admin, no
in-place time-off edit, no `428`, no `Practitioner` write here, no refactor of `fhir_reads.py`.

## Not in this run

- Task 24c2: `Practitioner` `PUT` and `DELETE` (decisions above), its version tests (profile title
  moves the user's version; old `If-Match` is 412), samples, hostile input, CapabilityStatement.
- `make mutate` and `make fhir-validate` full pass confirm after both runs.

Risks: the role create has no title (the profile's model default applies until a `Practitioner`
`PUT`); `notAvailable` on read changes staff samples; a Practitioner cannot be created through FHIR,
which the task allows when the ADR says so.

## Architect review

Verdict: approve.

- Slice is coherent: `PractitionerRole` writes, time off and `availableTime` refusal are one
  change; `Practitioner` stays read-only with its decisions already in ADR 0009, so the product
  is whole. One green stage can finish it; the full task would not fit.
- Ladder: no new rule, model, dependency or console change; reuses `admin_clinicians`, `time_off`
  and existing builders. The new domain module is pure and mutation-covered.
- Security: authorization from token, refusal before body, 401/403 matrix tested, time off reason
  kept out of audit, `notAvailable` visible to owner and admin only, body capped and schema-checked.
- Architecture: one transaction with `set_rollback` on first refusal, expected errors as values.
- Tests first: behaviours with named elements, atomicity, 412 on child-row version moves, console parity.
- Watch in green: (1) `If-Match` read under the lock, not before; (2) admin PUT that repeats
  `notAvailable` must compare by content, not order; (3) staff-read change updates every staff
  sample and whole-resource comparison; (4) the file `fhir_role_writes.py` and functions stay under
  the size caps; (5) 24c2 must be added to the backlog by the orchestrator.
