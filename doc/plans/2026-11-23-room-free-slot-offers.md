# Slot offers require a free room

Slice: items 1 to 5 (one red test pair, one green change, one ADR). Nothing else in this run.

## Finding and focal point

Which side is wrong: **the slot offer.** `GET /api/v1/slots` offers T because the offer path
never reads rooms. The hold is right to refuse T.

- Offer: `scheduling/use_cases/free_slots_query.py:53` calls `free_slots_by_start`
  (`scheduling/domain/slot_search.py:39`), which unions clinician-only `free_slots`
  (`scheduling/domain/free_slots.py:49`). No room appears anywhere on that path.
- Hold: `scheduling/use_cases/placement.py:205-206` picks a clinician from `free_ids`
  (clinician-only), then `_choose_room` (`placement.py:260`) finds no free room and returns
  `no_room_available` (`scheduling/domain/placement_rules.py:91`).
- "The hold does not try the other clinician" is ruled out. Rooms are a department pool:
  `lock_rooms` returns the department's rooms, and `choose_free_room`
  (`placement_choice.py:59`) takes the first free one for any clinician. If Heart is busy at
  T, it is busy for both cardiologists. Retrying another clinician cannot succeed, so
  `choose_clinician` stays as it is.

Refusal code: the second hold at T answers HTTP 409 with code `no_room_available`, not
`conflict`. `refusal_for` (`scheduling/domain/booking_refusals.py:37-40`) maps it to 409
"That time was just taken." Spec 5.2 step 5 and ADR 0004 name `no_room_available` as 409.
The status matches the smoke test; the code differs from the orchestrator's wording.

## Plan (one sentence per block)

- `scheduling/domain/slot_search.py`: add `starts_with_free_room`, a pure function that keeps
  an offer only when at least one active department room has no active appointment
  overlapping `[start, start + duration)`. Same rule as `busy_room_ids`
  (`placement_checks.py:102`): half-open, no buffer.
- `scheduling/use_cases/free_slots_query.py`: in `find_free_slots`, for a type with
  `needs_room`, load the department's active room ids and the active appointments in those
  rooms overlapping the query window (two queries, constant count), and filter the offers
  through `starts_with_free_room`. Types without a room need are untouched.
- `scheduling/domain/test_slot_search.py` and `scheduling/use_cases/test_free_slots_query.py`:
  the red tests below, written first.
- `doc/adr/0013-slot-offers-need-a-free-room.md`: short record that spec 5.1 defines a free
  slot by clinician only, that this run makes a room-needing type's offer also need a free
  room, and that the owner must confirm the wording (see For the owner).
- `doc/handover.md`: change only if it states the old offer rule (grep first; leave it alone
  if it does not).

Not touched, on purpose: `placement_choice.free_clinician_ids` and `choose_clinician`. Filtering
there would turn `no_room_available` into `no_clinician_available` for first-available holds
and change the spec 5.2 step 5 error. Also not touched: the DB exclusion constraints, the hold
code, and `load_schedules`.

## Failing tests to write first (red, then prove they fail)

Domain, `scheduling/domain/test_slot_search.py`:
- `returns_no_offer_when_every_room_is_busy_at_the_start`: one room, busy 09:00 to 09:30, offer
  09:00 for a 30 minute type: the start is dropped.
- `returns_offer_when_one_room_is_free_at_the_start`: two rooms, one busy: the start stays.
- `returns_offer_when_room_booking_ends_exactly_at_the_start`: booking 08:30 to 09:00, offer
  09:00: the start stays (half-open, no buffer).

Use case, `scheduling/use_cases/test_free_slots_query.py`:
- `returns_no_start_and_slot_taken_when_first_hold_booking_takes_the_only_room`: the type
  needs a room; the department has one room, Heart, and two cardiologists whose rules cover
  09:00. First visitor holds 09:00 with no clinician named and verifies the hold (the code
  comes from the test mail outbox, as the booking verification tests do; find the helper in
  the red stage). Expect: `find_free_slots` no longer offers 09:00 for the type with no
  clinician named; a second visitor's `create_hold` at 09:00 returns `no_room_available`
  (409 "That time was just taken."). Red today: 09:00 is still offered.
- `returns_start_when_second_room_is_free_after_first_booking`: same setup with a second
  active room: 09:00 is still offered and the second hold succeeds. Guards against
  over-filtering; passes today, must keep passing.

Existing `returns_same_query_count_when_ten_clinicians` must still pass unchanged.

## Invariants and blast radius

- No write path changes. The DB no-overlap constraints stay the only guard against double
  booking. Placement and `choose_free_room` are not edited.
- Server-side only. `appointment_type_id`, `clinician_id` and the window were validated by the
  view (`views/slots.py`) before the use case; the room query is scoped by the type's
  department. Only room ids and times are read; no patient data enters the query or the
  response.
- Time comes from the request context (`now` passed in); the new check uses the window
  already passed in. UTC explicit as before.
- Callers of `find_free_slots` that change behaviour for room-needing types: `/api/v1/slots`
  (`views/slots.py:42`), booking page (`booking_page_data.py:85,96,111,165`), clinician
  agenda (`clinician_agenda.py:71`), FHIR slot reads (`fhir_slot_reads.py:122,154`). Each now
  hides starts with no free room. This is the intended effect.
- Demo seed (`scheduling/demo_seed/booking.py`) may see fewer offers; its `row_unless_slot_taken`
  already treats a refused slot as taken.

## Trust boundaries

- Request → `find_free_slots`: already validated by the view. Nothing new crosses.
- DB → room check: read-only, department scoped. Nothing leaves the server.

## Domain entities (CLAUDE.md §3)

Hospital (time zone), Department, Room (active flag, needs-room type), AppointmentType
(duration, buffer, needs room), Clinician (ClinicianProfile, shares the department's rooms),
Appointment (room, active statuses), BookingHold, Visitor.

## What I will not do

- No new abstraction, no new dependency, no refactor of `free_slots` or `load_schedules`.
- No change to `choose_clinician`, `choose_free_room` or the hold use case.
- No reservation of rooms by holds (see Not in this run).
- No edit to `drlibre-specs.md`.

## Not in this run

- `scheduling/use_cases/search_availability.py:43` (public search, per clinician via
  `free_slots`) still ignores rooms: same defect class in search.
- `scheduling/use_cases/fhir_slot_reads.py:223` marks starts free or busy by clinician alone;
  it disagrees with the new offer list for room-blocked starts.
- Holds do not reserve rooms. Two visitors can each hold the same start with different
  cardiologists while the room is free; the second fails at verify with `no_room_available`.
  Needs its own task (hold-time room reservation).

## For the owner

- Spec 5.1 defines a free slot by clinician only. This run makes a room-needing type's offer
  also require a free room, which spec 5.2 step 5 already enforces at booking. Confirm this
  reading, or say the offer should stay room-blind and the hold should refuse instead.

## Checks for the green stage

- Lint, tests, gate; `make mutate` for `scheduling/domain` (the new function is pure).
- Re-run the smoke sequence on a fresh seeded stack: after one booking at T, GET `/api/v1/slots`
  must not offer T, and the second hold at T must answer 409.

## Architect review

Verdict: approve.

Checked against the code, not only the plan text:
- Finding holds. The offer path (`free_slots_query.py:53`, `slot_search.py:39`,
  `free_slots.py:49`) never reads rooms. Placement picks the clinician first (`placement.py:205-206`),
  then the room. `busy_room_ids` (`placement_checks.py:102`) takes no clinician, so a busy room
  is busy for every cardiologist. Retrying another clinician cannot succeed, so leaving
  `choose_clinician` alone is correct.
- Offer side is the only spec-consistent fix. Spec 5.2 step 5 already makes the hold refuse
  with `no_room_available`. Spec 5.1 is clinician-only and says nothing about rooms. Changing the
  offer changes product behaviour, which is why the owner question is right.
- Refusal code: spec 5.2 table (`drlibre-specs.md:142`) and ADR 0004 both give
  `no_room_available` as 409. The orchestrator's "conflict" wording is the one that is wrong.
- Query-count test (`test_free_slots_query.py:175`) compares two equal-shaped calls, so two
  extra constant queries keep it green.
- Minor drift: `_choose_room` is at `placement.py:255`, not 260. Fix the reference when the plan
  is next touched; it does not change the decision.

Risks the plan should name, not block on:
- Reschedule. `find_free_slots` takes no `replacing` argument, and `busy_room_ids` accepts
  `ignoring_appointment_id`. A room held only by the appointment being moved will now hide the
  start in the offer, while placement with `replacing_id` would accept it. The clinician side
  already has this gap, so it is not new in kind, but the room side widens it. Either add a
  reschedule test or record it under "Not in this run".
- The red test's second `create_hold` assertion passes today, so it guards nothing new. It is
  fine as a smoke check; the red proof rests on the offer assertion.
- ADR 0013 is the next free number (0012 is the latest in `doc/adr/`).
