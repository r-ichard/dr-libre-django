# Review: task 17c, QA round 2 clinician workspace

Scope: `git diff main...HEAD`, 26 files. Gate and tests passed in `check` (2535 passed, 34 s).

## Proof left no trace
Commits `verify_green` to `prove` touch only `test_booking_rules.py`, `test_calendar_grid.py` and
`mutation-equivalents.txt`. No product line changed after green. OK.

## Findings

- **Low**, `static/css/time-grid.css:10`: `overflow: hidden` on `.time-grid-item` silently clips
  text that does not fit. The task allows it ("belongs on the appointment page") only if the block
  links there; time off blocks have no link, so a long reason is cut with no way to read it.
  Smallest fix: title attribute or a time-off detail line on the time off page.
- **Low**, `scheduling/domain/audit_labels.py:51`: unknown action now reads "Changed the record".
  Plain, but hides a missing label in production; the new test over all actions guards it. Fine.
- **Low**, `scheduling/domain/booking_rules.py:60`: `START_IN_THE_PAST` applies to every actor and
  action except cancel. Intended by the task (#29); check no staff flow books a past walk-in.
  Tests green, so none found.
- **Low**, `scheduling/views/pages/clinician_calendar.py:99`: `_time_off_items` is called per day
  and loops all rows; seven days times few rows, no concern.
- **Low**, `scheduling/views/pages/local_time.py:19`: rule "first occurrence" (fold=0) matches
  `free_slots.py:112`. One rule, stated beside the field in `time_off.html:6`. Good.
- **Low**, `static/css/time-grid.css`: alignment of #25 is proved by CSS and HTML text tests
  (`test_time_grid_css.py`), not in a browser. Accepted limit of the sandbox.
- **Nit**, `mutation-equivalents.txt`: two new equivalents explained with a reason. Acceptable.

Trust boundaries: no new route, no authorization change; reschedule refusals go through the
existing `change_refused_page`; `asked_start` returns a value for out-of-range instants and 404
for non-instants, no leak. No type escape hatches added (`# noqa: S101` carries a code and
reason, same as existing code). No writes added, so no audit gap. No dependency added.
Domain `period_days.py` is pure and mutation-gated.

## Blocking
None.

## Later
- Give time off blocks a way to read a clipped reason (title or link).
- Consider a visible fallback for unlabelled audit actions in logs.
