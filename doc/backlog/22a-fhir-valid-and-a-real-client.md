Task 22a: FHIR API, valid resources and a real client.

Hardening of task 22 (`doc/backlog/22-fhir-conventions-tokens-public-resources.md`, ADR
0005) before task 23 builds writes on it. Everything below was found by the orchestrator
on the running stack with curl and the official HL7 validator
(`validator_cli.jar -version 4.0.1 -tx n/a`), or by the reviewer of task 22. Reproduce
each with a failing test before the fix.

Valid FHIR, proven:

1. Task 22 was asked to prove its JSON valid with a tool and did not (ADR 0005, last open
   point). The validator finds five errors in what `/fhir` serves today:
   - `PractitionerRole.healthcareService` is `[]` for a clinician with no service to
     list (staff view): "Array cannot be empty".
   - `CapabilityStatement.rest.resource.searchParam` is `[]` for `CodeSystem` and
     `ValueSet`: the same.
   - `CapabilityStatement`: cpb-2 ("SHALL have at least one of description, software, or
     implementation") and cpb-14 ("If kind = instance, implementation must be present").
   Rule: no resource ever carries an empty array, object or string, or a null; one
   function in the domain layer removes them for every mapper, under the mutation gate.
2. `make fhir-validate`: writes one sample of everything `/fhir` can answer into a
   directory (each resource type as the public and as the staff view, a search Bundle
   with and without `_include`, the CapabilityStatement, an OperationOutcome), from the
   demo seed, and runs the HL7 validator over it. It fails on any error; warnings are
   printed. The validator's version and checksum are pinned; it and a Java runtime are
   fetched when the target runs, not by `make setup`. It is not part of `make test`. Say
   in the plan how long it takes in the sandbox.
3. In `make test`, a cheap guard for the same rule: every sample of point 2 is walked and
   fails on an empty array, object or string, or a null.
4. A staff token that can read a `HealthcareService` gets it referenced from the
   `PractitionerRole` of the same answer (ADR 0005, open point "Inactive references").
   One viewer, one set of visible services.

A real client:

5. `POST`, `PUT`, `PATCH` and `DELETE` under `/fhir` answer `403 text/html`: Django's
   cross-site check page, because the request has no token for it. A FHIR client is a
   server: it sends a bearer token, no cookie and no `Origin`. `/fhir` never reads a
   cookie (ADR 0005), so the cross-site check has nothing to protect there. Rule: every
   answer under `/fhir` is FHIR JSON, for every method and every header a client can
   send. A known resource type with an interaction it does not have answers 405 with
   `Allow` and an `OperationOutcome` (finding 4 of the review).
6. The tests did not see point 5 because the test client skips the cross-site check.
   Every test of an API route, `/fhir` and `/api/v1`, uses a client that enforces it and
   sends what the route's real client sends: a browser sends `Origin` and the cookie, a
   FHIR client neither. Change the shared helpers so a new test gets this by default,
   and make the hostile-input test assert, under `/fhir`, the content type as well as
   the status.
7. `_include=PractitionerRole:practitioner&_include=PractitionerRole:organization`
   answers 400, because a repeated parameter is refused. Repeating `_include` is how a
   client asks for both. Accept it; say in the ADR which other parameters may repeat and
   what a repeat means.

Answers that depend on who asks:

8. The same address answers differently with and without a token and no header says so.
   Every `/fhir` answer carries `Vary: Authorization`; an answer to a request with a
   token is never stored (`Cache-Control: no-store`).
9. Review findings 2 and 3: the counter of failed attempts for an address is checked
   before the token is looked up, so 20 bad tokens from a shared address lock out every
   valid client behind it; and the counter is not under the advisory lock the other
   scopes use. A valid token is never refused because of someone else's failures.
10. Review finding 6: a search loads every matching id and cuts the page in Python. Count
    and cut in the database.

Update ADR 0005 for every decision above and remove the open points this task closes.

Tasks 19 to 21 (admin console) run beside this one. Keep out of their files:
`scheduling/views/pages/`, `scheduling/templates/`, `scheduling/use_cases/admin_*`.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone, and `make test` stays under 40 seconds on a
machine that runs nothing else.
