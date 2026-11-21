# Plan: task 12a, booking pages

One sentence: server-rendered pages (times, details/review, code, confirmation) and a calendar file, thin views over the existing use cases of tasks 07 and 12, with every piece of pure logic (week, email masking, iCalendar text, refusal wording) in `scheduling/domain` where `make mutate` covers it.

Focal point: `scheduling/views/pages/booking_pages.py` (the views). Everything else feeds it.

## Addresses (what 10a and 11 will link to)

No personal detail in any address; times, type and provider ids are not personal.

| Address | Method | What |
| --- | --- | --- |
| `/book/<type_id>?provider=<clinician_id>&week=<YYYY-MM-DD>` | GET | Times. No `provider` = first available in the type's department. `week` is any date in the wanted week, default this week in the hospital's zone; an unparsable or out-of-range (past week, more than 52 weeks ahead) value falls back to the current week. |
| `/book/<type_id>/details?provider=&starts_at=<UTC instant>` | GET | Visitor: details form. Signed-in patient: review page (optional reason, Confirm). |
| same address | POST | Visitor: create hold, 303 to the code page. Patient: place appointment, 303 to confirmation. Errors re-render with 4xx. |
| `/book/holds/<hold_id>/code` | GET, POST | Code page; POST verifies, sets session cookie, 303 to confirmation. |
| `/book/holds/<hold_id>/resend` | POST | New code, 303 back to the code page with `?sent=1`. |
| `/appointments/<appointment_id>/confirmation` | GET | Patient owner only. |
| `/appointments/<appointment_id>/calendar.ics` | GET | Patient owner only, `text/calendar`, attachment. |

The hold id (UUID, unguessable) addresses the pages after the details. The code page shows only the masked email and the appointment; the code itself still gates the booking.

## Blocks (one sentence each)

1. `scheduling/domain/booking_week.py` (new, pure): given a date and zone, return the Monday-to-Sunday `TimeRange` in UTC, previous/next week starts, and group slot starts into local days.
2. `scheduling/domain/email_mask.py` (new, pure): `mask_email("pat.smith@example.test")` keeps the first character and the domain: `p***@example.test`.
3. `scheduling/domain/calendar_event.py` (new, pure): builds the iCalendar text: CRLF, text escaping, 75-octet folding, UTC `DTSTART`/`DTEND`, `SUMMARY`, `LOCATION`, stable `UID`, `DTSTAMP` from the request clock, no `DESCRIPTION`.
4. `scheduling/domain/booking_refusals.py` (new, pure): maps a `Failure` to a `Refusal(message, way_forward_kind, status)`: slot taken (`conflict`, `no_clinician_available`, `no_room_available`, rule `outside_availability`), each booking rule in plain words, rate limit, mail down, not found or expired hold.
5. `scheduling/use_cases/booking_page_data.py` (new): read-only loaders for the pages: type + provider + hospital + department summary, hold summary (masked email, appointment, code attempts left, code expired), confirmation and calendar data for one patient. No writes, so no transaction and no audit entry.
6. `scheduling/views/pages/booking_pages.py` (new): times, details/review views. `booking_code_pages.py` (new): code, resend. `booking_confirmation_pages.py` (new): confirmation, calendar file. Each view parses, calls a use case, formats. Authorization from session, never payload.
7. `scheduling/views/pages/booking_form.py` (new): parse and validate the details form (required, lengths 200/254/30/reason max of the API, birth date parse) into `HoldCommand` and field errors keyed by form field; maps the use case's `birth_date` message to the `date_of_birth` field.
8. `scheduling/views/pages/week_strip.py` (new): view-model builder from `FoundSlots` + week into days, slot links, previous/next links, zone name. Reused later by provider page, reschedule, wizard.
9. Templates (new): `booking_times.html`, `booking_details.html`, `booking_review.html`, `booking_code.html`, `booking_confirmation.html`, `booking_refused.html`, `components/week_strip.html`, `components/appointment_summary.html` (chosen appointment, reused by details, review, code), `components/textarea.html`.
10. `components/checkbox.html` and `components/field.html`: add optional `error`, `autofocus` (checkbox) and `inputmode` (field). Backward compatible; sign-in tests guard them.
11. `static/css/components.css`: week strip, summary list, slot buttons (2.75rem tap target, 375 px: days stack, 1440 px: seven columns). `style.html`: show week strip and textarea in each state. Existing `focus_first_error.js` is reused; no new script.
12. `drlibre/urls.py`: seven routes above.

## Order of work

Domain tests and code (1 to 4), use-case loaders (5) with tests, components (8, 10, 11) with `/style`, forms and views (6, 7) by page: times, details+hold, code, confirmation+calendar, review, refusals. `doc/backlog.md`: set 12a to done only after the run, not in this task's code.

## Not touching

`placement*.py`, `booking_holds.py`, `booking_verification.py`, the API views and schemas, models, migrations, `base.html`, `focus_first_error.js`, search code. No new dependency, no JavaScript, no new setting.

## Invariants

- No double booking: pages call only `create_hold`, `verify_hold`, `place_appointment`; no page checks availability itself. A slot taken between page and POST arrives as a `Failure` and is shown, never ignored.
- Authorization server-side: patient actor is `self.user` from the session; a clinician or admin who opens a booking page gets the 403 page; confirmation and calendar answer 404 for any appointment not the signed-in patient's (no existence leak). No patient id, room id or end time is read from a form.
- Audit: unchanged, written by the use cases inside their transactions. Loaders write nothing.
- Never cached: pages go through `render_page` (never-cache headers); the calendar response sets the same headers. Test asserts `Cache-Control` on details, code, confirmation and the file.
- No sensitive data in logs, URLs or the calendar file: never reason or notes. Hold page never shows the full email or the name.
- Clock only from the request context (`current_request_context().now`); UTC explicit; hospital zone via `ZoneInfo`.

Blast radius: `urls.py`, shared `field`/`checkbox` components and `components.css`. Everything else is new files.

## Trust boundaries

| Boundary | Validation |
| --- | --- |
| Query `provider`, `starts_at`, `week` | UUID and ISO parse; bad value gives 404 (ids, instant) or current week (week); use cases re-check type, clinician and slot. |
| Details POST | `booking_form` plus use-case rules; CSRF enforced; `Origin` checked by Django. |
| Code POST | 6 digits regex; use case counts attempts. |
| Hold id in path | UUID converter; unknown or expired gives the expired page (404-class, no detail). |
| Confirmation and calendar | Session user must be the appointment's patient. |
| Calendar text | Escaped and folded in the domain function; filename fixed. |

## Failing tests to write first

Domain (`scheduling/domain/`):
- `returns_monday_to_sunday_in_utc_when_week_is_asked_for_a_date_in_sydney`: 2030-01-09 gives local 2030-01-07 00:00 to 2030-01-14 00:00 as UTC instants.
- `returns_a_seven_day_range_of_23_or_25_hours_shifted_when_a_clock_change_is_inside_the_week`.
- `returns_previous_and_next_monday_when_week_is_computed`.
- `returns_slots_grouped_under_their_local_day_when_utc_dates_differ` (a 23:30 UTC slot belongs to the next Sydney day).
- `returns_first_letter_and_domain_when_email_is_masked`; `returns_stars_and_domain_when_local_part_is_one_letter`.
- `returns_utc_start_and_end_summary_and_location_when_event_is_built`; `returns_no_description_when_event_is_built` (reason string passed nowhere); `escapes_comma_semicolon_backslash_and_newline_in_text`; `folds_lines_longer_than_75_octets_with_a_leading_space`; `ends_every_line_with_crlf`.
- `returns_slot_taken_with_link_back_to_times_when_conflict`; one test per rule code, each with its plain sentence (lead time: "Appointments must start at least 2 hours from now."; too many bookings: "You already have 3 upcoming online bookings."; type not online: "This appointment type cannot be booked online."; outside availability counts as slot taken); `returns_wait_an_hour_when_rate_limited`; `returns_try_again_in_a_few_minutes_when_mail_is_unavailable`; `returns_start_again_when_hold_not_found`.

Use cases (`scheduling/use_cases/`):
- `returns_masked_email_and_attempts_left_when_hold_is_open`; `returns_none_when_hold_is_expired`; `returns_appointment_only_for_its_own_patient`.

Views (`scheduling/views/pages/`, every POST through `browser_post`, Origin set, CSRF enforced; each page also checks no inline script or style):
- Times: `returns_week_of_slots_in_hospital_zone_naming_zone_type_duration_provider_hospital_and_address`; `returns_links_to_details_with_provider_and_start_when_slot_is_listed`; `returns_previous_and_next_week_links`; `returns_first_available_slots_when_no_provider_given`; `returns_404_when_type_or_provider_unknown`; `returns_current_week_when_week_is_not_a_date`; `returns_empty_state_with_next_week_link_when_week_has_no_slots`.
- Details: `returns_form_with_six_labelled_fields_and_chosen_appointment_when_visitor_opens_details`; `returns_303_to_code_page_and_creates_hold_when_details_are_valid` (address contains no name, email, birth date); `returns_field_errors_tied_by_aria_and_first_invalid_focused_when_details_are_invalid` (name, email, birth date, terms; one `data-autofocus`); `returns_403_when_post_has_no_csrf_token_or_wrong_origin`; `keeps_typed_values_but_not_when_refused`; `returns_review_page_without_details_form_when_patient_is_signed_in`; `returns_303_to_confirmation_and_books_when_patient_confirms`; `returns_403_page_when_clinician_opens_booking`.
- Code: `returns_masked_email_ten_minutes_and_resend_button_when_code_page_opens` (full address absent from HTML); `returns_303_to_confirmation_with_session_cookie_when_code_is_right`; `returns_message_with_tries_left_when_code_is_wrong`; `returns_send_new_code_message_when_attempts_are_used_up`; `returns_hold_expired_page_with_start_again_link_when_hold_expired`; `returns_sent_notice_after_resend`; `returns_rate_limit_message_when_resend_is_limited`.
- Confirmation: `returns_provider_title_specialty_date_time_zone_hospital_address_department_room_when_confirmed`; `omits_room_when_none_assigned`; `states_confirmation_email_sent_and_links_to_calendar_file_and_patient_appointments`; `returns_404_when_another_patient_opens_it`; `redirects_to_sign_in_when_not_signed_in`.
- Calendar: `returns_text_calendar_attachment_with_utc_times_hospital_location_and_no_reason_or_notes`; `returns_404_for_other_patient_and_for_cancelled_appointment`; `sets_never_cache_headers`.
- Refusals: `returns_slot_taken_page_409_with_times_link_when_slot_taken_between_page_and_post`; `returns_rule_message_when_lead_time_too_short`; `returns_429_page_when_hold_rate_limited`; `returns_503_page_with_retry_message_when_mail_is_down` (no hold left behind).
- Accessibility the server can prove: one `h1` per page, `lang`, every input has a label `for`, error ids referenced by `aria-describedby`, week strip is a labelled list with link text carrying date and time (not time alone), previous/next are links with text, slot links at least differ by accessible name, no colour-only status.

Each test is proved to fail before the code (red proven); domain tests go through `make mutate`.

## Domain vocabulary used

Visitor, Patient (passwordless), Clinician (shown as "provider"), Hospital, Department, Specialty, AppointmentType, ClinicianProfile, Room, Appointment, BookingHold, VerificationCode, Session.

## Decisions I make that the architect may reject

- Terms and privacy have no pages yet: the checkbox label names them without links. Flag in review.
- Expired-hold page links to `/`, because the hold row (and with it the type and provider) is gone; search (10a) will improve this. Slot-taken refusals keep the type and provider in hand and link to the refreshed times.
- Wrong, used-up and expired code share one use-case answer by design (no leak). The page tells them apart from the hold summary (attempts left, code expiry), which the hold id already addresses.
- A cancelled appointment has no calendar file (404).

## Will not do

No admin or clinician booking pages, no reschedule page, no search or provider pages, no JavaScript, no client-side validation, no change to use-case contracts, no new abstraction beyond the week strip, which the task requires. The Chrome pass (375 and 1440 px, keyboard, audit) belongs to the orchestrator; the sandbox cannot run it.

Done: `make setup && make lint && make test && make gate && make mutate`.

## Architect review

Verdict: approve.

- Ladder: new files only, one shared abstraction (week strip) which the task demands. Pure logic in `scheduling/domain`, so mutate covers it. No new dependency.
- Layers: views thin, loaders read-only, writes only through `create_hold`, `verify_hold`, `place_appointment`. Authorization from session; confirmation and calendar 404 for non-owners.
- Security: no personal data in addresses, never-cache on personal pages and the file, no reason or notes in the calendar, masked email only, CSRF and Origin tested through `browser_post`.
- Tests: named as behaviours with expected values, error paths included.
- Watch in implementation (not blocking):
  1. Check refusal mapping against the real `Failure` codes (`lead_time_too_short`, `too_many_open_bookings`, `conflict`, `no_clinician_available`, `no_room_available`, `outside_availability`, plus the not-online rule); add a test that every code the use cases can return has a refusal, so none falls to a generic error.
  2. Resend by hold id alone: rate limit must be keyed on the hold, and the "code page tells wrong from used-up" logic must not expose more than the hold id already allows.
  3. Keep each file under the 300-line / 50-line-function limits; `components.css` may need splitting.
  4. Terms and privacy without links: accepted, record as follow-up for the pages task.
