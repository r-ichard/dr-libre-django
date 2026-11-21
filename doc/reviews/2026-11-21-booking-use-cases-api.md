# Review: task 07, booking use cases and API

Diff `main...HEAD`: 22 files, +3068, no dependency or migration change. Reviewed the use cases,
views and schemas line by line; tests at plan level.

## Plan in one sentence per block (§2.5)

- `placement.py`: authorize from the session, lock clinicians, patient, rooms in one global order, check
  inside the lock, insert in a savepoint, audit and notify in the same transaction. Confirmed at a glance.
- `placement_checks.py`: conflicts in 5.2 order, rule inputs, constraint name to resource. Confirmed.
- `schedule_loading.py`: four queries for all clinicians; holds become BOOKED busy intervals. Confirmed.
- `placement_rules.py`: pure who-may-book-for-whom (5.4), room choice (5.2 step 5). Confirmed.
- Traced: lock order with `of=("self",)` and `order_by("pk")` (`placement.py:97`); under READ COMMITTED
  the checks after the locks see committed rows of the winner, so the loser gets `conflict` from the
  check, and from the constraint if it still slips through.

## Findings

1. **Nit** `scheduling/views/booking_schemas.py:30-31, 40-41`: `locals()["from"]` in a class body is a
   trick that is hard to read. Fix: a short comment is already there; later switch to `source="from"`
   style fields with names `starts_from` and `starts_before`.
2. **Nit** `scheduling/views/appointments.py:22`: `int(str(...))` to narrow `object`. Risk: none today.
   Fix: a typed `page_of(values)` helper beside `uuid_of`.
3. **Low** `scheduling/use_cases/schedule_loading.py:16-61` (placement): holds of the booking patient block
   the slot for themself. Task 12 (holds) must exclude the own hold when it converts a hold. Fix: note in
   task 12.
4. **Low** `scheduling/use_cases/free_slots_query.py:30`: an inverted range (`to` before `from`) is not
   rejected as `invalid_input`; behaviour rests on the engine returning no offers. Fix: reject
   `to <= from` in the schema.
5. **Low** `scheduling/use_cases/placement.py:81`: step 2 (named room inactive or foreign department)
   returns `not_found` after step 1 data is loaded; the specification names no code for step 2, so
   `not_found` is a reading, not a fact. Fix: confirm with the owner and put it in the spec.
6. **Low** `scheduling/use_cases/test_placement.py` is 426 lines (limit 300, hard 500). Fix: split by
   path (patient, staff, first available).
7. **Info** Proof left no trace: `943327d..7f15d35` touches test files only; `7bda64b` (refactor) edits
   product code, as the stage allows. `git log` names every stage.
8. **Info** Double booking: half-open intervals used in `find_conflicts` and `busy_room_ids`; clinician,
   patient and room all covered; constraint violation becomes `conflict` naming the resource, other
   integrity errors re-raise (invariant break). Racing tests exist for clinician, patient and room.
   Authorization comes from `signed_in_user(request)`; a payload `patient_id` is only a named party checked
   by `authorize_booking`. Audit entry and notification are in the placement transaction. Body omits
   reason and notes. No sensitive data logged.

Not run here: `make mutate` (the stage reports only gate, lint and tests, which passed: 1125 tests).

## Blocking

None.

## Later

- Findings 1 to 6 above.
