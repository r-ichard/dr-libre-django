Task 22: FHIR API, conventions, tokens and the public resources.

`drlibre-specs.md` sections 15.1, 15.2, 15.4 and 15.5, for the seven resources anyone may
read: `Organization`, `Location`, `HealthcareService`, `CodeSystem`, `ValueSet`,
`Practitioner`, `PractitionerRole`. Read and search only. `Schedule`, `Slot`, `Patient`
and `Appointment` are task 23; every FHIR write, `AppointmentResponse`, `Communication`
and `AuditEvent` are tasks 23 and 24. ADR 0003 already decided versions and ids: read it
first. The FHIR API is another door to the same product (15.1): it reads through the use
cases and visibility rules the application API has, never through a second copy of them.

Conventions:

1. FHIR R4 (4.0.1), JSON, base path `/fhir`, `Content-Type: application/fhir+json`. Say
   in the plan which `Accept` values are served and what the others get.
2. Under `/fhir` every failure is an `OperationOutcome` with the status of section 4:
   an unknown resource type, an unknown id, a method not allowed, a refused parameter,
   the input limits of ADR 0004, a bad token, and an unexpected error (500 with the
   correlation id and nothing of the internals). Never the application API's error body
   and never an HTML page. Every response carries the correlation id.
3. `GET /fhir/<Type>/<id>` reads one resource; `GET /fhir/<Type>` searches and answers a
   `searchset` Bundle with `total` and `self`, `next` and `previous` links. `_count` sets
   the page size (default 20, at most 100); `_sort` works on the parameters of 15.5. A
   parameter the resource does not have, or a value it cannot read, is refused with 400
   and named: a search never silently returns more than was asked for.
4. Each resource keeps the product's id and carries `meta.versionId` and
   `meta.lastUpdated` as ADR 0003 defines them, and a read answers a weak `ETag` of the
   version. A hospital is two resources, an `Organization` and a `Location`.
5. `GET /fhir/metadata` answers a CapabilityStatement built from the same declaration
   that routes the resources, their interactions and their search parameters, so it
   cannot name what is not served. Test both directions: everything declared answers,
   everything that answers is declared.

Mapping:

6. One pure function per resource in the domain layer, under the mutation gate, with the
   table of 15.2 as its tests: Organization (type `prov`, and `dept` with `partOf`),
   Location (the hospital site with address, phone, position and time zone; a room with
   physical type, `partOf`, managing organization, and floor, capacity and equipment as
   extensions), HealthcareService (duration, buffer, colour, needs-room and
   online-bookable as extensions), CodeSystem and ValueSet for the specialties,
   Practitioner, PractitionerRole (department, specialty, default room, bio, round robin
   weight as an extension, `availableTime` mirrored from the availability rules).
7. Decide the canonical URLs (extensions, the specialty code system, the value set) once
   and record them, with the other conventions of this task, in
   `doc/adr/0005-fhir-conventions.md`.
8. Prove the JSON is valid FHIR R4 with a tool, not by eye: a pinned development
   dependency that validates R4 resources, or the published R4 definitions vendored for
   the tests. Say which in the plan and why. Every resource and the Bundle go through it.

Access (15.4):

9. Without a token: active records only, and for a clinician only the public fields
   (name and title; never email, phone or birth date). Section 6.1 hides a clinician who
   has no appointment type patients may book online, and task 17b made such a type
   invisible to a caller without a session. Section 15.4 says "active clinicians". Take
   the stricter reading, through the same visibility rule the application API uses: what
   the public search and `GET /api/v1/slots` hide, `/fhir` hides. State it in the ADR as
   an open point for the owner.
10. With a token of a clinician or an admin: every record, inactive ones too, and a
    clinician's email and phone. With a patient's token: what a caller without a token
    gets.
11. Search parameters as in 15.5 for the seven resources, `near` for `Location`
    included, and `_include` for `PractitionerRole:practitioner` and
    `PractitionerRole:organization`. A search page costs a bounded number of queries
    whatever the number of rows: assert it.

Tokens:

12. `ApiClient` (domain vocabulary): a name, the one user whose rights it gives, the hash
    of its token, when it was made, last used and revoked. Only the hash is stored, as
    for sessions. `Authorization: Bearer <token>` gives exactly that user's rights.
13. A token that is unknown or revoked, or whose user is inactive, answers 401. It never
    falls back to the answer a caller without a token would get. A token is never read
    from the address. `/fhir` never authenticates by the session cookie. Failed attempts
    are limited with the mechanism of task 12; say the numbers in the plan.
14. Tokens are issued, listed and revoked by a management command, each step audited
    with ids only; the token is shown once, when issued, and appears in no log, audit
    entry or later output. Prove it with a planted token. An admin page for tokens is
    not in the specification: leave it out and say so in the ADR.

Everywhere:

15. The new model comes with its migration, its place in `doc/data-model.md`
    (`fhir_not_exposed`: a credential) and the tests of ADR 0002.
16. Every new route joins the hostile-input test (`scheduling/views/test_hostile_input.py`);
    under `/fhir` no answer is 500 and every failure is an `OperationOutcome`. Every
    audit action this task adds has its plain words in `scheduling/domain/audit_labels.py`.
17. Tasks 19 to 21 (admin console) run beside this one. Keep out of their files:
    `scheduling/views/pages/`, `scheduling/templates/`, `scheduling/use_cases/admin_*`.

The orchestrator reads and searches each resource with curl, with no token and with the
token of each role, follows the paging links to the end, and checks a hidden clinician
and an inactive hospital from both sides.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone, and `make test` stays under 40 seconds on a machine that runs nothing else.
