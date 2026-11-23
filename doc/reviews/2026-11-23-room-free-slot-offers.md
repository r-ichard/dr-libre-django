# Review: slot offers require a free room

Scope reviewed: `git diff main...HEAD` on `fabro/run/01M849QWZZHGGJBNK02KF1JBDT`
(5 files, +368 −8): plan, `scheduling/domain/slot_search.py`,
`scheduling/use_cases/free_slots_query.py`, and their two test files.

Verdict: **approve.** No blockers.

## Block by block

- `slot_search.py:65-76` `starts_with_free_room`: keeps an offer while fewer distinct rooms
  are booked over `[start, start + duration)` than exist. Confirmed at a glance: pure, no I/O,
  no clock.
- `slot_search.py:79-88` `_rooms_booked_over`: half-open overlap test
  (`span.starts_at < start + duration and span.ends_at > start`). Traced: a booking ending
  exactly at the start, or starting exactly at the end, does not count. Matches
  `placement_checks.py:102-114` (`busy_room_ids`, same statuses, no buffer). Traced.
- `free_slots_query.py:50-54`: a room-needing type with no active room returns an empty
  Success, as before (`_lacks_room` was replaced, same outcome). Confirmed.
- `free_slots_query.py:67-68`: the room filter runs after the clinician union, so it applies
  to every caller (named clinician or not). Correct: the room is a department pool
  (`placement_locks.py:25-33`, `placement_choice.py:59-68`).
- `free_slots_query.py:72-93` `_room_rows`: one query, left join via `FilteredRelation` with the
  active-status and overlap-window condition inside the join. A room with no booking yields one
  row with `None`, so the room count is still right. Window bounds are correct: a start in
  `[window.starts_at, window.ends_at)` overlaps only bookings with `starts_at < window.ends_at +
  duration` and `ends_at > window.starts_at`. Traced.
- `free_slots_query.py:96-102` `_with_free_room`: `room_count` counts distinct active rooms
  (rows exist for each, even empty ones). Confirmed.
- Tests (`test_slot_search.py:119-163`, `test_free_slots_query.py:262-304`): derived from the
  specified rule (5.2 step 5, half-open overlap), not from the code's output. The red test
  (`test_free_slots_query.py:262`) reproduces the two bookings from the orchestrator's smoke
  sequence: first hold at 09:00 verified, slot still offered before the fix, second hold refused.

## Proof trace (§7 rule 7)

- `5b4867f` red: test file only. Good.
- `0eb7bcd` verify_red, `1f71e3c` verify_green: no file change.
- `203be4b` green: product (`slot_search.py`, `free_slots_query.py`), before prove. Good.
- `9c06462` prove: `test_slot_search.py` and `test_free_slots_query.py` only, +89 lines, no
  product line. Good.
- `db6ddd9` refactor (after prove): moves the overlap count into `_rooms_booked_over`; the
  product change is behaviour-preserving (same predicate, same set). Allowed: it is after prove.
- `3ce8979` check: no file change.

## Authorization, boundaries, audit, sensitive data

- No new route, serializer, form or write. `find_free_slots` already receives validated
  input from `views/slots.py` (plan, trust boundaries). The room query is scoped by the type's
  department (`free_slots_query.py:77-79`). Only room ids and times are read.
- No audit entry needed: no write. No logging added. No new dependency.
- No `Any`, `cast`, bare `# type: ignore` or bare `# noqa` in the diff.
- Functions are under 20 lines; files are under 110 lines.

## Double booking (spec 5.2)

- No write path changed. The DB no-overlap constraints and placement are untouched.
- The offer and placement now agree on room occupancy: a start is offered only when at least
  one active room has no active booking over its whole length. Placement can still refuse a
  start that a concurrent hold just took (no hold reserves rooms). That is the known gap in the
  plan's "Not in this run", not a regression.

## Names and comments

- Names state roles: `starts_with_free_room`, `_rooms_booked_over`, `_room_rows`,
  `_with_free_room`, `booked`, `room_count`. Good.
- Docstrings are under 255 characters and say why (for `_with_free_room`: placement refuses
  such a start). Good.
- The `RoomRow` alias (`free_slots_query.py:30`) is clear.

## Findings

### Later

1. **Reschedule: a start held only by the appointment being moved is hidden.**
   `free_slots_query.py:67-68` and `_room_rows` (`:72-93`) have no `replacing` argument.
   Placement passes `replacing_id` to `busy_room_ids` (`placement_checks.py:102-114`,
   `ignoring_appointment_id`), so a reschedule can take a start the offer no longer lists.
   Risk: narrower reschedule offers. No double booking: placement still decides. The clinician
   side already has the same gap. Smallest fix: record it under "Not in this run" in the plan,
   or add a reschedule test.
2. **Plan's "Not in this run" list lacks the reschedule item** that the architect review asked
   for (`doc/plans/2026-11-23-room-free-slot-offers.md`, "Architect review", risks). Fix: add it.
3. **Query count not covered for the room path.** `test_free_slots_query.py:217`
   (`returns_same_query_count_when_ten_clinicians`) runs a type with no room need, so the two new
   queries in `_room_rows` are not counted. Smallest fix: a second count test with
   `needs_room=True`.
4. **Redundant test.** `returns_no_offer_at_nine_when_the_only_room_has_a_later_booking_too`
   (`test_free_slots_query.py:274`) adds a 13:00 booking that does not touch 09:00. It asserts
   the same as `:262`. Smallest fix: delete it, or make the second booking overlap 09:00 and
   assert it changes nothing.
5. **Private helpers imported across test modules.** `test_free_slots_query.py:17-22` imports
   `_create`, `_held`, `_last_code`, `_verify` from `test_booking_support`. Works, but the
   helpers should be public in that module. Later.
6. **Red run shows an error the green run does not.** The verify_red output has
   `ERROR scripts/test_size_cap.py::returns_0_when_every_listed_file_is_within_limits`, and red
   collected 5429 tests against 5428 passed in green. I ran `scripts/test_size_cap.py` with the
   Makefile environment (`SAFE_ENV`): 11 passed. The cause of the red-stage error is not
   established. Orchestrator: check the count on the verify branch.
7. **Plan drift.** The plan cites `placement.py:260` for `_choose_room`; it is at `:255`.
   Documentation only.
8. **Mutation not run here.** `make mutate` on `scheduling/domain` is the orchestrator's last
   gate; the new pure function is the target.

### Left for the orchestrator

From the plan's slice ("Slice: items 1 to 5 ... one ADR") and "Not in this run":

- ADR `doc/adr/0013-slot-offers-need-a-free-room.md` is **not in the diff**. Slice item 5.
  The owner decision it records is in "For the owner" below.
- `doc/handover.md`: grep finds no statement of the old offer rule. Nothing to change, as the
  plan allowed.
- Not in this run (plan): `search_availability.py:43` (public search ignores rooms);
  `fhir_slot_reads.py:223` (FHIR marks starts by clinician alone); holds do not reserve rooms
  (needs its own task).
- Reschedule risk (Later 1 and 2).
- `make mutate` and `make fhir-validate` (Later 8).

## For the owner

- Spec 5.1 (`drlibre-specs.md:159-177`) defines a free slot by clinician only and says nothing
  about rooms. This run makes the offer for a room-needing type also require a free room, which
  spec 5.2 step 5 (`drlibre-specs.md:188-191`) already enforces at booking. The owner should
  confirm this reading, or say the offer stays room-blind and the hold refuses instead. The
  spec text is not changed by this run.
- Refusal code: the second hold at a taken start answers 409 with `no_room_available`
  (spec table, `drlibre-specs.md:142`), not `conflict`. Both are 409; the code is per spec.

## Blocking

(none)
