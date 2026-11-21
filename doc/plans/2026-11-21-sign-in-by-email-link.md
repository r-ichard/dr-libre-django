# Plan: task 13, sign-in by email link

Focal point: `scheduling/use_cases/sign_in_link.py` (ask + use), with pure rules in
`scheduling/domain/sign_in_link_rules.py`. Views, pages and API only format.

## Findings from reading (what exists)

- `SignInLink` model already exists (`token_hash` unique, `patient`, `expires_at`, `used_at`). It lacks
  a way to say "cancelled". `SessionKind.EMAIL_LINK` and `session_lifetime` (24 h, never extended
  for non-PASSWORD kinds, any role) already exist: item 5 needs only `open_session(..., EMAIL_LINK)`.
- `take_hit(scope, email, address)` (task 12) is the rate limiter; scopes are `HOLD`, `CODE`.
- `issue_code` mails inside the caller's transaction; a dead mail server raises, giving the generic 500.
- `booking_verification._patient_of` does `select_for_update` on the user, then `place_appointment`
  locks clinicians then patient then rooms: the carried deadlock.
- Request log writes route pattern only, never path or query; `django.server` is discarded
  (`test_process_output.py` proves it). A token in the link's query string is not logged.

## Decisions

1. **Same answer, same time (item 1).** The request never waits on SMTP. Inside one transaction it
   always does the same steps: take the rate hit, normalise email, look the user up, generate a token
   and hash it, run the "cancel earlier links" UPDATE (matches zero rows for a non-patient), write
   the audit entry. Only a patient additionally inserts the link row. Then, via `transaction.on_commit`,
   a patient's mail goes to a small background thread pool (`use_cases/background_mail.py`,
   `ThreadPoolExecutor(2)`); the request returns at once. A send failure is caught in the worker and
   logged with correlation id only (no address, no token); the answer is unchanged. So the one
   slow, failure-prone step (network) is off the request path for both cases. Remaining difference
   is one INSERT, local database, no network. Said plainly in the code comment and the test names.
   Cost: a crash between commit and send loses the mail; the patient asks again. Alternatives
   rejected: mail inline (patient slower, and fails when SMTP is down); outbox table (would store the
   plaintext token, breaking item 3).
2. **Token.** `secrets.token_urlsafe(32)` (256 bits), stored as `session.hash_token` SHA-256
   (random token, so an unsalted hash is enough, same as sessions). Link URL
   `PUBLIC_BASE_URL/sign-in/link?token=...`.
3. **Cancelled.** New nullable `SignInLink.cancelled_at`. Asking again sets it on every still-open
   link of that patient. Usable = not used, not cancelled, `now < expires_at`, patient still
   active Patient (`link_is_usable` in the domain module).
4. **Use is POST only.** `GET /sign-in/link` reads nothing from the database and renders the same
   page for any token (so a scanner learns and spends nothing); form posts the token in the
   body to `POST /sign-in/link`; `POST /api/v1/auth/link/verify` does the same for API clients.
   One use case `use_link(token, user_agent)`: lock the link row `FOR UPDATE` (only that row, no
   user lock), check, set `used_at`, `open_session(user, EMAIL_LINK, ...)`, audit with the patient as
   actor. Redirect 303 to `/patient/` with the cookie; address has no token.
5. **One refusal.** Expired, used, cancelled, unknown, inactive or non-patient: `Failure.invalid_input`
   on field `token`, message "This sign-in link has expired or was already used." Page shows it plus
   a link "Email me a new sign-in link" to `/sign-in`. Audit `auth.link_refused` (domain only when
   the link is known, empty metadata otherwise).
6. **Rate limit.** New `RateLimitScope.LINK` = 3 per email, 10 per network address (as `CODE`),
   taken for every email, account or not, so a 429 reveals nothing about an account. A refused ask
   writes `auth.link_refused`. Rate-limited answer is the existing 429; page shows the form with a
   message.
7. **Audit.** `auth.link_requested` (every accepted ask, actor empty, email domain only; entity id
   is a fresh uuid, which is also the link's pk when one is made, so patient and non-patient
   entries look alike), `auth.link_used` (actor patient), `auth.link_refused`. Interpretation:
   "nothing is created" means no user, link or mail; audit and rate rows are bookkeeping.
8. **Mail down for holds (carried).** New `FailureCode.MAIL_UNAVAILABLE`, 503, message "We could not
   send the email. Try again in a few minutes." `issue_code` catches `OSError` (covers
   `smtplib.SMTPException`), logs without address, returns `Failure.mail_unavailable()`;
   `create_hold` and `resend_code` call `transaction.set_rollback(True)` and return it, so no
   hold, no code, no hit remains. No account is touched (accounts are created only at verify). The
   link ask never returns it.
9. **Lock order (carried).** `_patient_of` stops locking: reads the user unlocked; `place_appointment`
   already locks the patient after the clinicians. A new patient is inserted before clinician locks;
   no other path can reference that new row, so no cycle. Global order stays clinicians,
   patient, rooms.
10. **Network address.** Move `_network_address` from `views/booking.py` to `views/network_address.py`
    (third caller now), REMOTE_ADDR only.

## Files to touch, in order

1. `scheduling/domain/sign_in_link_rules.py` + test: `LINK_LIFETIME` 15 min, `TOKEN_BYTES`,
   `link_is_usable`.
2. `scheduling/domain/rate_limit_rules.py` + test: scope `LINK`.
3. `scheduling/domain/failure.py` + `test_failure.py`, `test_error_contracts.py`:
   `MAIL_UNAVAILABLE`; `views/failure_response.py` (status, message).
4. `scheduling/domain/email_content.py` + test: `sign_in_link_email(url, valid_minutes)` says "valid
   for 15 minutes" and "works once"; the only mail with a signing link.
5. `scheduling/models/access.py`: `cancelled_at`, scope choices; migration `0009_*`;
   `doc/data-model.md` via `manage.py render_data_model`; model tests (`test_access.py`).
6. `scheduling/use_cases/background_mail.py`, `sign_in_link.py` (+ tests).
7. `scheduling/use_cases/booking_codes.py`, `booking_holds.py` (mail-down), `booking_verification.py`
   (lock order) + tests.
8. `scheduling/use_cases/purge.py`: delete links with `expires_at < now` (table would grow), count in
   `PurgeCounts`; test.
9. `scheduling/views/auth_schemas.py` (`LinkRequest`, `LinkVerifyRequest`; share the email
   lower-casing with `LoginRequest`), `views/auth.py` (`LinkView`, `LinkVerifyView`),
   `views/network_address.py`, `drlibre/urls.py`.
10. Pages: `views/pages/sign_in_link.py` (ask form post, check-email, continue page, use post),
    templates `sign_in.html` (second form "Email me a sign-in link", own field `link_email`),
    `check_email.html`, `sign_in_link.html` (button), `sign_in_link_invalid.html`; routes
    `POST /sign-in/email-link`, `GET /sign-in/check-email`, `GET|POST /sign-in/link`. Link
    pages send `Referrer-Policy: no-referrer`. No inline script or style, works without JS.
    Read `.claude/skills/impeccable/reference/craft-floor.md` before the template edits.
11. `doc/backlog.md` left to the orchestrator.

Deliberately not touched: `placement*.py`, `session.py`, `session_rules.py` (already right),
clinician/admin paths, patient appointments list (task 14), `notifications`/`email_delivery`
(other mails stay sign-in-page links only).

## Invariants and blast radius

- No double booking: placement code untouched; only the order of one lock removed from verification.
- Authorization server-side: role and `is_active` read from the database at ask and at use; the
  link carries only a token; actor is set only on use.
- Audit append-only: entries written via `record_audit` inside the transaction of the change.
- Credentials: only hashes stored (token, rate keys); token never in logs, audit, error pages.
- Blast radius: booking hold/resend/verify (error path and one lock), sign-in page template,
  urls, purge, migration (one nullable column, one check/choice change on `RateLimitHit`).

## Failing tests to write first (`returns_X_when_Y`)

Domain: `returns_true_when_link_is_unused_uncancelled_and_before_expiry`; `returns_false_at_exactly_
fifteen_minutes`, `..._when_used`, `..._when_cancelled`; `returns_link_email_naming_fifteen_minutes_and_
single_use`; `returns_limit_of_three_per_email_when_scope_is_link`; `returns_mail_unavailable_
with_empty_details`.

Use case, ask: `creates_one_link_and_one_mail_when_email_is_active_patient` (mail after commit, token
hash stored, token not stored); `returns_same_success_and_creates_nothing_when_email_is_unknown_
admin_clinician_or_inactive`; `cancels_earlier_links_when_asking_again` (earlier one then refused);
`returns_rate_limited_on_fourth_ask_in_an_hour_and_on_eleventh_from_one_address`; `returns_same_answer_
when_mail_sending_fails` (backend raises); `returns_before_mail_is_sent_when_backend_blocks` (patient
call returns while a blocked fake backend is still waiting: proves send is off the request path);
`runs_same_statement_kinds_for_patient_and_stranger_except_one_insert` (query capture; difference is
one INSERT of the link, nothing else); audit rows: requested with domain only and empty actor.
Use: `signs_in_patient_with_24_hour_session_when_link_is_valid` (kind EMAIL_LINK, expires exactly +24 h,
still +24 h after later requests, also for a patient with a password); `returns_same_refusal_when_link_
is_expired_used_cancelled_unknown_or_user_inactive` (equal Failure values); `uses_link_once_when_two_
threads_post_it_together` (exactly one session); `returns_audit_with_actor_when_used`, refused with
empty actor.
Mail down: `returns_mail_unavailable_and_holds_nothing_when_hold_cannot_send`, same for resend
(no hold row, no code row, no rate hit, no user); API answer 503 with the new code and the message.
Lock order: `leaves_user_row_unlocked_when_verification_finds_existing_patient` (second connection
`FOR UPDATE NOWAIT` succeeds while `_patient_of` ran in an open transaction; fails on current code);
`returns_no_error_when_verification_races_booking_of_same_patient` (two threads, 20 rounds, pattern of
`test_placement_races.py`; no OperationalError, each side Success or a domain Failure).
Views/API: `POST /api/v1/auth/link` answers 202 with an empty JSON object for patient and
stranger alike; 400 for malformed email; 429 when limited. `POST /auth/link/verify` sets the cookie and
returns `{"home": "patient_portal"}`; bad token answers 400 with the one message; GET of the page
with any token returns 200 and leaves the link unused; POST of the page redirects 303 to `/patient/`
(no token in `Location`); invalid page offers "Email me a new sign-in link"; sign-in page contains
"Email me a sign-in link" and no inline `<script>`/`style=`; forms work with no JS (plain POST).
Secrets (`test_sign_in_link_output.py`): plant a known token by patching `secrets.token_urlsafe`; run
ask, page GET, page POST, API verify, refused paths and a forced mail failure with the real LOGGING
JSON formatter attached and `capfd`; assert the token appears in no log line, stderr/stdout,
audit metadata, `RateLimitHit`/link rows, error page bodies; assert only its hash is in the table.
The existing child-process probe already proves paths and queries never reach output.
Purge: `deletes_expired_links_and_keeps_open_ones`.

Red proven for each before green; `make mutate` on the new domain module, any survivor explained in
`mutation-equivalents.txt`.

## Trust boundaries

- Email, token from client (API JSON body, page form body, link query): validated by `StrictSerializer`
  / form checks (length 254, normalised), compared only as hashes, never echoed.
- Network address: `REMOTE_ADDR`, never a forwarded header.
- Page POSTs: CSRF token as the sign-in form. API: existing origin rule (section 12.3).
- Session cookie: set only by `open_session` result, same cookie flags as login.

## Vocabulary

Patient, Admin, Clinician, User, SignInLink, Session (kind EMAIL_LINK), AuditLogEntry, Notification
not used (the mail is not a Notification: it signs in, and carries a token).

## Will not do

No new dependency, no outbox, no per-address limit on verify (token has 256 bits), no change to the
session rules, no "remember me", no next-path carried through the link, no revocation of other sessions
on use, no patient appointments page.

## Architect review

Verdict: approve.

- Ladder: one new use case, one pure rules module, one nullable column. The background mail pool
  is the only new moving part and it is justified: it is what makes item 1 equal in time. No new dependency.
- Scope: all ten items and both carried fixes are covered, including purge, data-model doc, and the 503 contract.
- Tests first: named as behaviours with spec values (15 min boundary, 3 per hour, 24 h not extended, same
  refusal, one use under two threads, lock race, planted-token output proof).
- Security: token hashed, 256 bits, POST-only use, GET touches nothing, no-referrer on link pages,
  role and `is_active` read server-side, limiter taken for every email so a 429 leaks nothing.
- Implementation notes, not blockers:
  1. `on_commit` callbacks do not run inside pytest-django's default test transaction; use
     `django_capture_on_commit_callbacks(execute=True)` or `transaction=True` tests, and make the worker's
     pool shutdown/drain deterministic in tests.
  2. The timing test is structural (statement kinds), which is as far as a test can go; keep it.
  3. Make sure `link_refused` for the rate-limited case carries no email domain that distinguishes accounts
     (domain of the asked address is fine, since it is client-supplied).
  4. Confirm `open_session` takes no user row lock, so the use path keeps one lock (the link row).
