# Task 25b: UX pass, booking and the patient's pages

One sentence: three small, separate blocks (legal pages, date-of-birth group, one written
moment) each at its existing seam, with no use case, model or migration changed.

Reading done: `booking_forms.py`, `booking_details.py`, `patient_profile.py`, `portal_forms.py`,
`components/field.html`, `checkbox.html`, `base.html`, `email_content.py`, `placement_rules.py`,
`notifications.py`, `email_delivery.py`, `patient_notifications.py`, `page_walk_support.py`,
`test_page_quality.py`, `drlibre/urls.py`.

Assumption on item 3: the sentence "the notifications ... and every email, write `2026-11-23 at
13:00`" names the defect (today's wording), as item 9 of task 25 says. Target = ONE way
everywhere: "Monday 23 November 2026, 13:00 (Europe/Berlin)". Say so in the PR if wrong.
Assumption on item 2: "A date of birth is in the past" reads backwards; the message will be
"A date of birth must be in the past". Flag to the owner.

## Block 1: terms and privacy pages

Focal point: `scheduling/views/pages/legal_pages.py`.

- `legal_pages.py` (new): `TermsPage`, `PrivacyPage`, both `PageView`, no role required, GET only,
  static template. Routes `terms`, `privacy` in `drlibre/urls.py` (page_routes() walks them
  automatically, so the quality test covers them signed out and as each role).
- `templates/legal/terms.html`, `privacy.html` (new): one `h1`, plain placeholder text: "This is
  placeholder text. The hospital must supply its own terms before DrLibre is used for real."
  plus a line "Close this tab or use your browser's back button to return to your booking."
- `base.html` footer: two links, Terms, Privacy notice, on every page (error pages extend base? if
  one does not, it gets them too via the same footer include; checked by the test).
- `booking/details.html`: checkbox label stays "I accept the terms and the privacy notice"; text
  after the checkbox hint: `<a href="/terms" target="_blank" rel="noopener">terms (opens in a new
  tab)</a>` and the privacy equivalent, via `hint` of `checkbox.html` (no new component).
- **Keeping what was typed, no script:** the links open in a NEW TAB. The details form lives on
  untouched in the first tab, so nothing is lost and no state is stored (no draft in session, no
  cookie with personal data, no script). The reader closes the tab to come back; the legal pages
  say so. Rejected: draft in session (stores health-adjacent personal data server-side for no
  need); same-tab link relying on browser back (restore is the browser's choice, not ours).
- Not touched: `terms_accepted_at` storage, hold use case, API.

## Block 2: date of birth, three fields

Focal point: pure `scheduling/domain/date_parts.py`.

- `date_parts.py` (new, domain, mutation gate): `read_birth_date(day, month, year, today,
  required) -> Success[date | None] | Failure-like value` returning either the date or one error
  message. Order of checks, first wins, one error for the group:
  all three empty -> "Enter your date of birth." if required else value None (profile: removes it);
  empty day -> "Enter a day"; empty month -> "Enter a month"; empty year -> "Enter a year";
  a part not all ASCII digits -> "Use numbers only"; year not 4 digits -> "Enter a year with four
  digits"; `date(year, month, day)` ValueError -> "That date does not exist"; date today or later
  -> "A date of birth must be in the past"; older than `valid_birth_date` allows -> "Enter a valid
  date of birth". Reuses `valid_birth_date` from `visitor_rules.py` (no second copy of the rule).
  Expected errors are values, not exceptions (§9).
- `templates/components/date_group.html` (new): `fieldset` + one `legend`, optional hint, one
  error paragraph (`id_<name>_error`, icon + "Error:" like `field.html`), three inputs with
  visible labels Day / Month / Year, `name` = `<name>_day|_month|_year`, `inputmode="numeric"`,
  `pattern="[0-9]*"`, `maxlength` 2/2/4, `autocomplete` `bday-day`/`bday-month`/`bday-year`,
  `aria-describedby` on every input pointing at hint and error, `aria-invalid` on the group's
  inputs when it has an error, `data-autofocus` on the first input when it is the first error.
  Ids stay unique (`id_date_of_birth_day` ...; unique-id test).
- `static/css/components.css`: `.date-group` flex row, `gap`, `flex-wrap: wrap`; inputs
  `width: 4.5rem`, `4.5rem`, `6rem` via tokens. Invariant: at 375 px the group's `scrollWidth <=
  clientWidth` and every input edge sits inside the column. Measurement by numbers: 15 rem + 2
  gaps (2 x 1 rem) = 17 rem = 272 px < 375 px - 2 x page padding (read the token; state it in the
  test of the CSS, in the style of `test_time_grid_css.py`). No inline style/script.
- `booking_forms.py`: `TEXT_FIELDS` keeps the key `date_of_birth` for the JOINED ISO string (so
  `DetailsSchema`, `hold_command_of`, `HoldCommand.birth_date` and the use case receive the same
  `date`). `read_details` reads the three posted parts, calls `read_birth_date`, stores the three
  parts in `form.values` (`date_of_birth_day|month|year`) for re-render and the ISO string in
  `form.valid`; error key stays `date_of_birth`. Summary target for it = `id_date_of_birth_day`
  (first part with the problem). `_add_rule_failures` loses its date branch (now in the domain
  function); use-case failure `date_of_birth` ("Enter a valid date of birth.") still renders in
  the group.
- `patient_profile.py`: `post` reads the three parts, `required=False`; `get` splits the stored
  date into parts; `REAL_DATE` constant and `today`/`max` context removed; use case gets the same
  `date | None`. `portal_forms.day_or_none` stays (used elsewhere; checked by grep before delete).
- Templates `booking/details.html`, `patient/profile.html`, and the `/style` sample
  (`style.html`, `public_pages.SAMPLE_ERRORS`) use `components/date_group.html`.
  `focus_first_error.js` already follows `data-autofocus`; no script change.
- Not touched: API (`DateField` ISO on `/api/v1/booking/holds`), FHIR, models.

## Block 3: one way to write a moment

Focal point: pure `scheduling/domain/written_moment.py`.

- `written_moment.py` (new, domain, mutation gate): `written_moment(moment: datetime, zone:
  ZoneInfo) -> str` = "Monday 23 November 2026, 13:00 (Europe/Berlin)"; zone key always named;
  moves the `_written_time` of `placement_rules.py` here.
- Callers switched (one line each):
  `placement_rules.booked_notification_text` and `cancelled_notification_text` (and the
  reschedule text if it sits beside them), `email_content.patient_email` "When:" line,
  `patient_notifications._shown_at` (zone "UTC" named when the notice has no hospital).
  `booking_links.day_label` / `clock_label` and the ranges ("09:00 to 09:30") stay: they write a
  day or a span, not a moment, and the booking summary already shows the zone in its own row.
- Other emails (`verification_code_email`, `sign_in_link_email`) hold no date; the sweep test
  proves it, so a future date there fails.
- Demo seed books through the use cases: no seed code changes; a seed test asserts the result.

## Files, in order

1. tests (below), failing; 2. `domain/date_parts.py`, `domain/written_moment.py`; 3. callers of
written_moment; 4. `components/date_group.html`, CSS, `booking_forms.py`, `patient_profile.py`,
two templates, `/style`; 5. `legal_pages.py`, templates, `urls.py`, `base.html`, details hint;
6. `mutation-equivalents.txt` only for mutants explained as equivalent.

Deliberately not touched: use cases, models, migrations, serializers of API and FHIR, hold and
verification flow, `focus_first_error.js`, `field.html` (unless `max` becomes unused: then
remove it), grid and range labels.

## Invariants and blast radius

Double booking, server-side authorization, append-only audit log: untouched (no use case, no
write path changes). Hold still requires `terms_accepted`; the use case still validates the
birth date and the form's check is advisory. Blast radius: every page (footer), two forms,
notification and email wording (existing tests that pin "2026-11-23 at 13:00" are updated to the
new wording in the same step).

## Failing tests first (`returns_X_when_Y`)

Domain (`test_date_parts.py`, `test_written_moment.py`):
- returns_enter_a_year_when_year_is_empty; same for day and month ("Enter a day", "Enter a
  month").
- returns_that_date_does_not_exist_when_day_is_31_and_month_is_april; also 29 February 1990.
- returns_the_leap_day_when_year_is_2000_and_date_is_29_february.
- returns_must_be_in_the_past_when_date_is_today or tomorrow.
- returns_use_numbers_only_when_a_part_holds_letters, a minus sign, a space or a full-width digit.
- returns_four_digits_when_year_is_85.
- returns_none_when_all_three_are_empty_and_not_required; returns_enter_your_date_of_birth when
  required.
- returns_a_valid_date_when_year_is_exactly_120_years_back (boundary from `valid_birth_date`).
- written_moment: returns_monday_23_november_2026_1300_europe_berlin_when_utc_is_12_00; a
  Sydney moment that falls on the next local day; single-digit day has no leading zero.

Pages, as a browser sends them (CSRF enforced, `Origin` header set; `test_browser_forms.py`
pattern):
- returns_three_labelled_inputs_in_one_fieldset_when_details_page_is_rendered: one `legend`,
  `inputmode="numeric"`, `autocomplete` `bday-day|bday-month|bday-year`, no `type="date"`.
- returns_422_with_one_error_for_the_group_and_every_typed_value_when_year_is_empty
  (error text "Enter a year", appears once, inputs keep day/month; summary link targets the first
  bad part; `aria-describedby` points at an existing id).
- returns_303_to_code_page_and_hold_with_birth_date_1985_03_14_when_parts_are_14_3_1985.
- same two for the patient profile; returns_profile_saved_with_no_birth_date_when_all_three_empty;
  profile shows stored date split into three values.
- returns_422_and_reflects_nothing_unescaped_when_a_part_holds_a_script_tag (added to
  `test_hostile_input.py` for both forms).
- returns_links_to_terms_and_privacy_with_new_tab_notice_when_details_page_is_rendered.
- returns_200_placeholder_text_signed_out_for_terms_and_privacy; footer links on a page of
  every role and on error pages.
- Page quality: `terms`, `privacy` picked up by `page_routes()`; the details page and profile
  stay finding-free (existing walk test; `MINIMUM_PAGES` raised by 2).
- CSS invariant test for `.date-group` widths at 375 px, by numbers.

Moment sweep (`test_no_iso_dates_in_messages.py`): parametrized over every `NotificationKind`
member (a new kind without a case fails the parametrization check), drive the real use cases,
assert the body equals the written form and matches no `\d{4}-\d{2}-\d{2}`; and for every email
the product sends (notification emails via `send_notification_email`, verification code,
sign-in link) assert the outgoing body has no ISO date; the notifications page shows
"... (Europe/Berlin)" not UTC for a hospital-linked notice. Demo seed test: after `seed_demo`,
no notification body holds an ISO date.

Mutation: `make mutate` on the two new modules; every survivor killed by a boundary test or
named with a reason in `mutation-equivalents.txt`.

## Trust boundaries

- Form posts (day, month, year, terms): untrusted strings; length-capped by `maxlength` as a
  hint only, server checks digits, ranges, existence, rule; the use case re-validates; CSRF
  and Origin enforced; output auto-escaped, no `|safe`.
- Terms/privacy pages: public GET, static, no input.
- Date format: output only; names the hospital's zone from the DB.
- Authorization unchanged: profile = session user with role PATIENT; booking = visitor or
  patient, staff refused as today.

## Vocabulary (§3)

Visitor, Patient, Hospital (time zone), Appointment, Notification, WaitlistEntry, BookingHold
(`terms_accepted_at`, `visitor_birth_date`), VerificationCode, SignInLink, User (`date_of_birth`).

## Will not do

No new dependency, no JavaScript, no draft storage, no change of use cases, models, migrations
or API, no generic date-picker library, no rewrite of range/day labels, no localisation, no
real terms text.

Risks: week-day and month names depend on the locale (`%A`, `%B`), same as today's code;
the sandbox has no browser, so the 375 px, keyboard-only and inbox checks are the
orchestrator's.

## Architect review

Verdict: approve.

- Ladder: three blocks at existing seams, no use case, model, migration or dependency change. New-tab terms links keep typed values with no stored draft; sound and smallest.
- Layers: both new domain functions are pure and return error values (§8, §9). Boundary parsing stays in the form reader, and the use case still re-validates.
- Tests: behaviours are named with expected values. They cover edges (leap day, 31 April, today, tomorrow, 120-year boundary, non-ASCII digits), a browser-style CSRF and Origin form test, hostile input, and a sweep over every `NotificationKind` and email.
- Security: no new trust boundary beyond three more form strings. They are validated server-side, auto-escaped, and covered by the hostile-input test.

Fix while building (not blocking):
1. Item 2 quotes "A date of birth is in the past". The plan changes it to "must be in the past". Keep the owner's quoted wording unless the owner agrees, or flag the change in the PR.
2. `written_moment` is pure domain, but `%A` and `%B` depend on the process locale. Use fixed English weekday and month name tables so the output is deterministic and mutation-testable.
3. Delete `max` from `field.html` and `REAL_DATE` only after a grep shows they are unused (the plan already says so).
