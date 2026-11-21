Task 05: password sign-in, sessions and access rules.

`drlibre-specs.md` section 12 and the two sign-in endpoints of section 14, as use cases
and API only. The screens are task 05a. Sign-in by email link and by booking code come
with tasks 13 and 12: build the session so they can open one, and do not build them.

1. Sessions (12.2), on the existing `Session` model. A random token of at least 128 bits
   in a cookie that scripts cannot read, sent to the same site only, and over HTTPS only
   in production. The server stores a hash of the token and looks the session up by that
   hash. Sign-out deletes the session. A deactivated user's sessions stop working at
   once.
2. A session records how it was opened: password, email link or booking code. Add what
   the model needs with a migration and regenerate `doc/data-model.md`. After a password
   sign-in a session lasts 12 hours for an admin and 7 days for everyone else, and is
   extended to a full lifetime whenever less than half remains. A session opened by link
   or code lasts 24 hours and is never extended: provide the use case that opens one and
   test its lifetime, its callers come later.
3. Password sign-in (12.1). A wrong email and a wrong password give the same answer and
   take the same time: say in the plan how the time is equalised and test that the
   password hasher runs on both paths. An inactive user cannot sign in. After 10 failures
   in 15 minutes for one email address, sign-in for that address is refused until the
   window passes, a correct password included; a success clears the count. Say in the
   plan where the count lives and why it holds no readable email address.
4. Audit. Success, failure and lockout are audited through the audit writer, with the
   email domain only and an empty actor when no user is known (section 4).
5. `POST /api/v1/auth/login` and `POST /api/v1/auth/logout` with strict schemas and the
   failure contract. Login answers which home the user lands on: patient portal,
   clinician workspace or admin console.
6. Identity comes from the session, never from the request body (section 4). An API
   authentication step turns the session cookie into the request's user, and the
   use cases take the actor from there.
7. Access rules (12.3) as declarations a view states: public, any signed-in user, or
   named roles. Without a session the answer is `unauthenticated`; a signed-in user in
   another role's area gets `forbidden`. Give use cases one helper for the record rule:
   missing gives `not_found`, exists but belongs to someone else gives `forbidden`.
8. State-changing requests from another origin are refused (12.3). Say which mechanism
   holds for cookie-authenticated requests and test a cross-origin POST.
9. All time-dependent rules use the request clock: test expiry, extension at less than
   half, the lockout window and its end by moving the clock, never by waiting.

Read the rules the model plan left to use cases
(`doc/plans/2026-11-21-domain-model.md`, "Waits for its use case") and the carried items
in `doc/backlog.md` that name task 05.

Carried from the review of task 04b, to do here because sign-in is the first caller of the
audit writer: `AuditMetadata` checks `changed_fields` and `email_domain` at run time as it
does the other sections, and `TransactionRequired` gets a name that needs no lint
suppression.

Not in this task: screens, sign-in link and booking code endpoints, password change.

Done when `make setup && make lint && make test && make gate` pass from a fresh clone.
