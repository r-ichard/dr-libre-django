# Task 14: patient portal, home and appointments

Spec: section 8, 7.4, 5.3, 5.6, 12.3. Pages only: every change goes through the existing
`cancel_appointment`, `reschedule_appointment`, `place_appointment` (`use_cases/appointment_changes.py`,
`placement.py`). No new booking rule, no new endpoint of the API.

## Focal point

`scheduling/domain/portal_options.py` (new, pure): given status, start, now, it says whether a
patient may cancel / reschedule and, if not, the plain-words reason. The list rows, the cancel page
and the reschedule page all read it, so the rule text lives once. It reuses `violated_rules`
(`domain/booking_rules.py:49`), `can_transition`, `RESCHEDULABLE_STATUSES`
(`domain/appointment_status.py`); no rule is copied.

## Blocks, one sentence each

1. `domain/portal_options.py`: `is_upcoming(status, starts_at, now)`; `appointment_options(...)` ->
   cancel/reschedule each allowed or a reason (cancelled, over, started, less than 24 hours, checked in).
2. `domain/portal_refusals.py`: `change_refusal_for(failure)` -> message, way forward, HTTP status for cancel
   and reschedule refusals; defers to `refusal_for` (`domain/booking_refusals.py:25`) for booking rules and
   slot taken. Needed because `refusal_for` answers "That time was just taken." for `invalid_transition`
   and a booking-worded text for `forbidden`.
3. `use_cases/patient_appointments.py`: `upcoming(patient, now)` soonest first, `past_page(patient, now, page,
   size)` latest first with count, `next_upcoming`, `unread_notification_count` (Notification `read_at` null,
   recipient = patient), `own_appointment(id, patient)` via `guard_record`
   (`use_cases/record_access.py`): `not_found` / `forbidden` (12.3).
4. `use_cases/booking_page_data.py` (add): `bookable_services()` active + `is_bookable_online` types grouped hospital >
   department; `type_providers(type_id)` via `department_clinicians`
   (`use_cases/schedule_loading.py:106`).
5. `views/pages/patient_rows.py`: mapper appointment -> row dict (whom, when with zone named, where,
   phone, type, badge kind+text, reason, options, hrefs). Reuses `day_label`, `clock_label`, `address_of`
   (`booking_links.py`).
6. `views/pages/homes.py` `PatientPortal`: greeting, next appointment (card), unread count, "Book an appointment"
   -> `/book`; empty state when none.
7. `views/pages/patient_appointments.py`: `/patient/appointments` lists (`?page=` past, `?notice=cancelled|rescheduled`
   whitelisted, no personal data in URL), pagination component, two empty states.
8. `views/pages/patient_cancel.py`: GET confirmation page, POST validates required reason
   (`CancelRequest`, `CANCELLATION_REASON_MAXIMUM`, `views/booking_schemas.py:164`) via `validate_body`, calls
   `cancel_appointment`, 303 to list; 422 with error summary on empty reason; refusal page otherwise.
9. `views/pages/patient_reschedule.py`: GET week strip for same clinician and type
   (`week_of_slots` + `week_strip`), GET review (old and new time), POST calls `reschedule_appointment`.
10. `views/pages/booking_times.py`: `week_strip` gets an optional `slot_href` callable (default `details_href`) so
    reschedule links to its review; `detail_context.py` caller unchanged.
11. `views/pages/booking_steps.py`: `/book` (service) and `/book/<type>/provider` (named or "First available" ->
    existing `/book/<type>[?provider=]`, `TimesPage`). Times page gets "Change provider" / "Change service"
    links. Search page gets a "Browse all services" link to `/book`; hospital, specialty, provider pages
    already lead to the times step.
12. Templates: `homes/patient.html`, `patient/appointments.html`, `patient/cancel.html`,
    `patient/reschedule_times.html`, `patient/reschedule_review.html`, `booking/service.html`,
    `booking/provider.html`, `components/appointment_card.html`; `booking/refused.html` takes optional
    `heading`. Reuse badge, notice, empty_state, field, error_summary, pagination, week_strip,
    booking_summary. `static/css/components.css`: card variant for appointments, button-row spacing only.
    `style.html` shows the new component (DESIGN.md: every component at `/style`). `DESIGN.md` one line.
13. `drlibre/urls.py`: `/patient/appointments`, `.../<id>/cancel`, `.../<id>/reschedule`,
    `.../<id>/reschedule/review`, `/book`, `/book/<type>/provider`. `/book` must precede `book/<uuid>`;
    no clash.

## Files to touch, in order

domain (1,2) + tests -> use cases (3,4) + tests -> `booking_times.py` (10) -> mapper (5) -> views (6-9, 11)
-> templates, CSS, style page -> urls -> view tests -> `mutation-equivalents.txt` only if a survivor is
justified; `doc/backlog.md` is the orchestrator's.

## Will not touch

Models, migrations, the API views, `placement*`, `appointment_changes.py`, booking rules, sessions, sign-in
(`/patient/` already is the landing, `HOME_PATHS`), waitlist, notifications list, profile (task 15), the
existing confirmation page and calendar view (reused as is: 404 for another's or a cancelled appointment).

## Invariants and blast radius

- No double booking: reschedule and book only through the use cases (exclusion constraint + locks stay).
- Authorization from the session user only (`PageView.allowed_roles = {PATIENT}`); id in the path is looked
  up with `own_appointment`; never trust a patient id in the body. Staff get the 403 page, anonymous go to
  `/sign-in?next=`.
- Every write audited inside the use case transaction; the pages add none.
- Blast radius: `week_strip` signature (two callers), `refused.html` heading, `PatientPortal` template, search
  page link. Everything else is new.
- Cache: `render_page` already adds never-cache headers; the `.ics` view too.

## Failing tests first (`returns_X_when_Y`)

Domain `test_portal_options.py`, `test_portal_refusals.py`:
- returns_both_allowed_when_booked_and_starts_in_25_hours
- returns_cancel_allowed_when_start_is_exactly_24_hours_away; refused "less than 24 hours" at 23h59
- returns_started_reason_when_start_is_now_or_past; returns_cancelled_reason_when_cancelled
- returns_over_reason_when_completed_or_no_show; returns_checked_in_reason_for_reschedule_only
- is_upcoming: true for BOOKED/CONFIRMED/CHECKED_IN in future, false at start == now and for the other statuses
- refusal: invalid_transition -> "no longer allows"; window -> "less than 24 hours" with phone way; forbidden/not_found messages; slot taken -> times

Use cases `use_cases/test_patient_appointments.py`:
- returns_upcoming_soonest_first_and_past_latest_first; past paged (page 2 holds the oldest)
- returns_only_own_appointments; returns_zero_unread_when_all_read_or_other_patients
- own_appointment returns not_found for unknown id, forbidden for another patient's
- bookable_services excludes types not bookable online or inactive, groups by hospital and department

Views `views/pages/test_patient_*_pages.py` (client from `signed_in_patient`, forms through `browser_post`):
- home: greeting with name, next appointment shown, unread count, "Book an appointment" links `/book`; empty state
- list: row text lists provider + title, specialty, date, start-end, zone name, hospital + address,
  department, room, type, badge with word, reason; under 24 h row shows reason and hospital phone, no cancel
  button; cancelled row says already cancelled; past list paged; both empty states with an action
- returns_404_when_appointment_id_unknown, returns_403_when_appointment_belongs_to_another_patient on GET and POST
  of cancel, reschedule, review; body never contains the other patient's provider or reason
- returns_403_when_post_has_no_origin_or_other_origin (cancel, reschedule): as a browser sends it
- cancel: 422 + error summary + field focus when reason empty; 303 and status CANCELLED, reason stored,
  AuditLogEntry written when reason given; second POST answers refusal page, "already cancelled" wording
- reschedule: week lists only the same clinician's free slots; review shows old and new time; POST 303, start moved;
  slot taken meanwhile -> 409 refusal with link to the refreshed week; less than 24 h -> refusal with the reason
- book steps: service groups by hospital > department; provider lists "First available" and named providers; links
  land on `/book/<type>` with and without `?provider=`; unknown type 404
- access: anonymous redirected to sign-in with `next`; clinician gets 403
- cache: `Cache-Control` has `no-store` (or `no-cache, private`, as `add_never_cache_headers` sets) on every portal page
- HTML: one h1, labelled landmarks, every input labelled, link text discernible (visually-hidden appointment
  name on repeated "Cancel"/"Reschedule"), `lang`, no inline script or style (`no_inline_code`),
  status badge has text plus icon

Each red test proven to fail for the right reason before green; `make mutate` on the two new domain modules.

## Trust boundaries

- Path id, `?starts_at`, `?week`, `?page`, `?notice`: UUID path converter; `instant_from` / `week_from`;
  page clamped to >= 1; notice whitelisted. Bad value -> 404 or default, never a 500.
- POST reason: `validate_body(CancelRequest)`, server checks, CSRF + Origin enforced by middleware.
- Own record: session user -> `own_appointment` / use case `_may_change`; both agree.

## Vocabulary

Patient, User, Appointment, AppointmentType, Clinician (shown as "provider"), ClinicianProfile, Specialty,
Hospital, Department, Room, Notification, AuditLogEntry.

## Not doing

No new dependency, no JS (existing `focus_first_error.js` only), no new abstraction beyond blocks 1-5, no change
to rules or messages of the API, no flash-message framework (a whitelisted `notice` query), no waitlist,
notification list or profile links beyond what exists. A reschedule week strip hides the appointment's own
neighbouring slots that the use case would accept (self ignored there); a known, small gap, listed in risks.

## Risks

Reschedule strip derived from `find_free_slots` counts the appointment itself as busy; the use case does not.
Old type deactivated -> reschedule page 404. Real browser, keyboard and audit stay with the orchestrator.

## Architect review

Verdict: approve.

- Ladder: two new pure domain modules, two use-case modules, thin views, no dependency, no model or API change. Reuses `violated_rules`, `guard_record`, `week_strip`, existing components. Blocks 1-5 each have a second caller, so the abstractions hold.
- Knowledge: each block states its purpose in one sentence; vocabulary matches CLAUDE.md.
- Tests: named as behaviours with spec values (24 h boundary exact and 23h59, status sets, 404 vs 403 on GET and POST, Origin as a browser sends it, 422 on empty reason, slot taken 409, never-cache, no inline code).
- Security: the patient comes from the session, the id is looked up through `own_appointment`, the use case checks again, the query params are whitelisted or clamped, the body goes through `validate_body`, and no personal data appears in URLs. The audit entry is written inside the use case transaction.
- Architecture: the boundary only formats, expected failures are values, and refusals are mapped in one place.
- Minor, not blocking: add a test that the calendar file and confirmation page of another patient's appointment answer 404 or 403, since they are reused as is. Also test a BOOKED appointment whose start has passed: it lists as past, with no cancel offered.
