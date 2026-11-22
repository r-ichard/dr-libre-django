Task 26b: security hardening, start-up, cookies, proxy, logs and the access table.

Second part of the security review (`doc/backlog/26-security-hardening.md` holds the whole
list). The product is local only, in containers (owner decision): a fix makes the local product
safe to use and safe to grow, and adds no deployment machinery nobody asked for.
Reproduce each defect with a failing test before the fix. No new dependency without its
reason in the plan.

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
3a. Carried from 26a: the cookie of a booking hold (`drlibre_hold`) joins the list of
   item 2. The public detail pages (`/providers/<id>`, `/hospitals/<id>`,
   `/specialties/<id>`), their `/api/v1` twins, `/api/v1/slots` and a `/fhir` search
   without a token load schedules for anyone and have no limit; the search has one since
   26a. Give them the same mechanism, and say in the plan which share a counter.

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

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
