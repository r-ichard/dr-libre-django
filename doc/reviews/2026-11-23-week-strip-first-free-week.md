# Review: #44 second half, week strip opens on the first free week

Reviewer: second reader stage. Diff: `git diff main...HEAD` (9 files, 387 insertions, 4 deletions). Plan: `doc/plans/2026-11-23-week-strip-first-free-week.md`.

## Summary

The change does what the plan says. One keyword flag (`open_on_first_free`, default False) on `week_of_slots`, one private walk (`_first_free_start`), three caller lines (provider page, booking times page, patient reschedule). Staff callers keep the current week. No product code outside `booking_page_data.py` and the three callers. No spec, backlog, migration, dependency or template change. Verdict: approve. Findings below are Later.

## Plan per block (one sentence each, §2.5)

- `week_of_slots` (`scheduling/use_cases/booking_page_data.py:72-103`): shows the current week; if the flag is set, the address names no week and that week is empty, moves to the Monday of the first free start and loads that week. Confirmed at a glance.
- `_first_free_start` (`booking_page_data.py:156-175`): walks `[now + LEAD_TIME, now + HORIZON)` in 31-day chunks, steps back by the appointment duration between chunks, returns the first offer's start or None. Needed a trace: the step-back and the clipping (§2.3).
- Callers (`detail_pages.py:44`, `booking_times.py:41`, `patient_reschedule.py:55`): one keyword each. Confirmed at a glance. The staff callers (`admin_appointment_book.py:144`, `admin_appointment_reschedule.py:46`, `clinician_reschedule.py:43`) keep the default.

## Checks in the order of §2 of the review card

1. **Correctness.** Walk terminates: `duration_minutes` is a `SmallIntegerField` with `at_least 1` (`scheduling/models/organisation.py:115,131`), so at most 32767 minutes, under the 31-day chunk. Each step moves forward. `chunk_end` is clipped to `horizon_end` (`booking_page_data.py:164`), and the stop test is `chunk_end >= horizon_end` (`:172`). `offers` are sorted by start (`slot_search.py:62`), so `offers[0]` is the earliest. The `_lacks_room` early return still sets `duration` (`free_slots_query.py:44`), so the step-back is valid for room-less types. Errors: `Failure` from either `find_free_slots` call is returned as is, never swallowed (`booking_page_data.py:88-89, 92-93, 99-100`). No swallowed error.
2. **Authorization and trust boundaries.** `open_on_first_free` is a server constant at the three callers; the walk takes no client value. `online_only` comes from the same source as before (`online_only_for(user)` on the two public pages, fixed True on reschedule). The walk calls `find_free_slots` with the caller's `online_only`, so a visitor never sees a hidden clinician's free time (pinned by `test_booking_page_data.py:172` visitor test, and staff counterpart at `:186`). `week` still goes through `week_from` (`booking_links.py:84-89`). No new route, no payload-derived authority, nothing logged, nothing added to a URL.
3. **Double booking and writes.** Read-only. No transaction, no audit entry needed, no write path touched.
4. **Tests.** Derived from the plan's stated expectations, with dates and rules stated in the test bodies. The seven plan use-case tests are present (`test_booking_page_data.py:100-217`, default-flag test at `:220`). Tests not in the plan's list (`:230` lead-time, `:242` same query count as plain) are additions that pass the same review; not blocking. The border test (`:153`) fails without the step-back (M4 in the plan). The visitor test (`:172`) fails if `online_only` is dropped from the walk (M3). The query test (`:200-217`) is the one place the bound is asserted; see Later 1.
5. **Names and comments (§3, §4).** Names state roles: `first_free`, `horizon_end`, `chunk_start`, `chunk_end`. Comments: `booking_page_data.py:174` says why (a slot can cross the chunk border); docstring at `:159` is one line. All under 255 characters per block. No narration.
6. **Proof left no trace (§13 card 7).** Commit order from `git log`: `green 97ae93f`, `verify_green 3fa5c1a`, `prove cde6a74` (test file only: `test_booking_page_data.py`, +30/-1), `refactor b761448` (`booking_page_data.py`, 5 insertions, 6 deletions), `check 0f37fff` (`booking_page_data.py`, 11 lines, plus `test_booking_page_data.py`). `prove` touched tests only, so the rule holds. `refactor` runs after `prove`, outside the window the card names, and it is a sanctioned stage; its change is a rename plus replacing the inline Monday arithmetic with `_week_shown`. Equivalent for every date the walk can return, because the horizon is inside `day_in_range`. `check` then ran lint, the full suite (5257 passed) and the gate on that code. Not blocking.
7. **Scope.** No new dependency. No spec change (`drlibre-specs.md` not in the diff). No backlog edit. No template, CSS or domain change. `find_free_slots`, `slot_search.py`, `free_slots_query.py` untouched. Plan's "Not touched" list holds.
8. **Mutants M1 to M6.** Not re-run here. The mutant evidence lives in the prove stage; I did not see it in the diff. The orchestrator should confirm the prove log names each mutant it killed.

## Blocking

None.

## Later

1. **Query bound holds only for short types.** `scheduling/use_cases/test_booking_page_data.py:200-217`, `booking_page_data.py:161-175`. The plan states 37 as the bound for any type. It is the bound only while three chunks cover the horizon: chunk 3 ends at `s0 + 93 - 2d` days (`s0 = now + 2h`, `d` the duration in days), which covers the horizon end at `s0 + 89.92` days only when `d ≤ ~1.54` days (about 37 hours). Longer types need more chunks: a 10-day type walks 4 chunks (2 + 7 + 28 + 7 = 44 queries), and the 22.7-day maximum walks about 11 chunks. The walk is still bounded by the horizon, so this is not a hang, but "at most 37" is wrong for those types. Smallest fix: state the bound in the plan as `2 + 7 × (chunks + 2)` with `chunks ≤ ceil(90 / (31 − d))`, or add a test with a long type. Risk if left: a planner reading the plan believes a fixed 37.
2. **Booking times page test is weaker than the plan.** `scheduling/views/pages/test_booking_times_page.py:128-137`. The plan said "same two expectations" as the provider page (next and previous links). The test asserts `Mon 14 Jan` and `week=2030-01-21` only. The previous link (`week=2030-01-07`) is not asserted. Smallest fix: add `assert "week=2030-01-07" in html`. Risk: a regression that drops the previous link would pass.
3. **Two `LEAD_TIME` constants.** `booking_page_data.py:9` imports `LEAD_TIME` from `booking_rules.py:11`; `HORIZON` comes from `search_matching.py:11`, and that module defines its own `LEAD_TIME` at `search_matching.py:10`. The walk mixes the two sources. Both are 120 minutes today. Smallest fix: take `LEAD_TIME` from `search_matching` next to `HORIZON`, or name the duplication in a later task. Risk: drift if one value changes.
4. **Second `find_free_slots` call duplicates the first.** `booking_page_data.py:85-87` and `:96-98`. Three lines repeated. Smallest fix: compute the target week first, then call once. Nit; the orchestrator can decide if the diff is clear as is.
5. **Named but out-of-range weeks now open on the first free week.** `booking_links.py:84-89` returns None when `day_in_range` fails, so `?week=1900-01-01` is treated as "names no week" and the walk runs. Before this change such an address showed the current week. Plan intended this ("out-of-range" in the plan's Rule). Listed here and under For the owner.
6. **Time budget not judged.** `make test` took 461 s in the verify_green stage and 263 s in check, on a shared machine. Not a blocker; the orchestrator measures on a quiet machine.

## For the owner

- Out-of-range named week (Later 5): should `?week=` with a valid date outside the 52-past / 104-future window open on the first free week (current behaviour in this change), or on the current week as before? The spec does not say. Not decided in this run.

## Left for the orchestrator

From the plan's `## Not in this run`:
- Staff pages (admin book, admin reschedule, clinician reschedule) opening on the first free week. Owner decision, not done.
- `HospitalPage` strip: no week strip in code for the hospital page; check issue #44 before closing.
- The lead-time question for listed slots (`free_slots.py:70` filters `start < now`, not `now + LEAD_TIME`). Observed, not changed.

Plan items of the slice that the run did not finish: none found in the diff. The mutant proofs M1 to M6 are not visible in the diff (see review item 8).
