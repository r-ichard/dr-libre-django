# ADR 0008: FHIR admin writes for the organisation resources

Status: accepted, 2026-11-22. Builds on ADR 0006 (write rules) and ADR 0005. Covers `Organization`,
`Location` and `HealthcareService`. `CodeSystem` and `ValueSet` writes follow in the next run.

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
