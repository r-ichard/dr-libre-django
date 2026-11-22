# Review: task 21, admin dashboard, reporting, CSV export

Diff `main...HEAD`: 12 files, all in `scheduling/domain/` (6 modules, 4 test files), the plan and
`mutation-equivalents.txt`. Commits after `verify_green` touch tests and `mutation-equivalents.txt`
only, so the proof left no product mutation behind.

## Findings

### Blocker: most of the task is not in the diff
- No `scheduling/use_cases/admin_report.py` or `admin_appointment_export.py`, no dashboard or
  export view, template, route or CSS (plan blocks 6-10, files list). Goal items 4-13 are unmet.
- Export audit (`appointment.export` with `row_count`, same transaction) and its label in
  `domain/audit_labels.py` (plan block 11) do not exist. The domain `csv_cells.py` and
  `report_*.py` have no caller.
- Carried items 14-17 not done: `admin_audit.py` still has the hand list (only a registry
  `domain/audit_entity_types.py:5` exists, unused); `MAX_SLOTS_CHECKED` (item 15), `reference_messages`
  locks (16) and the missing notices (17) untouched.
- Role test and hostile-input test for new routes, query-count test, `browser_post` export test,
  duplicate-id test: none written (plan "Tests first").
- Fix: implement plan blocks 6-12 and the carried items, with the pages tests the plan lists.

### Important: the plan's own promise unmet in domain too
- `domain/report_figures.py` has no test for "same appointment counted once whatever the reader zone"
  at a hospital boundary beyond `hospital_day`; acceptable, but the superset fetch note 1 of the
  architect review (bound query by UTC day +-1) has no code yet.

### Nit
- `domain/report_utilisation.py:96` `_overlap` is correct only because gaps are merged; say so in a
  short why-comment or keep as is.
- `domain/csv_cells.py:3` adds tab and carriage return beyond the four in the spec; fine, documented in plan.
- `domain/report_figures.py:51` `percent_text` rounds half up with integer math; correct, tested.
- `mutation-equivalents.txt`: 5 new entries, each with a reason; `x__merged__mutmut_4` and the two
  `astimezone(None)` ones are plausible equivalents.

## What I confirmed at a glance
Domain blocks 1-5 each state in one sentence (range dates, figures, utilisation with DST by UTC
conversion, cell escape, audited type registry). Pure, typed, no escape hatches, small functions.
Zero denominators give "n/a". Utilisation merges time off and clips by rule validity.

## Blocking
- Dashboard, export, use cases, routes, templates, CSS absent (items 4-11, 13).
- Export audit entry and `appointment.export` label absent (item 10).
- Role test and hostile-input test coverage for new routes absent (item 12).
- Carried items 14, 15, 16, 17 not implemented.
- Query-count test (item 7) absent.

## Later
- Add a why-comment on `_overlap` relying on merged gaps.
- Implement the UTC superset fetch with tests for zones ahead of and behind UTC when the report use case lands.

## Outcomes of the blocking findings

| Finding | Outcome |
| --- | --- |
| Dashboard, export, use cases, routes, templates, CSS absent (4-11, 13) | fixed: `admin_report.py`, `admin_appointment_export.py`, `admin_dashboard.py`, `admin_appointment_export.py` (view), `admin/dashboard.html`, export form in `admin/appointments.html`, CSS in `components.css`. Tests: `test_admin_dashboard_page.py` (zeros and "n/a", hostile `range`, tiles equal database, five busiest, table total, no `style=` or `<script`), `test_admin_appointment_export.py` (ten columns, UTC, ids only, no-store, attachment, GET 405, filters, form not link, over-limit 422) |
| Export audit with `row_count` and `appointment.export` label absent (10) | fixed: `returns_an_audit_entry_with_the_row_count_when_exported`, `returns_no_rows_and_no_entry_when_the_audit_entry_cannot_be_written`, `returns_a_refusal_and_no_audit_entry_when_the_set_is_over_the_limit`; label passes `test_audit_action_labels.py` |
| Role, hostile-input and query-count tests absent (12, 7) | fixed: `EXTRA_ROUTES` 24 in `test_admin_access.py` (role test covers the export route, also POST); `test_hostile_input.py` and `test_unique_ids.py` enumerate routes from the URL configuration; `returns_no_duplicate_id_when_the_dashboard_is_filled`; `returns_the_same_number_of_queries_for_two_and_for_forty_appointments` (6 queries, bound 12) |
| Item 14, audit filter list | fixed: page uses `AUDITED_ENTITY_TYPES` (`SignInLink` and the also missing `SignInFailure` added); `returns_every_literal_audited_type_in_the_registry_when_the_source_is_read`, `returns_every_audited_type_as_a_filter_choice_that_finds_its_entries` |
| Item 15, `MAX_SLOTS_CHECKED` | fixed: busy times and time off left out in the query (`_without_conflicts`), cap kept only on the naming scan; `returns_the_fitting_time_when_it_is_behind_more_busy_times_than_the_scan_limit` (red before), `returns_the_second_time_when_the_clinician_has_time_off_over_the_first` |
| Item 16, `reference_messages` locks | fixed: `returns_no_for_update_query_when_a_form_is_checked_without_saving` (red before) |
| Item 17, admin actions without a notice | fixed: signed short-lived cookie `admin_redirect`, shown once in `admin_nav.html`; actions without one were status change (3), cancel, reschedule, book, waitlist add, offer, accept, record create, update, delete, user deactivate, reminder run (moved out of `?reminders=N`); `returns_a_notice_once_with_what_was_done_when_the_admin_acts` (14 cases), forged cookie and address test, `returns_every_admin_post_route_in_the_notice_list_or_the_download_list` |
| "Important": UTC superset fetch (architect note 1) | fixed in `admin_report._visits`: one UTC day more on each side, kept by hospital-local date. Not tested with zones on both sides of UTC (stays on the Later list) |
