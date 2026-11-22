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
