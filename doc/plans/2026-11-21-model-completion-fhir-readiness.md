# Plan: task 02a, finish the domain model and make it FHIR-ready

Base of every diff: `314732e`. Binding: `doc/backlog/02-domain-model.md` (with its waiver), ADR 0002.

Focal point: `scheduling/models/base.py` (a `Versioned` base class) plus one hand-written
migration holding the database triggers. Everything else is columns, a mapping declaration
per model, and the generated document.

## Decisions

### 1. Versions: a counter column, enforced by a trigger, checked by the writing statement
- `Versioned(Record)`, abstract: `version` positive integer, default 1, check `version >= 1`.
  14 models use it (every row a FHIR resource or part of one is built from). `Session`,
  `VerificationCode`, `SignInLink` stay `Record` (credentials, not exposed).
- **Trigger `scheduling_enforce_version`**, `BEFORE INSERT OR UPDATE ... FOR EACH ROW`, on each
  of the 14 tables: an insert must carry 1; an update must carry exactly `OLD.version + 1`;
  anything else raises (error code `check_violation`, so Django raises `IntegrityError`).
  So no path (ORM, `queryset.update`, raw SQL) changes a row without growing its version.
- **Stale write = detected in the statement that writes.** `Versioned.save()` on an existing row
  sets `version = loaded version + 1` (and adds `version` to `update_fields`). The `UPDATE`
  runs `SET version = <loaded+1>`; if another writer got there first, `OLD.version + 1` no longer
  matches and the trigger refuses, no prior read. For `If-Match` the use case later runs
  `filter(pk=..., version=expected).update(version=F("version") + 1, ...)` and reads the row
  count (0 = 412): plain ORM, no new helper now (no second caller). `save()` restores the
  in-memory version if the statement fails.
- `lastUpdated` = `updated_at`, set by `save()`. `queryset.update` does not touch it; the use
  case sets it. Not widened here.
- Audit rows: column exists (`AuditEvent` carries a versionId, always 1). The existing audit
  trigger name sorts before the version trigger, so its refusal still fires first.
- **Parts that change a parent resource.** `TimeOff` and `AvailabilityRule` are served inside
  `PractitionerRole` (`notAvailable`, `availableTime`). A statement-level-safe row trigger
  `scheduling_touch_clinician_profile` (`AFTER INSERT OR UPDATE OR DELETE` on both tables) runs
  `UPDATE clinicianprofile SET version = version + 1, updated_at = now() WHERE id IN (OLD/NEW clinician)`,
  so a stale `If-Match` on the PractitionerRole fails after any schedule change.
  Moving a schedule row to another clinician bumps both parents (old and new). A statement that
  changes N rows bumps the parent N times; accepted: the rule is "never fewer than one per change".
- **Practitioner is built from two rows** (`User` for name, email, phone, active; `ClinicianProfile`
  for `title`). Trigger `scheduling_touch_user` on `ClinicianProfile`: `AFTER INSERT OR DELETE`, and
  `AFTER UPDATE WHEN (OLD.title IS DISTINCT FROM NEW.title OR OLD.user_id IS DISTINCT FROM NEW.user_id)`,
  runs `UPDATE user SET version = version + 1, updated_at = now()` for OLD and NEW user. Only `title`
  feeds Practitioner, so other profile changes (bio, weight, schedule touches) leave the Practitioner
  version alone. Effect: a `User` instance held stale across a profile title change is refused on
  `save()` (intended, the Practitioner did change). Chain is acyclic: schedule rows -> profile
  (-> user only when title or owner changed) -> nothing.
- **Use cases re-read.** A profile or user touched by a trigger in the same transaction is stale in
  memory; the use case re-reads it before saving. Stated in ADR 0003.
- **Specialty before first change.** The migration calls `nextval` once, so `last_value` is 1 and `is_called` true on a fresh database: `versionId` = `last_value`, defined from the start.
- **Specialty list.** `CodeSystem` and `ValueSet` are one resource over all rows, rows can be
  deleted, so a sum of row versions can fall. A sequence `scheduling_specialty_revision`
  advanced by a statement trigger after any insert, update or delete on `Specialty`;
  `versionId` = its `last_value`.

### 2. One FHIR Appointment for a waitlist entry and its booking (ADR 0003)
Two tables stay (concepts keep their names). The accepted entry and the new booking are linked
and share the entry's id and a continuing version:
- `Appointment.waitlist_entry`: nullable one-to-one to `WaitlistEntry`, `PROTECT`. Set when the
  appointment was placed by accepting an offer. Unique, so an entry books once.
- `Appointment.inherited_version`: positive integer, default 0. The use case writes the entry's
  final `version` into it at acceptance. FHIR `versionId` of a joined resource =
  `inherited_version + version`; it never falls, so an `If-Match` taken from the waiting
  resource cannot match the booked one. The statement guard uses `version = expected - inherited_version`.
- Check `appointment_inherited_version_only_from_waitlist`: `inherited_version = 0` when
  `waitlist_entry` is empty.
- FHIR logical id = `waitlist_entry_id` when set, else the appointment's own id. Reads of
  `Appointment/{id}`: the appointment row if one has that id or that `waitlist_entry_id`,
  else the entry. Searches: appointments plus entries that have no appointment. Mapper work, later.
- `AppointmentResponse/{id}` is the entry itself (id and version = entry's), present when its
  status is `BOOKED`.
- `BookingHold` is a separate `Appointment` `pending` with its own id; no continuation (the
  hold is gone before the booked resource exists).
- Not enforceable in a CHECK: status `BOOKED` implies an appointment points at the entry
  (reverse link). Stays with the accept use case; listed below.
- Rejected: one table for everything (null clinician and times, status lists mixed, breaks
  the exclusion constraints' meaning); same id in two tables (no link, no version rule);
  summing two row versions in the mapper (deletion-free but implicit).

### 3. Mapping check, 15.2, 15.3, 15.5 (element -> column)
Legend: Column = exists now; NEW = added in this run; Derived = no column, reason given.

| Resource | Element or parameter | Source |
| --- | --- | --- |
| all | `id`, `meta.versionId`, `meta.lastUpdated` | `id`, `version` (NEW), `updated_at` |
| Organization (hospital) | name, identifier, `active`; type `prov` | `name`, `code`, `is_active`; type Derived (constant) |
| Location (hospital) | name, description, address (street, postal, city, country), phone, position, time zone, status; `near` | `name`, `description`, `street_address`, `postal_code`, `city`, `country`, `phone`, `latitude`, `longitude`, `time_zone`, `is_active`; type Derived (constant site) |
| Organization (department) | name, identifier, description, `partOf` | `name`, `code`, `description`, `hospital`; type `dept` Derived; `active` Derived (the hospital's `is_active`; section 3.1 gives departments no flag) |
| Location (room) | name, identifier, floor, capacity, equipment, status, managing organization, `partOf` | `name`, `code`, `floor`, `capacity`, `equipment`, `is_active`, `department`; `partOf` Derived (department's hospital); physical type Derived |
| CodeSystem, ValueSet | concept code, display, status | `Specialty.code`, `name`, `is_active`; resource id and version Derived (sequence above) |
| Practitioner (clinician) | name, title, email, phone, `active` | `User.full_name`, `ClinicianProfile.title`, `email`, `phone`, `is_active` |
| Practitioner (admin) | same, with a role coded administrator | User row with `role = ADMIN`; the `PractitionerRole` is Derived (no profile row; id and version from the user) |
| PractitionerRole | practitioner, organization, specialty, location, bio, weight, `availableTime`, `notAvailable` | `user`, `department`, `specialty`, `default_room`, `bio`, `round_robin_weight`; `availableTime` from AvailabilityRule, `notAvailable` from `TimeOff.starts_at`, `ends_at`, `reason` |
| PractitionerRole | search `active` | Derived (`user.is_active`; profile has no flag) |
| PractitionerRole | search `location`, `service`, `organization` | `default_room`; `service` Derived (appointment types of the department); `department` |
| Patient | name, birthdate, email, phone, active | `full_name`, `date_of_birth`, `email`, `phone`, `is_active` |
| HealthcareService | name, identifier, provided-by, duration, buffer, colour, needs-room, online-bookable, `active` | `name`, `code`, `department`, `duration_minutes`, `buffer_minutes`, `colour`, `needs_room`, `is_bookable_online`, `is_active` |
| HealthcareService | `specialty` (element and search) | Derived: distinct specialties of the department's clinicians. No column: section 3.1 gives the type none. **Open point for the owner** |
| Schedule | actors, horizon, weekday, times, step, `date` | `clinician`, `room`, `valid_from`, `valid_to`, `weekday`, `start_time`, `end_time`, `slot_step_minutes`; `active` Derived (valid_to open or not past, clinician's user active) |
| Slot | all | Derived (computed, read-only); id from schedule, type, start; `busy-tentative` from BookingHold, `busy-unavailable` from TimeOff |
| Appointment (booked) | patient, practitioner, room, `serviceType`, start, end, status, source ext, internal status ext, `cancelationReason`, `reasonCode.text`, `comment`, `location` search | `patient`, `clinician`, `room`, `appointment_type`, `starts_at`, `ends_at`, `status`, `source`, `cancellation_reason`, `patient_reason`, `clinical_notes`; `cancelled_at` served as an extension |
| Appointment (waitlist) | status, `requestedPeriod`, preferred practitioner, patient, `serviceType`; offered start, end, practitioner | `WaitlistEntry.status`, `earliest_at`, `latest_at`, `preferred_clinician`, `patient`, `appointment_type`; offered fields Derived from `offered_appointment` |
| Appointment (hold) | status `pending`, practitioner, `serviceType`, start, end, reason, visitor name, source | constant, `clinician`, `appointment_type`, `starts_at`, `ends_at`, `visitor_reason`, `visitor_name`, `source`; `expires_at` as an extension |
| AppointmentResponse | actor, appointment, `participantStatus` accepted | `WaitlistEntry.patient`; appointment id Derived (rule 2); status Derived from `status = BOOKED` |
| Communication | recipient, category, payload, `sent`, `received`, `about` | `recipient`, `kind`, `title` and `body`, `created_at`, `read_at`, `appointment`; **NEW** `waitlist_entry` for `about` on `WAITLIST_OFFERED` (the freed appointment is cancelled and is not the resource the patient is offered) |
| AuditEvent | action, time, agent, entity, entity-type, details, correlation id | `action`, `created_at`, `actor`, `entity_type` with `entity_id`, `metadata`, `correlation_id` |
| Session, VerificationCode, SignInLink | not exposed | credentials; sign-in events are `AuditEvent` |

Also Derived, no column: Bundle `total`, links, `_count`, `_sort` (use the columns above),
`_include`, CapabilityStatement, `Slot` ids, FHIR name split (`text` only), `PractitionerRole`
`active`.

New columns in total: `version` on 14 models, `Appointment.waitlist_entry`,
`Appointment.inherited_version`, `Notification.waitlist_entry` (nullable, `PROTECT`).

### 4. Mapping declared on the model, rendered in the document
- Two class attributes on every concrete model, no new dependency: `fhir_resources`
  (tuple of resource names) and `fhir_not_exposed` (reason text); `Record` sets neither
  (`()` and `""`). Exactly one must be set.
- `data_model_document.py` prints one line per model under its heading: `FHIR: Organization,
  Location` or `FHIR: not exposed, <reason>`. `version`, the new links and the new checks appear
  through the existing field and constraint rendering. Triggers are not rendered; a `pg_trigger`
  test guards them. `doc/data-model.md` is regenerated and committed.
- Declarations: Hospital (`Organization`, `Location`), Department (`Organization`),
  Specialty (`CodeSystem`, `ValueSet`), User (`Practitioner`, `Patient`), ClinicianProfile
  (`PractitionerRole`), Room (`Location`), AppointmentType (`HealthcareService`),
  AvailabilityRule (`Schedule`), TimeOff (`PractitionerRole`), Appointment (`Appointment`),
  WaitlistEntry (`Appointment`, `AppointmentResponse`), BookingHold (`Appointment`),
  Notification (`Communication`), AuditLogEntry (`AuditEvent`), Session / VerificationCode /
  SignInLink (not exposed, credentials).
- No model is renamed (5): names stay as CLAUDE.md.

## Files, in order
1. Tests first (below), in `scheduling/models/test_version.py`, `test_waitlist_resource.py`,
   additions to `scheduling/test_data_model_document.py` and `test_migrations.py`.
2. `scheduling/models/base.py`: `Versioned`.
3. Models: `organisation.py`, `people.py`, `availability.py`, `booking.py`, `audit.py`
   (switch base class, add `fhir_*` attributes); `access.py` (declarations only);
   `booking.py` gets the two Appointment columns, the Notification link and one check.
4. `scheduling/migrations/0003_*` (generated: columns, checks) and `0004_*` hand-written
   (trigger functions, triggers on 14 tables, touch triggers incl. profile -> user, specialty sequence, reverse SQL).
   Existing `0001` and `0002` untouched.
5. `scheduling/data_model_document.py`, then `python manage.py render_data_model` writes
   `doc/data-model.md`.
6. `doc/adr/0003-fhir-readiness-versions-and-waitlist-identity.md`.
7. Update the existing assertions that change (`test_migrations` migration name list,
   builders if `queryset.update` on versioned tables needs `F("version") + 1`).

Not touched: `CLAUDE.md`, `Makefile`, `scripts/`, settings, `0001`, `0002`, `identifiers.py`,
views, health. No serializers, mappers, use cases, admin, seed, `ApiClient` (task for 15).

## Invariants and blast radius
- Must not break: no double booking (three exclusion constraints, unchanged), append-only audit
  (trigger fires before the version trigger; truncate untouched), no cascade (new FKs are
  `PROTECT`), hash-only secrets.
- New trigger on a hot path: every update of 14 tables. Existing tests that call
  `queryset.update(...)` without `F("version") + 1` on those tables will now fail; fixing them
  is part of this run.
- `Versioned.save()` is the only Python code touched in the write path; `bulk_update` and
  `queryset.update` are covered by the trigger, not by Python.
- Authorization: none in this task (stored columns and checks only). The mapping notes who may
  see what (`clinical_notes`, `visitor_*`, email) and the later FHIR layer enforces it.

## Failing tests to write first (`returns_X_when_Y` / `rejects_X_when_Y`)
Versions (each with the legal neighbour):
- `returns_version_1_when_row_is_inserted`; `rejects_version_5_when_row_is_inserted`; `rejects_version_0` (check).
- `returns_version_2_when_row_is_saved_once` and `returns_version_3_when_saved_twice`
  (parametrised over all 14 versioned models).
- `rejects_update_when_queryset_update_does_not_grow_version`;
  `returns_version_plus_one_when_queryset_update_grows_it_by_one`;
  `rejects_update_when_version_grows_by_two`; `rejects_update_when_version_is_lowered`.
- `rejects_save_when_row_was_changed_since_it_was_loaded` (two instances of one row, second save
  refused, stored values and version stay the first writer's).
- `returns_zero_rows_when_update_filters_on_a_stale_version` (If-Match shape: 0 means 412).
- `rejects_raw_sql_update_when_version_is_not_incremented`.
- `returns_in_memory_version_unchanged_when_save_is_refused`.
- `returns_no_version_column_when_session_code_and_link_models_are_inspected`; and every
  `Versioned` model has the trigger (`pg_trigger` lookup), so a future model without one fails.
- `returns_parent_version_plus_one_when_time_off_is_added`, `_changed`, `_deleted`; same for
  availability rule; `returns_parent_version_unchanged_when_other_clinician_time_off_changes`.
- `returns_user_version_plus_one_when_profile_title_changes`; `_when_profile_is_added`, `_when_profile_is_deleted`;
  `returns_user_version_unchanged_when_profile_bio_changes`;
  `returns_user_version_unchanged_when_profile_of_other_clinician_changes`;
  `rejects_save_when_user_was_loaded_before_profile_title_changed`.
- `returns_both_parent_versions_plus_one_when_time_off_moves_to_another_clinician` (same for availability rule).
- `returns_parent_version_plus_row_count_when_one_statement_changes_many_rows` (accepted, "one per change").
- `returns_revision_one_when_specialty_has_never_changed` (fresh database; value defined, not an error).
- `returns_larger_revision_when_specialty_is_added`, `_changed`, and `_deleted` (never smaller).
- Audit still refused: existing audit tests must stay green (`rejects_update_when_audit_entry_is_changed`).

Waitlist resource:
- `returns_appointment_linked_to_entry_when_waitlist_entry_is_set`;
  `rejects_second_appointment_when_entry_already_booked` (one-to-one unique);
  `rejects_entry_delete_when_appointment_refers_to_it` (`PROTECT`, ORM and raw SQL).
- `rejects_inherited_version_when_appointment_has_no_waitlist_entry`;
  `returns_appointment_when_inherited_version_comes_with_waitlist_entry`;
  `rejects_negative_inherited_version`.
- `returns_larger_version_when_booked_appointment_replaces_waiting_entry`: entry at version 3,
  appointment with `inherited_version = 3`, `version = 1` gives 4, above every earlier value.
- `returns_notification_about_waitlist_entry_when_offer_is_sent`; `rejects_entry_delete_when_notification_refers_to_it`.

Mapping and document:
- `rejects_model_when_it_declares_neither_fhir_resource_nor_reason`; `rejects_model_when_it_declares_both`
  (the real check walks `apps.get_models()`; the two negative cases use throwaway classes).
- `returns_fhir_line_per_model_when_document_is_rendered` (Hospital lists `Organization` and
  `Location`; WaitlistEntry lists `Appointment` and `AppointmentResponse`; Session says
  `not exposed` with its reason).
- `returns_committed_document_when_rendered_from_models` (existing) stays the drift guard.
- `returns_five_migrations_when_loader_reads_the_app` (replaces the name list assertion);
  `returns_no_pending_changes_when_models_match_migrations` (existing);
  `returns_empty_database_migrated_when_all_migrations_apply_and_reverse` (migrate to 0002 and
  back to head).

Proof stage (item 6) must, in the foreground, break and show a test failing for: a range check
(capacity), uniqueness (hospital code), overlap exclusion (clinician), append-only audit trigger,
protected delete (a foreign key), and each rule added here: version insert rule, version update
rule, `save()` bump, touch-parent trigger, touch-user trigger (title change), specialty sequence trigger, inherited-version check,
waitlist one-to-one, FHIR declaration check. The diff must be clean afterwards.

## Trust boundaries
None crossed: no request path, no input. The mapping records, per element, what the later FHIR
layer must hide from non-staff (`email`, `phone`, `clinical_notes`, `visitor_*`). Database
privilege: triggers and a sequence are created by the application role (owner). Trigger text
holds no user data; error messages state the rule only.

## Domain entities used
All 17 CLAUDE.md names, unchanged. No Visitor/Patient/ApiClient table.

## Deferred (waits for its use case, with reason)
- Status `BOOKED` on a waitlist entry implies an appointment with `waitlist_entry` pointing at
  it, and `inherited_version` equals the entry's final version: cross-table, written in the accept transaction.
- A `BOOKED` or `EXPIRED` entry never changes again: status transitions (5.8) belong to the use case.
- `HealthcareService.specialty` derivation: owner decision needed (section 3.1 has no column).
- `lastUpdated` for `queryset.update`: set by the use case.
- Everything deferred in the task 02 plan stays deferred.

## Will not do
No mapper, serializer, use case, helper class for `If-Match`, renames, new dependency, change to
`0001` or `0002`, index beyond the new unique constraint, admin, seeds.

## Fresh-clone path
`make setup && make lint && make test && make gate`; `python manage.py migrate` on an empty
database; `python manage.py render_data_model` leaves `git diff doc/data-model.md` empty.

## Open points
1. `HealthcareService.specialty` (above).
2. Department and clinician `active` are derived; a flag on either would be a spec change.
3. Specialty `CodeSystem` admin writes (15.4) are per-concept writes; collection-level `If-Match`
   uses the sequence.

## Revision after architect review (verdict `revise`)
- Material: Practitioner now has a bump rule (`scheduling_touch_user`), three tests and a proof item.
- Non-blocking, all folded in: move-between-clinicians and multi-row tests; ADR 0003 states the
  use-case re-read; specialty revision defined before the first change.

## Architect review

Verdict: approve. Second review, after the revision that added `scheduling_touch_user`.

Checked and holding:
- Ladder: one abstract base, one hand-written trigger migration, two columns on `Appointment`,
  one on `Notification`. No new dependency, no mapper or use case. Triggers are the smallest
  place that covers ORM, `queryset.update` and raw SQL.
- Versions: insert must be 1, update must be `OLD.version + 1`, so a stale `save()` is refused
  by the writing statement (BEFORE ROW trigger re-evaluates on the locked, latest row under
  READ COMMITTED). The `If-Match` shape is a filtered `UPDATE` row count. Parent bumps now
  cover `PractitionerRole` (schedule rows) and `Practitioner` (title, owner).
- Waitlist identity: link plus `inherited_version` gives a never-falling `versionId`; the
  cross-table `BOOKED` rule is named as deferred to the accept use case, with a reason.
- Mapping: 15.2, 15.3 and 15.5 walked against `drlibre-specs.md`; every element has a column
  or a stated derivation. The one open owner point (`HealthcareService.specialty`) is named.
- Tests: first tests are behaviours with legal neighbours, edge and error paths included
  (version 0, 5, +2, lowered, move between clinicians, multi-row, no change before first
  specialty edit). Proof stage lists each existing rule kind and every added rule.
- Security: no boundary crossed; audit trigger order kept; PROTECT on new FKs; hide-list for
  `email`, `phone`, `clinical_notes`, `visitor_*` handed to the FHIR layer.

Non-blocking, fold in while writing ADR 0003 (no re-plan needed):
1. Derived elements have the same staleness class as the Practitioner finding: `PractitionerRole`
   and `Schedule` `active` come from `User.is_active`, department `Organization.active` from
   `Hospital.is_active`, offered start/end/practitioner on a waitlist `Appointment` from
   `offered_appointment`. A change there leaves the served resource's `versionId` unchanged.
   State in the ADR that `versionId` follows the stored row plus the listed touch rules and
   that these derived elements are outside it (or add a touch rule if the owner disagrees).
2. Add a test that two concurrent transactions on one row (second blocks, then is refused)
   leave the first writer's values; the plan only tests two in-memory instances.
3. Test that `Versioned.save()` on a new instance with an explicit pk inserts at version 1.
