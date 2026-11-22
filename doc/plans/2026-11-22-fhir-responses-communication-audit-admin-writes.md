# Plan: task 24, FHIR `AppointmentResponse`, `Communication`, `AuditEvent` and the admin writes

Plan in one sentence: three read-mostly resource types join the single declaration as `Part`s read by the
existing `search_parts` machinery (one with a create that calls `accept_offer`, one with an update that calls
`mark_read`, one read-only), and the admin and time-off writes decode a body purely into the fields the console's use
cases already take, so no FHIR write has a rule the screens lack; the section-15 tables become test data that checks
the declaration, the CapabilityStatement and the routes against each other.

Read: `drlibre-specs.md` 4, 15.1 to 15.6, 5.8; ADR 0003, 0005, 0006; plan of 23a; `fhir_declaration.py`,
`fhir_resources.py`, `views/fhir/views.py`, `writes.py`, `fhir_schedule_writes.py`, `fhir_reads.py` (`Part`,
`search_parts`), `fhir_appointment_reads.py`, `fhir_appointment_writes.py`, `fhir_loading.py`, `samples.py`,
`scripts/fhir_validate.sh`; use cases `waitlist.accept_offer`, `notification_inbox.mark_read`, `admin_records`,
`admin_clinicians`, `admin_users`, `time_off`, `admin_audit`; models `Notification`, `AuditLogEntry`, `TimeOff`.

## Focal point

`scheduling/use_cases/fhir_resources.py` (the router) and `fhir_declaration.py` (the one list). Everything else is an
adapter behind one of the two. Views change in one place: `_allowed_methods` (10d) and the `If-Match` plumbing for delete.

## Decisions (reject here if wrong)

- **AppointmentResponse id** = the waitlist entry id (same as the Appointment, ADR 0003). One resource per entry that
  is `BOOKED`: `participantStatus: accepted`, `appointment: Appointment/<entry id>`, `actor: Patient/<id>`,
  `start`/`end` of the booking. Read, search (declared params: none in 15.5, so only the common ones; `patient`
  and `status` are NOT added: the table says nothing else) show only booked entries. An entry that is waiting, offered
  or expired has no response; declining does not exist, so no `declined`/`tentative` is ever created or shown and a
  POST with any status but `accepted` is 400 `AppointmentResponse.participantStatus` (ADR: declining not in spec).
  Visibility: patient own entries, admin all, clinician and public 403 / 401.
- **AppointmentResponse create**: body `appointment` reference (an `Appointment/<entry id>` in `proposed`), `actor`
  patient reference, `participantStatus accepted`. `accept_offer(entry_id, user)` runs; its failures are the contract
  (`invalid_transition` 409 for second acceptance and a gone offer, `conflict`/`no_room_available` 409 for a taken slot,
  `forbidden` for another patient's offer). `actor` must equal the entry's patient, else 400 `AppointmentResponse.actor`
  (an admin accepts for the patient, so the actor is the patient, never the token). 201 + `Location`.
  Update, delete: 405.
- **Communication id** = notification id. `recipient` Patient/Practitioner reference (recipient user by role),
  `category[0].coding` kind (system `<base>/CodeSystem/notification-kind`, code = kind value), `payload[0].contentString`
  title + body, `sent` created_at, `received` read_at when set, `about` Appointment (appointment id, or the waitlist
  entry id whose Appointment carries the same logical id), `status completed`. Visible: `recipient = token user`,
  for every role including admin. Another's id = 403 as Appointment does (same body as absent).
- **Communication update**: body equal to the stored resource except `received`; `received` set from absent and equal to
  the server time is not trusted: the client's value is checked only as a valid dateTime and the server stamps its own
  clock (`mark_read`, "once": already read stays read, a body that sets `received` again to another value is 409
  `invalid_transition`; an echo is a no-op). Any other changed element is 400 naming it (`Communication.payload`). Create,
  delete: 405. Mark-as-read audit keeps the id and `changed_fields` only.
- **AuditEvent id** = entry id. `action` coding `<base>/CodeSystem/audit-action` code = the action string,
  `recorded` created_at, `agent[0].who` Practitioner/Patient reference of the actor (absent for a shell issue), `entity`
  `what.identifier` = entity type + id (`entity` search token `<type>/<id>` or `<id>`), `entity.detail` one per metadata
  key with `valueString` (ids, counts, status values, field names, email domain only: `audit_metadata` types cannot carry
  more), `extension correlation-id`. Admin only; others 403, public 401. All writes 405.
- **AuditEvent search**: `agent` actor id, `entity` token, `entity-type`, `action`, `date` (range as Slot/Appointment do via
  `day_bounds`). Default order newest first through a new `default_sort`; uses the existing `audit_*_idx` indexes. A page
  is cut as `admin_audit.list_audit` does (keys first, rows after): 2 queries for the page, `total` is a count
  (one more). Asserted: bounded query count and under a time limit on 50 000 rows (bulk-inserted in a test fixture through
  `bulk_create`; the trigger only refuses update/delete).
- **Admin writes** each decode a body in a pure `fhir_<type>_write.py` into the values dict the console use case takes
  (`create_record`/`update_record`/`delete_record`, `attach_profile`/`update_profile`/`delete_profile`, `create_user`/
  `update_user`/`delete_user`), call it with the token user, and answer by loading the saved row. A field the mapper does not
  serve is 400 with its path; a field the console would reject is the console's `invalid_input` mapped through
  `FHIR_PATH_OF_FIELD` (extend the table for each record field).
- **Hospital**: the client writes the `Location` (site) because it holds every required field (address, phone, position,
  time zone). `Organization` of type `prov` answers: create 400 `Organization.type` ("write the Location"), update accepts an
  echo only (a changed element 400 naming it), delete 409 `invalid_transition`-style refusal naming the Location. Delete of
  the Location deletes the hospital through `delete_record("hospital")` (has_dependents when departments exist). An id
  that is both is resolved to its hospital row first. Department = `Organization` type `dept` + `partOf`; room = `Location`
  type `ro` + `partOf` + `managingOrganization`; `HealthcareService` = appointment type (`providedBy` the department).
- **Specialty list**: one `CodeSystem` PUT with `If-Match` on the revision. The server diffs the `concept` list against
  stored rows by code: a code that is new = `create_record("specialty")`; same code, new display = `update_record` (rename);
  a code absent = `delete_record` (refused with `has_dependents` 409 when a clinician uses it, whole PUT rolled back, one
  transaction). Changing a code is remove + add. Deactivating is a console-only action and is not offered. `ValueSet`
  PUT accepts only an echo (the set includes the whole code system); POST on both = 409 `conflict` (the single id
  exists); DELETE on both = 409 `has_dependents` ("the specialty list is not deleted as a whole; remove its concepts").
  All four interactions stay declared because 15.4 says so; the ADR states the answers.
- **Practitioner/PractitionerRole**: Practitioner create = `create_user` (role CLINICIAN, email from `telecom`, name from
  `name.text`); PractitionerRole create = `attach_profile` (department, specialty code to id, title, bio, weight, default
  room). Update = `update_user`/`update_profile`; delete = `delete_user`/`delete_profile`. `Practitioner.qualification` is the
  title and lives on the profile row: a Practitioner PUT with a changed title is 400 (write the role); the role carries
  `qualification`'s twin `extension role-title`. OPEN: `create_user` requires a password and FHIR has none; plan: generate a
  random one inside the pure mapper's caller, never returned or logged, and tell the owner a new clinician signs in through the
  existing sign-in link flow. If the console cannot do that (check `sign_in_link` for roles), STOP and hand to the owner.
- **notAvailable**: `PractitionerRole.notAvailable[]` is served from `TimeOff` rows (`description` = reason, `during`
  start/end); the mapper change is in `fhir_practitioner_role.py` and `loading._roles`. The version follows ADR 0003: a
  `TimeOff` change already bumps the profile; a test proves it. A clinician's PUT of the own role: diff the body against
  what the caller sees; only `notAvailable` may differ; a period whose (start, end) is new = `create_time_off`; a period absent
  = `delete_time_off` (matched by (start, end)); a period with the same description but another start/end is
  indistinguishable from remove + add by design, a period matched by (start) with another end or the same period with a
  changed `description` = 400 `PractitionerRole.notAvailable` ("recorded and removed, not edited"). Any other element 400.
  A clinician touching another's role: 403.
- **If-Match**: `update_record`, `delete_record`, `delete_profile`, `delete_user`, `delete_time_off`, `update_profile`
  gain an optional `expected_version` compared under their lock, answering `stale_version()` (pattern of 23a). Pages
  pass nothing: behaviour unchanged. Specialty list compares against the revision.
- **Sort by database collation** (10d): ADR 0007/0005 says which: today the candidate query sorts `Lower(Cast(...))` in
  PostgreSQL's default collation, not by code point; checked in the sandbox which one it is, and stated.

## Blocks (one sentence each)

Domain, pure, under the mutation gate (`test_*.py` beside each):
1. `fhir_appointment_response.py`: stored booked-entry values to `AppointmentResponse`; `decode_response(body)` to the
   entry id and patient id, or the refused element.
2. `fhir_communication.py`: row values to `Communication`; `decode_read(stored_as_seen, body)` to `MarkRead` | `NoChange` | element.
3. `fhir_audit_event.py`: row values to `AuditEvent`, metadata to `entity.detail`, entity token parser.
4. `fhir_organization_write.py`, `fhir_location_write.py`, `fhir_service_write.py`, `fhir_specialty_write.py`: bodies to the
   console's values dict; specialty `diff_concepts(stored, body)` to adds, renames, removals.
5. `fhir_practitioner_write.py` (Practitioner and PractitionerRole): bodies to values; `time_off_changes(stored, body)` to
   `Add(period)`, `Remove(period)` or the refused element.
6. `fhir_practitioner_role.py`: add `notAvailable`; `fhir_write_failures.py`: `FHIR_PATH_OF_FIELD` extended.
7. `fhir_declaration.py`: `AppointmentResponse` (read, search-type, create), `Communication` (read, search-type, update),
   `AuditEvent` (read, search-type) with the 15.5 parameters (`recipient` reference, `category` code, `sent` date; `agent`
   reference, `entity` token, `entity-type` code, `action` code, `date` date) and the writes added to the five admin types,
   `Practitioner`, `PractitionerRole`; `default_sort` field. `fhir_write_shapes.py`: one shape per writable type.

Use cases (adapters, no new rules):
8. `fhir_response_reads.py`, `fhir_communication_reads.py`, `fhir_audit_reads.py`: `Part`s with their own visibility, filters
   and builders (loaders in `fhir_response_loading.py`, `fhir_audit_loading.py`, batched).
9. `fhir_response_writes.py` (create via `accept_offer`), `fhir_communication_writes.py` (update via `mark_read`),
   `fhir_admin_writes.py` (five admin types + CodeSystem diff in one transaction), `fhir_practitioner_writes.py` (admin writes
   and clinician `notAvailable`).
10. Use cases gain optional `expected_version` (list above), so `If-Match` is checked under the lock.
11. `fhir_resources.py` routes the new types; a table `WRITERS: dict[(type, interaction), function]` replaces the growing `if` chain
    (three or more callers per interaction, so it earns its place).
12. `views/fhir/views.py`: `_allowed_methods` returns an empty tuple or a 404 value instead of `assert` (10d); `NO_STORE_TYPES`
    adds the new types; delete reads `If-Match` as it does for Schedule (no change expected in `writes.py`).

Carried points (10a to 10d):
13. `samples.py` split in two files (it grows past 300 lines): Appointment views (booked, cancelled with reason, checked in,
    fulfilled, no-show, hold, waitlist, offered), each write body, a refusal naming `violated-rule`, search with the three
    `_include`s; plus the new types and each write body. `test_samples.py`: test that fails when a declaration type has no
    `*-read-*` sample.
14. `doc/adr/0007-fhir-appointment-and-booking.md` (23a decisions: status and source extensions, `violated-rule`/
    `conflicting-resource`, hold and waitlist entry, what a body may change, collation); `0008` is task 26's, not used.
    `doc/adr/0009-fhir-responses-communication-audit-admin-writes.md` for this task's decisions (hospital two resources,
    specialty list, declining, notAvailable, Communication once). ADR 0005 open points closed or handed to the owner
    (admin Practitioner as role `administrator` not served: owner; clinician visibility kept; tokens expiry: owner).
15. 10c: one lookup in `update_appointment`; `read_appointment` takes the parsed id; `test_fhir_appointment_race.py` typed
    through a small typed helper instead of `type: ignore` lines.
16. 10d: `scripts/fhir_validate.sh` drops its database on exit (`trap` runs `dropdb`/`psql DROP DATABASE`); busy intervals
    out of `fhir_slot_reads.py` (290 lines) into `fhir_slot_busy.py`.
17. README section "FHIR API": issue a token, read, search, book (curl). `doc/backlog.md` row, `doc/retro.md` is the
    orchestrator's.

## Files to touch, in order

`scheduling/domain/`: `fhir_declaration.py`, `fhir_write_failures.py`, `fhir_practitioner_role.py`, the new
`fhir_appointment_response.py`, `fhir_communication.py`, `fhir_audit_event.py`, `fhir_*_write.py` (five), `fhir_write_shapes.py`.
`scheduling/use_cases/`: `admin_records.py`, `admin_clinicians.py`, `admin_users.py`, `time_off.py` (optional version),
`fhir_loading.py` (`_roles` + `notAvailable`), new `fhir_response_*`, `fhir_communication_*`, `fhir_audit_*`, `fhir_admin_writes.py`,
`fhir_practitioner_writes.py`, `fhir_slot_busy.py`, `fhir_slot_reads.py`, `fhir_appointment_writes.py`,
`fhir_appointment_reads.py`, `fhir_resources.py`. `scheduling/views/fhir/`: `views.py`, `samples.py`, `samples_appointment.py`
(new), `test_samples.py`; `scripts/fhir_validate.sh`; ADRs 0005, 0007, 0009; `README.md`; `doc/backlog.md`;
`mutation-equivalents.txt` only for explained survivors.

Deliberately not touched: `views/pages/`, templates, static, `placement.py`, `booking_holds.py`, `appointment_changes.py`
beyond nothing, `waitlist.py` and `notification_inbox.py` (called as they are), the model files and migrations (the audit
and notification indexes exist; check with `EXPLAIN` in the 50 000 test, add an index only if the test proves it needed and
then as its own migration with an ADR line), the demo seed.

## Invariants and blast radius

- No double booking: acceptance only through `accept_offer` -> `place_appointment`; no new booking path.
- Server-side authorization: from the token user: acceptance via `_may_accept`, mark-read via `recipient_id`, writes via
  `is_admin`/`locked_profile`; a body's `actor`, `recipient` or practitioner id never grants rights.
- Audit append-only and inside the use case's transaction; the AuditEvent view adds nothing and has no write route (405).
  The CodeSystem diff is one transaction: any refusal rolls every concept change back.
- Privacy: AuditEvent exposes only what `AuditMetadata` can hold; planted values are tested absent. Communication, AuditEvent and
  AppointmentResponse are `no-store`; no log carries a value.
- Blast radius: the optional `expected_version` parameter on six console use cases (default none: pages unchanged);
  `fhir_resources.py` routing; `PractitionerRole` now carries `notAvailable` (a public caller sees time-off periods: **decision
  needed**: only staff and the own clinician see `notAvailable` and `description`, the public sees `during` without reason
  or not at all; plan picks staff and owner only, absent for public, so no leak). `fhir_validate.sh`, samples.

## Failing tests first (`returns_X_when_Y`)

Domain (each kills its mutants): `returns_accepted_response_with_appointment_link_when_entry_is_booked`;
`returns_actor_refused_when_participant_status_is_declined`; `returns_communication_with_kind_text_sent_and_received`;
`returns_received_set_when_only_received_changes`; `returns_payload_named_when_text_changes`;
`returns_no_change_when_body_echoes_the_stored_resource`; `returns_audit_event_with_action_agent_entity_and_details`;
`returns_no_agent_when_actor_is_empty`; `returns_adds_renames_and_removals_when_concepts_differ`;
`returns_element_named_when_time_off_period_changed_in_place`; `returns_add_and_remove_when_periods_differ`;
`returns_organization_type_refused_when_create_names_prov`; `returns_every_console_field_as_fhir_path` (exhaustive table).

API, as a FHIR client (bearer token, no cookie, no `Origin`, cross-site check enforced), each with patient, clinician, admin
and no token, and expected status in words from 15.4:
- AppointmentResponse: patient accepts own offer: 201, Appointment `booked`, same id as the entry; second acceptance 409;
  offer expired/cancelled 409; slot taken by another 409 `conflict`; another patient's offer 403; admin accepts for the patient;
  `declined` 400; clinician 403; no token 401; read/search own vs all, `total` counts what the caller may see; PUT and DELETE 405.
- Communication: recipient reads/searches own only; admin reads none of another's (list empty, id 403); filters `recipient`,
  `category`, `sent`; PUT `received` once sets the read time to the request clock, stays 200 on echo; any other element 400
  naming it; stale `If-Match` 412; POST and DELETE 405; `about` is the appointment and for a waitlist offer the entry's id.
- AuditEvent: admin reads/searches; patient and clinician 403; none 401; each filter; POST, PUT, DELETE 405; 50 000 rows: page
  of `_count=100` in a bounded number of queries (<= 4, asserted with `CaptureQueriesContext`) and under a second; seed scan:
  no name, email beyond domain, phone, birth date, reason or note in any event; the accept and mark-read the orchestrator does
  show up as `waitlist.accept` and the notification entry.
- Admin writes (five types + two): admin create 201 / update 200 / delete 200; clinician and patient 403; none 401; each field
  check equals the console's; delete of a hospital with departments, department with clinicians, specialty in use: 409
  `has_dependents` with the console's words; audit entry with the console's action and metadata keys; stale `If-Match` 412 on
  update and delete for every type; absent `If-Match` allowed; Location and Organization hospital behaviour; specialty list
  add, rename, remove, remove in use rolled back whole.
- Practitioner role: clinician adds a period (TimeOff row, calendar shows it, audit `time_off.create`), removes one (row
  gone), edits one in place 400, changes another field 400, edits another clinician's role 403, admin edits a role in place
  (the console fields), child-row change moves `versionId` of role (and the Practitioner) once.
- Hostile input: every type with a write joins the existing loop (wrong `resourceType`, wrong `id`, deep nesting, wrong types).
- Closing (point 11): data tables of 15.2, 15.4 and 15.5 in a test file; walks the declaration, `GET /fhir/metadata` (resource,
  interaction, search parameter, `_include`) and the real routes (a method per interaction answers other than 405/404; every
  other method on every type is 405; an unlisted parameter is 400); the three agree and nothing else is named.
- Samples: no empty value; every declaration type has a sample; `make fhir-validate` over every new view and body.

## Trust boundaries

| Boundary | Validation and authorization |
| --- | --- |
| Bearer token | `resolve_token`; user and role from the token only |
| Body | size limit, JSON object, `exact_elements` against the type's shape, id/type match URL, decoder checks values, use case validates again |
| References (`appointment`, `actor`, `recipient`, `partOf`, concept codes) | parsed ids; unknown = `not_found` from the use case; owner checks by the use case, not the body |
| Query string | declaration parser; `entity`, `agent`, `date` parsed or 400 |
| `If-Match` | integer, 0 absent, compared under the use case lock |
| Output | per-viewer visibility built before filters; audit view bounded by `AuditMetadata` types; `no-store` |

## Domain vocabulary used

WaitlistEntry, Appointment, Patient, Admin, Clinician, ClinicianProfile, Hospital, Department, Room, AppointmentType, Specialty,
TimeOff, Notification, AuditLogEntry, ApiClient.

## What I will not do

No new dependency, model, migration or column (index only if the 50 000 test fails). No second booking, accept, mark-read or admin
path. No decline, no Communication create/delete, no AuditEvent write, no admin-user Practitioner (owner), no token expiry or scopes.
No change to pages, templates, `placement`, `waitlist`, notification or time-off rules. No generic REST framework beyond the
`WRITERS` table. The sandbox may lack Java or network for the HL7 validator: `make fhir-validate` is reported as it runs.

## Risks to watch

Size: the task is large; each new file under 300 lines, `fhir_reads.py` (347) and `samples.py` not grown, `fhir_declaration.py` stays one
table. `create_user` requires a password (see Decisions, owner-open). `notAvailable` on public reads must stay absent.

## Architect review

Verdict: approve.

- Ladder: one declaration, existing `Part`/`search_parts`, writers decode into the console's values dicts; no new dependency, model or migration. `WRITERS` table has three or more callers per interaction. Holds.
- Scope: covers points 1 to 12 and 10a to 10d, plus the closing table test, ADR 0005/0007/0009 and README.
- Security: authorization from the token user, body `actor`/`recipient` never grants rights, AuditEvent bounded by `AuditMetadata`, `no-store`, one transaction for the CodeSystem diff. Holds.
- Tests: first tests are named as behaviours and cover error paths, hostile input, 50 000-row bound, privacy scan.

Notes for the implementer (not blockers):
1. Re-check `update_user` in `admin_users.py`: it already takes `expected_version`; add it only where missing.
2. `create_user` requires a password. The plan's STOP rule for the random-password case stands: verify the sign-in link flow works for clinicians before relying on it; otherwise hand to the owner.
3. Organization (hospital) delete refusal: pick a concrete failure kind from the table in ADR 0005 and name it in the ADR, not "invalid_transition-style".
4. `notAvailable` differing per viewer (absent for public) must also differ in the cache and `versionId` logic: versionId stays viewer-independent.
5. The "under a second" assertion on 50 000 rows can flake; keep the query-count assertion as the hard one and give the time bound slack.
