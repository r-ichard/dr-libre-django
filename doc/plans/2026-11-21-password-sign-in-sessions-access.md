# Plan: task 05, password sign-in, sessions and access rules

Spec: section 12, section 4 (identity, audit, failure codes), section 14 (`/auth/login`, `/auth/logout`).
Model plan "Waits for its use case" rows read: session lifetime and extension (this task), audit
metadata content (done in 04b, hardened here). Backlog carried items naming task 05: "Session needs to
record how it was opened" (done here). Use cases and API only, no screens.

## Focal point

`scheduling/use_cases/sign_in.py` (`sign_in_with_password`) and `scheduling/use_cases/session.py`
(`open_session`, `resolve_session`, `sign_out`). Everything else is a pure rule they call or a thin
adapter that carries their result to HTTP.

## Blocks, one sentence each

1. `domain/session_rules.py` (pure): lifetime per kind and role, and the extension rule, as functions
   of `now`; no clock read.
2. `domain/lockout_rules.py` (pure): the constants 10 and 15 minutes, `window_start(now)`, `is_locked(failure_count)`.
3. `domain/sign_in_rules.py` (pure): `Home` StrEnum and `home_for(role)`.
   These three may be one file if each stays under 60 lines; they import only the `Role` and
   `SessionKind` enums from the models, never the ORM.
4. `models/access.py`: `SessionKind` (PASSWORD, EMAIL_LINK, BOOKING_CODE), `Session.opened_by` with a
   value-list CHECK (`one_of`), new model `SignInFailure`.
5. `use_cases/sign_in.py`: the password sign-in flow, returns `Result[SignedIn]`.
6. `use_cases/session.py`: opens, resolves (lookup, expiry, activity, extension) and ends sessions.
7. `use_cases/record_access.py`: `guard_record(record, may_access) -> Result[Record]`, missing gives
   `not_found`, present but refused gives `forbidden`.
8. `views/session_cookie.py`: cookie name, attributes, set and clear; no policy.
9. `views/authentication.py`: `SessionAuthentication` (DRF) turns the cookie into `(user, SessionIdentity)`;
   a bad, expired or deactivated session returns `None` (anonymous), so a public endpoint stays public.
10. `views/access.py`: declarations `public()`, `signed_in()`, `roles(*roles)` returning `permission_classes`
    lists; `signed_in_user(request) -> User` for views to hand to use cases. `DenyUnlessDeclared` stays the default.
11. `views/api_view.py`: `ApiView` gets `authentication_classes`, an Origin check in `initial()` and cookie
    reissue in `finalize_response` when a session was extended.
12. `views/auth.py` + `views/auth_schemas.py`: `LoginView`, `LogoutView`, strict request schemas.
13. `drlibre/urls.py`: two routes before the catch-all.
14. Carried from 04b: `AuditMetadata.__post_init__` checks `changed_fields` and `email_domain` against
    `FIELD_NAME_PATTERN` and `HOSTNAME_PATTERN`; `TransactionRequired` renamed `TransactionRequiredError`, `noqa` removed.

## Decisions the architect may reject

- **Session token.** `secrets.token_urlsafe(32)` = 256 bits. Stored: SHA-256 hex (64 chars, fits the
  existing column and CHECK). Lookup by hash; unique constraint exists. No keyed hash needed, the token is
  already high entropy.
- **Cookie.** `drlibre_session`, `HttpOnly`, `SameSite=Strict`, `Secure` = `settings.HTTPS_ONLY`, `Path=/`,
  expiry = `expires_at`. Strict is the literal "same site only"; if a first cross-site navigation (email
  link into the portal) hurts, 05a revisits it. Cookie is reissued when a session is extended, otherwise
  the browser would drop it at the old expiry.
- **Lifetime is derived, not stored.** Password: 12 h admin, 7 d others (role read from the user at
  extension time); link and code: 24 h, never extended. Extension: if `expires_at - now < lifetime / 2`,
  set `expires_at = now + lifetime`. Only `opened_by` is added to `Session` (migration with a `PASSWORD`
  default for existing rows, `preserve_default=False`).
- **Extension is not audited.** It moves an expiry on a credential row, at most about twice per lifetime
  per session; sign-in, sign-out, failure and lockout are audited. Say no here if the rule "every write
  audited" is meant to include it.
- **Equal time.** Exactly one password-hasher call on every attempt, whichever way it ends: a user with a
  usable password gets `check_password`; unknown email, deactivated user with no usable password, and
  passwordless patient get `make_password(submitted)` as the dummy (same algorithm and cost as the
  stored hashes). A locked address also runs the hasher and discards the result. The answer is built
  after the hash. Both failure paths also write one `SignInFailure` row and one audit row, so the database
  work matches. Timing itself is not asserted (flaky); the test asserts the hasher call count.
- **Where the count lives.** New table `SignInFailure(email_hash, failed_at)`, index on both. In the
  database, not a cache, so it survives restarts and is shared by every worker. `email_hash` is
  HMAC-SHA256 of the lower-cased email keyed by `SECRET_KEY`: no readable address is stored, and a leaked
  table cannot be dictionary-tested without the key. It uses its own `failed_at`, supplied from the request
  clock (the `auto_now_add` column of `Record` would defeat clock-moving tests, same reason as 0005).
  Counted for unknown emails too, so lockout does not reveal which addresses exist. Locked when
  `count(failed_at > now - 15 min) >= 10`. Refused attempts add no row, so the lock ends when the oldest
  failure leaves the window. Success deletes the rows for that hash; a failure also deletes the rows
  older than the window for that hash (no purge job needed).
- **Lockout answer** is the same `unauthenticated` as a wrong password: no oracle for which addresses
  are locked. The audit trail tells them apart (`auth.lockout`). Section 4 has no 429 code and the 429
  mapping belongs to task 12.
- **Audit.** Actions `auth.login`, `auth.login_failed`, `auth.lockout`, `auth.logout`. Metadata:
  `email_domain` only (plus `failure_count` on lockout). Actor is the user when one matched the email,
  empty otherwise. `entity_type`/`entity_id`: `Session` + session id for login and logout;
  `SignInFailure` + the row id for a failure; for a lockout, the id of the newest failure row in the window.
  Written in the same `transaction.atomic()` as the change; failure paths return a `Failure` value so the
  transaction commits and the failure row and audit persist.
- **CSRF.** Cookie-authenticated API writes are protected by two layers: `SameSite=Strict`, and an Origin
  check in `ApiView.initial()` before authentication. An unsafe method with an `Origin` header that is not
  the request's own scheme and host, nor in `CSRF_TRUSTED_ORIGINS`, answers `forbidden`, login included
  (login CSRF). No `Origin` passes: browsers send it on every cross-origin POST, and non-browser clients
  are not CSRF vectors. No token flow, so the future JS client needs nothing extra. Django's
  `CsrfViewMiddleware` stays for the server-rendered forms of 05a (DRF views are exempt from it). Gap:
  the host is compared as Django sees it, so behind a TLS-terminating proxy the carried item "SECURE_PROXY_SSL_HEADER"
  (task 26) applies.
- **Login response** `200 {"home": "patient_portal" | "clinician_workspace" | "admin_console"}` plus
  `Set-Cookie`. Logout `204`, cookie cleared, session row deleted. Logout without a session is
  `unauthenticated`.
- **Request schema.** `LoginRequest`: `email` (EmailField, stripped, lower-cased, max 254, domain must pass
  `email_domain()` so audit cannot raise), `password` (not trimmed, 1 to 1000 characters, to bound hasher
  cost). Unknown fields refused (`StrictSerializer`). Logout takes an empty strict schema.
- **Audit-write failure** raises (broken invariant), login does not complete.

## Files, in order

1. `scheduling/domain/audit_metadata.py` (+ test), `scheduling/use_cases/audit.py` (+ `test_audit.py` import).
2. `scheduling/models/access.py`, migration `0006_*` (generated, `makemigrations`), `doc/data-model.md`
   (`manage.py render_data_model`), `scheduling/models/builders.py` (builder for the new model and `opened_by`),
   `scheduling/models/test_access.py` (value-list and hash guard rows for new model).
3. `scheduling/domain/` rules + tests.
4. `scheduling/use_cases/session.py`, `sign_in.py`, `record_access.py` + tests.
5. `scheduling/views/` cookie, authentication, access, api_view, auth, schemas + tests; `drlibre/urls.py`.
6. `doc/backlog.md` (carried item resolved), `doc/adr/0005-sessions-and-access.md` (token, cookie,
   lockout store, CSRF mechanism).

Not touched: `settings.py` (cookie flags use `HTTPS_ONLY`; `DEFAULT_AUTHENTICATION_CLASSES` stays empty so
probe views and the existing 403 test are unchanged), `failure.py`, `failure_response.py` (all codes
exist), `middleware.py`, demo seed, FHIR, email, any screen, `scheduling/use_cases/test_no_wall_clock.py`
(it already scans the new use cases for clock reads).

## Invariants and blast radius

- Authorization server-side: actor only from `request.user` set by the session; no schema has a user field.
- Audit log append-only and written in the change's transaction; no audit row holds an email, only a domain.
- Lock-out never reveals existence of an email; no secret (token, password, email) in logs or audit.
- Blast radius: `ApiView` (every API view now authenticates and checks Origin on writes; health and the catch-all
  stay public), `Session` table (new column), one new table, `AuditMetadata` (stricter, 04b tests re-run).
- Known limit: concurrent bad attempts can slip a few past 10 (no row lock). Existing sessions of a user who
  signs in again are not revoked, expired session rows are not purged: neither asked for.

## Failing tests, written first (behaviour names, expected values in words)

Domain (`scheduling/domain/`):
- `returns_twelve_hours_when_admin_opens_password_session`; `returns_seven_days_when_clinician_or_patient_opens_password_session`.
- `returns_twenty_four_hours_when_session_opened_by_link_or_code`, also for an admin.
- `returns_new_expiry_when_less_than_half_remains`; `returns_no_change_when_exactly_half_remains` (boundary: half is not "less");
  `returns_no_change_when_more_than_half_remains`; `returns_no_change_when_session_opened_by_link_or_code`.
- `returns_locked_when_ten_failures_counted`; `returns_open_when_nine_failures_counted`; `returns_window_start_fifteen_minutes_before_now`.
- `returns_home_of_the_role` for ADMIN, CLINICIAN, PATIENT: admin_console, clinician_workspace, patient_portal.
- `rejects_changed_field_when_it_is_not_a_field_name` ("Jane Doe"), `rejects_email_domain_when_it_is_an_address` ("jane@example.test"),
  `returns_metadata_when_changed_fields_and_domain_are_valid`.

Use cases (`scheduling/use_cases/`, context bound with a movable clock):
- `returns_session_expiring_in_twenty_four_hours_when_open_session_is_called_for_email_link` and `..._booking_code`; stored hash is 64 hex characters, the returned token is not stored and is at least 43 characters; two tokens differ.
- `returns_user_when_cookie_token_matches_a_live_session`; `returns_unauthenticated_when_token_is_unknown`;
  `returns_unauthenticated_when_clock_passes_expiry` (one second before: signed in; at expiry: refused);
  `returns_unauthenticated_when_user_is_deactivated` (same token worked a moment before);
  `returns_longer_expiry_when_clock_moves_to_under_half_remaining` and `returns_same_expiry_when_more_than_half_remains`;
  `returns_same_expiry_when_link_session_is_resolved_late`.
- `returns_unauthenticated_when_session_is_signed_out_and_token_reused`; sign-out deletes the row and writes `auth.logout` with actor.
- Sign-in: `returns_home_and_session_when_password_is_right` (admin 12 h, patient 7 d, audit `auth.login` with actor and domain `example.test`);
  `returns_unauthenticated_when_email_is_unknown` and `returns_unauthenticated_when_password_is_wrong`: equal `Failure`;
  `runs_password_hasher_once_when_email_is_unknown` and `..._when_password_is_wrong`, `..._when_user_is_inactive`, `..._when_patient_has_no_password`, `..._when_address_is_locked` (counting hasher registered in `PASSWORD_HASHERS`);
  `returns_unauthenticated_when_user_is_inactive_and_password_right`;
  `returns_unauthenticated_when_tenth_failure_is_followed_by_correct_password` (locked, no session created, audit `auth.lockout` with actor from the matching user);
  `returns_signed_in_when_clock_moves_fifteen_minutes_after_the_failures` (14 min 59 s still refused);
  `returns_signed_in_when_ninth_failure_is_followed_by_correct_password`; `returns_zero_failures_when_sign_in_succeeds` (count cleared; ten more needed to lock);
  `returns_independent_counts_when_two_addresses_fail` and unknown address locks like a known one;
  `stores_no_readable_address_when_failure_is_recorded` (no row field, no audit JSON contains the local part; domain only; actor empty for unknown);
  `returns_audit_with_empty_actor_when_email_is_unknown`.
- `returns_not_found_when_record_is_missing`; `returns_forbidden_when_record_belongs_to_someone_else`; `returns_record_when_actor_may_access`.

Views (`scheduling/views/`, Django test client, probe urlconf for access declarations):
- `returns_200_home_and_cookie_when_login_is_right`: cookie `HttpOnly`, `SameSite=Strict`, no `Secure` in dev, `Secure` when `HTTPS_ONLY`; `returns_401_unauthenticated_when_login_is_wrong` (same body for unknown email); `returns_400_invalid_input_when_login_has_unknown_field_or_bad_email_or_missing_password`.
- `returns_204_and_clears_cookie_when_logout_has_session`; `returns_401_when_logout_has_no_session`; the old cookie then yields 401.
- Access: `returns_401_when_signed_out_user_calls_signed_in_view`; `returns_403_when_patient_calls_admin_view`; `returns_200_when_admin_calls_admin_view`; `returns_200_when_public_view_is_called_with_stale_cookie`; undeclared view stays closed (401 anonymous, 403 signed in).
- `returns_user_from_cookie_when_body_names_another_user_id`: body field naming another user is ignored (or refused as unknown by schema).
- CSRF: `returns_403_forbidden_when_login_post_has_foreign_origin`; `returns_403_and_keeps_session_when_logout_post_has_foreign_origin` (row still there); `returns_204_when_logout_post_has_own_origin`; `returns_204_when_logout_post_has_no_origin`; `returns_200_when_get_has_foreign_origin`.
- `returns_new_cookie_expiry_when_request_extends_the_session`.
- Clock moves are via `bind_request_context(RequestContext(..., now=...))` in use case tests and a patch of `scheduling.views.clock.now_utc` in view tests; no sleeping anywhere.

Red must fail for the right reason: missing symbols or missing behaviour, not an import typo.

## Trust boundaries

- Request body (email, password): `LoginRequest`, strict, bounded lengths; password never logged or audited.
- Cookie (token): hashed then looked up; unknown or expired gives anonymous; user `is_active` re-read per request.
- `Origin` / `User-Agent` headers: Origin compared exactly; User-Agent truncated to 300 chars before storage.
- Identity and role: from the Session row only; permission classes check `request.user.role`; use cases take `actor: User`.
- Audit writer and `SignInFailure`: email reduced to domain or keyed hash before it leaves the sign-in use case.

## Vocabulary

User, Session, ApiClient (untouched), Admin, Clinician (role CLINICIAN, "provider" only in public text), Patient,
AuditLogEntry. New: `SignInFailure` (a named record of a failed sign-in, hashed address and instant). It appears
in `doc/data-model.md`; the CRUDL rule is met by its use cases: create (failure), read (count), delete (clear and prune), no update by design, stated in the ADR.

## What I will not do

No screens, no link or booking-code endpoints, no password change or reset, no rate limit other than the
lockout, no CORS, no `Throttled` 429 mapping, no purge job, no session revocation on re-sign-in, no new
dependency, no change to `DenyUnlessDeclared`, no change to Django `CsrfViewMiddleware` settings, no generic
abstraction beyond the one guard helper (used by every later use case but with one caller now: the guard is
asked for by the task).

## Architect review

Verdict: approve. Scope covers all nine task items plus both carried 04b items. No new dependency,
one new table justified by the lockout item. Layers right (pure rules, use cases own transaction and
audit, views thin). First tests are named behaviours with spec values (10/15 min, 12 h/7 d/24 h,
half-boundary, hasher count on every path).

Points for the implementer (not blocking):
- Spec section 14 lists logout as "Anyone". The plan answers `unauthenticated` for logout without a
  session. Prefer declaring logout `public()` and returning 204 when no session exists (clear the cookie,
  delete nothing, no audit), or state the deviation in the ADR. Adjust the `returns_401_when_logout_has_no_session` test accordingly.
- Extension is unaudited by decision. Acceptable for a credential expiry bump; record it in the ADR as an explicit exception to "every write audited".
- Origin check: treat `Origin: null` as foreign (it does not match, so it is refused; add a test).
- Deactivated user with a usable password runs `check_password`; deactivated without one runs the dummy. Test both stay at one hasher call.
- Lockout audit on every refused attempt can flood the log for an attacker; acceptable, note it in the ADR.
