# Task 15: patient portal, waitlist, notifications and profile

Spec: section 8 (rest), 4 (audit, validation), 5.8, 11, 12.1, 12.3. Pages only, plus three new use-case
modules for the writes the API does not have (mark read, profile, change password). Joining and accepting
reuse `join_waitlist` and `accept_offer` (`use_cases/waitlist.py:46,125`); no booking rule is copied.
No model change, no migration, no API endpoint (FHIR/API for these concepts is out of scope here).

## Focal point

`scheduling/use_cases/profile.py` (new): `update_profile` and `change_password`, the two writes with
validation, audit and the lockout coupling. Pure rules sit in `domain/profile_rules.py` so the format
rules (phone, birth date, new password) are mutation-tested.

## Blocks, one sentence each

1. `domain/profile_rules.py` (pure): `phone_failure(text)` (empty ok; 7-20 chars of digits, spaces, `+ ( ) -`),
   `birth_date_failure(date, today)` (not in the future), `new_password_failures(current, new)` (10 to 72
   characters, different from current); each returns `FieldMessage` or none, messages as constants.
2. `domain/waitlist_window.py` (pure): `window_instants(earliest_day, latest_day, zone)` -> start of the first
   local day, start of the day after the last (so "latest day" is inclusive); `invalid_input` when the days
   are reversed. Needed once: the form speaks dates, the use case speaks instants.
3. `use_cases/profile.py`: `update_profile(command, actor)` locks the user, validates through block 1, saves
   phone and date of birth (empty clears), audits `profile.update` with `changed_fields` = names that
   actually changed (no value), in one transaction; no change -> success, no audit.
   `change_password(current, new, actor, keep_session_id)`: passwordless -> `forbidden`; locked address
   (`is_locked`, `hash_email` of the actor's email) or wrong current -> failure recorded by
   `record_sign_in_failure` (the existing `_record_failure` made public, `use_cases/sign_in.py:77`, second
   caller) and `invalid_input` on `current_password`; right -> clear the address's failures, `set_password`,
   delete the actor's other `Session` rows, audit `auth.password_change` with `changed_fields=["password"]`
   and `counts={"session_count": n}`; the audit never holds a password or hash.
4. `use_cases/notification_inbox.py`: `notifications_page(patient, page, size)` newest first with count,
   `unread_count(patient)`, `mark_read(notification_id, actor)` through `guard_record` (404/403 values),
   `mark_all_read(actor)`; each locks rows, sets `read_at` from the request clock, audits
   `notification.read` (ids, `changed_fields=["read_at"]`, `counts={"notification_count": n}`) in the same
   transaction; already read or none unread -> success, no write, no audit. `homes.py` uses `unread_count`.
5. `use_cases/waitlist_inbox.py`: `own_waitlist(patient)` newest first, with type, hospital, offered
   appointment and its clinician loaded; `own_entry(id, patient)` via `guard_record` (404/403).
   `accept_offer` already enforces the record rule; the page checks first to answer 404 vs 403 like task 14.
6. `use_cases/booking_page_data.py`: reuse `bookable_services()` and `type_providers()` for the join form's
   type and provider choices; no change expected.
7. `views/pages/portal_nav.py` not needed: `templates/components/portal_nav.html`, parameter `current`:
   `<nav aria-label="Patient portal">` list of five links (Home `/patient/`, Appointments, Waitlist,
   Notifications, Profile), `aria-current="page"` on the current one. Included by the five section pages
   and the change-password page (current = profile).
8. `views/pages/patient_waitlist.py`: `/patient/waitlist` GET (form + list), POST join: `validate_body`-style
   field checks (type uuid from the select, optional provider, two dates) -> block 2 -> `join_waitlist`;
   422 with error summary on bad input; 303 to the list with `?notice=joined`. `/patient/waitlist/<id>/accept`
   POST: record rule, `accept_offer`; success 303 to `/patient/appointments?notice=booked`; every failure to
   `waitlist_refused_page` (block 12). Select shows type names; a provider field depends on the type, so
   without JavaScript the form lists providers as `Name (type)`-free single select of all providers of the
   bookable types, and the use case rejects a clinician outside the type's department (`not_found` ->
   message "That provider does not offer this service.").
9. `views/pages/patient_waitlist_rows.py`: mapper entry -> row (type, window shown in the hospital's zone
   with the zone named, preferred provider or "Any provider", status badge with word, offer block with time,
   provider, hospital, accept action only when OFFERED).
10. `views/pages/patient_notifications.py`: `/patient/notifications?page=` (page clamped, same helper as
    appointments), POST `/patient/notifications/<id>/read` and `/patient/notifications/read-all` -> 303 back
    to the list, same page number kept only as a whitelisted digit string. Rows: title, body, time, "Unread"
    badge with text, "Mark as read" button naming the title for screen readers (visually-hidden), a link to
    the waitlist or appointment page when the row links one of the patient's own. Pagination component reused.
11. `views/pages/patient_profile.py`: `/patient/profile` GET shows name and email as text, form with phone
    and date of birth (`type=tel`, `type=date`, `max` today), POST -> `update_profile`, 422 with summary or
    303 with `?notice=saved`; `/patient/profile/password` GET/POST, `Http404` when the user has no usable
    password (GET and POST); passwordless profile page shows no link to it. Password inputs
    `type=password`, `autocomplete=current-password` / `new-password`, never echoed back. Success: 303 to
    profile `?notice=password-changed`; the current session stays signed in.
12. `views/pages/patient_refusal.py`: add `waitlist_refused_page(request, failure, user)` next to
    `change_refused_page`: slot taken / conflict -> "That time was just taken." and "Back to your waitlist"
    (the entry stays WAITING? check: `accept_offer` fails inside its transaction, entry stays OFFERED; the
    page says the offer may expire and links to the waitlist); `invalid_transition` -> "This offer is no
    longer open."; `rule_violation` -> text from `refusal_for` plus the hospital phone; all with a link to
    `/patient/waitlist`. Expected values come from `refusal_for` (`domain/booking_refusals.py:25`).
13. Carried fixes from the task 14 browser check:
    a. `static/css/components.css`: `.card-list { display: grid; gap: var(--space-4); margin: 0; padding: 0;
       list-style: none; }`; appointment lists, waitlist list and notification list render as
       `<ul class="card-list"><li>` around the card (`appointments.html`, new templates). Space is the token,
       asserted by the CSS file test and by the `card-list` class in HTML; the orchestrator re-measures in
       Chrome.
    b. `domain/portal_options.py`: `expects_change_hint(status)` true only for `UPCOMING_STATUSES`; the card
       shows the "Call ..." hint only then, so completed, missed and cancelled show none. Row gets
       `show_change_hint`.
    c. `views/pages/patient_reschedule.py:50`: a failed `week_of_slots` returns the refusal page (heading
       "This change was not made", message "We could not load times for this appointment.", link "Back to
       your appointments") with status 404, instead of bare `Http404`.
14. Templates: `patient/waitlist.html`, `patient/notifications.html`, `patient/profile.html`,
    `patient/password.html`, `components/portal_nav.html`, `components/waitlist_card.html`,
    `components/notification_card.html`; edit `homes/patient.html` (nav, count links to notifications),
    `patient/appointments.html`, `components/appointment_card.html`, `patient/reschedule_times.html`. Reuse
    field, select, notice, badge, empty_state, error_summary, pagination, button-row. New CSS only for
    `.card-list` and `.portal-nav` (wrap, 44 px targets, current marked by weight plus underline, not colour
    alone). `style.html` and `DESIGN.md` get the two new components. No inline script or style.
15. `drlibre/urls.py`: eight routes under `patient/` (see 8, 10, 11); no clash with `patient/appointments`.

## Files to touch, in order

domain 1, 2, 13b + tests -> `sign_in.py` (make `record_sign_in_failure` public) -> use cases 3, 4, 5 + tests
-> homes.py (unread via block 4) -> views 8-12, 13c -> templates, CSS, style page, DESIGN.md -> urls -> view
tests -> `mutation-equivalents.txt` only for a justified survivor. `doc/backlog.md`, `doc/retro.md` are the
orchestrator's.

## Will not touch

Models, migrations, API views and schemas, `placement*`, `waitlist.py` (accept and join stay as they are),
`notifications.py` (creation), booking rules, session opening, sign-in pages, admin and clinician pages,
the booking wizard.

## Invariants and blast radius

- No double booking: accepting goes only through `accept_offer` -> `place_appointment` (exclusion constraint
  and locks stay). A refused accept leaves the entry OFFERED and writes nothing.
- Authorization from the session user (`allowed_roles = {PATIENT}`); ids in paths looked up with the record
  rule; use cases check again (`_may_accept`, `guard_record`). No patient id is read from any form.
- Audit append-only: every write calls `record_audit` inside its transaction; metadata built only through
  `AuditMetadata` (cannot carry free text). A failed password attempt writes the existing `auth.login_failed`.
- Lockout: ten failures in 15 minutes (`lockout_rules.py`) lock sign-in and password change alike, one counter.
- Blast radius: `_record_failure` rename (one file), `appointment_card.html` (home, list), `appointments.html`
  markup, `homes.py`. The rest is new.
- Cache: `render_page` never-cache headers on every page; password fields are never rendered with a value.

## Failing tests first (`returns_X_when_Y`, expected values in words)

Domain `test_profile_rules.py`: returns_no_failure_when_phone_is_empty; returns_failure_when_phone_has_6
characters; none at 7 and at 20, failure at 21; failure when phone has a letter; none for "+33 (0)1-23 45 67";
returns_failure_when_birth_date_is_tomorrow, none today and for 1990-02-28, (29 Feb of a non-leap year is
refused by the form parser: "Enter a real date"); returns_failure_when_new_password_has_9_characters, none at
10 and 72, failure at 73; returns_failure_when_new_password_equals_current.
`test_waitlist_window.py`: returns_start_of_first_day_and_start_of_day_after_last_in_hospital_zone (Paris, DST
change day gives a 23- or 25-hour day end); returns_invalid_input_when_last_day_before_first.
`test_portal_options.py`: expects_change_hint false for COMPLETED, NO_SHOW, CANCELLED; true for BOOKED, CONFIRMED,
CHECKED_IN.

Use cases:
- `test_profile.py`: stores phone and birth date and audits `profile.update` with `changed_fields` exactly
  `["phone"]` / `["date_of_birth"]`; empty input clears; unchanged -> no audit entry; audit metadata JSON does
  not contain the phone digits or the date; future date and bad phone -> `invalid_input` with field names, no
  row changed and no audit; another user's id cannot be named (actor only).
- `test_change_password.py`: right current + valid new -> password changes, other sessions deleted, own session
  kept, audit `auth.password_change` with `session_count` and no password or hash in metadata; wrong current ->
  `invalid_input` on `current_password`, one `SignInFailure` row, `auth.login_failed` audit; the 10th wrong
  attempt locks: sign-in with the right password is then refused too, and a right current password during
  lockout is refused; new equals current, 9 and 73 characters -> `invalid_input`; passwordless patient ->
  `forbidden`, nothing written; failure inside the transaction leaves password and sessions untouched.
- `test_notification_inbox.py`: newest first and paged (page 2 holds the oldest); only own notifications;
  `mark_read` sets `read_at` to the request clock, audits once, second call writes nothing; another patient's
  id -> `forbidden`, unknown id -> `not_found`, and the other patient's row stays unread; `mark_all_read`
  changes only own unread rows and audits `notification_count`; unread count drops accordingly.
- `test_waitlist_inbox.py`: own entries only, newest first; `own_entry` returns not_found / forbidden.

Views (client = `signed_in_patient`, forms through `browser_post`, one test file per page):
- waitlist: join as a browser sends it -> 303, entry WAITING with window from the dates in the hospital zone,
  audit written; missing type / reversed dates / past window -> 422, error summary, field error with
  `aria-describedby`, entered values kept; provider of another department -> 422; list shows type, window with
  zone name, status badge with word; OFFERED entry shows offered time, provider, hospital and an accept form
  with CSRF; accept -> 303 and an appointment exists, entry BOOKED; slot taken meanwhile (another patient
  booked it) -> refusal page 409 with "just taken" wording and link to the waitlist, entry unchanged; booking
  rule failure (cancel window or active-appointment overlap) -> its `refusal_for` message plus way forward;
  another patient's entry id on accept -> 403 and body has no provider name; unknown id -> 404; WAITING entry
  accept -> refusal "no longer open"; empty state with the join form still present; POST with no or foreign
  `Origin` -> 403.
- notifications: newest first, 10 per page, `?page=abc` shows page 1; unread shown with word "Unread", read
  ones without; "Mark as read" 303 and marks; another patient's id -> 403, body shows nothing of it; mark-all
  marks only own; empty state; unread count on home equals list; foreign Origin -> 403.
- profile: name and email shown as text, not inputs; phone and birth date prefilled; save 303 with `notice`;
  bad phone and future date -> 422, summary, values kept; empty clears; link to change password present only
  for a patient with a usable password; passwordless: no link, GET and POST of `/patient/profile/password` ->
  404.
- password: wrong current -> 422, message on `current_password`, field empty on re-render; 10 wrong attempts ->
  locked message; success -> 303, other client's session now redirected to sign-in, this one still works;
  inputs are `type=password` with `autocomplete` values; foreign Origin -> 403.
- portal nav: on all five section pages exactly one `<nav aria-label>` with five links, `aria-current="page"`
  on exactly the current one; one `h1`; no inline script or style (`no_inline_code`); every input labelled.
- carried: appointment list wraps cards in `card-list`; `components.css` declares `.card-list` with
  `var(--space-4)` gap; COMPLETED, NO_SHOW, CANCELLED cards do not contain "Call"; a BOOKED card under 24 h
  and a BOOKED card already started still do; reschedule page for a type with no slots source (inactive type)
  answers the refusal page with a link to `/patient/appointments`, status 404.
- access: anonymous -> sign-in with `next`; clinician -> 403 on every new page.

Each red test is proven to fail for the right reason first; `make mutate` covers the two new domain modules
and the `portal_options` change.

## Trust boundaries

Form fields (type id, provider id, two dates, phone, birth date, passwords), path ids, `?page`, `?notice`:
UUID path converter; dates parsed strictly (`date.fromisoformat`, ASCII digits) else field error; page
clamped; notice whitelisted; unknown keys in a form body are ignored by the page and never reach a use case
(the use case takes typed commands); CSRF + Origin enforced by middleware. Identity from the session only.
Passwords are never logged, never in URLs, never in audit metadata or error messages. Notification and entry
bodies carry time only (spec 11), so the page leaks no names beyond the offered provider and hospital the
spec asks for.

## Vocabulary

Patient, User, WaitlistEntry, AppointmentType, Clinician (shown "provider"), Hospital, Appointment,
Notification, AuditLogEntry, Session, SignInFailure (task 05 lockout counter).

## Not doing

No new dependency, JavaScript, endpoint, model or abstraction beyond blocks 1-5 and 7; no edit of name or
email; no delete of notifications; no per-type provider filtering with script (the use case checks the
pair); no flash framework (whitelisted `notice`); no change to booking rules or message text of the API.

## Risks

`changed_fields=["password"]` names the field only; if the reviewer reads "nothing of a password" as banning
the name too, use `counts={"session_count": n}` alone. An all-providers select on the join form is long for
big hospitals; accepted without JavaScript. A refused accept leaves the offer open until it expires, so the
page says so. Real browser, keyboard and 375 px measurement stay with the orchestrator.

## Architect review

Verdict: approve.

- Ladder: no model, migration, dependency or endpoint; join and accept reuse `join_waitlist` and `accept_offer`, which already enforce the record rule, the department check for a preferred clinician and the window checks. Blocks 1 to 5 each have one sentence of purpose. The one refactor (`_record_failure` made public) gets its second caller, so the abstraction is earned.
- Tests: the first failing tests are behaviours with boundary values (6/7/20/21, 9/10/72/73, today/tomorrow, DST day). They cover the error paths: lockout on the 10th wrong attempt, passwordless 404 on GET and POST, and foreign ids giving 403 with no leaked body. Forms go through `browser_post`, with a foreign-Origin case.
- Security: identity comes from the session, ids go through `guard_record`, and audit metadata is built only through `AuditMetadata`. Passwords are never echoed, logged or put in a URL.
- Conditions for the implementer, not blockers:
  1. Use `counts={"session_count": n}` alone for `auth.password_change` and drop `changed_fields=["password"]`. The task says audit holds "nothing of a password", and the plan's own risk note flags this reading. The cheaper reading is the safe one.
  2. In `change_password`, a wrong current password must return `Failure` without raising, so the `SignInFailure` row and the audit entry commit. A raise inside `transaction.atomic` would roll them back. Add a test that the failure row persists after the refusal.
  3. Block 12 contains an unresolved "(... check?)" aside. State the rule in code: a refused `accept_offer` leaves the entry OFFERED and writes nothing. Test that no row changed.
  4. Block 8 wording on the provider select is garbled. The intent is one select of the providers of the bookable types, with the use case rejecting a mismatched pair (already true in `join_waitlist` via `not_found`). Map that `not_found` to the field message on the provider field, not to a 404 page.
  5. The `make gate` cap is 500 lines a file and 100 a function. Keep the new view modules split as planned.
