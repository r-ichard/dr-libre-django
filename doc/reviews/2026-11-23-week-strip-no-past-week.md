# Review: week strip offers no week wholly in the past (#44, second half)

Reviewer: second reader, diff `main...HEAD` (run 01M82T964YBYGZMTC6XBTBMD4W). Plan: `doc/plans/2026-11-22-week-strip-no-past-week.md`, approved at round 3. I did not re-run the suite; the recorded `verify_green` (5225 passed) and `check` (lint, test, gate clean) stages are the evidence for that.

## Stage 1: plan per changed block, in one sentence

- `scheduling/views/pages/booking_times.py:79-82`: "Compute the hospital's date, and omit the previous-week href when that week's start is not after today." Confirmed at a glance.
- `scheduling/templates/components/week_strip.html:4`: "Render the Previous week link only when `previous_href` is truthy." Confirmed at a glance.
- `scheduling/views/pages/test_booking_times_page.py:52-84`: three tests (no link when the previous week is past; Sunday/Berlin boundary; link kept when the week still contains today). Read them, did not need to trace.
- `scheduling/views/pages/test_detail_pages.py:105-131`: provider page default has no `rel="prev"`; `?week=2030-01-14` keeps it with `type=`. Confirmed at a glance.

Traced, because it matters: the rule `week_start <= today` as "previous week is past". The previous week ends on `week_start - 1`; that is before `today` exactly when `week_start <= today`. Correct. `week.week_start` is always a Monday (`booking_page_data.py:133`, `asked_week - timedelta(days=asked_week.weekday())`), so the Monday-to-Sunday span holds.

## Stage 2: correctness and error handling

- Clock and zone: `current_request_context()` is read in the view. It is bound by the middleware from `clock.now_utc()` (`scheduling/views/middleware.py:56`), and it raises `LookupError` outside a request. The only caller of `week_strip` is a view, so no swallowed or new error path. `now` is timezone-aware (checked in `scheduling/domain/request_context.py`), so `.astimezone(week.time_zone)` is safe.
- `previous_href` is `None` or a string; the template's `{% if %}` treats both correctly. The `"previous_href"` key remains in the dict, so the other callers (`detail_context.py:47`, the admin book, the reschedule views) keep working.
- Past weeks typed by hand: `_week_shown` still returns a past week within 52 weeks. Such a week now shows no previous link, which is the intended result of the rule. Closing the past-week address is the other half, outside this run.

No finding.

## Stage 3: authorization, boundaries, sensitive data

- No new input. The comparison uses the server clock and the hospital's zone; `?week=` is parsed by the existing `week_from` path, unchanged.
- No new route, serializer, form, query, or log line. No sensitive data in the URL: the removed link only drops a `week=` parameter.

No finding.

## Stage 4: double booking

Not touched. No write path, no conflict check changed.

## Stage 5: tests

- The Sunday boundary test (`test_booking_times_page.py:61-70`) pins `2030-01-06 23:30 UTC`, which is Monday `2030-01-07 00:30` in Berlin, with `?week=2030-01-07`. Under the correct rule the link is absent; under UTC-today (plan M2) the link appears and the test fails. This is the kill for M2 and it is correct.
- The guard test (`test_booking_times_page.py:73-87`) pins the link when the week still contains today. It is green before the change; the plan says so and names M3 and M4 as its kills. Honest.
- The updated provider-page test (`test_detail_pages.py:105-118`) asserts the default page has no `rel="prev"`. Under plan M1 (`>=`) it fails. Good.
- Red was recorded: `verify_red` shows the three intended tests failing on `rel="prev"`.
- Nothing I would call a test that passes forever: each new assertion has a concrete value (`week=2030-01-07`, `type=`).

Not a blocker: the plan's mutation proof (M1 to M5) is described but no result is recorded in the repo. `prove` left no product diff (see Stage 7), so the mutants were either reverted or not run here. Left for the orchestrator to re-run, see below.

## Stage 6: names and comments

- `previous_is_past`, `previous_href`, `today`: state their roles. Good.
- `booking_times.py:80` comment: "The previous week ends the day before this one starts, so it is past once that day is gone." States why, not what. Under 255 characters. Keep.
- Test names follow `returns_X_when_Y`. `returns_next_week_link_and_no_previous_when_previous_week_is_past` is a long name but reads as a sentence. Keep.

No finding.

## Stage 7: proof left no trace

`git diff` between the commits shows:

- `7c593b0` green: `week_strip.html`, `booking_times.py` (product, expected).
- `6a4754c` verify_green, `f7147fc` prove, `83d66e0` refactor, `a0de85e` check: no content diff against their predecessor (empty `git diff`). Nothing changed after `verify_green` that is not already in `7c593b0`.
- Tests: `git diff c3730e7 HEAD -- '*test_*'` is empty, so the tests as they stand are the ones written at red (`c3730e7`), and nothing changed them afterwards.

No mutation left behind. No finding.

## Stage 8: scope, dependencies, contracts

- Diff touches: plan doc, one template, one view module, two test files. No CSS, no domain module, no use case, no query, no migration, no dependency.
- `drlibre-specs.md` is not in the diff. `doc/handover.md` and `doc/backlog.md` are not in the diff either; the orchestrator updates the backlog after merge (CLAUDE.md "How work flows"). The handover does not describe the previous link, so no state change needs recording there.
- Contract: the `week_strip` context key `previous_href` is now `None` instead of a URL when the previous week is past. Its consumer is the template only (grep: `components/week_strip.html:4` is the sole reader). No other consumer.
- `admin/calendar.html`, `clinician/calendar.html`, `clinician/today.html`, `clinician/rooms.html` keep their own "Previous" links, as the plan says. Untouched.

No finding.

## Findings

### Later

1. **Layout is unmeasured.** `scheduling/templates/components/week_strip.html:3-5`. The task asks that the title and the remaining link fit at 375 px and 1440 px. The sandbox has no browser, so nothing here is measured. The plan notes one visible effect to check: with two children under `space-between`, the title moves to the left edge rather than the centre. Risk: a visual shift on the five strip pages. Smallest fix: none in code; measure in Chrome per the plan's invariant (`nav.scrollWidth <= nav.clientWidth`, edges inside the nav). Left for the orchestrator.
2. **Mutation results are not recorded.** `scheduling/views/pages/test_booking_times_page.py:61-87`. The plan requires M1 to M5 run in a scratch edit. The repo does not show the outcome. Risk: a guard that does not kill a mutant. Smallest fix: run the five mutants on block 1 and record the result in the plan. Left for the orchestrator.
3. **The comparison sits in the view module.** `scheduling/views/pages/booking_times.py:79-82`. CLAUDE.md §8 keeps views thin. The plan accepted one line here, with the reason under "Will not do". Risk: low; the rule is one comparison. Smallest fix if it grows: a pure `previous_week_is_past` in `scheduling/domain/booking_week.py`.
4. **Four callers have no direct previous-link test.** Admin book, patient reschedule, clinician reschedule and admin reschedule all call `week_strip` (`admin_appointment_book.py:168`, `patient_reschedule.py:68`, `clinician_reschedule.py:63`, `admin_appointment_reschedule.py:67`) but no test pins their previous link. They share the one builder, so the rule holds for them through that builder. Risk: a future caller that bypasses the builder would not be covered. Smallest fix: one test per page, when next touched.

## Left for the orchestrator

From the plan's `## Not in this run`, unchanged:

- Strips open on the week of the first free time within the booking horizon, and "Bounded queries: say the number" (backlog 27b item 8, first half and its count). Not in this run.
- The hospital page: `hospital_context` in `scheduling/views/pages/detail_context.py` builds no week strip, so the QA line naming it needs checking in the other half.
- Past `?week=` addresses still render a past week when typed by hand (QA reports `?week=0001-01-01` answers 200). Closing that is the other half's rule.

Also from the plan, not finished in the sandbox:

- Layout measurement at 375 px and 1440 px (Later 1).
- Mutation proof M1 to M5 and its recorded result (Later 2).
- Commit message must say `Refs #44`, not `fixes` or `closes`, since the week-opening half is still open.

## Blocking

None.

## Later

See Later 1 to 4 above.
