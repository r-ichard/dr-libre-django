Task 26: security review and hardening.

Every open point the build left for the security review (`doc/backlog.md`, "Carried
items", marked task 26), closed in code or decided in writing. The product is local
only, in containers (owner decision): a fix makes the local product safe to use and safe
to grow, and adds no deployment machinery nobody asked for. Reproduce each defect with a
failing test before the fix. No new dependency without its reason in the plan.

Start-up and settings:

1. Start-up refuses to run with `DEBUG` off and the development `SECRET_KEY`, an empty
   `ALLOWED_HOSTS`, or the published `DEMO_PASSWORD` set. One check, one message that
   names the variable; test each.
2. With `DEBUG` off every cookie the product sets (session, cross-site token, notice) is
   `Secure`, `HttpOnly` where a script never needs it, and `SameSite`; list them in the
   plan with their flags and assert them in one test over a signed-in and a signed-out
   request.
3. Behind a proxy that ends TLS the product must know the scheme and the caller's
   address: `SECURE_PROXY_SSL_HEADER` and the network address used for rate limits come
   from one setting that says how many proxies are trusted, default none. A forwarded
   header from an untrusted caller changes nothing: test it.

Abuse:

3a. #46 (QA round 3, `doc/qa/2026-11-22-round-3.md`): the sign-in lockout is bypassed
   by requests in parallel. One hundred wrong passwords for one address, fifty at a
   time, had 23 to 29 evaluated before the lockout answered; specification 12.1 allows
   ten in fifteen minutes. The count is read and the failure written without
   serialising per address. At most ten wrong passwords are evaluated per window,
   however the requests arrive: test it with parallel transactions, as the booking
   races are tested. The same for the other counters of the product (booking codes,
   sign-in links, bearer tokens): show for each that it is serialised, or fix it.
3b. #47: answers of `/api/v1` to a signed-in caller carry no `Cache-Control` and no
   `Vary: Cookie`. An answer that depends on who asks is never stored and says what it
   varies on, as `/fhir` does since task 22a.
3c. #48: state-changing routes of `/api/v1` accept a `text/plain` body. A browser can
   send that across sites without a preflight. Refuse any content type but JSON on a
   write, before the body is read.
4. A locked address writes one `auth.lockout` audit entry per attempt, so an attacker
   can flood the append-only log. Audit the crossing of the threshold once per window.
5. The public search loads the whole catalogue and 90 days of schedules for each request
   and has no limit. Give it the rate limit mechanism of task 12, and a bounded number
   of queries whatever the size of the catalogue: assert the number.
6. The booking code page is addressed by the hold's id and shows a masked email address
   to whoever has the address. Bind it to the browser that made the hold; another
   browser gets the page a missing hold gets.
7. `scheduling/domain/user_rules.py` accepts `a@b` as an email address; the sign-in page
   and the booking form refuse it. One rule for an email address, in one place.

Logs and errors:

8. `background_mail._send` logs a failed send without its trace. Log the error type and
   trace with the correlation id, and never the recipient or the body: prove with a
   planted address.
9. A test reads every log line the suite produces for one booking, one sign-in by link,
   one admin user edit and one FHIR patient read, and fails on an email address, a phone
   number, a name, a birth date, a token, a code or a password.

Access, proven as data:

10. One table in the tests lists every route of the URL configuration with who may use
    it (visitor, patient, clinician, admin, token of each role) and what the others get.
    A route missing from the table fails the test. The table is the access section of
    the review document below.

Hygiene the gates should hold:

11. `make test` has no time gate and one test, the hostile-input test, grew to a minute
    once. A single test that takes longer than a stated number of seconds fails the
    suite, with the number in one place; say it in the plan after measuring the ten
    slowest tests. Bring those under it without dropping a case.
11a. `make mutate` passes a mutant no test reaches: of 6221 mutants in
    `scheduling/domain`, 1165 are "no tests", most of them in the FHIR write modules,
    which only tests of the views layer exercise. The card says pure domain logic is
    held by the mutation gate; for a fifth of it that is not true. The gate fails on a
    mutant without a test unless `mutation-equivalents.txt` explains it, and the domain
    modules get tests of their own until it passes. Start with the modules that decide
    access or what a write may change.
12. `test_api_tokens.py::returns_audit_entries_with_ids_only_when_token_issued_and_revoked`
    failed once in four full runs. Find the cause and fix it; a rerun is not a fix.
13. `make audit`: checks the pinned dependencies against known vulnerabilities with a
    pinned tool, and fails on one. Run by the orchestrator at hand-over, not by `make test`.
14. Module docstrings that name a task ("Task 10a: ...") say what the module is for
    instead. The test-only probe views leave the product package.
15. The report has no test with hospital zones on both sides of UTC (review of 21): add
    it for the day an appointment is counted on.

Decided in writing, `doc/adr/0011-security-review.md` and `doc/security-review.md`:

16. Encryption at rest for clinical notes and for a visitor's details in a booking hold:
    what protects them today, what a deployment must add, and the choice left to the
    owner. No code unless the plan shows it is small and needs no new dependency.
17. The server: the container runs Django's development server and file server, also
    with `DEBUG` off. Say what that is safe for and what a deployment would replace.
18. The review document: for each rule of specification sections 4, 11 and 12, where it
    is enforced and which test holds it; the table of item 10; the limits of ADR 0004;
    what was not reviewed.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` and `make audit` pass from a fresh clone.
