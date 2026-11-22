Task 24b: FHIR API, admin writes for the organisation resources.

`drlibre-specs.md` section 15.4, "Create, update, delete: Admin", for `Organization`,
`Location`, `HealthcareService`, `CodeSystem` and `ValueSet`, on the write rules of ADR
0006 (body checked against the declared shape, one failure table, `If-Match`, 201 with
`Location` and `ETag`) and through the use cases of the admin console (task 18:
`scheduling/use_cases/admin_records.py`). A FHIR write does exactly what the console
does: the same field checks, the same refusals, the same audit entry, the same version.
This task adds no rule.

1. `POST`, `PUT` and `DELETE` with an admin's token; any other token and no token are
   refused as the failure table says. Test every write with each role's token and with
   none, as a FHIR client sends it (bearer token, no cookie, no `Origin`).
2. A hospital is one record and two resources. Say in the ADR which of the two a client
   writes (`Organization` of type `prov`, or the `Location` of the site), what the other
   answers to a write, and how the fields of the hospital divide between them. A
   department is an `Organization` of type `dept`; a room a `Location`; an appointment
   type a `HealthcareService` with its extensions.
3. The specialty list is one `CodeSystem` and one `ValueSet` (ADR 0003, 0005). Say how a
   client adds, renames, deactivates and removes one specialty, and what `versionId`
   does after each.
4. A delete that something still depends on answers 409 with `has_dependents` and what
   still uses the record, as the console's delete page says it.
5. `If-Match` on every update and delete: a stale version is 412; the answer to an
   update carries the new `ETag`.
6. What the public search and the booking pages offer follows a FHIR write at once: one
   test per resource type, through the search use case.
7. Every write has its samples in `make fhir-validate` (the request body and the
   answer), joins the hostile-input test, and is named in the CapabilityStatement;
   nothing the statement does not name answers.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
