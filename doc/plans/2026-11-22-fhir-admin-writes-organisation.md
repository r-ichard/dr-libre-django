# Plan: task 24b, FHIR admin writes for the organisation resources

Slice: items 1, 2 (hospital, department, room, appointment type), 4, 5, 6 and 7 for `Organization`,
`Location` and `HealthcareService`. `CodeSystem` and `ValueSet` (items 2's specialty half, 3) are
`## Not in this run`.

## Focal point

One new use-case module, `scheduling/use_cases/fhir_record_writes.py`: it turns a checked FHIR body
into the `values` dict of `admin_records.create_record` / `update_record` / `delete_record`, calls
them, and rebuilds the answer with the existing `fhir_loading` builders. Everything else is
routing, shapes and samples. The console's field checks, refusals, audit entry and version are
reused, so this task adds no rule.

## Decisions (go into new ADR 0008, `doc/adr/0008-fhir-admin-writes-organisation.md`)

- **A hospital is one row, two resources, one door: the `Location` of the site.** Decided now
  (architect round 1). The place fields (address, phone, position, time zone) exist only on the
  `Location`, and the console needs them on create (`street_address`, `postal_code`, `city`,
  `country`, `phone`, `time_zone`), so the site `Location` is the only door that creates, updates
  and deletes a hospital. Body: `physicalType` `si`, `name`, `identifier` (code), `status`,
  `address` (line, city, postalCode, country), `telecom` phone, `position` (optional pair),
  `hospital-time-zone` extension. On create and PUT each of address line, city, postalCode,
  country, phone and the time-zone extension is required by the pure `site_values`; a missing one
  is 400 naming the element (`Location.address.city`, ...). `description` has no FHIR element: a
  write never touches it (create stores the model default ""). The `Organization` of type `prov`
  is the read-only mirror: `POST /fhir/Organization` with type `prov` is 400 naming
  `Organization.type` ("Create a hospital as a Location with physicalType si");
  `PUT`/`DELETE /fhir/Organization/<hospital id>` is 405 with `Allow: GET`. Fields divide:
  Organization shows `name`, `identifier`, `active`; Location carries all of them plus place.
  `Location` `POST` with `physicalType` `ro` is a room, as below. First failing test:
  `returns_201_with_location_and_etag_when_admin_posts_a_hospital_site` (full body; row exists with
  the place fields; audit `hospital.create`), then
  `returns_400_naming_the_element_when_a_hospital_site_lacks_a_place_field` (one case per field).
- **Code.** Every record needs a `code` the console asks for; reads gain `identifier`
  (system `<base>/identifier/code`) on Organization, Location and HealthcareService so a client
  reads what it must send. Create requires it; update must repeat or change it (the console's
  `code` rule: unique, case-insensitive).
- **Department** = `Organization` type `dept`: `name`, `identifier`, `partOf` (the hospital).
  **Room** = `Location` type `ro`: `name`, `identifier`, `status`, `managingOrganization` (the
  department), floor, capacity, equipment extensions; `partOf` is derived and, when present, must
  equal the department's hospital. **Appointment type** = `HealthcareService`: `name`,
  `identifier`, `active`, `providedBy` (the department), the five `service-*` extensions;
  `type` and `specialty` are derived and, when present, must equal what the server builds.
- Derived elements round-trip (a client may PUT what it GET) but a difference is 400, named.
- **Failures**, from the one table: not admin 403, no token 401, stale `If-Match` 412 (the use
  cases' `conflict([kind])` becomes `stale_version()` in this module), `has_dependents` 409 with
  the console's counts text, code taken 400 on `identifier`.
- Use-case field names become FHIR paths (`name` → `Organization.name`, `code` →
  `Organization.identifier`, `hospital`/`department` → `partOf`/`managingOrganization`/
  `providedBy`, `time_zone` → the extension URL), the way `fhir_patient_writes` does.

## Files, in order

1. `scheduling/use_cases/admin_records.py`: `RecordEdit.version: int | None` (None = no `If-Match`,
   apply to current, skip the check); `delete_record(..., expected_version=None)` returns
   `stale_version()` under the lock. Console callers unchanged. Smallest change that gives item 5.
2. `scheduling/domain/fhir_record_write.py` (pure): shapes `ORGANIZATION_SHAPE`, `LOCATION_SHAPE`,
   `SERVICE_SHAPE`; `organization_values`, `site_values`, `room_values`, `service_values` return a
   values dict or the name of the bad element; `derived_difference` compares derived elements.
   Split in two files if it passes 300 lines.
3. `scheduling/domain/fhir_common.py`, `fhir_organization.py`, `fhir_location.py`,
   `fhir_service.py`, `scheduling/use_cases/fhir_loading.py`: add `identifier` (code) to the five
   builders and their `values_list`s.
4. `scheduling/use_cases/fhir_record_writes.py` (new, the focal block): `create_*`, `update_*`,
   `delete_*` for the three types; decides the kind from the body (`type` coding, `physicalType`)
   or from which table owns the id; admin from `caller.user`, never from the body.
5. `scheduling/use_cases/fhir_resources.py`: route the three types in `create`, `update`, `delete`.
6. `scheduling/domain/fhir_write_shapes.py`, `fhir_declaration.py`: add shapes; interactions
   `(*READ_ONLY, "create", "update", "delete")` for the three types. Routes, `Allow` and the
   CapabilityStatement follow from the declaration. Per-id 405 for a hospital Organization PUT/DELETE is in
   `writes.py` via a small guard before `_deleted`.
7. `scheduling/views/fhir/samples_records.py` and `samples.py`: request body and answer for each
   write (create, update, delete outcome) of each kind, plus one `has_dependents` refusal.
8. `scheduling/views/test_hostile_input.py`: add the three types' paths and bodies, allow their
   `resourceType`s.
9. `doc/adr/0008-...md`, `doc/backlog.md` is the orchestrator's, not touched.

Not touched: `views.py`, `responses.py`, `writes.py` except the one guard, the console pages,
`admin_record_specs.py`, `delete_dependents.py`, models, migrations, `fhir_reads.py` (already 348
lines; reads need no change beyond loading).

## Invariants and blast radius

- Authorization from the token's user; `create_record` etc. refuse non-admin (403) themselves.
  Test every write with admin, clinician, patient and no token.
- One transaction per write, audit entry inside it (the use cases do it); version +1 per change;
  a no-op PUT leaves version and audit untouched, as in the console.
- Audit log stays append-only; hospital deletes still refused while departments exist.
- Blast radius: `identifier` added to five read builders changes their sample documents and any
  test comparing whole resources; `RecordEdit.version` type widened; every other use is unchanged.
- Trust boundary: JSON body from the network. Checked by `exact_elements` against the shape, then
  by the pure `*_values` functions, then by the use case's own field checks. Sizes already capped
  by `request_limits`.

## Failing tests first (names `returns_X_when_Y`)

Views, with `fhir_client(token)`: bearer, no cookie, no `Origin`.
- `returns_201_with_location_and_etag_when_admin_posts_a_department` (Location ends in the new id,
  ETag `W/"1"`, audit entry `department.create` by the admin, row exists). Same for a type
  (`appointment_type.create`), a room, a hospital (Location site).
- `returns_200_with_new_etag_when_admin_puts_with_the_current_if_match`; per type; version
  after = before + 1, audit `*.update` names the changed fields only.
- `returns_412_when_if_match_is_stale` for each update and delete; row unchanged.
- `returns_200_and_keeps_version_when_put_changes_nothing`.
- `returns_403_when_a_clinician_or_patient_token_writes` and `returns_401_when_no_token_writes`
  for POST, PUT, DELETE of each type; no row, no audit entry.
- `returns_409_has_dependents_naming_counts_when_deleting_a_hospital_with_departments`
  ("2 departments"), a department with rooms, a room with appointments, a type with appointments;
  `failure-code` extension `has_dependents`; row remains.
- `returns_200_outcome_when_deleting_an_unused_record`; the row is gone; audit `*.delete`.
- `returns_400_naming_identifier_when_code_is_taken`; `returns_400_naming_partOf_when_the_hospital
  is_unknown`; `returns_400_naming_the_element_when_a_derived_element_differs`.
- `returns_400_when_posting_a_prov_organization`;
  `returns_405_with_allow_when_putting_or_deleting_a_hospital_organization`;
  `returns_409_has_dependents_when_deleting_a_hospital_site_with_departments`.
- `returns_the_same_fields_as_the_console_when_fhir_and_console_write_the_same_values`: one
  parity test per type comparing the stored row and the audit metadata.
- Follows-at-once, through the search use case (`search_catalog`): a hospital created or
  deactivated by FHIR appears or vanishes in hospital search; a department/clinician unaffected
  case omitted; an appointment type created `bookable_online` shows in `bookable_types`, then
  `active=false` removes it; a room with `status` inactive is not offered to `find_free_slots`
  as a room (one test per type, three types plus the room).
- CapabilityStatement test: lists create, update, delete for exactly the three types, nothing for
  Organization-less types; a method not named answers 405 (`Slot` POST).
- Domain tests for `fhir_record_write.py` (shapes, `*_values`, derived difference), mutated by
  `make mutate`.
- `test_samples.py`: the new samples exist, are named, and validate under `make fhir-validate`.

## Domain entities

Hospital, Department, Room, AppointmentType, Admin, ApiClient (token), AuditLogEntry.

## Not doing

No new rule, no new use case beside the FHIR adapter, no change to console pages or models, no
`description` element, no new dependency, no refactor of `fhir_reads.py`, no `428` without
`If-Match`.

## Not in this run

- `CodeSystem` / `ValueSet` writes (items 2 half, 3, and their halves of 4 to 7). Design: `PUT
  CodeSystem/specialty` carries the whole concept list; concepts are matched by `code`; new code =
  add (`create_record specialty`), changed `display` = rename, `property` `inactive` `valueBoolean`
  true = deactivate (`is_active` false, concept kept and flagged for admin reads), concept absent
  = remove (`delete_record`, 409 `has_dependents` while clinicians use it). One transaction, table
  locked, `versionId` is `scheduling_specialty_revision`: +1 per changed row, unchanged on a no-op;
  `If-Match` compared to it under the lock. `ValueSet` is derived: a PUT equal to the stored one
  answers 200 unchanged, any difference 400; POST and DELETE 405 for both ids.
- ADR 0008 sections for the specialty list land with that run.
- `make mutate` and `make fhir-validate` full pass confirm after both runs.

Risks: `identifier` on reads changes public output; a console-parity gap: the console form requires place fields, the use case does not, so the FHIR adapter enforces them in `site_values` (no use-case change).

## Architect review

Verdict: revise (round 1, addressed above: creating door is the site Location; `RecordEdit.version` None path gets its own test: `skips_the_version_check_when_version_is_none_but_still_locks_and_audits`; console callers always pass an int).

- **Hospital create is undecided and, as written, cannot work.** `SPECS["hospital"]` needs `street_address`, `postal_code`, `city`, `country`, `phone`, `time_zone` (non-blank model fields), and the plan gives the `Organization` prov door only `name`, `identifier`, `active`. The plan defers this to "decide on reading the console's test", which is a decision the plan must make. Choose now: either the Organization prov create body carries the place fields (address, telecom, time-zone extension) and the Location site is update-only, or the Location site is the creating door. Name the failing first test for it (`returns_201_..._when_admin_posts_a_hospital` with the full body, and a 400 naming the missing element when place fields are absent). Fix the ADR 0008 sentence to match; remove the "only if the use case accepts that" hedge.
- Slice is acceptable (organisation resources now, CodeSystem/ValueSet next) and leaves the product whole, provided the CapabilityStatement names exactly the three types and the specialty ids still answer 405 for writes. Keep that test.
- Ladder: `RecordEdit.version: int | None` is a reasonable minimal change; confirm the console path still always passes a version and add a test that None skips the check but delete/update still lock.
- Security, layering, transaction and test list are otherwise sound (admin from token user, shapes before values, use cases audit in-transaction, all roles + no token tested).
- Minor, not blocking: the "follows at once" test for rooms should go through `find_free_slots` as stated; the hostile-input and samples items are covered.

### Architect review, round 2

Verdict: approve.

- Round 1 problem fixed: the site `Location` is the one creating door, with required place fields, a named first test and a 400 per missing element. The prov `Organization` is a read-only mirror (POST 400, PUT/DELETE 405 with `Allow`). ADR sentence matches.
- Slice is coherent: three types complete (create, update, delete, 409, 412, samples, hostile input, CapabilityStatement), specialty ids stay read-only, product whole. The design for CodeSystem/ValueSet is stated under "Not in this run" for the next run.
- No `428` without `If-Match` matches ADR 0006; `RecordEdit.version: int | None` is the smallest change, console passes an int.
- Security and layering sound: admin from token user, shape then pure values then use-case checks, audit inside the transaction, every role plus no token tested.
- Non-blocking: size the run carefully (five builders, three shapes, samples); split files early at 300 lines. Fix the garbled CapabilityStatement test line ("Organization-less types") to "no other type lists a write".
