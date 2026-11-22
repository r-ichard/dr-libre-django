Task 27d: QA round 3, the FHIR API: searches that answer the wrong set, and what a
write must declare.

Findings of the FHIR area of QA round 3 (`doc/qa/2026-11-22-round-3.md`, "Area: the FHIR
API": #50, #51, #52 and the four not filed), on the conventions of tasks 22 to 24d (ADR
0005 to 0009): one declaration, pure rules in the domain layer under the mutation gate,
every answer FHIR JSON, `make fhir-validate` over every new view. Reproduce each finding
with a failing test before the fix. If the whole does not fit one run, the slice is
items 1 to 3, in that order.

A search never answers a wrong set:

1. #51 (P1). A date search leaves out what it should find. The orchestrator saw, with
   eight booked appointments of which two start on 2026-11-24 (09:00Z and 23:00Z) and
   two on 2026-11-23 (12:00Z and 21:00Z): `Appointment?status=booked&date=2026-11-24`
   answers 0; `date=eq2026-11-23` 0; `date=le2026-11-23T23:59:59Z` 0;
   `date=lt2026-11-24T00:00:00Z` 0 while `date=lt2026-11-24T12:00:00Z` finds the two of
   the 23rd; `date=ge2026-11-23&date=lt2026-11-24` 0. A client that reads a calendar day
   by day sees empty days. `Communication?sent=lt…` and `AuditEvent?date=lt…` fail the
   same way. Find the cause and say in the plan why neither the tests nor the mutation
   gate saw it. Then, for every date parameter of the declaration (`Appointment.date`,
   `Communication.sent`, `AuditEvent.date`, `Slot.start`, `Schedule.date`,
   `Patient.birthdate`): each prefix FHIR R4 defines for a date is served by its
   definition or refused with 400, and the ADR lists which; a value of day precision is
   that whole day, in a zone the ADR names. Tests as a table whose expected ids are
   written by hand, not computed by the code under test: records one second before a
   bound, on it, one second after, twelve hours before and a day before; each prefix;
   day precision, a second with `Z`, a second with an offset. And as properties: for any
   bound, `lt` and `ge` split the whole set; `ge` a day with `lt` the next day equals
   `eq` that day.
2. #50 (P1). A NUL byte in a string search parameter answers 500, without a token, on
   thirteen parameters. No value of a search parameter reaches the database with a
   character it cannot carry: one rule, 400 with the parameter named. The hostile-input
   test takes every type and every search parameter from the declaration, so a new
   parameter is covered, and none answers 500.
3. A comma list (`status=booked,cancelled`, `type=prov,dept`) is read as one value and
   answers an empty set; `AuditEvent?action=C` answers an empty set although the
   resources carry that code. FHIR R4 reads a comma as "either". For a parameter with a
   closed list of codes: a comma list finds either, and a value outside the list is 400
   with the list, never an empty set. What a resource shows under an element is what
   its parameter finds: `action=C` finds the events that show `C`; say in ADR 0009 how
   the product's action stays searchable.

What a write must declare:

4. #52 (P2), and carried from task 26a2. A FHIR write with `Content-Type: text/plain`
   is parsed as JSON and books. A write that carries a body says `application/fhir+json`
   or `application/json`, or is refused with 415 and an `OperationOutcome` before the
   body is read. And for `/api/v1`: under the server the product runs on, a request
   without a `Content-Length` header reaches the application with `CONTENT_LENGTH` set
   to the empty string (`wsgiref` puts it in the base environment), which
   `refuse_non_json_write` reads as a malformed body. `curl -X POST` without `-d` on
   `auth/logout`, `check-in`, `no-show` or `jobs/reminders` still answers 400 on `main`;
   with `Content-Length: 0` it passes. A request without `Content-Length` and without
   `Transfer-Encoding` has no body (RFC 9112, section 6.3). One rule decides "does this
   write carry a body, and does it say JSON" for both APIs. The live-server test of 26a2
   used `urllib`, which adds `Content-Length: 0`: send the bytes over a socket, exactly
   a request line, `Host` and the cookie, for one write of each API.

What a refusal says:

5. Every 400 under `/fhir` says "The request is not valid." and names an element. Each
   issue carries the message `/api/v1` gives for the same refusal (section 4:
   `invalid_input` has a message for each field), so a client can tell what to fix.
   Section 15.6 says "Reschedule: update the appointment's start": a client that reads
   an appointment, changes `start` and puts it back is refused for `Appointment.end`.
   The end is never taken from the client (5.2): an `end` equal to the stored one or to
   the one the new start gives is accepted, any other is refused and says so.
6. `_sort` is refused on every parameter but `name`, `address-city` and `active`
   (ADR 0005 narrowed section 15.1). Serve it, both directions, on every date parameter
   of the declaration, and let each type's entry in the CapabilityStatement say which
   values it takes.

Not in this task: the HTML page the development server answers for an over-long address
or header (414, 431), which belongs to the security review document (26d).

The orchestrator reads a week of appointments day by day through `/fhir` and compares
it with the database; sends a NUL byte in every string parameter; books with
`text/plain`; and signs out with `curl -X POST` and nothing else.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
