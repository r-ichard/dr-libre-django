# Task 25d: page titles, status words, empty states, kept input

Slice: items 1, 2 and 3. Item 4 (refused forms keep what was typed) is the next run.

Item 1 is a one-line template fix, items 2 and 3 are one component each plus walking tests.
Item 4 needs a per-form inventory with its own failing tests; planning it here would be a plan
nobody finishes.

## Focal point

`scheduling/views/pages/page_quality_findings.py`: it already reads every rendered page, so the
title rule, the token rule, and the status and empty-state rules are findings in it. Pages are
derived from the URL configuration (`page_walk_support.page_routes`), so new pages are covered.

## Blocks

1. **Title (item 1).** `admin/appointments.html`: move the export form out of `{% block title %}`
   so the block is `Appointments · DrLibre`; the form stays once, at the end of `content`.
2. **Title and token findings.** `findings_of` gains: title contains `<`, title longer than 80
   characters, a `csrfmiddlewaretoken` value outside a `<form>`. The 80-character cap is applied
   to the title text. Two different pages sharing a title is checked in
   `test_page_quality.py` across the walk, per role, keyed by URL (same route with different
   ids may repeat only if the path is the same). Pages that collide get a specific title in
   their template (one-line edit each; the list is whatever the test finds).
3. **One status component (item 2).** Keep `components/badge.html` (kind, word, icon). Add
   `scheduling/views/pages/status_words.py`: one table mapping every status value of the
   vocabulary to `(kind, word)`: AppointmentStatus, WaitlistStatus, user active/inactive,
   clinician, hospital, room, appointment type, specialty (active/inactive). It absorbs
   `STATUS_BADGES` (`patient_rows.py`) and `STATUS_BADGE_TEXT` (`admin_appointments.py`) so
   there is one source for wording; the existing "Missed" versus "No-show" difference is
   settled to one word ("No-show", as the admin already shows; patient wording tests updated).
4. **Admin list cells.** `_cell` in `admin_records.py` stops returning the string
   "Active"/"Inactive"; the status column yields a `(kind, word)` pair and `admin/list.html`
   renders a pair cell with `badge.html`. `admin/appointments.html` renders `row.status` through
   the badge too. Waitlist admin already does.
5. **Empty states (item 3).** Each list gets `empty_state.html` with what is missing and the
   next step. Missing now (found by reading templates): dashboard "Appointments per day"
   (wrap table in `{% if per_day %}`), clinician patients is done, availability done, time off
   done. Whatever the walking test finds beyond that (search with a nothing-query, filters)
   is fixed in its template with one include.

## Files to touch, in order

`test_page_quality.py`, `page_quality_findings.py` (+ its tests), `admin/appointments.html`,
`status_words.py` (new), `patient_rows.py`, `patient_waitlist_rows.py`, `admin_appointments.py`,
`admin_records.py`, `admin_record_kinds.py`, `admin/list.html`, `admin/appointments.html`,
`admin/dashboard.html`, `static/css/components.css` only if the badge needs a new kind.
Not touched: models, use cases, domain, API, `drlibre-specs.md`, migrations, the mutated
domain package.

## Failing tests first (`returns_X_when_Y`)

- `returns_a_finding_when_a_title_holds_markup`: `<title>A<form></form></title>` gives
  "title holds markup".
- `returns_a_finding_when_a_title_is_longer_than_80_characters`: 81 characters gives
  "title longer than 80 characters"; 80 gives none.
- `returns_a_finding_when_a_token_sits_outside_a_form`: a hidden token in `<p>` is a finding,
  the same input inside `<form>` is not.
- `returns_no_two_pages_with_one_title_when_every_page_is_walked`: duplicate titles across
  distinct paths fail with the paths named.
- `returns_the_admin_appointments_title_as_plain_text_when_the_page_opens`: the `<title>`
  equals "Appointments · DrLibre" and the export form appears once in `<main>`.
- `returns_a_badge_with_a_word_when_a_status_value_is_rendered`: loops every value of
  AppointmentStatus, WaitlistStatus and the active/inactive states of user, clinician,
  hospital, room, appointment type, specialty; asserts the table has an entry and that the
  admin list, admin appointment list and patient pages render `class="badge` with that word.
  Fails today on admin lists (plain text "Active").
- `returns_an_empty_state_when_a_list_page_has_nothing_to_show`: walks every list page as the
  role that owns it with an empty database, then with `?q=zzzz-no-match`; every list page
  without a row shows `class="empty-state"` with a title and text. Lists are the pages whose
  template contains a table or list region; the test reads `empty-state` against that.
- `returns_the_dashboard_empty_state_when_no_day_has_an_appointment`.

Each test is shown to fail on the current tree before the fix (red proven); the
mutation run covers `scheduling/domain` only and this slice changes none of it.

## Invariants and blast radius

Rendering only: no double-booking path, authorization or audit entry changes. Every
status-word edit touches existing wording tests; blast radius is templates and the view
helpers named above. Authorization stays in the use cases; no new route.

## Trust boundaries

None added. The search query is already trimmed and parameterized (`list_records`); badge
text comes from the fixed table, not user input; template autoescape stays on.

## Domain vocabulary used

Appointment, WaitlistEntry, User, ClinicianProfile (Clinician), Hospital, Room,
AppointmentType, Specialty.

## What I will not do

No new dependency, no new CSS framework, no inline style or script, no per-status colour
beyond the five existing badge kinds, no rewrite of list views, no change to item 4 forms.

## Not in this run

- Item 4: refused forms keep what was typed (every form's inventory, a test posting a
  refused value to each, password excepted).
- The Chrome check of five tab titles and the emptied database per role is the
  orchestrator's after merge.

## Architect review

Verdict: approve.

- Slice (items 1 to 3, item 4 next run) is coherent: rendering only, product stays whole, one green stage can finish it. Item 4 is declared under "Not in this run", not dropped. The task's "Done when" is only met after the next run.
- Ladder: findings go into the existing page-quality walker, one status table absorbs two existing tables, one badge component reused. No new dependency or route.
- Tests are named as behaviours, include boundary (80 vs 81) and the in-form versus outside-form pair.
- Security: no new boundary; tokens-outside-form finding is a net gain.

Notes for the implementer (not blockers):
1. The duplicate-title rule is worded loosely. Define it: collect title per distinct path (ids as in the URL), fail when two different paths give one title, except a route's own repeats. Say which routes need a specific title in the test, not in prose.
2. "Missed" to "No-show" is a visible wording change; keep it to the one word and update only the wording tests that name it.
3. The empty-state walker must name how it recognises a list page (decide on a marker, e.g. the list templates' table or `empty-state` include), not guess from template text. Patient pages (no appointment, no waitlist entry, no notification) and clinician (no patient, rule, time off) must be in the walk, not assumed "done"; verify by the test, not by reading templates.
4. Prove each new test red on the current tree before the fix, including the badge test on admin lists.
