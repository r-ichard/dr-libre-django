# Plan: #44 second half, no week wholly in the past

Slice: #44 second half only, the "Previous week" link. The half that opens a strip on the week of the first free time, and the query-count sentence of backlog 27b item 8, stay open.

Focal point: `scheduling/views/pages/booking_times.py::week_strip` (line 82, `previous_href`). It is the one builder every week-strip page calls (booking times, provider detail, admin book, patient, clinician and admin reschedule), so one comparison there covers all of them.

## Rule

The previous week spans `[week_start - 7, week_start - 1]`. It is wholly past when its last day is before today, that is `week_start - 1 < today`, that is `week_start <= today`. So the link is shown iff `week_start > today`. "Today" is the hospital's date, the same reading `booking_page_data.py::_week_shown` (line 128) already uses.

## Blocks

1. `booking_times.py::week_strip`, line 82: `"previous_href"` becomes `week_href(previous_week_start(week.week_start)) if week.week_start > today else ""`, with `today = current_request_context().now.astimezone(week.time_zone).date()` computed once above the return. Add the import of `current_request_context` from `scheduling.use_cases.request_context`. Nothing else in the function changes.
2. `components/week_strip.html`, line 4: wrap the `Previous week` `<a>` in `{% if previous_href %}` ... `{% endif %}`. Nothing else in the template changes.
3. `scheduling/views/pages/test_booking_times_page.py`, line 52: `returns_previous_and_next_week_links` pins the bug. Change it to the new rule (see tests).
4. `scheduling/views/pages/test_detail_pages.py`, line 105: `returns_week_strip_monday_to_sunday_with_previous_and_next_links_on_the_provider_page` pins the bug. Change it to the new rule (see tests).

## Files, in order

1. `scheduling/views/pages/test_booking_times_page.py`: two new tests and the update of line 52 (red, see below).
2. `scheduling/views/pages/test_detail_pages.py`: update line 105 (red). The frozen clock is `NOW = 2030-01-07 06:00 UTC` (`search_pages_support.py:13`), Monday 07:00 in Berlin, so the default page shows the week starting Monday 2030-01-07, the day itself, and its previous week (Dec 31 to Jan 6) is wholly past. New assertions: the default page has no `rel="prev"`; `_html(f"{base}?week=2030-01-14")` has `rel="prev"` pointing at `week=2030-01-07` and keeping `type=`; `rel="next"` stays on both.
3. `scheduling/views/pages/booking_times.py`: block 1 (green).
4. `scheduling/templates/components/week_strip.html`: block 2 (green).

Not touched: `static/css/components.css` (no CSS change, see Layout); `scheduling/domain/booking_week.py` (the comparison is one line in the view, and the rule needs the clock, which the view layer reads, as `detail_pages.py` does); `scheduling/use_cases/booking_page_data.py` (no query change, `_week_shown` unchanged); `admin/calendar.html` and `clinician/calendar.html`, which have their own "Previous week" and do not use the strip.

Checked, no change needed: `test_admin_user_pages.py:243-246` asserts the admin calendar's own link; `test_patient_portal_guards.py:171,256`, `test_read_limits.py:100`, `test_detail_pages.py:126` and `test_booking_times_page.py:94-99` do not assert a previous link.

## Failing tests first

Clock: monkeypatch `clock.now_utc` as the existing frozen-clock fixtures do. Hospital zone: `make_clinic` uses `time_zone = "Europe/Berlin"` (`builders.py:47`), so the Berlin wall clock is the expected reading. Dates checked against the calendar: 2030-01-07 is a Monday, 2030-01-06 and 2030-01-13 are Sundays, 2029-12-31 is a Monday.

- `returns_no_previous_link_when_previous_week_ends_before_today_in_hospital_zone` (new, booking times, the Sunday boundary): now `2030-01-06 23:30 UTC`, which is Sunday 23:30 UTC and Monday 2030-01-07 00:30 in Berlin; `?week=2030-01-07`; the page has no `rel="prev"`. The previous week ends on Sunday 2030-01-06, before today in Berlin. Red: the current code always builds the link.
- `returns_previous_link_when_previous_week_still_contains_today` (new, booking times, guard): now Sunday `2030-01-13 12:00 UTC`; `?week=2030-01-14`; `rel="prev"` links to `week=2030-01-07` (Jan 7 to 13 contains today, Sunday). **Green before the change**: the current code always builds this link. It is a guard against over-correction, not a red test. Its kill role is named under "Proof that the tests guard".
- `returns_previous_and_next_week_links` (updated, booking times, line 52): now Monday 2030-01-07 06:00 UTC; `?week=2030-01-09` shows Jan 7 to 13, which holds today. Expect no `week=2029-12-31` in the html and `week=2030-01-14` present. Red: the current code still builds `week=2029-12-31`.
- `returns_week_strip_monday_to_sunday_with_previous_and_next_links_on_the_provider_page` (updated, detail, line 105): as in "Files, in order" item 2. Red for the same reason.

No separate "Sunday today" test: its shown week and today give the same result under every mutant below, so it would add a case without a kill. The Sunday boundary is covered by the first test above.

## Proof that the tests guard

In a scratch edit (not committed), apply each mutant to block 1 alone, run the tests, and check the named test fails. Revert before commit.

- M1, `week.week_start >= today`: killed by `returns_no_previous_link_when_previous_week_ends_before_today_in_hospital_zone` (Jan 7 >= Jan 7 shows the link) and by the updated provider-page test (default page, Jan 7 >= Jan 7).
- M2, UTC today (`current_request_context().now.date()`): killed by `returns_no_previous_link_when_previous_week_ends_before_today_in_hospital_zone` only (UTC today is Sunday Jan 6, so Jan 7 > Jan 6 shows the link). The provider-page test does not kill M2: its NOW is Jan 7 in UTC too.
- M3, previous week's start instead of its end (`week.week_start - 7 > today`, or the same with `>=`): killed by `returns_previous_link_when_previous_week_still_contains_today` (Jan 7 > Jan 13 is false, the link disappears when it must stay).
- M4, always hide, and M5, always show: killed by the guard test (M4) and by the Berlin boundary test (M5).

The guard test stays green under the correct rule and under M1, M2; it is the only test for M3 and M4.

## Layout

No CSS change. `.week-strip__nav` is flex, wrapping, `justify-content: space-between`. With the previous link gone, the nav holds the title and the Next link. The title is an `h2` with `text-wrap: balance`, no fixed width. Removing a child cannot widen the nav. Visible effect to check, not to fix here: with two children, `space-between` puts the title at the left edge, not the centre as before.

Invariant at 375 px and 1440 px on the provider page with a week that has no previous link: `nav.scrollWidth <= nav.clientWidth`; the title's and the Next link's right edges are `<=` the nav's right edge; the title is fully visible, not clipped; the title's left edge is `>=` the nav's left edge.

The sandbox has no browser, so the fit is not measured here. The orchestrator measures in Chrome at 375 px and 1440 px on the provider page with a week that has no previous link. Numbers not measured in the sandbox are reported as unmeasured.

## Invariants and blast radius

- No new query: `current_request_context()` reads the request's in-memory context; `week_of_slots` is unchanged. Every caller of `week_strip` already runs `week_of_slots`, which reads the same context (`booking_page_data.py:128`), so the new read adds no failure mode.
- No write path, no authorization change, no audit change.
- Blast radius: every page that renders `components/week_strip.html`, including admin book and the patient, clinician and admin reschedule pages. Those get the same rule through the shared builder; accepted, one rule for all strips.
- Clock: taken from request context (CLAUDE.md §8), never `datetime.now()` in the view.

## Trust boundaries

None new. `?week=` is already parsed by `week_from`; the comparison uses the server clock and the hospital's zone, and no payload feeds it. A visitor who types a past `?week=` still gets that week (`_week_shown` is unchanged); only the link is removed. That is the other half's concern.

## Domain vocabulary

Hospital (time zone), Visitor, Patient, Clinician, Admin, Appointment (the reschedule pages).

## Will not do

No new domain function, abstraction or dependency. The comparison stays in the view, as the one line in `week_strip`; a pure `previous_week_is_past` in `booking_week.py` was considered and rejected for this diff size, since it would add a function, an import and a test for one comparison. No CSS change; no change to `week_of_slots`, `_week_shown` or the week-opening rule; no change to the admin calendar's own "Previous week"; no query-count assertion (it belongs to the other half).

## Commit

Message names #44 with `Refs #44`, not `fixes`: the week-opening half is still open. Test, lint and gate run before commit: `make test`, `make lint`, `make gate`.

## Not in this run

- Strips open on the week of the first free time within the booking horizon, and "Bounded queries: say the number" (backlog 27b item 8, first half and its count).
- Hospital page: `hospital_context` in `detail_context.py` builds no week strip, so the QA line naming it needs checking in the other half.
- Past `?week=` addresses still render a past week when typed by hand; closing that is the other half's rule.

## Architect review, addressed

- Point 1 (missing test), earlier: `test_booking_times_page.py:52` is in the file list (item 3) and the failing-test list.
- Point 2 (red claim), earlier: the guard test is marked green before the change and proven by mutation M3 and M4.
- Point 3 (mutation proof, this revision): the Sunday test is removed as a separate case, since it kills no mutant. Each mutant now names its killing test; M2 is killed by the Berlin test only, and the provider-page test does not claim it.
- Point 4 (placement, this revision): the comparison stays in the view, one line, with the reason under "Will not do".
- Points 5 to 7 confirmed unchanged: the rule `week_start > today`, the expected dates, the layer, the trust and query reading, and the layout plan.

## Architect review

Checked against the code: `week_strip` is the one builder (booking times, detail, admin book, three reschedule pages); every caller gets `week` from `week_of_slots`, which already needs the request context. Dates: 2030-01-06 and 2030-01-13 are Sundays, 2030-01-07 a Monday. Line 52 of `test_booking_times_page.py` does fail under the new rule (`week=2029-12-31` disappears), so the earlier gap is closed.

Finding: the mutation proof is wrong for the Sunday test. Shown week Jan 7 to 13, today Sunday Jan 13. Under `week_start >= today` the test sees `Jan 7 >= Jan 13` = false, so the link stays absent and the test stays green. Under a UTC `today` it reads the same Sunday, also green. Only the Berlin-boundary test kills the UTC mutant; for `>=` the Berlin test and the default provider-page test (Jan 7 >= Jan 7) kill it. Fix: in "Proof that the tests guard", name the killing test per mutant, and drop "the Sunday test must fail under each".

Note, not a reason to revise: the comparison sits in the view module, which CLAUDE.md §8 keeps thin. Accepted as written; see "Will not do".

Layout, scope, trust boundary and query reading: confirmed as written.

Verdict: revise (one material fix: the mutation proof).

## Architect review, round 3

Re-read against the code and the current text (not the round-2 finding). The Sunday test as written in "Failing tests first" is 2030-01-06 23:30 UTC, which is Monday 2030-01-07 00:30 in Berlin, with `?week=2030-01-07`. Today in the hospital zone is Jan 7, so the shown week starts on today. The round-2 finding (shown week Jan 7 to 13, today Sunday Jan 13) describes a different case, not this test. The mutation proof, checked per mutant:

- M1 `week_start >= today`: Berlin test sees `Jan 7 >= Jan 7`, link shown, red. Provider default page the same. Correct.
- M2 UTC today: UTC now is Jan 6, so `Jan 7 > Jan 6` shows the link, red for the Berlin test. Provider default page has UTC today Jan 7, hides the link, green, as stated. Correct.
- M3 `week_start - 7 > today`: guard test, `Jan 7 > Jan 13` false, link hidden, red. Berlin test stays green under M3 (it expects hidden). Correct as stated.
- M4 always hide: guard test red. M5 always show: Berlin test red. Correct.

Rule `week_start > today` is right: the previous week's last day is `week_start - 1`, which is before today exactly when `week_start <= today`. Line 52 and the provider-page test both fail under the new rule as the plan says (`week=2029-12-31` disappears; `previous` regex returns None on the default page). `test_admin_user_pages.py:243-246` asserts the admin clinician calendar's own link (`admin_user_pages.py:101`), not the strip, so it is untouched. `week.time_zone` and `week.week_start` exist on `WeekOfSlots` (used by `week_strip` already). `current_request_context` is in `scheduling/use_cases/request_context.py:10`. No new query, no trust input, no write path.

Non-blocking, unchanged from round 2: the comparison sits in the view module. Accepted as one line; see "Will not do".

Verdict: approve.
