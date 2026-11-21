# Plan: scheduling engine, pure (task 06)

Spec: `drlibre-specs.md` 5.1, 5.3, 5.5, 5.6, 4 (time). Model plan "Waits for its use case":
status transitions (5.6) and the pure policy numbers (5.3) land here; the rest stays task 07.

## Focal point

`free_slots` in `scheduling/domain/free_slots.py`. A wrong slot books a patient into time that
does not exist. Everything else is small tables and comparisons.

## Blocks, one sentence each

All under `scheduling/domain/`, plain frozen dataclasses in, values out. No ORM, no clock
(`now` argument), no I/O. Enums (`AppointmentStatus`, `Role`, `AppointmentSource`) are imported
from `scheduling.models` as `session_rules.py` already does.

1. `appointment_status.py`: `ACTIVE_STATUSES` (every status except `CANCELLED`, `NO_SHOW`;
   defined once, the one place the exclusion constraint's meaning is mirrored), `is_active`,
   `ALLOWED_TRANSITIONS` table, `can_transition(from, to)`, `RESCHEDULABLE_STATUSES`
   (`BOOKED`, `CONFIRMED`), `may_change_status(actor_role, is_own_appointment, to)` returning
   bool (check-in, complete, no-show: staff only, clinician own, admin any; cancel: patient own,
   clinician own, admin; patient 24 h rule is a booking rule, not here).
2. `free_slots.py`: `free_slots(rules, appointment_type, time_off, appointments, window, now,
   time_zone) -> list[datetime]` for one clinician; the four steps of 5.1 in four small
   functions (days in range, starts per rule, drop, dedupe+sort).
3. `slot_search.py`: `free_slots_by_start(clinicians: Mapping[id, ClinicianSchedule], ...)
   -> list[SlotOffer]`, `SlotOffer(start, clinician_ids: tuple)` sorted by start, ids sorted;
   refuses a window over `MAXIMUM_QUERY_DAYS = 31` by returning a value (`QueryTooWide`), not
   raising.
4. `booking_rules.py`: `POLICY` constants in one place (`LEAD_TIME = 120 min`,
   `CANCELLATION_WINDOW = 24 h`, `OPEN_ONLINE_BOOKINGS_MAXIMUM = 3`), `BookingRule` StrEnum with
   the five names from the table, `violated_rules(action, actor_role, new_start, current_start, now,
   open_online_bookings, type_bookable_online, slot_is_free) -> list[BookingRule]` returning all
   violations in table order. Two starts because 5.3 splits them on reschedule: `new_start`
   (BOOK, RESCHEDULE; `None` on CANCEL) feeds `lead_time_too_short` only; `current_start`
   (RESCHEDULE, CANCEL; `None` on BOOK) feeds `cancellation_window_closed` only. A start missing
   where the action needs it is a broken invariant (raises). `type_bookable_online` and
   `slot_is_free` refer to the new slot. To keep args near 3, the call takes one frozen
   `BookingAttempt` dataclass holding these fields plus `now`. `action` in {BOOK, RESCHEDULE, CANCEL}. Staff: only `outside_availability`
   (book, reschedule). Cancel by patient: only `cancellation_window_closed`.
   `count_open_online_bookings(appointments, now)` helper (future, active, source `ONLINE` or
   `ROUND_ROBIN`).
5. `first_available.py`: `rank_candidates(candidates, now) -> list[id]` and `first_available`
   returning the first id or `None`. Never assigned first; then largest `(now - last_assigned)
   * weight`; ties to the lowest id. Candidates with weight 0 are excluded (5.5 step 1).

## Decisions the spec leaves open

- **Weekday**: spec and stored rule: 0 Sunday to 6 Saturday. Python: `date.isoweekday() % 7`.
  Note: `scheduling/models/availability.py` names its bounds `WEEKDAY_MONDAY = 0`,
  `WEEKDAY_SUNDAY = 6`; the numbers are right, the names are wrong. Not touched here (blast
  radius: migrations, data model doc); recorded as a follow-up in the reply.
- **Rule valid on a day**: `valid_from <= local_day` and (`valid_to` is None or `local_day <=
  valid_to`), both inclusive.
- **Slot loop**: start = rule start; while start + duration <= rule end, emit, start += step.
- **Buffer**: each active appointment blocks `[starts_at, ends_at + buffer_of_booked_type)`.
  Time off blocks `[starts_at, ends_at)`. Overlap of half-open intervals: `a.start < b.end and
  b.start < a.end`. A slot may start when time off or an appointment (plus buffer) ends.
- **Range**: drop slot if `start < range_start`, `end > range_end`, or `start < now`. A start
  equal to `now` is kept (not in the past).
- **Daylight saving (local wall-clock, `zoneinfo`)**: local date and time combine into an
  aware datetime with `ZoneInfo`.
  - *Start does not exist* (spring forward, wall time in the gap, e.g. 02:30 in
    `Europe/Paris` on 2027-03-28): the slot is **skipped**. Never shifted: a patient was
    promised a wall-clock time that was never on the clock. Detected by round trip: convert
    the aware value to UTC and back to the zone; wall time differs means it does not exist.
  - *Start exists twice* (fall back, e.g. 02:30 on 2026-10-25 in `Europe/Paris`): offered
    **once**, the first occurrence (`fold=0`, the earlier UTC instant). The second is not
    offered, so a start is never ambiguous and the list stays unique.
  - Slot end is start plus duration in absolute time (UTC arithmetic), so a slot across a
    change is still the type's duration long. Rule end for the loop is compared in wall-clock
    time of that day as the rule says; a day with a gap or overlap inside the window keeps the
    local wall-clock bound, so the loop is done in local naive time and each candidate start
    is converted afterwards.
  - Days come from the local date of the range start to the local date of the range end, in
    the hospital zone, not UTC.
- **Union**: one entry per start; clinicians free at that start listed ascending by id.
- **Query width**: window longer than 31 days is a value result, expected failure (§9).
  Caller maps it to `invalid_input`.
- **5.3 numbers**: lead time check `start - now < 120 min` violates (exactly 120 passes);
  cancellation `start - now < 24 h` violates (exactly 24 h passes); open bookings `>= 3`
  violates.

## Files to touch, in order

1. `scheduling/domain/appointment_status.py` + `test_appointment_status.py`
2. `scheduling/domain/first_available.py` + test
3. `scheduling/domain/booking_rules.py` + test
4. `scheduling/domain/free_slots.py` + test (examples, daylight saving, property tests)
5. `scheduling/domain/slot_search.py` + test
6. `pyproject.toml`, `uv.lock`: dev deps `mutmut` (pinned) and `hypothesis` (pinned); mutmut
   config scoped to `scheduling/domain/` (excluding tests, `request_context`, `failure`
   glue as needed).
7. `Makefile` `mutate` target; `doc/adr/` note only if the tool choice needs one (the choice
   is stated in this plan; no ADR unless architect asks).

Not touched: models, migrations, views, use cases (task 07), `drlibre-specs.md`, existing
domain modules, `scripts/`, CI/process files, `.fabro/`.

## Mutation tool

`mutmut` (3.8.1 on PyPI; `requires-python >=3.10`, fits 3.13): Python-native, pytest-based,
mutates by file path glob, runs in the foreground, no server or Node. Alternative `cosmic-ray`
needs a session database and a separate `init`/`exec` pipeline and is heavier to bind to one
`make` line. Pin exact versions; `uv lock` records hashes. Task 06 modules scored in the
reply with wall time. Equivalent survivors are marked ignored, not chased (§10.2). Fallback if
mutmut cannot import Django settings or collect the xdist/pytest config: run it with
`-p no:xdist`, pure tests need no database.

## Invariants and blast radius

- No double booking: engine only reports free starts; the database exclusion constraint and
  task 07 lock stay the guard. The engine must never offer a start that overlaps an active
  appointment plus buffer, time off, or the past.
- Authorization stays server-side: `may_change_status` and `violated_rules` take the role and
  ownership from the use case's session, never the payload. Engine decides nothing alone.
- Audit log append-only: untouched (no writes).
- Blast radius: new modules and two dev dependencies. Nothing imports them until task 07.

## Failing tests first (`returns_X_when_Y`)

Appointment status
- `returns_false_when_status_is_cancelled_or_no_show` for `is_active`; true for the other four.
- `returns_true_when_transition_is_in_the_5_6_table`, one per row: BOOKED to CONFIRMED,
  CHECKED_IN, CANCELLED, NO_SHOW; CONFIRMED to CHECKED_IN, CANCELLED, NO_SHOW; CHECKED_IN to
  COMPLETED, CANCELLED.
- `returns_false_when_transition_is_not_in_table`: every other pair, including same to same,
  and anything out of COMPLETED, CANCELLED, NO_SHOW.
- `returns_true_when_status_is_booked_or_confirmed` for reschedulable; false for the rest.
- `returns_false_when_patient_checks_in`, `returns_false_when_clinician_completes_other_clinicians_appointment`,
  `returns_true_when_admin_marks_no_show_on_any_appointment`,
  `returns_true_when_patient_cancels_own_appointment`, `returns_false_when_patient_cancels_other_appointment`.

First available
- `returns_never_assigned_clinician_when_others_were_assigned`.
- `returns_lowest_id_when_several_were_never_assigned`.
- `returns_larger_idle_times_weight_when_all_were_assigned` (idle 2 h weight 1 loses to idle
  1 h weight 3).
- `returns_lowest_id_when_scores_tie`.
- `returns_none_when_no_candidate`; `skips_clinician_with_weight_zero`.

Booking rules
- Each rule in both directions at its boundary: start exactly 120 minutes away passes, 119
  violates; exactly 24 h passes, 23 h 59 violates; 2 open bookings pass, 3 violate; type not
  online violates; slot not free violates.
- `returns_every_violated_rule_when_several_fail_at_once` (stated list in table order).
- `returns_only_outside_availability_when_staff_books_a_slot_that_is_not_free`; staff never get
  the patient rules.
- `returns_no_rules_when_patient_cancels_25_hours_ahead`; cancel does not check lead time,
  online flag, count.
- Reschedule checks lead time, window, online flag, availability, not open-booking count.
- `returns_cancellation_window_closed_when_reschedule_current_start_is_under_24_hours` (new
  start days away: only that rule).
- `returns_no_cancellation_rule_when_reschedule_current_start_is_24_hours_away_but_new_start_is_close`
  (current start 25 h away, new start 60 min away: only `lead_time_too_short`).
- `returns_lead_time_too_short_from_new_start_not_current_start_when_rescheduling` (current
  start 3 h away is not enough alone to hide a new start 30 min away).
- `raises_when_reschedule_has_no_current_start` (invariant break).
- `count_open_online_bookings`: counts future active ONLINE and ROUND_ROBIN; ignores STAFF,
  past, cancelled, no-show.

Free slots (fixed zone `Europe/Paris`, `now` well before)
- 09:00 to 10:00, step 15, type 30 min: starts 09:00, 09:15, 09:30 (09:45 would end 10:15);
  start 09:30 ends exactly 10:00 is offered.
- `returns_nothing_when_rule_weekday_differs` and Sunday is 0 (2026-11-22 is Sunday), Saturday 6.
- Rule valid from and to inclusive; day before valid_from and after valid_to give nothing;
  `valid_to` empty is open ended.
- Time off 09:00 to 09:30: 09:30 offered, 09:15 not (overlap), slot ending at 09:00 offered.
- Appointment 09:00 to 09:30 and booked type buffer 10: slot at 09:30 and 09:35 dropped,
  09:40 offered; the appointment's own type buffer is not used (appointment type buffer 30,
  booked type buffer 10 gives the same answer).
- Cancelled and no-show appointments block nothing.
- Range edges: slot starting before range start dropped; slot ending after range end dropped;
  slot ending exactly at range end kept.
- Start before `now` dropped; start equal to `now` kept.
- Two overlapping rules same weekday: duplicate starts appear once, sorted ascending.
- Result is in UTC aware datetimes, sorted.
- Daylight saving, northern `Europe/Paris` and southern `Australia/Sydney` (and optionally
  `America/Sao_Paulo`-free list kept to two zones): spring forward in Paris 2027-03-28 and
  Sydney 2026-10-04: rule 01:30 to 04:00 step 30 type 30: the nonexistent local starts are
  skipped, local starts before and after keep their wall-clock time, offsets differ by the
  change. Fall back in Paris 2026-10-25 and Sydney 2027-04-04: the ambiguous start is offered
  once, at the first occurrence; same wall-clock rule on the day before and after gives the
  same local time with the other UTC offset. Range converted to local days in the zone: a
  range crossing local midnight but not UTC midnight picks the right local day.
- Property tests (`hypothesis`, strategies produce rules, time off, appointments within a
  few days): every slot lies within the range, starts at or after `now`, overlaps no time off,
  overlaps no active appointment extended by the buffer; the list is sorted and has no
  duplicates.

Slot search
- `returns_union_with_clinicians_free_at_each_start_when_two_clinicians_overlap`: start free
  for both lists both ids ascending; start free for one lists one.
- `returns_one_entry_per_start`; sorted ascending.
- `returns_too_wide_when_window_is_over_31_days`; exactly 31 days accepted.
- `returns_empty_when_no_clinicians`.

Each red test is proven to fail for the right reason first (§10.1); mutation then audits.

## Trust boundaries

None crossed: pure functions, no input parsing. The use cases (task 07) validate and
authorize, taking actor role and ownership from the session (§11). Engine functions take typed
values, `time_zone` as a `ZoneInfo` (the hospital name is validated by the hospital use case,
per the model plan). A zone that fails to load is the caller's error, not handled here.

## Vocabulary used (§3)

Clinician (`ClinicianProfile` fields `round_robin_weight`, `last_assigned_at`),
AvailabilityRule, TimeOff, Appointment, AppointmentType (duration, buffer, bookable online),
Hospital (time zone), Patient, Admin, Visitor not relevant. Domain input types are plain
dataclasses named after these (`AvailabilityWindow`, `BusyInterval`, `ClinicianSchedule`,
`SlotOffer`, `Candidate`), not model rows.

## Will not do

No use cases, no queries, no views or API, no clock access, no cache, no strategy classes, no
abstraction without a second caller, no refactor of existing domain modules, no rename of
the weekday constants, no `Any`, `cast` or bare suppressions. `make mutate` runs only
`scheduling/domain/`. Time spent for `make mutate` is measured and reported; if it exceeds a
single stage turn the scope narrows to the modules of this task.

## Architect review

Verdict: **revise** (one material gap; rest sound).

Material:
- `violated_rules` takes one `start`. On reschedule, 5.3 splits the times: lead time (120 min) and
  `outside_availability` apply to the **new** start; the 24 h window ("The appointment starts 24
  hours or more from now") applies to the **existing** start. One `start` cannot express both and
  would let a patient move an appointment that begins in 2 h to a far slot, or the reverse. Add a
  second argument (current start, used for RESCHEDULE and CANCEL) and name first tests:
  `returns_cancellation_window_closed_when_reschedule_current_start_is_under_24_hours` (new start far away),
  `returns_no_cancellation_rule_when_reschedule_current_start_is_24_hours_away_but_new_start_is_close`
  (new start still hits `lead_time_too_short`).

Checked and fine:
- Ladder: pure modules, one tool dep (mutmut, reason stated), hypothesis allowed by task. No speculation.
- Spec fidelity: 5.1 four steps, half-open intervals, booked-type buffer, 0 Sunday weekday, DST
  skip/once rule with both hemispheres, 31 days as a value, 5.5 ranking, 5.6 table all match.
- Security/architecture: no trust boundary crossed; role and ownership come from the use case; no I/O, no clock.
- Scope: waits-for-use-case items (status transitions, policy numbers) are picked up.

Non-blocking notes:
- Mutation: `hypothesis` inside mutmut runs can be slow; cap `max_examples` or mark deterministic
  examples as the killing tests. Report wall time and score as planned.
- Weekday constant naming bug in `models/availability.py` is correctly left as a follow-up, record it in the reply.

## Revision after architect review

Block 4 now takes `new_start` and `current_start` (see block 4); the four reschedule tests above
are written first. Non-blocking notes taken: hypothesis `max_examples` capped, deterministic
examples carry the mutation kills; weekday constant naming recorded as follow-up in the reply.

## Architect review (second pass, after revision)

Verdict: **approve**.

- The earlier gap is closed: `BookingAttempt` carries `new_start` (lead time, availability) and
  `current_start` (24 h window), with the three reschedule first tests and the invariant raise named.
- Re-read against 5.1, 5.3, 5.5 and 5.6: weekday 0 Sunday, inclusive validity dates, booked-type buffer,
  half-open overlap, 31-day value result, ranking and transition table all match. The DST choices
  (skip nonexistent, offer ambiguous once at the first occurrence) are stated and tested in both hemispheres.
- Ladder: only `mutmut` and `hypothesis`, both asked for; tool choice reasoned. No use case, ORM or clock.

Non-blocking, for the implementer:
- `may_change_status` for `CONFIRMED` is unspecified in 5.6 (no action sets it); keep it out of the tests
  beyond the table row.
- Keep `booking_rules.py` under 300 lines and `violated_rules` under 50 lines; split per-rule predicates if needed.
- Report `make mutate` wall time and score; if hypothesis slows mutmut, cap `max_examples`.
