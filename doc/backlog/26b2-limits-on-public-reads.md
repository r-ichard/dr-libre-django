Task 26b2: a limit on every public read that costs work, and what 26b left small.

The rest of task 26b's item 3a and the "Later" list of its review
(`doc/reviews/2026-11-22-security-settings-logs-26b.md`). The mechanism exists: the rate
limits of task 12, the search limit of task 26a (`search_limited.py`, `Retry-After`, the
limited page), the caller's address of task 26b (`network_address`). Reproduce each
point with a failing test before the fix.

1. The public detail pages (`/providers/<id>`, `/hospitals/<id>`, `/specialties/<id>`),
   their `/api/v1` twins, `/api/v1/slots`, the booking pages that list free times
   (`/book/...`) and a `/fhir` search without a token compute schedules for anyone, with
   no limit. Give them the mechanism of the search. Say in the plan which routes share
   a counter and why, and the number for each: a person who walks from the search to a
   provider and through four weeks of times must never meet it. A limited page keeps
   its header, its footer and a way on; a limited `/fhir` answer is an
   `OperationOutcome`; each carries `Retry-After`.
2. A caller with a session or a valid token is not counted against the public limit of
   its address: a clinic's staff behind one address must not lock each other out. Say
   in the plan what limits a signed-in caller instead, or that nothing does and why
   that is safe.
3. One test takes every route of the URL configuration that answers without a session
   or token and fails when one of them has neither a limit nor an entry in a short list
   of routes that cost nothing (health, static pages), each with its reason.
4. `TRUSTED_PROXY_COUNT` accepts a negative number and treats it as 0: refuse it at
   start-up, naming the variable.
5. The start-up check reads `DEMO_PASSWORD` from `os.environ`; every other setting goes
   through `drlibre/environment.py`. One way.
6. The README says what start-up refuses with `DEBUG` off and which variables a person
   sets to run that way locally, and what `TRUSTED_PROXY_COUNT` means.
7. The log privacy test plants no password: add one sign-in by password with a planted
   password and assert it appears in no log line.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
