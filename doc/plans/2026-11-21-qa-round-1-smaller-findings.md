# Plan: task 17b, QA round 1, the smaller findings

One sentence: ten P2 findings and five leftovers of task 17a are fixed one block at a time,
each behind a test that fails first, and the hostile-input test is sharded and trimmed so
`make test` returns under 30 seconds with every route, actor and kind of value kept.

Sources read: `doc/qa/2026-11-21-round-1.md`, `drlibre-specs.md` 5.2, 6.1, 8, 10, 11, 12.3, 16,
ADR 0004, and the files named per block. Orchestrator note: the line in CLAUDE.md "DEBUG off
shows ours (403, 404, 500...)" becomes stale with block 12; update it with the merge.

## Focal point

`scheduling/use_cases/schedule_loading.py` (`active_appointment_type`, `department_clinicians`):
the single place that decides which type and which clinicians a caller may see. Blocks 1 and 4
meet there and in `placement._select`. Everything else is a local fix.

## Blocks (one sentence each), in the order of work

Order: leftovers that other blocks lean on first (13 domain move, 11, 12), then access, booking,
forms, then the test speed-up last because it needs the new fixtures of block 14.

13. **Limits into the domain.** New `scheduling/domain/request_limits.py` holds the constants
    (body bytes, fields, JSON depth, earliest and latest instant, maximum page) and the pure
    functions `json_depth`, `declared_length`, `query_field_count`, `instant_in_range`, with
    boundary tests beside it in `scheduling/domain/test_request_limits.py` (20 and 21 deep, 200
    and 201 fields, 1 MiB and 1 MiB + 1, 2000-01-01 and 1999-12-31T23:59:59Z, 2099-12-31T23:59:59Z
    and 2100-01-01, page 1_000_000 and 1_000_001); `views/input_limits.py`,
    `booking_schemas.py` and `patient_appointments.py` import from it and keep only the DRF part.
    ADR 0004 gets an "Amendment, task 17b" table: limit, shipped value, where enforced (body
    1 MiB: `refuse_oversized` for the API, Django `DATA_UPLOAD_MAX_MEMORY_SIZE` for pages; fields
    200: `refuse_oversized` for API query, `DATA_UPLOAD_MAX_NUMBER_FIELDS` for pages; JSON depth 20:
    `refuse_oversized`; instants 2000 to 2099: `OffsetDateTimeField`; page 1 to 1_000_000: the
    `AppointmentsQuery` schema, and 6 digits in the portal list). Values are read from the code, so
    the ADR states what ships, not the 17a plan.
11. **Bad `Content-Length`.** `refuse_oversized` reads the header through `declared_length`; text
    that is not a non-negative integer raises `invalid_input` naming `body`.
12. **400 page.** `errors/400.html` (same layout as 403, with correlation id), `bad_request_page`
    in `views/pages/errors.py`, `handler400` in `drlibre/urls.py`; Django calls it for
    `TooManyFieldsSent` and `RequestDataTooBig` with `DEBUG` on or off.
1.  **#17 online only.** `active_appointment_type`, `department_clinicians` and the four readers
    that call them (`find_free_slots`, `slot_choice`, `week_of_slots`, `type_providers`) take
    `online_only: bool`; true filters `is_bookable_online` and the clinicians the public search
    hides (inactive specialty or hospital); `SlotsView` and the booking pages pass
    `online_only = role is not staff`, with the role read from the optional session
    (`request.user` for the API, `self.user` for pages); clinician and admin pages keep false.
    `placement.lock_clinicians` gets the same flag for visitor and patient actors so a hold cannot
    name a hidden clinician. Unbookable type or hidden clinician answers not_found (404).
2.  **#11 forbidden vs missing.** `booking_confirmation._PatientAppointmentPage.own_appointment`
    uses `patient_appointments.own_appointment` (the `guard_record` path of the portal): missing
    gives 404, someone else's gives the 403 page, own cancelled stays 404 as today.
3.  **#22 notice once.** The query value `notice` is no longer read. The three portal pages set a
    short-lived `HttpOnly`, `SameSite=Strict` cookie `drlibre_notice` on the 303 answer, holding a
    key of the existing `NOTICES` allowlist; the next page that renders takes the text and deletes
    the cookie in the same response. One helper pair in `portal_forms.py` (`remember_notice`,
    `take_notice`) replaces the six `?notice=` redirects and three `request.GET` reads.
4.  **#16 no-room type.** `domain/placement_rules.choose_room` tests `not needs_room` before the
    named room (a mutation-covered line), and `placement._select` passes no room id to
    `lock_rooms` and `find_conflicts` for such a type, so the named room is dropped, not blocked.
    The spec says only "get none"; dropped (not refused) is the reading of the QA write-up, flagged
    for the owner.
5.  **#15 field name.** `booking_holds._invalid_input` names `date_of_birth`; the
    `USE_CASE_FIELD_NAMES` map in `booking_forms.py` is deleted.
6.  **#20 phone.** `PHONE_PATTERN`/`phone_failure` of `profile_rules` is the one rule; the hold
    use case (`_invalid_input`, so the API too) and `read_details` both call it; error on `phone`.
7.  **#21 details for a time not offered.** `DetailsPage.get` asks a new read-only
    `slot_is_offered(type, clinician, starts_at)` (built on `find_free_slots` with the same
    `online_only` flag, so it is the offered grid) and raises 404-style refusal through
    `refused_page` ("times" way) before any form; on POST the "slot taken" ("times") refusal
    re-renders the details form with values kept, the notice and a "See the refreshed times" link
    carrying the week of the chosen time. Personal details never go into a URL (§11), so choosing
    another time still starts the form again; said on the page.
8.  **#23 notification text.** `domain/placement_rules` gets `cancelled_notification_text`
    ("Your appointment on Wednesday 25 November 2026, 11:00 (Europe/Berlin) is cancelled.") and
    `rescheduled_notification_text` ("Your appointment has moved to Wednesday 25 November 2026,
    11:00 (Europe/Berlin)."); `notify_patient` takes the text builder as one defaulted parameter,
    `appointment_changes` passes the two. Booked, reminder and waitlist text unchanged.
9.  **#19 focus.** `static/js/focus_first_error.js` selects `[data-autofocus], [aria-invalid="true"]`
    (first in document order): every field, select and checkbox component marks an invalid
    control with `aria-invalid`, so every form including the profile form is covered once. No
    per-template change.
10. **#24 rounds and "enter".** `read_details` also runs birth-date (`valid_birth_date` with the
    request clock) and phone and terms checks before returning, so one answer lists everything.
    `change_password`: empty `current` gives `FieldMessage("current_password", "Enter your current
    password.")`, empty `new` gives "Enter a new password." and the checks of both fields are
    collected into one failure; a wrong non-empty current password still counts toward lockout
    and says "not right". The lockout stays one failure for a locked account.
14. **Hostile test reaches the parsing.** `test_hostile_input.py` builds one world per actor (a
    hospital, department, type, clinician profile, patient with an appointment, waitlist entry,
    notification, availability rule, time off; for a clinician the profile's own, for a patient
    their own, admin anything) and fills each path id by converter name with that record; the
    random id stays as an extra path per route. Any answer below 500 passes.
15. **Speed.** (a) Combinations proving nothing, dropped without dropping a route, actor or value
    kind: a method the route does not accept is refused before any parsing, so it gets one
    request with one value, not the whole table (`view.http_method_names`/handler lookup from the
    resolved view class); a GET carries no body, so `json` and `form` kinds, which the helper sends
    as the same plain GET today, run once as `query`; DELETE and PUT without a handler likewise.
    (b) Spread: the test is parametrised by actor times eight route shards (32 tests instead of
    4), so `-n auto --maxprocesses=4` loads all workers; each shard builds its client and world
    once. The generated-JSON `hypothesis` test stays, parametrised per actor with the same
    `max_examples`. (c) `[tool.mutmut]` ignores the hostile file
    (`--ignore=scheduling/views/test_hostile_input.py`), because it touches every domain function
    and makes each mutant run it; that is the cause of the five timeouts, to be confirmed by
    `make mutate`. Target: `make test` under 30 s, measured and written in the reply.

## Files to touch (order)

`scheduling/domain/request_limits.py` + test, `views/input_limits.py`, `views/booking_schemas.py`,
`views/pages/patient_appointments.py`, `doc/adr/0004-...md`, `views/pages/errors.py`,
`templates/errors/400.html`, `drlibre/urls.py`, `use_cases/schedule_loading.py`,
`use_cases/free_slots_query.py`, `use_cases/booking_page_data.py`, `use_cases/placement.py`,
`use_cases/placement_locks.py`, `views/slots.py`, `views/pages/booking_{times,steps,details,forms,
confirmation}.py`, `detail_pages.py`, `domain/placement_rules.py`, `use_cases/notifications.py`,
`use_cases/appointment_changes.py`, `use_cases/booking_holds.py`, `use_cases/profile.py`,
`domain/profile_rules.py`, `views/pages/portal_forms.py`, `patient_{appointments,profile,waitlist,
reschedule}.py`, `static/js/focus_first_error.js`, `views/test_hostile_input.py`, `pyproject.toml`,
plus tests beside each.

Not touched: models and migrations, `booking_refusals.py`, templates of forms (block 9 is JS
only), the confirmation email text and notification times in UTC (both carried items), the
`make` targets, `mutation-equivalents.txt` unless `make mutate` shows a new explained survivor.

## Invariants and blast radius

Double booking: the exclusion constraints and the lock order in `placement` stay; block 4 only
removes a room from the no-room path, and a test proves a named room is not blocked afterwards.
Authorization stays server-side from the session: blocks 1 and 2 add checks, never relax one;
staff keep unbookable types. Audit: no write path changes, so each existing audit entry stays in
its transaction; block 10 keeps `record_wrong_password` and the password-change audit. Blast
radius: every public booking page and `/slots` (block 1), the three portal pages (3), every form
(9), all error pages (12), the whole suite's runtime (15).

## Failing tests first (`returns_X_when_Y`)

- Slots, no session, non-online type: `returns_404_when_slots_ask_for_a_type_not_bookable_online`;
  same for a patient; `returns_slots_when_admin_asks_for_a_type_not_bookable_online`;
  `returns_404_when_booking_page_names_a_clinician_with_inactive_specialty`;
  `returns_404_when_details_page_gets_a_type_not_bookable_online`.
- `returns_403_when_confirmation_or_calendar_belongs_to_another_patient`;
  `returns_404_when_confirmation_id_does_not_exist`.
- `returns_no_notice_when_address_carries_notice_cancelled`; `returns_cancelled_notice_once_after_cancelling`
  (second GET has none); same for password-changed on the profile page.
- `returns_no_room_when_staff_book_a_type_needing_none_and_name_a_room`; domain
  `returns_none_when_type_needs_no_room_and_a_room_is_named`; the named room stays free for
  an overlapping booking of a room type.
- `returns_date_of_birth_field_when_hold_has_an_impossible_birth_date`.
- `returns_phone_error_when_details_phone_is_abc` (page and API) and none for `+49 (30) 123-456`.
- `returns_refusal_when_details_start_is_in_the_past` and `..._off_the_grid` (GET, no `<form>`);
  `returns_form_with_typed_values_when_the_slot_was_taken_meanwhile` (post sent with `Origin`).
- `returns_text_naming_the_cancelled_time_when_appointment_is_cancelled`; rescheduled likewise,
  both with "Wednesday 25 November 2026, 11:00 (Europe/Berlin)".
- Focus: a script test that the file selects `aria-invalid`, and page tests that the first invalid
  control on waitlist, password and profile carries `aria-invalid`; JS execution is not run here.
- `returns_every_error_when_details_has_future_birth_date_bad_email_and_no_terms` (one answer);
  `returns_enter_message_when_current_password_is_empty`, `..._and_new_password_is_empty_names_both`.
- API login and holds: `returns_400_invalid_input_naming_body_when_content_length_is_abc` (raw
  `CONTENT_LENGTH="abc"` through `RequestFactory`/`Client` extra, on login and one more route,
  anonymous); `returns_400_page_with_correlation_id_when_page_gets_201_fields`, `..._body_over_1_mib`.
- Domain boundary tests of block 13; the hostile test reaches parsing, plus a canary test that
  a write on an own appointment with a hostile `reason` gets a 4xx from its own parser, not 404.

Each is run red for the stated reason before its fix.

## Trust boundaries

Query, path, JSON, form and cookie values all cross in: ids parsed as UUID, dates through the
bounded field, notice cookie value looked up in a fixed dict (unknown means no notice), header
length parsed strictly, role from the session never from a payload. Anonymous callers are never
told that a hidden type or clinician exists (404).

## Vocabulary

Visitor, Patient, Clinician, Admin, AppointmentType, ClinicianProfile, Room, Appointment,
BookingHold, Notification, Session, Hospital, Specialty, WaitlistEntry, AvailabilityRule, TimeOff.

## Will not do

No new dependency, no flash framework, no model or migration, no CSS, no change to `refusal_for`,
no rewrite of the confirmation email or UTC notification times, no per-template focus changes,
no dropping of a route, actor or value kind in the hostile test. Last stage reply ends with
"Closes #11, #15, #16, #17, #19, #20, #21, #22, #23, #24".

## Risks / unchecked

Block 7's "keep what was typed" stops at the page: no personal data in URLs. Block 15's target is
a measurement; if 30 s is missed, shards or `max_examples` are the knobs, not the route table.
Focus behaviour needs a browser; only markup is tested.

## Architect review

Verdict: approve.

- Ladder: every block maps to a numbered finding; no new dependency, model or migration. Shared helpers (`remember_notice`/`take_notice`, `online_only` flag, `request_limits`) each have two or more callers.
- Layering: pure rules go to `scheduling/domain` (blocks 4, 8, 13) where mutation covers them; use cases own authorization (blocks 1, 2); views stay thin.
- Tests first: every block names a `returns_X_when_Y` test with spec-derived values, edge and error paths included (boundary pairs for limits, raw `CONTENT_LENGTH`, `Origin` on form posts).
- Security: notice cookie is HttpOnly, SameSite=Strict, allowlisted key, deleted on read; hidden type or clinician answers 404 to anonymous and patient; staff keep access; no personal data in URLs.
- Scope: all 15 items covered, ADR 0004 amendment and the stale CLAUDE.md line are named.

Watch items (not blockers):
- Block 4: QA #16 expected text should be re-read when writing the test; "dropped" is the plan's reading, keep it flagged for the owner.
- Block 1: a hold made earlier for a now-hidden clinician or type should not break confirm; test it or state it.
- Block 15: the 30 s target is a measurement; run `make mutate` to confirm the timeout cause, and keep "one `query` request per GET route" from silently losing the hostile-body kinds on routes that do accept bodies.
- Block 3: cookie set on the 303 must also be deleted when the redirect target is never rendered (expiry, a short `max_age`, is enough).
