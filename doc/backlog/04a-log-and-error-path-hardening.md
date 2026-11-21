Task 04a: log and error path hardening.

Defects the orchestrator found on the running stack after task 04, and the "Later" list
of its review (`doc/reviews/2026-11-21-request-plumbing.md`). No new feature.

1. Logs leak raw paths. On the running stack a request to
   `/api/v1/patients/jane@example.test?token=x` prints the plain-text line
   `Not Found: /api/v1/patients/jane@example.test` next to the JSON request line. The
   `django.request` logger is configured with no handler and no propagation, so Python's
   last-resort handler prints its warnings, raw path included. Paths will carry
   identifiers and sign-in tokens. No line with a raw path or a query string may be
   written, by any logger.
2. Not every line is JSON. Besides the line of item 1, `django.server` writes
   `{"message": "\"%s\" %s %s"}` once per request: noise that says nothing. Every line
   the process writes is one JSON object that carries information, and the request is
   logged once.
3. The tests of task 04 exercised the formatter and missed both. Add a test at the level
   of the process: run requests through the real logging configuration, capture
   everything written to standard output and standard error, and assert that each line
   parses as JSON and that no line holds the path segment, the query string or the email
   address that were sent. Show it failing first.
4. An unexpected error outside the API views (a server-rendered page, a middleware) gets
   no correlation id header and no log line with its trace. It must get both, and answer
   with a generic error whatever `DEBUG` says about the body for API paths. Server-rendered
   pages arrive with task 05; make the path right now and test it with a failing plain
   Django view.
5. Unknown fields are rejected at every depth: today a nested request schema drops an
   unknown key in silence (review finding 3).
6. `scripts/ensure_database.py`: a non-numeric `DB_PORT` names the variable instead of
   raising a bare `ValueError`.

Done when `make setup && make lint && make test && make gate` pass from a fresh clone.
The orchestrator repeats the leak check on the running stack.
