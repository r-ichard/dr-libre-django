# Plan: task 12, booking without signing in (use cases and API)

Sections 7.1, 7.2, 7.5, 7.6, 7.7, 14 (three hold endpoints), 5.2, 5.5, 11. No UI (task 12a), no link
sign-in (task 13).

**Focal point:** `scheduling/use_cases/booking_holds.py` (create hold, resend) and
`booking_verification.py` (verify). Everything else feeds these two.

## Decisions the task asks me to state

- **Second hold for the same email replaces the first.** In one transaction the old hold and its
  code are deleted and audited `booking_hold.replaced`, then the new one is made. Reason: the visitor
  who changed their mind or lost the page is not locked out for 10 minutes. Cost: anyone who knows an
  address can drop that address's hold; bounded by the rate limits below, and the victim can re-hold.
  A DB `UniqueConstraint(visitor_email)` backs the rule; an advisory lock on the email key (taken by
  the rate limiter) serialises concurrent creates, so the constraint is never hit in normal flow.
  An expired hold of that email is removed first and audited `booking_hold.expired`.
- **No hold-time check may touch the account.** Placing checks "for a patient" include two that read
  the patient (overlap with their appointments, 3 open online bookings). Run at hold time they would
  answer differently for an existing patient and leak the account (7.5). So hold creation runs the
  placing checks for a *new* patient: type, clinician, department, room, clinician conflict (holds
  included), lead time, online-bookable, slot free, first-available ranking. The two patient-specific
  checks run at verify, where the code has proved the address is the caller's. Deviation from "no
  hold for a slot that could not be booked": only for those two checks; say so in the review.
- **Staff or inactive address:** hold and code are created and sent exactly as for anyone (same
  status, body shape, rows, one email, same audit actions). The refusal is at verify after a *correct*
  code: `forbidden` 403, generic, hold kept (expires on its own). Nothing is written for the refusal.
- **Wrong, expired, used-up code:** one answer for all three, `invalid_input` on field `code`, "The
  code is not valid." (no oracle). Unknown or expired hold id: `not_found`.
- **Mail server down:** the code email is sent inside the hold's transaction, so an SMTP failure
  rolls back hold, code and counter hit; the visitor gets `internal_error` 500 (generic, logged) and
  nothing is held. Visitor action: try again; if it keeps failing, no booking is possible online.
  On resend a failed send rolls back only the new code: the earlier code keeps working. SMTP timeout
  is already 10 s (`settings.MAILERS`), which bounds the clinician row lock. Confirmation emails use
  the existing outbox and retry (`send_pending_emails`).
- **Rate limits, where counters live:** new table `RateLimitHit` (scope, key_hash, hit_at) in
  PostgreSQL, same pattern as `SignInFailure`. `key_hash` = HMAC-SHA256(SECRET_KEY, `"<kind>:<value>"`)
  of the lower-cased email or of `REMOTE_ADDR`; no readable address is stored, a leaked table gives
  no mailbox or IP list, and a hash of an IP cannot be reversed without the key. `X-Forwarded-For` is
  never trusted (spoofable; the product has no proxy). Limits per hour, rolling window:

  | scope | per email | per network address |
  | --- | --- | --- |
  | `hold` (create) | 5 | 20 |
  | `code` (resend) | 3 (spec) | 10 |

  Network numbers are higher because one hospital Wi-Fi shares an address. Hits are recorded for
  allowed requests only; a refused request is `rate_limited` 429, `{}` details, fixed message "Too
  many requests." Mail volume per email is thus at most 5 holds + 3 resends per hour. Verify is
  limited by its 5 attempts per code, not by a counter (so at most 40 guesses per email per hour).
  The purge job deletes hits older than the window. Check-then-insert runs under
  `pg_advisory_xact_lock(<64 bits of key_hash>)` (parameterised) so concurrency cannot overshoot.
- **Code:** `secrets.randbelow(10**6)` zero-padded; stored as HMAC-SHA256(SECRET_KEY,
  `"booking-code:<hold id>:<code>"`), compared with `hmac.compare_digest`. One `VerificationCode` per
  hold (OneToOne); resend overwrites hash, `expires_at` and resets `attempts_used`, so the earlier
  code stops working.
- **Booking made audit:** the placing use case already writes `appointment.book`; it gets an optional
  `email_domain` so that same entry carries the domain (no second entry). Actor = the patient.

## Blocks, one sentence each

1. `domain/booking_codes.py` (new, pure): constants (hold 10 min, code 10 min, 5 attempts, 6 digits)
   and `code_is_usable(expires_at, attempts_used, now)`.
2. `domain/rate_limit_rules.py` (new, pure): `RateLimit` table above, `window_start`, `is_limited`.
3. `domain/visitor_rules.py` (new, pure): `valid_birth_date(birth, today)` (not future, not over 120
   years back) and email normalisation (strip, lower).
4. `domain/failure.py`: `FailureCode.RATE_LIMITED` + `Failure.rate_limited()`.
5. `domain/email_content.py`: `verification_code_email(code, valid_minutes)`: code, expiry, no URL.
6. `models`: `BookingHold.terms_accepted_at` + `UniqueConstraint(visitor_email)`;
   `VerificationCode.hold` OneToOne PROTECT (migration deletes old rows first: nothing creates them
   today); `User.terms_accepted_at` null (copied from hold when a patient is created, unchanged for
   an existing one); `RateLimitHit` (Record, `fhir_not_exposed`, index scope+key_hash+hit_at, hash is
   64 chars). Migration + `make` regeneration of `doc/data-model.md` via `render_data_model`.
   Update `builders.py` defaults.
7. `use_cases/placement*.py`, `schedule_loading.py`: (a) `find_conflicts` counts a live hold on the
   clinician as `clinician` conflict, ignoring the caller's own hold; `load_schedules` ignores the
   caller's hold too; (b) `PlacementCommand.via_hold: HoldClaim | None` (hold id, source, email
   domain) overrides source to the hold's and passes the ignore ids; (c) `PlacementCommand.announce:
   bool = True`; (d) `probe_placement(command) -> Result[Probe]`: the checks of `_place` for no patient
   (patient None: no patient conflict, zero open bookings), returns chosen clinician; `_place` is split
   so both share it. Placement.py is 281 lines: move the clinician/room choice helpers to a new
   `placement_choice.py` to stay under 300.
8. `use_cases/rate_limits.py` (new): `take_hit(scope, email, address)`: lock, count both keys, refuse
   or record both.
9. `use_cases/booking_codes.py` (new): make code, hash, issue/replace for a hold, send email, check.
10. `use_cases/booking_holds.py` (new): `create_hold`, `resend_code`; audit `booking_hold.created`,
    `.replaced`, `.expired` (via 11).
11. `use_cases/hold_expiry.py` (new): `expire_hold(hold)` (delete code and hold, audit
    `booking_hold.expired`) and `expire_booking_holds()` for the job, `skip_locked`.
12. `use_cases/booking_verification.py` (new): `verify_hold`: lock hold; unusable code -> count attempt
    (`code_is_usable`), audit `booking_code.verification_failed`, return the one answer, committed;
    correct code -> savepoint; staff/inactive -> `forbidden`; else get or create Patient (audit
    `user.patient_created`, email domain), `place_appointment` with `via_hold`, `announce` default;
    Failure -> `savepoint_rollback` (no account, no booking, hold kept, attempts kept); Success ->
    delete code and hold, `open_session(BOOKING_CODE)`. Returns appointment and token.
13. `use_cases/waitlist.py` + `notifications.py`: titles "Waitlist slot offered" and "Waitlist slot
    booked"; `accept_offer` passes `announce=False` so only the waitlist email goes out.
14. `use_cases/purge.py`, `jobs/worker.py`: purge also deletes old `RateLimitHit`; new job
    `expire_booking_holds` every 1 minute; `management/commands/expire_booking_holds.py`.
15. `views/hold_schemas.py` (new) and `views/booking.py` (new): `POST /booking/holds`,
    `/holds/{id}/resend`, `/holds/{id}/verify`, all `public()`, `StrictSerializer`. Hold body:
    `id, appointment_type_id, clinician_id, starts_at, ends_at, expires_at` only. Verify sets the
    session cookie like `LoginView` and returns the appointment body. Network address from
    `REMOTE_ADDR`. `failure_response.py`: 429 and message. `drlibre/urls.py`: three routes.
16. `doc/adr/0004-...md`: add `rate_limited` 429 `{}` to the table; note the hold replacement rule.

## Files to touch, in order

domain (1-5, with tests) -> models, migration, builders, `doc/data-model.md` -> placement (7) ->
rate_limits, booking_codes, hold_expiry, booking_holds, booking_verification -> waitlist, notifications
-> purge, worker, command -> failure_response, schemas, views, urls -> ADR 0004.

**Not touched:** search, free-slots endpoint (it already hides held slots), appointment_changes,
reminders, pages, templates, CSS, FHIR, sign-in by link, `email_delivery.py` (the code email is built
and sent by `booking_codes.py`, not a Notification: its recipient is not a user), `.fabro`, skills.

## Invariants and blast radius

- No double booking: clinician row lock then free-slot and conflict checks including holds; the three
  exclusion constraints stay the last line. Two holds cannot overlap on one clinician (lock). Verify
  places through `place_appointment` only.
- Authorization server-side: actor of placing is the patient looked up by verified email, never from
  payload; `patient_id` and `room_id` are not accepted fields (StrictSerializer).
- Audit append-only, inside the transaction of each change; metadata only email domain, ids, counts.
- Blast radius: `find_conflicts` and `load_schedules` are shared by every booking path, slots query,
  waitlist and reminders, so their tests re-run. `PlacementCommand` new fields default, so callers
  are unchanged except waitlist. Purge counts gain a field (existing purge tests and job command
  output change: "1 2" gains a third value).

## Trust boundaries

Public request body and `REMOTE_ADDR` -> `StrictSerializer` (types, lengths, email format, terms must
be `true`) -> use case re-checks birth date against the request clock, type, clinician, slot (never
trusts `ends_at`, end computed). Hold id in path is a UUID, unguessable, still gated by the code.
Code compared constant-time. No sensitive value in logs or URLs; emails in logs never. Session token
leaves only in the cookie.

## Entities (CLAUDE.md vocabulary)

Visitor, Patient (passwordless), Admin/Clinician (refused), BookingHold, VerificationCode, Session
(kind BOOKING_CODE), Appointment, AppointmentType, ClinicianProfile, Notification, AuditLogEntry.
New: RateLimitHit (bookkeeping, like SignInFailure).

## Failing tests first (`returns_X_when_Y`)

Domain:
- `returns_false_when_attempts_used_is_5`, `returns_true_when_attempts_used_is_4`,
  `returns_false_when_code_expires_exactly_now`, `returns_true_one_second_before_expiry`.
- `returns_true_when_hits_equal_limit`, `returns_false_when_hits_are_one_below_limit`,
  `window_start_is_one_hour_before_now`.
- `returns_false_when_birth_date_is_tomorrow`, `returns_true_when_birth_date_is_today`, 120-year edge.
- `returns_code_and_no_url_when_code_email_is_built`; `rate_limited_has_status_429_and_empty_details`.

Use cases (PostgreSQL):
- Hold: `returns_hold_for_ten_minutes_when_slot_is_free`; `returns_rule_violation_when_lead_time_short`
  (no hold row); `returns_clinician_chosen_by_ranking_when_none_named` (weight x time since last
  assignment, never-assigned first, lowest id) and that clinician is held; `no_clinician_available`
  when none free; `returns_invalid_input_when_terms_not_accepted`; terms time stored equals now.
- Hold as conflict: placing on a held slot returns `conflict` with resources `["clinician"]`, not
  `rule_violation`; the slots query no longer offers it; an expired hold (clock +10 min) frees it;
  the hold's own verify is not blocked by itself.
- One per email: second hold replaces the first (first row gone, one `booking_hold.replaced` audit,
  old code no longer verifies); expired earlier hold is removed and audited expired.
- Code: stored value is 64 hex and not the code; resend returns a new code, old one answers invalid;
  fourth resend within the hour returns `rate_limited`, a request 61 minutes later succeeds;
  fifth wrong attempt then the correct code still answers invalid; resend resets attempts.
- Verify: correct code books for a new email: Patient with typed name, birth date, phone, no usable
  password, `email_verified_at` now, `terms_accepted_at` set; appointment `ONLINE` (named) or
  `ROUND_ROBIN` (first available, clinician `last_assigned_at` = now); hold and code deleted; session
  kind BOOKING_CODE expiring in 24 h; confirmation Notification "Appointment booked" with one email
  after commit. Existing active patient: booking theirs, name, phone, birth date unchanged. Admin,
  clinician, inactive user: `forbidden`, no appointment, no new user, hold kept.
- Failed placing (a second patient overlapping, or 3 open online bookings, or the slot taken by an
  appointment after the hold): `conflict`/`rule_violation` returned, no user created, no appointment,
  hold and code intact, no session.
- Nothing leaks: for a new address, an existing patient and an Admin address, hold create returns the
  same status and body keys, one code email each, the same set of audit actions, the same row counts
  (holds, codes, hits), with identical queries counted by `assertNumQueries`-style equality; resend
  and a wrong-code verify likewise; no response contains a name, birth date, patient id or
  appointment of an existing patient before the code.
- Rate limits: 6th hold per email in an hour and 21st per network address return `rate_limited`
  (429, code `rate_limited`); stored `key_hash` contains neither the email nor the address; a refused
  request writes no hold and sends no mail; the purge removes hits older than an hour.
- Mail: SMTP failure on hold create leaves no hold, no code, no hit, answers `internal_error`; on
  resend leaves the earlier code valid. Code email body has no `http`.
- Audit: created/expired/verification-failed carry actor None and email domain only (no local part,
  no name); patient created and booking made carry actor patient; `expire_booking_holds` job deletes
  expired holds and writes one `booking_hold.expired` each, ignores live ones; worker schedule has
  it at 1 minute.
- Carried: waitlist offer title "Waitlist slot offered"; accept title "Waitlist slot booked" and
  exactly one email (`mail.outbox` length 1) with no "Appointment booked" notification row.

API (views): three endpoints are reachable with no session; unknown field is 400; wrong method and
unknown id 404; 429 body has the wire shape with correlation id; verify sets cookie
`drlibre_session`, HttpOnly, expiring in 24 h.

Mutation: `make mutate` on the three new domain modules; any equivalent mutant goes to
`mutation-equivalents.txt` with a reason.

## Will not do

No abstraction beyond one second caller (rate limiter has two scopes, placement probe has two
callers); no new dependency; no proxy-header trust; no Retry-After header; no booking pages; no
per-network limit on verify; no refactor of placement beyond the split needed for 300 lines; no
Notification row for the code email.

## Risks

Probe duplicates the checks path if the split is sloppy: tests compare probe and place answers on
the same slots. Advisory lock keyed by 64 bits of a hash can collide: harmless (extra waiting).
Replacing a hold lets a third party cancel someone's pending hold: accepted, rate limited.

## Architect review

Verdict: approve.

- Ladder: new tables and modules each have a second caller or a spec line behind them. No new dependency. The `placement_choice.py` split is forced by the 300-line cap.
- Plan knowledge: each block has a one-sentence purpose. Vocabulary matches CLAUDE.md. `RateLimitHit` is a bookkeeping table like `SignInFailure`.
- Tests first: named as behaviours with spec values (5 attempts, 3 resends an hour, 10 min, 24 h, 429). Edge and error paths are covered, including the no-leak triple, rollback on a failed placing, and the carried waitlist email count.
- Security: the threat is named (account enumeration, hold-dropping DoS, code guessing, mail flooding). Controls: HMAC-keyed hashes, constant-time compare, no `X-Forwarded-For`, a single invalid-code answer, an actor taken from the verified email.
- Architecture: use cases own the transaction, views are thin, expected failures are values.
- Scope: everything in the task is mapped. Callers that break are listed (purge counts, `find_conflicts` blast radius).

Non-blocking notes for the implementer:
1. `BookingHold.terms_accepted_at` is new on an existing table. Make the migration safe: delete old holds first, or give it a default. Say which.
2. The hold-time deviation (the two patient-specific checks run at verify) is justified by 7.5. Keep it in the review notes, and test that a hold for an existing patient with an overlapping appointment answers like any other, then fails at verify with `conflict` or `rule_violation` and the hold kept.
3. SMTP failure answers 500 `internal_error`. Acceptable, but log it with the correlation id and never the address. Consider a test that the 500 body is the generic one.
4. Normalise the email (strip, lower) before hashing and before the unique constraint. Add a test that `A@x.com` and `a@x.com` share one hold and one counter.
5. Verify on a staff address returns `forbidden` only after a correct code. That is the one place the address type shows, and only to the mailbox owner. Keep the message generic and identical for inactive and staff.
6. Check that `/style`, the OpenAPI or route lists, and `drlibre-specs.md` section 14 mention nothing that needs the new 429 code. The task names ADR 0004 only.
