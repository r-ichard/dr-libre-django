# Plan: task 25, accessibility and UX pass (spec section 16)

One sentence: every page meets section 16 and one walking test keeps it so; wording, templates and
style sheets change, no product rule changes.

## Focal point

`scheduling/views/pages/test_page_quality.py` (new): walks every route of the URL configuration
as signed out, patient, clinician and admin and checks the rendered HTML (item 13). It is the
red test for items 1, 2, 7, 14 and 15 and the guard for every later page. Everything else is a
block below; each block is one sentence.

Route derivation moves from `test_unique_ids.py` into `scheduling/views/pages/page_walk_support.py`
(routes, world, client per role, path filler); both tests import it. No other refactor.

## Blocks (one sentence each), in file order

Shared

- **A. Date and time for a person (item 9).** New pure `scheduling/domain/written_time.py`:
  `written_date(day)` "Monday 23 November 2026", `written_clock(moment, zone)` "13:00",
  `written_when(moment, zone)` "Monday 23 November 2026, 13:00", `with_zone_name(...)` appends
  "(Europe/Berlin)" for emails and notifications. It replaces `placement_rules._written_time`
  and the ISO text in `booked_notification_text`, `email_content.patient_email`,
  `booking_links.day_label`/`clock_label`, `slot_text`, `admin_appointments.when_text` (ISO
  today), `clinician_time_off` and `admin_appointments` line 169 (`%d %b %Y`). Left as is: the
  audit log time (`admin_audit.py:77`, seconds, UTC by section 11), `.ics` stamps, URL `starts_at`
  values, CSV export, FHIR: not read by a person as prose.
- **B. Notice by code (item 12a).** `admin_notices.admin_redirect(path, code, ids)`; the cookie
  holds signed JSON `{"code", "ids"}` (ids are UUIDs and counts only). New pure
  `scheduling/domain/notice_sentences.py` maps code + names to the sentence (verbs as today:
  "Booked an appointment for {name}." and the rest). `PageView.page` resolves names from the ids
  through an existing read in `use_cases/admin_record_reads.py` (plus one small read of patient
  name by id) and only on admin pages (`shows_admin_notice`), so the reader is an admin. Callers
  (12 sites in `admin_*.py`) pass a code and ids instead of an f-string. An unknown code, a bad
  signature or an id that no longer exists is no notice (never a 500).
- **C. Single-form measure (item 1).** `base.html` gets `{% block page_class %}`; `.page--narrow`
  in `base.css` (`max-width: 32rem; margin-inline: auto`). Used by `sign_in`, `sign_in_link`,
  `sign_in_link_invalid`, `check_email`, `booking/code`, `booking/details`, `account/password`,
  `patient/password`. Invariant: on 1440 px the first form's left edge minus the viewport's left
  edge equals the viewport's right edge minus the form's right edge (centred), width at most 32rem.
- **D. Date of birth group (item 4).** New `components/date_group.html`: `fieldset` + `legend`,
  three `input` (day, month, year; `inputmode="numeric"`, `autocomplete="bday-day|bday-month|bday-year"`,
  each with its own visible label), group error `p#id_date_of_birth_error` referenced by the
  fieldset's `aria-describedby`, `aria-invalid` on the three. `booking_forms.read_details` and
  `patient_profile` join the three posts into `date_of_birth` ISO for the existing validation
  (same messages); typed parts are kept on refusal. Summary link targets the day input.
  Used by booking details and profile (one component, two callers).
- **E. Terms and privacy (item 3).** Routes `/terms`, `/privacy` (`public_pages.py`, templates
  `legal/terms.html`, `legal/privacy.html`): plain placeholder text saying the hospital must
  supply its own. The checkbox label links both with `target="_blank" rel="noopener"` and the words
  "(opens in a new tab)", so the form is never left and what was typed stays; `checkbox.html` takes
  an optional `label_template`.
- **F. Lockout and favicon (item 5).** `sign_in.LOCKED_OUT` built from `lockout_rules.LOCKOUT_WINDOW`
  (minutes, through one tiny function in `lockout_rules.py`); hint and "check your email" text use
  `sign_in_link_rules.LINK_LIFETIME` the same way. `static/favicon.svg` fill becomes `#0b5c63`
  (the `--colour-primary` value; a test reads both files, so the token and the icon cannot drift).

Public pages and sign-in (templates/views)

- **G. Sign-in order (item 1).** `sign_in.html`: email-link form first (heading "Sign in with an
  email link"), then "Sign in with a password"; line between: "Patients use the email link.
  Clinicians and admins use a password." Focus and error summary logic unchanged.
- **H. Invalid link header (item 2).** `LinkContinuePage.post` renders the invalid page through
  `self.page(...)` (so `signed_in_user` is passed), status 400 and the referrer header unchanged.

Patient portal

- **I. Waitlist accept notice (item 6).** `patient_appointments.NOTICES["booked"] = "Your waitlist
  slot is booked."`; `AcceptOfferPage` already sets key `booked`, the list never knew it.
- **J. Headings (item 7).** `notification_card.html` `h3` becomes `h2`; the walking test lists
  any other jump (`appointment_card`, `waitlist_card`, `agenda_row` are checked by it first).
- **K. Notification time (item 8).** `patient_notifications` builds each row's time with block A in
  the zone of the notification's hospital (appointment or waitlist entry, `select_related` added
  to the read in `notification_inbox.py`); no linked hospital: "UTC" named. The card prints the
  zone name.

Clinician workspace

- **L. Time line fits (item 10).** Where the 9 px come from: the block's text width is
  column 144 px (`minmax(9rem, 1fr)`) − rail 16 px (`--rail`, block in front of a time off band) −
  padding 2 × 8 px − left border 6 px − right border 1 px = **105 px**. The time line needs the
  14 px icon (`.icon` is 1em of 14 px text) + 4 px margin (`--space-1`) + the bold "13:00–13:15"
  (96 px, measured by the orchestrator) = **114 px**. Short by **9 px**. Fix: column minimum
  `10rem` (160 px) gives 121 px, 7 px slack for a wider zone digit and a font fallback. For a band
  overlapping another band (two lanes, no rail) `time_grid.py` adds `time-grid__column--lanes-N`
  and the column's `min-width` is N × 137 px (114 + 23 frame), the track is `minmax(auto, 1fr)`.
  The grid already scrolls inside its own box below that width.
  Measurement (orchestrator, QA): for the first line of every block at 1440 px and 1024 px,
  `scrollWidth <= clientWidth`. In the sandbox the CSS test computes 160 − 16 − 16 − 7 = 121 ≥ 114
  from the style sheet's own values and fails if a value drops.

Admin console

- **M. List as cards (item 11).** `.table--stacked` in `components.css`: under 40rem `thead` is
  visually hidden, `tr` is a card, each `td` shows `attr(data-label)` before its value; from 40rem
  it is the table. Each `td` carries `data-label` equal to its `th`. Applied to `admin/list.html`
  (the shared component of every admin kind), `appointments`, `waitlist`, `audit`, `dashboard`.
  Wrapper keeps `overflow-x: auto` only from 40rem. Invariant (QA, 375 px): `document.scrollWidth
  == innerWidth` and the wrapper's `scrollWidth == clientWidth`. Test: every `td` of every admin
  table has `data-label` equal to a header text.
- **N. Conflict page shows the other save (item 12).** The stale form (409) shows a table "What
  changed since you opened this": field, "Saved by the other admin" (current value), "Your
  version" (typed), for the fields where the current value differs from the value the admin
  opened. The audit log keeps field names only (section 4), no old values, so the opened value
  comes from hidden `opened_<field>` inputs rendered on the edit form; they are used for this
  display only, never to write or authorise (the write still checks `version`). Password and
  other secret fields get none. Decision for the architect: the alternative is "yours vs now" for
  every differing field without knowing who changed it; worse, so not chosen.
  Text `STALE_TEXT` still says nothing is saved; the sentence "Saving again replaces theirs"
  stays as the consequence, below the table.

Wording and states

- **O. Statuses (item 14).** One badge (word + icon) wherever a status shows: appointment
  (patient card, agenda row, admin and clinician detail, admin list, time grid icon), waitlist
  (card, admin table), user and record `is_active` (admin list, show). Found as plain text:
  admin list status column (`ACTIVE_COLUMN`) and show page; both move to the badge.
- **P. Empty and refusal states (item 15).** Lists found without an empty state that says what is
  missing and what to do: admin dashboard "Appointments per day" table (empty table, no text),
  `details/provider.html` and `search/provider_result.html` ("No availability in the next 90
  days" with no next step; add "Try another provider or a later week" link to the search),
  `components/week_strip.html` empty week. Forms found whose refusal drops what was typed: none
  by reading; the walking test posts every POST form route with empty and bad fields and asserts
  typed text comes back (passwords excepted); fixes follow whatever it finds.
- **Q. Destructive actions (item 16).** Found: patient cancel (`patient/cancel.html`), clinician
  cancel (`clinician/cancel.html`), admin cancel (`admin/appointment_cancel.html`), admin delete
  record (`admin/delete.html`), admin deactivate user (`admin/deactivate.html`), clinician
  availability rule delete (`rule_delete.html`), clinician time off delete (`time_off_delete.html`).
  Each is reached by a GET page with a danger button and "Keep it" link; lists and detail pages
  link to it and carry no form that posts the action directly. API token revoke has no page (a
  management command), nothing to confirm. Patient leaving the waitlist has no action at all
  (needs a use case): **named, not built**. Test: GET each page shows the form and a safe link;
  list pages hold no `<form>` whose action ends in `/cancel`, `/delete`, `/deactivate`.

## Files to touch, in order

1. tests: `page_walk_support.py`, `test_page_quality.py`, edits to `test_unique_ids.py`.
2. domain: `written_time.py` (+ test), `notice_sentences.py` (+ test), `placement_rules.py`,
   `email_content.py`, `slot_text.py`, `lockout_rules.py`; tests that assert the old ISO text
   (`test_placement_rules`, `test_email_content`, `test_slot_text`, `test_appointment_emails`,
   `test_change_notification_text`, `test_patient_notifications_page`) change to the new text.
3. views: `admin_notices.py`, `page_view.py`, the 12 `admin_*.py` redirects, `sign_in.py`,
   `sign_in_link.py`, `booking_forms.py`, `booking_details.py`, `patient_profile.py`,
   `patient_notifications.py`, `patient_appointments.py`, `booking_links.py`, `time_grid.py`,
   `public_pages.py`, `admin_records.py`, `urls.py` (two routes).
4. use case read only: `notification_inbox.py` (`select_related`), `admin_record_reads.py` (name by id).
5. templates: `base.html`, `sign_in*.html`, `check_email.html`, `booking/details.html`,
   `booking/code.html`, `patient/profile.html`, `patient/notifications.html`, `legal/*.html`,
   components (`date_group`, `checkbox`, `notification_card`, `badge` callers), `admin/*.html`,
   `details/provider.html`, `search/provider_result.html`.
6. CSS: `base.css`, `components.css`, `time-grid.css`; `static/favicon.svg`; `/style` shows the
   date group, stacked table and badge states.

Not touched: models, migrations, use case rules, FHIR, API routes, audit write path, `.fabro`,
`.claude`, vendored skills, the audit-log time format, `.ics`, CSV.

## Failing tests first (`returns_X_when_Y`)

- `returns_no_finding_when_any_page_is_walked_as_each_role`: no field without label, image without
  alt, duplicate id, heading level jump or second `h1`, nameless link or button, table without `th`,
  missing `title`, `lang`, `main`. Red today on the notification page (h3 after h1).
- `returns_the_email_form_before_the_password_form_when_signed_out_opens_sign_in`.
- `returns_the_signed_in_name_when_the_link_not_valid_page_renders`.
- `returns_pages_for_terms_and_privacy_that_the_checkbox_links_in_a_new_tab`.
- `returns_three_fields_in_one_fieldset_when_details_open`; `returns_the_typed_day_month_year_and_one_group_error_when_the_date_is_refused`.
- `returns_fifteen_minutes_from_lockout_window_when_locked_out` (patched window of 5 min says 5);
  `returns_favicon_fill_equal_to_primary_token`.
- `returns_a_notice_when_a_waitlist_offer_is_accepted`.
- `returns_the_hospital_zone_name_when_a_notification_time_shows`.
- `returns_no_iso_date_when_any_notification_body_or_email_is_written` (all six kinds, booked,
  cancelled, rescheduled, reminder, offered, waitlist booked); `written_when` gives
  "Monday 23 November 2026, 13:00" for 2026-11-23 12:00 UTC in Europe/Berlin.
- `returns_121_pixels_for_the_time_line_when_a_block_sits_in_a_time_off_band` (CSS arithmetic),
  `returns_a_lane_column_class_when_bands_overlap`.
- `returns_a_data_label_on_every_cell_when_an_admin_list_renders`; the stacked class on every
  admin table.
- `returns_the_changed_fields_with_both_values_when_a_save_meets_a_newer_version`; no `opened_`
  input for a password; a forged `opened_` value changes nothing written.
- `returns_no_name_in_the_cookie_when_an_admin_action_redirects` (decoded payload holds a code and
  ids only); `returns_the_sentence_with_the_name_when_the_page_reads_the_cookie`; an unknown code
  and a deleted id give no notice. `test_admin_notices` guard stays.
- `returns_word_and_icon_when_a_status_renders` per status of appointment, waitlist, user, record.
- `returns_an_empty_state_with_a_next_step_when_a_list_has_no_rows` for each list of P.
- `returns_a_confirmation_page_when_a_destructive_route_is_opened` for each of Q.
- Mutation: `written_time.py` and `notice_sentences.py` are in `scheduling/domain`; `make mutate`
  needs tests that kill every mutant of weekday, month, zero padding and each sentence;
  equivalents go to `mutation-equivalents.txt` with a reason.

## Invariants and blast radius

Must not break: no double booking (no write path touched); authorization from session on every
page (walk test also asserts a patient still gets 403 on admin routes); audit log append-only and
free of free text (notice names are read at render, never stored); CSRF and `Origin` on every form
(new form posts go through `browser_post`); no inline script or style (CSP); every step works
without JavaScript. Blast radius: every template, three style sheets, every notification and email
text. `make gate` limits (500 lines a file, 100 a function, comment cap) stay: `components.css`
is 226 lines, fine.

## Trust boundaries

- Notice cookie: signed, 60 s, `HttpOnly`, `SameSite=Strict`; payload parsed strictly (code from a
  fixed set, ids as UUID or int); names read after session check, admin only.
- Date parts and `opened_*` inputs: client text, bounded by `input_limits`, validated by the existing
  schema; `opened_*` never reaches a use case.
- `/terms`, `/privacy`: static, public, no input.
- Links `target="_blank"` carry `rel="noopener"`.

## Domain entities (CLAUDE.md vocabulary)

Visitor, Patient, Clinician (public word "provider"), Admin, Hospital (time zone), Appointment,
AppointmentType, WaitlistEntry, Notification, AvailabilityRule, TimeOff, User, Session,
SignInLink, BookingHold, AuditLogEntry (read for nothing, written never).

## Will not do

No new dependency (HTML checks use `html.parser`), no JS, no CSS framework, no modal, no change
to a use case, model or migration, no waitlist "leave" action (named for a later task), no new
abstraction beyond `written_time`, `notice_sentences`, `date_group`, `page_walk_support`
(each has two or more callers), no change to audit, FHIR or CSV time formats.

## Unchecked in the sandbox (for the orchestrator's QA round)

Pixels: item 10 (`scrollWidth <= clientWidth` at 1440 and 1024), item 1 (centred edges), item 11
(no sideways scroll at 375), contrast of the new badge states, keyboard order on the date group.

## Architect review

Verdict: approve. Smallest sufficient change for a task that spans every page; no new dependency,
no use case, model or migration change; each block states its purpose in one sentence and uses the
vocabulary. Arithmetic of item 10 checks (144-16-16-6-1 = 105; 160-16-16-7 = 121 >= 114).
Block N is feasible: `admin_records.py:250` already holds the current record and the typed values.

Notes for the implementer (not blockers):
- Item 4: add first tests for malformed parts ("3", "x", "2000"; empty parts; day 31 in month 2).
  The join must produce the existing error, never raise, and keep every typed part.
- Block N: `admin_user_pages.py:53` also answers 409 (confirmation, no field values); decide there
  explicitly, either the same table or "nothing to compare", and say which in the reply.
- Block B: a rendered sentence must never reach a log; the name lookup runs after the admin check.
- Block K/A: stored notification bodies written before this change keep ISO text; no data migration
  is allowed, so name this in the reply (demo data is reseeded).
- Block Q: the walking test should derive destructive routes from URL names/suffixes, so a new one
  is caught, not only the seven listed.
- Block L lane widths (N x 137 px) are unmeasured; state that in the reply as unchecked.
