# Plan: #44 second half, a strip opens on the first free week

Slice: #44 second half, backlog 27b item 8 only: the provider page, the booking times page and the patient reschedule page open on the week of the first free time within the booking horizon when the address names no week and the current week has none. The first half (no past "Previous week") is merged in 78f7d60 and is not touched. The four staff callers of `week_of_slots` keep today's week.

Focal point: `scheduling/use_cases/booking_page_data.py::week_of_slots` (line 69). One keyword flag selects the new rule, so the three named pages opt in and nothing else changes.

## Rule

When the address names no week (`asked_week is None`, which `week_from` returns for a missing, unparsable or out-of-range address), the flag `open_on_first_free` is True, and the current week has no offer for the visitor's view, the strip opens on the week of the first offer inside the horizon `[now + LEAD_TIME, now + HORIZON)`. `LEAD_TIME` is 120 minutes (`booking_rules.py:11`), `HORIZON` is 90 days (`search_matching.py:11`, spec 6.2). When nothing is free in the horizon, the current week is shown, as today. An address that names a valid week always shows that week. Weekday convention in tests: `AvailabilityRule.weekday` is 1 for Monday (`free_slots.py:86`).

## Blocks

1. `week_of_slots`, lines 69 to 82: add a keyword-only parameter `open_on_first_free: bool = False`. Keep `_week_shown` and the current-week `find_free_slots` call. If the flag is set, `asked_week` is None and that result has no offers, call `_first_free_start` (block 2). A start moves `week_start` to the Monday of that start in the hospital zone, and the same `find_free_slots` call loads that week. A `Failure` from the walk is returned as is, as the current-week call does. The function stays under 50 lines.
2. New `_first_free_start(appointment_type_id, clinician_id, online_only) -> Result[datetime | None]`, about 15 lines, placed after `_week_shown`: walk `[now + LEAD_TIME, now + HORIZON)` in chunks of at most `MAXIMUM_QUERY_DAYS` (31, `slot_search.py:18`). Each chunk calls `find_free_slots` with the same type, clinician and `online_only`. Return the first offer's start of the first chunk that has one, else None. Between chunks step back by the appointment duration (`chunk_end - found.value.duration`) so a slot crossing a chunk border is not lost. The step back is the same rule as `search_availability.next_starts`.
3. Imports in `booking_page_data.py`: `LEAD_TIME` from `scheduling.domain.booking_rules`, `HORIZON` from `scheduling.domain.search_matching`, `MAXIMUM_QUERY_DAYS` from `scheduling.domain.slot_search`. Constants are reused, none added.
4. Three one-line callers pass `open_on_first_free=True`: `scheduling/views/pages/detail_pages.py:39` (provider page), `scheduling/views/pages/booking_times.py:36` (booking times page), `scheduling/views/pages/patient_reschedule.py:50` (patient reschedule).

## Why the walk does not call `next_starts`

`search_availability.next_starts` works on one `ClinicianSchedule` that the caller already loaded. It does no room check and does not take `online_only`. `week_of_slots` gets its schedules through `find_free_slots`, which owns the clinician union, the room check, `online_only` and the 31-day cap. Reusing `next_starts` would mean loading schedules a second time in the use case. So the walk calls `find_free_slots` per chunk and reuses the same step-back rule and the `MAXIMUM_QUERY_DAYS` constant.

## Files, in order

1. `scheduling/use_cases/test_booking_page_data.py`: the use-case tests below (red).
2. `scheduling/views/pages/test_detail_pages.py`, `scheduling/views/pages/test_booking_times_page.py`, `scheduling/views/pages/test_patient_portal_guards.py` (near line 166, the existing reschedule week test): one page test each (red).
3. `scheduling/use_cases/booking_page_data.py`: blocks 1 to 3 (green).
4. The three callers in block 4 (green).

Existing tests of the staff pages (`test_admin_booking_pages.py`, `test_admin_appointment_pages.py`, `test_clinician_qa_round_two.py`) need no change: their default is today's week, and a test pins that (below).

## Not touched

`find_free_slots`, `free_slots_query.py`, `slot_search.py`, `search_availability.py` (no reuse, see above), `_week_shown`, `booking_times.py::week_strip`, the templates, CSS, the admin book, admin reschedule and clinician reschedule pages (staff keep today's week), `HospitalPage` (it has no week strip in code, although issue #44 lists a hospital page), `booking_rules.py`, `search_matching.py`, `doc/backlog/` (orchestrator updates the backlog), the spec.

## Invariants and blast radius

- Read-only: no write, no audit entry, no transaction. Double booking untouched.
- Offers come from `find_free_slots` with the caller's `online_only`, the path the time list uses. A strip cannot show a slot the list would not, and a visitor never sees a free time only a hidden clinician or a staff-only type has. Pinned by a test below.
- Blast radius: three pages. Staff pages are unchanged because the flag defaults to False.
- Filter used by the walk is `start < now` inside `free_slots` (read at `free_slots.py:70`); the lead time is not applied to listed slots by `find_free_slots`. That is existing behaviour, see "Observed" below.

## Query bound (stated and asserted)

Counted from the code, the red stage measures and corrects it if needed:
- `find_free_slots` costs 6 queries for a type that needs no room (`active_appointment_type` 1, clinician ids 1, `load_schedules` 4: rules, time off, appointments, holds). A type that needs a room adds 1 (`exists()`), so 7.
- `slot_choice` costs at most 2.
- `week_of_slots` makes at most five `find_free_slots` calls: the current week, at most three horizon chunks (90 days in chunks of 31 with the step back), and the found week.

Bound: 2 + 5 × 7 = **37 queries**. Worst case for a room type with first free time in the last chunk: 2 + 7 + 3 × 7 + 7 = 37. Nothing free in the horizon: 2 + 7 + 21 = 30. The bound is asserted with `CaptureQueriesContext` in the test below (`<= 37`), using a rule whose first free Monday is in the last chunk.

## Failing tests first

Clock: monkeypatch `clock.now_utc` as the existing frozen-clock tests do. Hospital zone Europe/Berlin (`builders.py`). Default `make_clinic` rule: Monday 09:00 Berlin, valid from 2030-01-01, appointment type 30 minutes, bookable online. Now Sunday 2030-01-13 12:00 UTC unless stated. The current week, Monday 7 to Sunday 13 January, has no free time because its Monday is past. Horizon chunks (`[now + 2h, now + 90d)` cut in 31-day chunks, step back 30 minutes): Jan 13 15:00 Berlin to Feb 13 15:00; Feb 13 14:30 to Mar 16 14:30; Mar 16 14:30 to Apr 13 12:00 UTC.

Use case tests (`scheduling/use_cases/test_booking_page_data.py`):
- `returns_week_of_first_free_time_when_current_week_has_none_and_week_is_not_named`: flag True. Expected `week_start` 2030-01-14 (first free Monday 14 January 09:00 Berlin).
- `returns_named_week_when_named_week_has_no_free_time`: flag True, `asked_week` 2030-01-07. Expected `week_start` 2030-01-07 with no days. Guard test, green before the change.
- `returns_current_week_when_nothing_is_free_within_horizon`: flag True, rule valid from 2030-07-01 (after 13 April 2030). Expected 2030-01-07.
- `returns_week_of_slot_that_crosses_the_first_chunk_border`: flag True, rule Wednesday 14:45 to 16:00 Berlin, valid from 2030-02-13 (the Wednesday the first chunk cuts at 15:00). Chunk 1 cannot hold the 14:45 slot (it ends 15:15, past the cut). Only the step back finds it. Expected `week_start` 2030-02-11. Without the step back: 2030-02-18.
- `returns_current_week_for_visitor_when_only_hidden_clinicians_are_free`: flag True, `clinician_id` None, the clinician's specialty inactive. Visitor (`online_only=True`) expected 2030-01-07. Staff (`online_only=False`) expected 2030-01-14.
- `returns_at_most_37_queries_when_first_free_time_is_in_last_horizon_chunk`: flag True, rule valid from 2030-03-18 (the first Monday of chunk 3). Expected `week_start` 2030-03-18 and `len(captured.captured_queries) <= 37`.
- `returns_current_week_when_first_free_time_is_not_asked_for`: flag default (False), now as the first test. Expected 2030-01-07. Pins the staff callers.

Page tests (red), each with now Sunday 2030-01-13 12:00 UTC and no `week` in the address:
- provider page (`test_detail_pages.py`): `next` link is `week=2030-01-21`, `previous` link is `week=2030-01-07`.
- booking times page (`test_booking_times_page.py`): same two expectations.
- patient reschedule page (`test_patient_portal_guards.py`, near line 166, existing fixture): the strip's `next` link points at the week after the first free week. The expected date is derived from that fixture's rule in the test, stated in its name.

## Proof that the tests guard

Scratch edits, reverted before commit, one per mutant. Each named test must fail:
- M1, always the current week (no walk): the first test and the three page tests.
- M2, horizon longer than 90 days: the nothing-free test (first free Monday after 13 April 2030). Horizon shorter than 62 days: the query test (its free Monday is in chunk 3). No test pins the exact 90th day.
- M3, `online_only` dropped from the walk: the visitor test.
- M4, no step back: the border test (expects 2030-02-11, gets 2030-02-18).
- M5, `asked_week` ignored: the named-week guard test.
- M6, flag ignored (always walk): the default-flag test.

## Trust boundaries

- `week` query parameter: `week_from` checks the range; the walk takes no client value.
- `online_only`: from `online_only_for(user)`, or fixed True on the patient reschedule page, as today.
- `open_on_first_free`: a constant set in server code, not a request value.
- Extra work: anonymous visitors on the provider and times pages cause up to 37 queries per GET. The times page's `read_scope` is `RateLimitScope.SCHEDULE`; the provider page's scope is checked in the red stage and stated in the review if it differs. Not a new endpoint.

## Domain entities (CLAUDE.md §3)

Visitor, Patient, Clinician (ClinicianProfile), Hospital (time zone), Department, AppointmentType (duration, bookable online), AvailabilityRule, TimeOff, Appointment, BookingHold.

## What I will not do

No new abstraction, module or dependency. No change to the strip template, CSS, `find_free_slots`, the domain, the lead-time rule for listed slots, or the staff pages. No backlog or spec edit. No `_week_shown` rewrite.

## Observed, not changed

Read in `free_slots.py:70` and `free_slots_query.py`: the strip's slot list filters `start < now`, not `now + LEAD_TIME`, so a slot inside the 120 minute lead time can still be listed. The walk starts at `now + LEAD_TIME`, so it never opens on such a slot. Separate task if the owner wants the lead time applied to listed slots.

## Not in this run

- Staff pages (admin book, admin reschedule, clinician reschedule) opening on the first free week. Owner decision: the task named three pages. Would need the owner's OK and a test change.
- `HospitalPage` strip: no week strip exists in code for the hospital page. The issue text is older than the code. Orchestrator to check against #44 before closing.
- The lead-time question above, if the owner asks.

## Architect review, addressed

1. Border test: rule now valid from 2030-02-13, so only the step back finds the 14:45 slot. M4 fails the test.
2. Scope: restricted to the three named pages with a keyword flag defaulting to False. Staff pages keep today's week, and a test pins it. Owner question for staff pages is in "Not in this run".
3. Query test: corrected chunk dates in the test notes (Jan 13, Feb 13, Mar 16 cuts). Rule now valid from 2030-03-18, the first Monday of chunk 3, expected 2030-03-18.
4. Reuse: the walk does not reuse `next_starts`, with the reason above. It reuses its step-back rule and `MAXIMUM_QUERY_DAYS`.

## Architect review

Second review, against the revised plan and the code. Verdict: approve.

1. Ladder: one keyword flag on `week_of_slots`, one private walk, three caller lines. No new module, dependency or abstraction. Right layer (use case; the view only passes a flag).
2. Blocks: each stated in one sentence. Vocabulary matches CLAUDE.md §3.
3. Tests: the border test is now sound. The rule starts Wed 13 Feb 2030, so chunk 1 cannot hold the 14:45 slot and only the step back finds it (week of Mon 11 Feb). Without the step back the next offer is Wed 20 Feb (week of 18 Feb), so M4 fails the test. Edge and error paths are covered: nothing free, named week, hidden clinicians for visitor and staff, default flag.
4. Query bound checked against code: `active_appointment_type` uses `select_related`, so no-room `find_free_slots` is 6 queries, room type 7 (`_lacks_room` short-circuits on `needs_room`). `slot_choice` is 2. 2 + 5 × 7 = 37 holds. The red stage must still measure it.
5. Reuse: `next_starts` (in `scheduling/domain/search_availability.py`, not `use_cases/`) takes a preloaded `ClinicianSchedule`, has no room check and no `online_only`. The stated reason holds. The walk reuses its step-back rule and `MAXIMUM_QUERY_DAYS`. `FoundSlots` carries `duration`, so `found.value.duration` exists.
6. Scope: restricted to the three named pages behind a default-False keyword. Staff callers are pinned by a test and listed under "Not in this run".
7. Security: `open_on_first_free` is a server constant; `online_only` comes from the same source as today; the walk takes no client value. Anonymous GET cost rises to at most 37 queries; the rate-limit scope check is named as a red-stage item.

Nits, not reasons to revise:
- `week_from` returns None only outside `day_in_range`, but `_week_shown` treats anything beyond 52 past or 104 future weeks as the current week. An address naming a week between those bounds and `day_in_range` shows the current week and does not walk. The plan's "names a valid week" wording should say this, or the red stage should pin it.
- The walk's stop condition (`chunk_end` reaching the horizon end) is not written out. The red stage should check the last chunk is clipped to `now + HORIZON`.
- The existing test at `test_patient_portal_guards.py:166` passes `?week=2030-01-21` explicitly, so it is unaffected by the change. Keep it that way.
