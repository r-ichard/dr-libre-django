Task 26b3: access, proven as data.

Item 10 of the security review (`doc/backlog/26-security-hardening.md`), left by the
first run of task 26b. Tests and one document; no product behaviour changes. A route
that answers differently from what the specification says is a finding: name it in the
review under "For the owner" with the section, and write the table as the specification
has it so the test fails on it.

1. One table in the tests lists every route of the URL configuration, `/fhir` included
   (each resource type and interaction of the declaration), with who may use it:
   visitor, patient, clinician, admin, and a token of each role; and what each of the
   others gets (401, 403, 404, a redirect to the sign-in page), by sections 11 and 12
   of the specification. The table is data, split over files that stay under the size
   cap, in an order a person can read.
2. A route of the URL configuration that is missing from the table fails the test, and
   so does a row for a route that no longer exists.
3. One test walks the table: each caller sends each route's request as that route's
   real client sends it (`CLAUDE.md`, "API routes" and "Page forms") and gets the
   answer of its row. For a route that names a record, the caller is tried against the
   own record and against another user's: the second never tells whether the record
   exists.
4. `doc/security-review.md` gains the access section, generated from the table by a
   command of the Makefile, and a test fails when the document and the table differ.
5. Keep the suite's time in view: say in the plan how many requests the walk sends and
   what it costs, and share sessions and tokens across rows.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
