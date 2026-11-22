Task 27d2: the FHIR API, what a write must declare, what a refusal says, and sorting
by time.

The rest of task 27d (`doc/backlog/27d-qa-round-3-fhir.md`, items 4 to 6; its first run
took the searches, items 1 to 3), on the conventions of tasks 22 to 24d (ADR 0005 to
0009). Findings: `doc/qa/2026-11-22-round-3.md`, "Area: the FHIR API" (#52 and the ones
not filed). Reproduce each with a failing test before the fix.

What a write must declare:

1. #52 (P2). A FHIR write with `Content-Type: text/plain` is parsed as JSON and books.
   A write that carries a body says `application/fhir+json` or `application/json`, or
   is refused with 415 and an `OperationOutcome` before the body is read.
2. Carried from task 26a2, still on `main`: under the server the product runs on, a
   request without a `Content-Length` header reaches the application with
   `CONTENT_LENGTH` set to the empty string (`wsgiref` puts it in the base environment),
   which `refuse_non_json_write` reads as a malformed body. `curl -X POST` without `-d`
   on `/api/v1/auth/logout`, `check-in`, `no-show` or `jobs/reminders` answers 400; with
   `Content-Length: 0` it passes. A request without `Content-Length` and without
   `Transfer-Encoding` has no body (RFC 9112, section 6.3). One rule decides "does this
   write carry a body, and does it say JSON" for `/api/v1` and `/fhir`. The live-server
   test of 26a2 used `urllib`, which adds `Content-Length: 0`: send the bytes over a
   socket, exactly a request line, `Host` and the credentials, for one write of each
   API, and for a `text/plain` body of each.

What a refusal says:

3. Every 400 under `/fhir` says "The request is not valid." and names an element. Each
   issue carries the message `/api/v1` gives for the same refusal (section 4:
   `invalid_input` has a message for each field), so a client can tell what to fix. The
   first run started this (`_with_messages` in `scheduling/domain/fhir_outcome.py`):
   finish it for every write and every search refusal, and show it with one test over
   the declaration: no 400 of `/fhir` is without a message of its own.
4. Section 15.6 says "Reschedule: update the appointment's start": a client that reads
   an appointment, changes `start` and puts it back is refused for `Appointment.end`.
   The end is never taken from the client (5.2): an `end` equal to the stored one or to
   the one the new start gives is accepted, any other is refused and says so.

Sorting and lists:

5. `_sort` is refused on every parameter but `name`, `address-city` and `active`
   (ADR 0005 narrowed section 15.1). Serve it, both directions, on every date parameter
   of the declaration, and let each type's entry in the CapabilityStatement say which
   values it takes. The paging test of task 23a follows `next` to the end under each
   new sort.
6. From the review of the first run: a comma splits a text and a reference value too,
   and FHIR's escape (`\,`, `\\`) is not read, so `name=Smith\, John` cannot be asked.
   Read the escape in the one splitter.

The specification is the owner's text:

7. The first run edited `drlibre-specs.md` (the `type` parameter in the table of 15.5
   and a paragraph on search values) so that the test over the tables of section 15
   would pass. Put the file back as it was on `917edd1`. The test reads what the
   decision records add to section 15 from a list beside the tables, each entry naming
   its ADR, and still fails on anything served that neither the specification nor that
   list names. What this task decides goes into the ADR and into the review under
   "For the owner", never into the specification.

The orchestrator books with `text/plain`, signs out with `curl -X POST` and nothing
else, reschedules by changing only `start`, and lists a week of appointments sorted by
time in both directions.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
