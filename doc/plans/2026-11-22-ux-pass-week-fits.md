# Plan: task 25a, the week fits again, and the small leftovers

Focal point: `static/css/time-grid.css`. Everything else is small and independent.

## Arithmetic (item 1)

- Page inside margins at 1440 px: 1088. Axis `3.5rem` = 56. Columns area: 1032.
- Seven columns, six gaps of `--space-2` = 8: 1032 - 48 = 984; 984 / 7 = 140.57. Largest
  whole-rem-quarter that fits: `8.75rem` = 140 px (7 x 140 + 48 = 1028 <= 1032).
  Column: `minmax(8.75rem, 1fr)`, so at 1440 the `1fr` share (140.57) is what is drawn.
- Time line text is 114 px (icon and its margin included, measured). Block frame today,
  beside a time off rail: rail 16 + padding 8+8 + border 6+1 = 39, giving 160-39 = 121.
  At 140 the same frame gives 101: 13 px short. Fix inside the block, not the column:
  - `.time-grid-item` horizontal padding `var(--space-2)` -> `var(--space-1)`: saves 8.
  - `--rail` `1rem` -> `0.5rem`: saves 8 (the band stays visible as an 8 px strip).
  - Frame beside the rail: 8 + 4+4 + 7 = 23; line gets 140 - 23 = 117 >= 114 (3 px spare).
    Alone in its column: 140 - 15 = 125 >= 114.
- Status icon stays where it is (leads the first line); colour is never the only signal.
- Below 1440 px the frame may scroll sideways as now (`overflow-x: auto` kept); no change to
  the page.

## Blocks

1. `time-grid.css`: column `minmax(8.75rem, 1fr)`, padding, `--rail` per above.
2. `sign_in.html` + `views/pages/sign_in.py`: hint text takes `link_minutes` from
   `LINK_LIFETIME` (`_link_minutes()`, twin of `_locked_out_message`), passed in `_form` context.
3. `sign_in.html`: sentence under h1 becomes "Patients can sign in with the email link. If
   you have a password, use it below." True for clinicians, admins, and admin-created patients.
4. New `use_cases/notice_subjects.py`: the three name lookups (patient of appointment, patient
   of waitlist entry, user name) move out of `views/pages/notice_sentences.py`, which only
   formats sentences and calls them. Same return values and fallbacks ("the patient", "the user").
5. `use_cases/notification_inbox.py::notifications_page`: `select_related` of
   `appointment__appointment_type__department__hospital` and the same through `waitlist_entry`;
   `_shown_at` then reads without queries.
6. Item 5 (favicon): test `returns_favicon_fill_equal_to_primary_token_when_the_files_are_read`
   already exists in `test_ux_pass_pages.py` and passes; nothing to do. The "typed twice"
   remains by design (an SVG file cannot read a CSS token); the test is the tie.

## Files, in order

Tests first: `views/pages/test_time_grid_css.py`, `views/pages/test_ux_pass_pages.py`,
`views/pages/test_patient_notifications_page.py`, `use_cases/test_notice_subjects.py` (new).
Then `time-grid.css`, `sign_in.html`, `sign_in.py`, `notice_subjects.py`, `notice_sentences.py`,
`notification_inbox.py`. Replace the older 114-px test in `test_ux_pass_pages.py` (it hard
codes frame 39 and the `10rem` regex) with the new arithmetic.

Not touched: `check_email.html` (also says "15 minutes" as text; same drift, not listed, report
it as a follow-up), domain `calendar_grid.py` (vertical constants unchanged), tasks 25b/25c.

## Failing tests first

- returns_seven_columns_that_fit_1088_pixels_when_axis_and_gaps_are_counted: parse column min
  rem, axis rem, gap token; assert 56 + 7 x min + 6 x 8 <= 1088.
- returns_a_time_line_of_at_least_114_pixels_when_a_block_sits_beside_a_time_off_rail: parse
  column min, rail, padding-inline, border (6+1); assert min - rail - 2 x padding - 7 >= 114.
- returns_a_time_line_of_at_least_114_pixels_when_a_block_is_alone_in_its_column: same, rail 0.
- returns_15_minutes_in_the_hint_when_the_link_lifetime_is_15_minutes and
  returns_5_minutes_when_the_link_lifetime_is_5_minutes (monkeypatch `LINK_LIFETIME`; the view
  reads the module attribute at call time, as the lockout test does).
- returns_no_false_claim_when_a_patient_with_a_password_reads_sign_in: page no longer contains
  "Clinicians and admins use a password" and says patients can use the email link and that a
  password goes in the second form.
- returns_name_of_patient_when_appointment_notice_is_rendered / "the patient" when gone
  (use case test for `notice_subjects`), plus an AST/grep test that `notice_sentences.py`
  imports no `scheduling.models` (layer rule).
- returns_constant_query_count_when_notifications_page_has_one_or_five_rows_with_appointments:
  `django_assert_num_queries` with an exact number, equal for 1 and 5 rows.

## Invariants and blast radius

No write path, no authorization change, no audit change. Notification list still filtered by
`recipient=patient` in the use case. Blast radius: calendar and rooms timeline layout (both use
`.time-grid`), sign-in page text, admin notice sentences, patient notifications query shape.
Rooms timeline shares the CSS: same arithmetic holds (same column rule).

## Trust boundaries

None new. Notice cookie still carries code and id only; ids are parsed as UUID, bad value falls
back to the generic noun. No payload feeds authorization.

## Vocabulary

Appointment, WaitlistEntry, Notification, User, Hospital, Department, AppointmentType, Patient,
Clinician, Admin.

## Will not do

No new abstraction, dependency, or refactor beyond moving the three queries; no JS; no inline
style; no change to `check_email.html`; pixel result cannot be measured in the sandbox (no
browser), so the arithmetic is held by the style sheet test and the orchestrator re-measures
in Chrome at 1440: `grid.scrollWidth <= grid.clientWidth`, `line.scrollWidth <= line.clientWidth`.

## Architect review

Verdict: approve.

- Ladder: CSS fix sits inside the block (padding, rail), column derived from 1088 - 56 - 48; arithmetic checks (7 x 140 + 48 = 1028 <= 1032; 140 - 23 = 117 >= 114). Only extraction is the three lookups the task names. No new dependency.
- Tests first: named as behaviours with numbers; the CSS test holds both rules. Query-count test uses an exact number equal for 1 and 5 rows.
- Layer: lookups move to a use case, view only formats; AST test guards the rule.
- Security: no new boundary, no write, no audit change; recipient filter stays in the use case.
- Watch in implementation: (a) item 5 is already satisfied; confirm the existing test really reads both files and fails on a changed colour (prove it can fail). (b) `check_email.html` keeps "15 minutes" as text; plan reports it as follow-up. Acceptable, but it is one line of the same drift and the reviewer may ask for it. (c) Rooms timeline shares the CSS; the same test covers it. (d) Multi-lane blocks are narrower than 114 px by design; not in scope.
