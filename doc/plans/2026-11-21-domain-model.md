# Plan: task 02, domain model and migrations

Focal point: `scheduling/models/` (schema as code) and its constraint tests. Everything else is a thin
wrapper: one settings line, one generated document, one pending-migration test.

One-sentence plan per block:

1. **`models/base.py`**: abstract `Record` gives every model `id`, `created_at`, `updated_at`, `created_by`; helper `not_blank(field)` builds a "length at least 1" check.
2. **`identifiers.py`**: `new_identifier()` returns a UUIDv7 (Python 3.13 has no `uuid.uuid7`; 12 lines, RFC 9562 layout).
3. **`models/organisation.py`**: Hospital, Department, Specialty, Room, AppointmentType with their unique codes and ranges.
4. **`models/people.py`**: User (`AbstractBaseUser`, email login, role) and ClinicianProfile.
5. **`models/availability.py`**: AvailabilityRule and TimeOff.
6. **`models/booking.py`**: Appointment (with three exclusion constraints), WaitlistEntry, Notification.
7. **`models/access.py`**: Session, BookingHold, VerificationCode, SignInLink (hash columns only).
8. **`models/audit.py`**: AuditLogEntry; its append-only trigger lives in a hand-written migration.
9. **Migrations**: `0001_initial` generated, with `BtreeGistExtension()` hand-inserted as its first operation (the exclusion constraints need it); `0002_audit_log_append_only` hand-written `RunSQL` trigger with reverse SQL.
10. **`data_model_document.py` + management command `render_data_model`**: renders `doc/data-model.md` (Mermaid ER + per-model fields and constraints) from `_meta`; the command writes the file.
11. **Tests**: constraint tests per model file, `test_migrations.py`, `test_data_model_document.py`.

## Decisions

### Identifier: UUIDv7 in a native `uuid` column (ADR 0002)
- Opaque (not a counter, not guessable, not enumerable), unique without coordination, 16 bytes in PostgreSQL.
- Time-ordered in the high bits, so it sorts; "lowest id" (5.5, 5.8) is a total order that follows creation. Ties inside one millisecond fall to random bits: still deterministic, not chronological. Acceptable; rules only need a stable tiebreak.
- Rejected: UUIDv4 (does not sort), ULID string (36 vs 26 chars, no native type, no gain), `BigAutoField` (sequential, forbidden), PostgreSQL 18 `uuidv7()` (we run 15).
- Wire form is the canonical lowercase hyphenated string (the "opaque string" of section 3). The default is `new_identifier` in Python, not a database default, so an id is known before insert.
- Generator is the only new "abstraction"; it has callers in every model through `Record`.

### Time
`USE_TZ = True` already; PostgreSQL stores `timestamptz`, Django returns aware UTC. Fields: `*_at` for instants, `start_time`/`end_time` only for the local wall-clock window of an AvailabilityRule. Appointment, hold and time off use `starts_at` / `ends_at`.

### Deletion
Every foreign key is `on_delete=PROTECT`; no `CASCADE`, `SET_NULL`, `SET_DEFAULT`. Django's FK constraint is `DEFERRABLE INITIALLY DEFERRED` with `NO ACTION`, so the database refuses a dangling delete at commit. Tests prove both layers: ORM `ProtectedError`, and raw SQL `DELETE` followed by `SET CONSTRAINTS ALL IMMEDIATE` raising `IntegrityError`.

### Foreign key targets
Clinician references (Appointment, WaitlistEntry, BookingHold, TimeOff, AvailabilityRule) point at **ClinicianProfile**, because section 10 "Deleting" says a clinician profile cannot be deleted while it has appointments. Patient references point at User.

### Settings
`AUTH_USER_MODEL = "scheduling.User"`. `INSTALLED_APPS` stays `["rest_framework", "scheduling"]`: no contrib app is needed (`AbstractBaseUser`, `ExclusionConstraint`, `ArrayField`, `BtreeGistExtension` import without being installed). ADR 0001 said task 02 revisits this; the answer is "unchanged", recorded in ADR 0002. `MIDDLEWARE` unchanged (sessions are our own model; no use case yet). If the implementer finds a Django system check failing without `auth`, add the minimum and say why.

## Schema (database-enforced rules)

Naming: every constraint is named `<model>_<rule>` and carries a `violation_error_message` in plain words; the generated document prints both.

| Model | Fields beyond `Record` | Constraints |
| --- | --- | --- |
| Hospital | name, code, description, street_address, postal_code, city, country, phone, time_zone, latitude?, longitude?, is_active | code unique; name and code not blank; latitude in [-90, 90]; longitude in [-180, 180]; latitude and longitude both set or both empty |
| Department | hospital, name, code, description? | code unique; name, code not blank |
| Specialty | name, code, is_active | code unique; name, code not blank |
| User | email, password (hash, unusable allowed), full_name, role, is_active, phone, date_of_birth?, last_login?, email_verified_at? | email unique; email equals `lower(email)` and not blank; role in ADMIN, CLINICIAN, PATIENT; full_name not blank; only PATIENT may have an unusable password (hash starts with `!`); a passwordless patient has `email_verified_at` |
| ClinicianProfile | user (one to one), department, specialty, title, bio?, default_room?, round_robin_weight (default 1), last_assigned_at? | user unique (one profile per user); weight at least 1 |
| Room | department, name, code, floor, capacity, equipment (array of text), is_active | code unique; capacity at least 1; name, code not blank |
| AppointmentType | department, name, code, duration_minutes, needs_room, buffer_minutes, colour, is_active, is_bookable_online | code unique; duration at least 1; buffer at least 0; colour matches `#rrggbb`; name, code not blank |
| AvailabilityRule | clinician, weekday, start_time, end_time, slot_step_minutes, room?, valid_from, valid_to? | weekday 0 to 6; end_time > start_time; both times on whole minutes (HH:MM); step 5 to 240; valid_to >= valid_from |
| TimeOff | clinician, starts_at, ends_at, reason (varchar 200, may be empty) | ends_at > starts_at |
| Appointment | patient, clinician, appointment_type, room?, starts_at, ends_at, status, source, patient_reason, clinical_notes, cancelled_at?, cancellation_reason | ends_at > starts_at; status in six values; source in three; notes at most 5000 characters; `cancelled_at` and a non-blank cancellation reason exist exactly when status is CANCELLED; **three exclusion constraints** (below) |
| WaitlistEntry | patient, appointment_type, preferred_clinician?, earliest_at, latest_at, status, offered_appointment? | latest_at > earliest_at; status in four values; WAITING has no offered appointment, OFFERED has one; one OFFERED entry per freed appointment (partial unique) |
| Notification | recipient, kind, title (200), body, appointment?, read_at? | kind in five values; title not blank; one reminder per appointment (partial unique on appointment where kind is reminder, makes 5.7 safe to run twice) |
| AuditLogEntry | actor?, action, entity_type, entity_id (varchar 64), metadata (JSON), correlation_id | action, entity_type, entity_id, correlation_id not blank; **append-only trigger** |
| Session | user, token_hash, expires_at, user_agent | token_hash unique, exactly 64 characters; expires_at > created_at |
| BookingHold | clinician, appointment_type, starts_at, ends_at, source, visitor_name, visitor_birth_date, visitor_email, visitor_phone, visitor_reason, expires_at | ends_at > starts_at; expires_at > created_at; visitor_email lower case; source in ONLINE, ROUND_ROBIN |
| VerificationCode | code_hash, email, purpose, expires_at, attempts_used | code_hash 64 characters; email lower case; purpose in (BOOKING); attempts_used at least 0; expires_at > created_at |
| SignInLink | token_hash, patient, expires_at, used_at? | token_hash unique, 64 characters; expires_at > created_at |

Notes:
- Choice lists are `TextChoices`; the check is written explicitly from `values`, so the database refuses an unknown value.
- Character limits come from the specification where it states one (reason 200, notes 5000); other `CharField` lengths are chosen here (names 200, codes 50, email 254, phone 30) and listed in the document.
- `Record.created_by` is a nullable FK to User, PROTECT, `related_name="+"`. Nullable because system and visitor-originated rows have no signed-in creator. Kept on every model, as section 3 says "every record".
- Exclusion constraints, all `ExclusionConstraint` on `tstzrange(starts_at, ends_at, '[)')` with `&&`, condition `status NOT IN ('CANCELLED','NO_SHOW')`, one per `clinician`, `patient`, `room` (`=`, needs `btree_gist`). Half-open ranges: touching is legal. A null room is never equal to another, so room-less appointments never collide. The 5.1 buffer is not in the database (it depends on the type being booked); free-slot search owns it.
- The AuditLogEntry trigger: `BEFORE UPDATE OR DELETE ... FOR EACH ROW` and `BEFORE TRUNCATE ... FOR EACH STATEMENT` call one function that `RAISE EXCEPTION`. A superuser can still drop the trigger; the application role cannot. Tests use the transactional `db` fixture (rollback), never `transaction=True`, because the flush at teardown would TRUNCATE; the test run states this in a comment.

## Sections 4 to 12: which stored-data invariants are in this schema

Encoded now (single-row or single-table, expressible as constraint): lower-case email (4, 7.2 lookups); passwordless patient only (7.2, 12.1: staff use passwords); cancellation time and reason iff CANCELLED (5.6); no overlap per clinician, patient, room (5.2 step 3); one reminder per appointment (5.7); one offer per freed appointment (5.8 manual offer); WAITING/OFFERED link consistency (5.8); audit never changed (4); hash-only secrets (7.3, 12.2); FK protection for every row of the section 10 deletion table (the "reasons" listing stays in the use case).

Waits for its use case, with the reason:

| Invariant | Section | Why not now |
| --- | --- | --- |
| Appointment's clinician and type in the same department; clinician default room, availability rule room, appointment room in the clinician's department; room active at booking | 3.2, 5.2, 10 | Spans tables; a CHECK cannot read another row. Composite FKs are not in Django 6.1; triggers would hide business rules. Booking use case checks under a lock (task for 5.2). |
| Appointment end equals start plus type duration | 5.2 | Needs the type row. Use case sets it; end is never accepted from callers. |
| `clinician` has role CLINICIAN, `patient` has role PATIENT, profile user is a CLINICIAN | 3.1, 5.4 | Cross-table. User-management and booking use cases. |
| Hospital `time_zone` is an IANA name | 4 | Zone list lives in `zoneinfo`, not in a CHECK. Validate in the hospital use case. |
| Held slot counts as a conflict; one open hold per email; hold expiry | 7.1 | Depend on "now" and span tables. Hold use case, with a lock. |
| Attempts at most 5; 3 codes or links per hour; link used once and earlier links cancelled | 7.1, 7.3 | Policy numbers belong in code (section 5.3 calls them constants); counts need a clock. Indexes arrive with the queries. |
| Session lifetime per sign-in kind; extension when under half remains | 12.2 | Policy over time. Use case. |
| Audit metadata holds no personal data; metadata is a JSON object | 4 | Content rule; cannot be a CHECK. Audit writer is the single path (task for it). |
| Room cannot move department while clinicians use it as default | 10 | Cross-table update rule. Room use case. |
| Admin cannot deactivate or re-role self; at least one admin | 10 | Needs the actor. Use case. |
| One availability rule per weekday window without overlap | 5.1 | Not stated; free-slot search deduplicates starts. |
| Status transitions (5.6) | 5.6 | A transition is a pair of rows in time; domain function plus use case. |
| Waitlist offer window contains the freed slot | 5.8 | Needs the appointment row. |
| Secrets are really hashes of the right algorithm | 7, 12 | The sign-in tasks hash; the schema fixes only column shape (name `*_hash`, 64 characters). |

## Tests, written first

Placement: `scheduling/models/test_*.py`, plus `scheduling/test_migrations.py` and `scheduling/test_data_model_document.py`. Builders in `scheduling/models/builders.py` (`build_hospital()` ... `build_appointment(**overrides)`; not collected). A helper `refuses(action)` runs the action in `transaction.atomic()` and asserts `IntegrityError`. All marked with `pytest.mark.django_db` (module `pytestmark`).

Each constraint gets a pair: `rejects_X_when_Y` and `returns_X_when_Y` (accepted neighbour, saved row read back with the stated value). Expected values in words from the specification:

- Identifier: `returns_time_ordered_uuid_when_two_identifiers_are_generated_in_turn` (second sorts after first, version 7); `returns_uuid_primary_key_when_record_is_saved` (not an integer).
- Record: `returns_utc_aware_creation_time_when_record_is_saved`; `returns_later_update_time_when_record_is_saved_again`; `returns_empty_creator_when_no_user_created_record`; creator stored when set.
- Unique codes, one pair each for Hospital, Department, Specialty, Room, AppointmentType: `rejects_duplicate_code_when_code_repeats`, `returns_saved_row_when_codes_differ`.
- User email: `rejects_mixed_case_email_when_stored`; `returns_lower_case_email_when_stored`; `rejects_second_user_when_email_differs_only_by_case`.
- User passwordless: `rejects_passwordless_patient_when_email_unverified`; `returns_passwordless_patient_when_email_verified`; `rejects_passwordless_clinician`; `returns_unusable_password_when_set_unusable_password_called` (Django hashing: `has_usable_password()` False; a set password is a hash, not the plain text).
- Ranges, boundary pairs (illegal / smallest legal): capacity 0 / 1; duration 0 / 1; buffer -1 / 0; weight 0 / 1; weekday -1, 7 / 0, 6; slot step 4, 241 / 5, 240; latitude 90.1 / 90 and longitude 180.1 / 180, one coordinate alone / both; end equals start / end one minute after (AvailabilityRule, TimeOff, Appointment, WaitlistEntry window, BookingHold); times with seconds / whole minutes; valid_to before valid_from / equal; reason 201 / 200 characters; notes 5001 / 5000 characters; colour `red`, `#FFFFFF` / `#00ff7f`.
- Value lists: `rejects_unknown_status_when_appointment_saved` for each of Appointment status and source, User role, Notification kind, WaitlistEntry status, BookingHold source, VerificationCode purpose; each legal value accepted (parametrised over `Choices.values`).
- Cancellation: `rejects_cancelled_appointment_when_no_cancellation_time`; `rejects_cancellation_time_when_status_is_booked`; `returns_cancelled_appointment_when_time_and_reason_given`.
- Double booking, for each of clinician, patient, room (nine tests in `test_appointment_overlap.py`):
  - `rejects_appointment_when_active_one_overlaps_for_same_clinician` (10:00-10:30 then 10:15-10:45)
  - `returns_appointment_when_it_starts_where_the_other_ends` (touching: 10:30-11:00 accepted, also the reverse order)
  - `returns_appointment_when_overlapping_one_is_cancelled`, same for `NO_SHOW`
  - `returns_appointment_when_overlap_is_for_a_different_clinician_patient_or_room`
  - `returns_appointment_when_two_have_no_room`
  - `rejects_update_when_cancelled_appointment_is_reactivated_into_overlap`
  - `rejects_identical_appointment_when_active` (same interval)
  - `returns_appointment_when_checked_in_and_completed_statuses_do_not_overlap` is not needed; `CHECKED_IN` and `COMPLETED` rejection is covered by parametrising active statuses (BOOKED, CONFIRMED, CHECKED_IN, COMPLETED).
- Waitlist: `rejects_second_offered_entry_when_same_appointment_offered`; `returns_second_entry_when_first_is_booked`; `rejects_waiting_entry_with_offered_appointment`; `rejects_offered_entry_without_appointment`.
- Notification: `rejects_second_reminder_when_appointment_has_one`; `returns_second_notification_when_kind_differs`.
- Audit: `rejects_update_when_audit_entry_is_changed` (ORM `save`, `queryset.update`, raw SQL `UPDATE`); `rejects_delete_when_audit_entry_is_removed` (ORM, raw SQL); `rejects_truncate_when_audit_table_is_emptied`; `returns_entry_unchanged_when_read_after_refused_update`; `returns_entry_when_appended` (insert works, empty actor allowed).
- Deletion: for each foreign key a parametrised `rejects_delete_when_row_is_referenced` (ORM `ProtectedError`; raw SQL then `SET CONSTRAINTS ALL IMMEDIATE` gives `IntegrityError`); `returns_deleted_row_when_nothing_refers_to_it`. A meta test `returns_protect_on_delete_when_every_foreign_key_is_inspected` walks `apps.get_models()`.
- Secrets: `returns_no_secret_column_when_session_code_and_link_models_are_inspected` (every field name containing `token` or `code` ends in `_hash`; none is a text/blob that is not 64 characters; Session, VerificationCode, SignInLink); `rejects_hash_when_not_64_characters`; `returns_hash_when_64_hex_characters`.
- Expiry: `rejects_expiry_when_not_after_creation` / `returns_row_when_expiry_is_after_creation` for Session, BookingHold, VerificationCode, SignInLink.
- `test_migrations.py`: `returns_no_pending_changes_when_models_match_migrations` (`makemigrations --check --dry-run`, runs inside `make test`); `returns_extension_installed_when_exclusion_constraints_exist` (via `pg_extension`).
- `test_data_model_document.py`: `returns_committed_document_when_rendered_from_models` (string equality with `doc/data-model.md`, failure message names the command to regenerate); `returns_every_model_when_document_is_rendered`; `returns_every_constraint_name_when_document_is_rendered`; `returns_mermaid_relationship_when_foreign_key_exists`.

Red-proof: red stage shows suite failing for the right reason (models absent, then each constraint omitted in turn makes its one test fail). The prove stage deletes a constraint and the appointment trigger and shows the tests catching it.

## Files, in order
`scheduling/identifiers.py` (+test), `scheduling/models/__init__.py` (re-exports all 17 so `makemigrations` sees them), `base.py`, `organisation.py`, `people.py`, `availability.py`, `booking.py`, `access.py`, `audit.py`, test modules and `builders.py`, `drlibre/settings.py` (one line), `scheduling/migrations/0001_initial.py`, `0002_audit_log_append_only.py`, `scheduling/data_model_document.py`, `scheduling/management/commands/render_data_model.py` (+ two `__init__.py`), `doc/data-model.md` (generated, committed), `doc/adr/0002-identifiers-and-schema-guards.md`, `doc/backlog.md` status line is the orchestrator's.

Deliberately not touched: `Makefile` (pending-migration check is a test, so `make test` already runs it), `.env.example`, compose, health view, `scripts/`, admin registration, views, serializers, use cases, seeds, `doc/backlog/*`, `CLAUDE.md`.

Size: models split into one file per group to stay under 300 lines; migration `0001` is generated and exempt (§5), its single hand-inserted extension operation is called out in the ADR. Layer note: `scheduling/domain/` gets nothing now; models are storage, no behaviour beyond fields and constraints.

## Invariants, trust boundaries, blast radius
- Invariants held: double booking (database last line), append-only audit, no cascade, hash-only secrets. Server-side authorization: no code path here; roles are stored values only. Never log or store: no secret column exists; `clinical_notes` and `visitor_*` are plain text for now (open point).
- Trust boundaries: none crossed (no input path, no request). Database privileges: `CREATE EXTENSION btree_gist` runs as the application role; it is a trusted extension in PostgreSQL 13+ and the role owns the database (`ensure_database.py` creates it so). If compose's `db` or a managed server forbids it, the failure is loud at migrate. Verified in the sandbox by `make test`; compose image is verified by the host.
- Blast radius: `AUTH_USER_MODEL` is fixed by the first migration (changing it later is a rewrite, hence the owner review). Only `scheduling` and `settings.py` change; the health view and its test must stay green.

## Domain entities used
All 17 of the CLAUDE.md vocabulary (Hospital, Department, Specialty, User, ClinicianProfile, Room, AppointmentType, AvailabilityRule, TimeOff, Appointment, WaitlistEntry, Notification, AuditLogEntry, Session, BookingHold, VerificationCode, SignInLink). Not modelled: ApiClient token (task for section 15), Visitor and Patient as separate tables (Patient is a User role; Visitor is nobody).

## Open points (stated, not solved)
1. **Encryption at rest** for `clinical_notes` and BookingHold `visitor_*` fields: stored plain now. Options (column encryption with a key from the environment, pgcrypto, disk-level only) need an owner decision and key management. BookingHold rows are short-lived; clinical notes are long-lived and the larger risk.
2. **`CONFIRMED`** (section 17): kept in the status list, the check, the exclusion filter (active) and the doc, because the specification keeps it in the transition table. Removing it later is one migration and one enum member.
3. BookingHold `source` column: spec step 7.1.5 needs ONLINE or ROUND_ROBIN at booking time but 3.1 lists no such field for the hold. Included; owner may drop.
4. Unstated lengths and formats chosen here: colour `#rrggbb`, patient reason (no cap), character limits for names, codes, phone. Listed in `doc/data-model.md`.
5. VerificationCode `purpose` has one value (BOOKING) until another flow needs a code.
6. UUIDv7 ties inside one millisecond are random; revisit only if "lowest id" must mean "created first".
7. A superuser can disable the audit trigger; defence beyond that is operations (roles, backups), not schema.

## Will not do
Admin registration, managers, serializers, seeds, indexes beyond those implied by FKs, unique and exclusion constraints (indexes arrive with the queries that need them), composite foreign keys, triggers other than the audit one, any new dependency, any change to scaffold files beyond the one settings line.

## Fresh-clone path
`make setup && make lint && make test && make gate`; `python manage.py migrate` on an empty database must succeed and `python manage.py render_data_model` must leave `git diff doc/data-model.md` empty.

## Architect review

Verdict: approve.

- Ladder: one generator, one base class, one extension, one trigger; no new dependency; no admin, view or serializer. Right place (`scheduling/models/`, storage only).
- Plan knowledge: each block has a one-sentence purpose; all 17 vocabulary names used; ApiClient correctly deferred.
- Tests: named as behaviours, illegal/legal boundary pairs, touching, cancelled and NO_SHOW overlaps, audit via ORM and raw SQL and TRUNCATE, PROTECT at both layers, stale-document and pending-migration tests. Covers task item 8.
- Security: append-only audit in the database, hash-only secrets, no cascade. Plaintext `clinical_notes` and `visitor_*` are stated as open point 1. Fine for this task.
- Scope: items 1 to 9 are all present; the deferred-invariants table gives a reason per row.

Implementer watch-points (not blocking):
1. `btree_gist` must work on the `db` image in compose as well as the sandbox; the migration fails loudly if not. State in the hand-off that compose was not run if so.
2. The exclusion constraint on `patient` and `room` needs `btree_gist` uuid support (present in PG 15). Prove with the actual rejected-overlap tests, not by reading.
3. Keep `0002` reverse SQL working (`migrate scheduling 0001`), and make sure the `django_migrations`/test DB teardown never TRUNCATEs the audit table.
4. Task wording says Session needs no column that could hold the secret; the `*_hash` plus 64-character check satisfies that. Keep the inspection test strict.
