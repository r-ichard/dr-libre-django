Task 26a2: abuse limits, as the real server and a real visitor meet them.

Runs on the branch of task 26a (`task/26a-security-abuse-limits`), which is verified and
held, not merged: its gates pass from a fresh clone, and in the container stack the
lockout race, the cache headers, the search limit and the booking code page hold. The
orchestrator found the defects below with curl and a browser against that stack. This
task changes what 26a added and nothing else. Reproduce each defect with a failing test
before the fix.

What the server hands over:

1. Every write of `/api/v1` that has no body and no `Content-Type` header answers 400,
   "The request body is not readable", under the server the product runs on:
   `auth/logout`, the `check-in`, `complete` and `no-show` of an appointment, the
   `accept` and `offer` of a waitlist entry, the `resend` of a hold, `jobs/reminders`.
   `curl -X POST` sends exactly that request, and before 26a each of them answered.
   `refuse_non_json_write` lets "no type and no body" pass, as its docstring says, but
   `wsgiref` under `runserver` fills `CONTENT_TYPE` with `text/plain` when the header is
   absent. The test client does not, so every test passes. Decide by what a body can
   carry: a write without a body passes whatever its type says; a write with a body
   says it is JSON or is refused before the body is read. For every write route of
   `/api/v1` in the URL configuration, taken from the URL configuration so a new route
   is covered, a request without a body and with `CONTENT_TYPE` `text/plain` is never
   answered with the unreadable-body refusal: a route that needs fields names the
   fields, a route that needs none does its work.
2. One test sends a write without a body over a socket to the product's own server
   class (pytest-django's `live_server`) and one sends a `text/plain` body the same way,
   so the next difference between the test client and the server is seen by a test and
   not by curl (`CLAUDE.md`, "API routes").

What a limited visitor sees:

3. The start page is the search page. A limited address gets a separate 429 page for
   `/`, with or without a query, and that page's only link, "Go to the start page",
   leads to the same 429: a dead end, and the header with the sign-in link is the only
   way on. A limited search answers the search page itself with status 429: header,
   form and footer as always, the message where the results would be. Invariant, as a
   test: every link and form target on the page a limited visitor gets answers below
   400 for that visitor, apart from the search itself.
4. No 429 of the product says when to come back; the page says "in an hour" whenever
   the oldest hit leaves the window. Every 429 the rate limits answer (hold, code,
   link, token, search; `/api/v1`, `/fhir` and the pages) carries `Retry-After` in
   seconds until the caller's next request would pass, from the clock of the request
   context, and the page's sentence agrees with it. The calculation is pure and lives
   in `scheduling/domain/rate_limit_rules.py`, under the mutation gate.

From the review of 26a (`doc/reviews/2026-11-22-security-hardening-26a.md`):

5. Task 26 item 3a asked to show for each counter that it is serialised. The sign-in
   counter has its race test; add the same for the hold counter (five an hour for one
   email address) and the resend counter (three an hour), with parallel transactions,
   in the style of `test_sign_in_race.py`.
6. `drlibre_hold` is one cookie name: a second hold in the same browser makes the first
   tab's code page answer "Booking not completed" although its code arrived by email.
   A visitor who books two appointments in two tabs completes both: the cookie proves
   every hold its browser made that has not expired, stays `HttpOnly`, and stays
   bounded in size. Test both tabs, and that another browser still gets the page a
   missing hold gets for each.
7. `ResendPage.post` reads the hold before it checks the cookie. The cookie check comes
   first, as on the code page.

Not in this task: start-up checks, cookie flags, the trusted proxy and a rate limit for
the public detail pages and the anonymous FHIR searches (26b).

The orchestrator signs out, checks in and resends with `curl -X POST` and no header;
runs 121 searches and follows every link of the page that answers; holds two slots in
two tabs of one browser and completes both.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
