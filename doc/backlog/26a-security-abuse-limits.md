Task 26a: security hardening, abuse limits and what an answer may be.

First part of the security review (`doc/backlog/26-security-hardening.md` holds the whole
list). Three findings of QA round 3 (`doc/qa/2026-11-22-round-3.md`, #46 to #48) and four
points the build left open. The product is local only, in containers (owner decision): a fix makes the local product
safe to use and safe to grow, and adds no deployment machinery nobody asked for.
Reproduce each defect with a failing test before the fix. No new dependency without its
reason in the plan.

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

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
