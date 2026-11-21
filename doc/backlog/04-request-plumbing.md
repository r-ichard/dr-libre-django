Task 04: request plumbing: failure contract, correlation id, structured logs, clock.

The parts of `drlibre-specs.md` section 4 that every later feature leans on. No feature
endpoint: the health endpoint and test-only views are the consumers. The audit writer and
the security headers are task 04a.

1. Failure contract. One result type for use cases: a success value, or an expected
   failure carrying one of the ten codes of the section 4 table with its details (field
   messages, resources in conflict, current status, dependents, violated rules). Expected
   failures are values, never exceptions (§9). One mapper turns a failure into the HTTP
   status of the table and into one JSON body shape, the same for every endpoint. State
   the shape in the plan and record it in an ADR: the screens and the FHIR
   `OperationOutcome` mapper will both read it.
2. Everything else an API request can hit answers in the same shape: unknown path, wrong
   method, unreadable body, failed validation, missing access rule. An unexpected error
   answers 500 with a generic message and the correlation id, never a stack trace or an
   internal name, whatever `DEBUG` says, and is logged with its trace.
3. Unknown fields are rejected on writes (section 4): a base for request schemas that
   answers `invalid_input` naming the unknown field. Boundary types are derived from the
   schema (§7).
4. Correlation id. Taken from the `x-correlation-id` request header when it is sane
   (bounded length and character set), generated otherwise. Returned on every response,
   errors and unknown paths included. Reachable by use cases through the request context,
   and present on every log line of the request.
5. Structured logs: one JSON object per line with time, level, logger, message and
   correlation id, and one line per request with method, matched route pattern, status
   and duration. Log the route pattern, never the raw path or the query string: both
   will carry identifiers and tokens. Keep sensitive data out by construction (say how in
   the plan) and prove it with an email address, a token and a clinical note.
6. Clock. Use cases never read the system clock (§8). One instant per request, taken when
   the request starts, reachable through the request context and replaceable in tests.
7. Closed by default. An API view that does not declare who may call it refuses the
   request; the health endpoint declares itself public. Test it with a view that declares
   nothing.

Layers as recorded in `CLAUDE.md`: domain (pure, no I/O), use cases, views. Put each
piece where its rule belongs and say where in the plan.

Done when `make setup && make lint && make test && make gate` pass from a fresh clone.
