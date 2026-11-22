# ADR 0008: FHIR admin writes for the organisation resources

Status: accepted, 2026-11-22. Builds on ADR 0006 (write rules) and ADR 0005. Covers `Organization`,
`Location`, `HealthcareService` and, in task 24b2, the specialty list (`CodeSystem`, `ValueSet`).

## Decisions

- **Admin only, through the console's use cases.** `POST`, `PUT` and `DELETE` call `create_record`,
  `update_record` and `delete_record` of `admin_records`: same field checks, refusals, audit entry
  and version. A caller who is not an admin is 403 (answered before the body is read), no token 401.
- **A hospital is one record and two resources; a client writes the `Location` of the site**
  (`physicalType` `si`). The place fields (address, phone, position, time zone) exist only there, and
  the console needs them to create a hospital, so each of address line, city, postal code, country,
  phone and the `hospital-time-zone` extension is required; a missing one is 400 naming the element.
  Its `Organization` (type `prov`) is the read-only view: `POST` with that type is 400 naming
  `Organization.type`; `PUT` and `DELETE` on a hospital's id are 405 with `Allow: GET`. The
  Organization shows name, identifier and active; the Location carries those and the place fields.
  `description` has no FHIR element and a write never touches it.
- **Department** is an `Organization` of type `dept` (`name`, `identifier`, `partOf` the hospital);
  **room** a `Location` of type `ro` (`managingOrganization` the department, `room-floor`,
  `room-capacity`, `room-equipment` extensions); **appointment type** a `HealthcareService`
  (`providedBy` the department, the five `service-*` extensions).
- **Code.** Every record has a unique `code`. Reads now carry it as `identifier` (system
  `<base>/identifier/code`); a write sends it back. A taken code is 400 naming `identifier`.
- **Derived elements** (`managingOrganization` of a site, `partOf` of a room, `specialty` of a
  service) round-trip but may not differ from what the server builds: 400, named. A `type` on a
  service is its name again and is ignored.
- **`If-Match`.** Optional, as in ADR 0006. A stale version is 412 on update (checked under the
  record's lock) and delete; a no-op `PUT` answers 200 and leaves version and audit untouched.
- **`has_dependents`.** A delete something still uses is 409; the `failure-code` extension says
  `has_dependents` and `issue.diagnostics` adds the console's counts ("Still used by: 2
  departments."). Counts and fixed words only.
- **Follows at once.** The writes change the same rows the search and booking use cases read.

## The specialty list (task 24b2)

- **A client writes the `CodeSystem` with id `specialty`, by `PUT`, and the body is the whole list.**
  The list is one resource with one version (ADR 0003), so the body is what the list should become:
  a stored specialty the body omits is removed. No `POST` (one fixed id), no `DELETE`; a `PUT` to
  another id is 404. Admin only, 403 before the body is read, no token 401.
- **Matching:** a concept matches a specialty by `code`, ignoring case (`caseSensitive` is false,
  the table's unique index is on `lower(code)`). Absent from the list = add, differing `display` =
  rename, differing `inactive` = (de)activate, omitted = remove. Changing a code is therefore a
  remove plus an add, and answers 409 while clinicians use the old one. Two concepts with the same
  code ignoring case are 400 naming `CodeSystem.concept[i].code`.
- **Inactive in FHIR R4:** the CodeSystem declares a `property` `inactive` (uri
  `http://hl7.org/fhir/concept-properties#inactive`, type `boolean`); a concept says
  `property: [{code: "inactive", valueBoolean: true}]`, an active one sends none or `false`.
  `url`, `name`, `status`, `content`, `caseSensitive`, `property` and `count` round-trip and must
  equal what the server builds, else 400 naming the element.
- **Reads for an admin list inactive concepts** (flagged, counted), so GET then PUT does not delete
  them. Public reads stay active only (spec 15.4); the `versionId` is the same.
- **A write without `If-Match` replaces the list**: a partial body removes what it omits (ADR 0006
  has no 428). The removal is audited and blocked while clinicians use it.
- **`ValueSet` is the read-only view of the same list.** Its interactions stay read and search;
  `PUT`, `POST` and `DELETE` answer 405 with `Allow: GET`. Its `versionId` moves with the list. Both
  resources therefore share one ETag series but only the CodeSystem accepts a body.
- **Writes go through the console's use cases** (`create_record`, `update_record`,
  `delete_record` for `specialty`): same checks, same audit entry per changed specialty, inside one
  transaction. The steps run removals, edits, adds, so a code a removal frees can be reused in the
  same body. The first refusal rolls back every earlier step and its audit entries; a console
  field error is renamed to the element of the client's body.
- **Removal with clinicians:** 409, `failure-code` `has_dependents`, the console's counts in
  `issue.diagnostics`; nothing of the request is applied.
- **Version and `If-Match`:** the revision trigger fires once per changed row, so a request that
  changes n specialties moves the version by n and one that changes nothing leaves it (200, no
  audit). A stale `If-Match` is 412, checked under the list lock. Two admins at once: the second
  waits, then sees the new version, so it is 412 with `If-Match`; without, its diff runs on the
  committed rows and the list ends as exactly what it sent, never a mix.
- **Follows at once:** the public search reads the same rows: a new specialty shows with the
  fallback icon, a rename shows, a deactivated one is gone.
