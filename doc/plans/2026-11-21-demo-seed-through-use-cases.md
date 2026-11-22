# Plan: task 17d, the demo seed books through the use cases

Focal point: `scheduling/demo_seed/writer.py`. The organisation and people stay as they are
(upsert by code or email). Appointments, status changes, waitlist entries, offers, notifications
and reminders stop being model writes and become calls to the use cases of tasks 08 and 09.

One sentence of plan: build the moving world by calling `place_appointment`, `change_status`,
`cancel_appointment`, `join_waitlist`, `accept_offer`, `expire_waitlist`, `send_reminders` and
`mark_read` as the demo users, on weekday slots that `free_slots` offers, once per local day,
and recognise it by an audit marker.

## Blocks

| Block | File | One sentence |
| --- | --- | --- |
| Weekdays | `catalogue.py:13` | `WEEKDAYS_WORKED = (1, 2, 3, 4, 5)`: stored 0 is Sunday (spec 3.1), so Monday to Friday is 1 to 5. Rules stay 09:00 to 17:00, inside the 07:00 to 19:00 grid. |
| Working days | `scenarios.py` | `day_offset` becomes a working-day offset in the hospital's zone: 0 is today, or the next Monday to Friday when today is a weekend; negative goes back over working days. `starts_at_for` skips Saturday and Sunday. Pure, no clock. |
| Hours | `scenarios.py` | Every `hour` becomes a start on the 15 minute step between 09:00 and 16:00 and ends by 17:00; no two seeds of one clinician touch (the 5 minute buffer included). |
| Time off | `writer.py` | `create_time_off(TimeOffCommand(start, end, reason), clinician_user)` as the clinician, start = local midnight of the first day, end = local midnight after the last day, both converted to UTC from the hospital zone. Repeatability: before calling, skip a period already present in `TimeOff` for that clinician (same start and end). A `Failure` raises. Seeded time off gets its `time_off.create` audit entry; later-day runs add a new period only when a period of the same label is not already there. |
| Scenarios | `scenarios.py` | `NOTIFICATIONS` goes (titles come from the use cases). `AppointmentSeed` loses `from_waitlist`, `WaitlistSeed` loses `offered` and `status`: those states now follow from the steps. `CONFIRMED` is dropped, see below. |
| Booking | new `demo_seed/booking.py` | `book(seed, clock)`: actor is the patient for `ONLINE` and `ROUND_ROBIN` (no clinician named), the clinician's user for `STAFF`; a `Failure` raises `SeedBrokeRuleError`, never swallowed. |
| Clock | `demo_seed/booking.py` | See "Clock". |
| Marker, retire | new `demo_seed/marker.py` | See "Marker". |
| Mail | `writer.py` | See "No email". |
| Run order | `writer.py` | `seed_demo` upserts the stable catalogue, then, only if the world is not current for today, retires the old world and builds the new one (below), then writes the summary audit entry. A current world writes nothing. |
| Command | `seed_demo.py` | Unchanged: `DEBUG` check, `DEMO_PASSWORD` check, outer context. |

## Build order (inside one `transaction.atomic`, as today)

1. Appointments, one per `APPOINTMENTS` seed, in file order, each booked at clock
   `min(now, start - 2 days)` so the lead time rule holds and the slot is not past at that clock.
   A round robin seed comes after the named clinician's seed at the same start, so the ranking has
   one candidate (no dependence on random ids).
2. Status changes: `change_status` as the clinician: `BOOKED -> CHECKED_IN`, `CHECKED_IN ->
   COMPLETED`, `BOOKED -> NO_SHOW`. Cancels: `cancel_appointment` as the clinician with a reason
   (staff are free of the 24 hour rule), at the booking clock for past ones, at now for future.
3. Waitlist joins: `join_waitlist` as the patient, window = whole local days. Done before the
   cancel of step 2 that should offer, so the cancel makes the offer: order is "book, join, cancel".
   - waiting: Berlin cardiology consult, preferred clinician, no matching cancelled slot.
   - offered: Berlin patient joins for the phone follow-up; the cancel of the other patient's
     phone slot offers it (`offer_freed_slot`), notification "Waitlist slot offered".
   - booked: Sydney other patient joins; the cancel of a paediatric slot (new cancelled Sydney
     seed) offers it; `accept_offer` as that patient books it (source becomes `ONLINE`, the
     use case's own rule).
   - expired: New York other patient joins at a clock before an all-past window; `expire_waitlist`
     at now expires it.
4. `send_reminders(None)` once at now; `mark_read` as the patient on the notifications that should
   show read. The rest stay unread.

## Clock

The seed never touches the clock source. It enters `bind_request_context(RequestContext(id, moment))`
(a context manager over a `ContextVar`, `use_cases/request_context.py`) around a single use case
call and leaves it in `finally`; the outer context of the command comes back unchanged. The only
caller is `booking.py::at_clock(moment)`; every seed call goes through it, nothing else in the
package imports `bind_request_context`. A past clock is never later than the real now (a test
asserts it), and use cases read `current_request_context().now`, not the wall clock, so nothing else
can move it (`test_no_wall_clock.py` already guards that). Audit entries of past steps carry the
past instant, which is true to the story.

## No email

Each notification is saved with `email_pending=True` and sends on commit
(`notifications._notify`, `transaction.on_commit`). The seed snapshots the ids of pending rows before
the build and, still inside its transaction and before commit, sets `email_pending=False` on every
pending row that is not in the snapshot (queryset `update`, so no version bump). The on-commit
callback filters `email_pending=True` and finds nothing: no send, no `notification.email_sent`
audit entry, nothing for `send_pending_emails`. Pending rows of real users that existed before are
left alone. Test: run with `django_capture_on_commit_callbacks(execute=True)`; `mail.outbox` empty
and zero pending rows.

## Marker

One `AuditLogEntry` per seeded appointment and waitlist entry, written by the seed inside the
build: action `demo_seed.mark`, entity type `DemoSeed` (the type the old summary entry already
uses), entity id the row's pk as text, metadata ids `appointment_id` or `waitlist_entry_id` (keys
the audit metadata type accepts), created at the build's `now`. Seeded set = rows whose pk is in a
`demo_seed.mark` entry. The log is append-only by trigger, so a mark survives a retire and tells the
run day. No column of any model changes. A booking made by a person is never in the set, so the seed
never retires it.

Why it leaks nothing: the only reader of `AuditLogEntry` outside use cases is
`use_cases/clinician_appointment.py:26 appointment_history`, which filters `entity_type="Appointment"`
and `entity_id`; a `DemoSeed` entry never matches. Grep for `AuditLogEntry` and `audit` in views,
serializers and API routes (red step, before writing code) must find no other reader; the plan lists
the result in the run notes. Tests, not prose: (a) `returns_same_history_actions_when_seeded_and_person_booked`:
the `appointment_history` actions of a seeded booked appointment equal those of one a person
booked with `place_appointment` (`appointment.book` only, no `demo_seed.*`); (b) the clinician
appointment page of a seeded appointment, fetched as that clinician, does not contain `demo_seed`;
(c) a fetch of every existing page and API route as admin finds no `demo_seed` string
(parametrised over the route list the existing tests already use). The planned FHIR `AuditEvent` is
admin-only (spec 15.4), not built yet; if built later it shows entity type and id, no names.

Repeat: the world is current when the newest mark's local date equals today's local date in each of
the three hospital zones. Then nothing runs: no row changes, no audit entry (the `demo_seed.run`
summary entry is written only when a build happened). Later day: retire, then build.
Retire deletes, in order, clinical notes, notifications, waitlist entries, appointments of the
seeded set (relations are `PROTECT`, so order matters). Marks of retired rows stay.

## Later day and taken slots

Decision: skip, never reset. A later-day build asks `place_appointment` for each seed; a `Failure`
with code `CONFLICT`, `NO_ROOM_AVAILABLE` or `NO_CLINICIAN_AVAILABLE` (the slot is taken, by a person
or by another seed) means the seed is skipped and every step that depends on it (status change,
cancel, the waitlist join and offer built on it) is skipped with it. Any other `Failure` (forbidden,
invalid input, rule violation) is a defect of the seed and raises, rolling back. Test 10 changes
accordingly: a person's booking on a seeded slot makes the run succeed, the person's booking survives
unchanged, the skipped seed is absent, and the second run is still a no-op.
Past slots cannot be taken by a person (no booking in the past), so the story of a finished visit is
never skipped.

## Invariants

- Double booking: only `place_appointment` creates appointments; the exclusion constraints stay the
  last line. The seed builds nothing the constraints refuse; a `Failure` raises and rolls back.
- Server-side authorization: every call carries a real demo user as actor; the use cases decide.
- Audit append-only: the seed only inserts; retire never touches `AuditLogEntry`.
- One transaction for the whole seed, as now. A raise leaves the database as it was.
- Blast radius: `scheduling/demo_seed/`, its tests, `mutation-equivalents.txt` untouched (domain not
  changed), `doc/backlog.md` and `doc/retro.md` by the orchestrator. Production code outside the
  seed is not touched.

## Files, in order

1. `scheduling/demo_seed/test_seed_world.py` (new, red first) and edits to `test_writer.py`,
   `test_seed_demo_command.py`, `seed_support.py`.
2. `catalogue.py`, `scenarios.py`, `booking.py`, `marker.py`, `writer.py`.

Not touched: models, migrations, views, templates, API, any use case, `seed_demo.py`, domain, README
(none exists in the repo; the account list is in `catalogue.PEOPLE` and `.env.example`).

## Failing tests first (`returns_X_when_Y`, expected values in words)

1. `returns_weekdays_one_to_five_when_seeded` (#32): each demo clinician has rules for stored
   weekdays 1 to 5 exactly, none for 0 or 6.
2. `returns_every_appointment_inside_a_rule_and_outside_time_off_when_seeded_on_an_empty_database`:
   for each seeded appointment, local weekday in spec numbering has a rule of its clinician valid on
   the day, start on the rule step, end not after rule end, within 07:00 to 19:00, no overlap with
   the clinician's time off; `full_clean` and `validate_constraints` pass.
3. `returns_each_appointment_on_a_free_slot_when_booked`: the seed's own booking step, replayed at
   its clock, finds the start in `free_slots` (guards a seed that drifts from the rules).
4. `returns_whole_local_days_when_time_off_is_seeded`: each time off starts at 00:00 local and ends
   at 00:00 local of the next day after its last day (not 01:00 local, not UTC midnight).
5. `returns_section_11_titles_when_notifications_are_seeded`: every title is one of the six of section 11
   ("Appointment booked", "Appointment rescheduled", "Appointment cancelled", "Waitlist slot offered",
   "Waitlist slot booked", "Appointment reminder"). Expected state, by recipient:
   - `patient@example.test` unread: "Waitlist slot offered" (the offered entry) and "Appointment booked"
     for the checked-in visit today. Read (the seed calls `mark_read` as the patient): "Appointment
     booked" of the completed and of the no-show visits.
   - `passwordless@example.test` unread: "Appointment booked" for each of its two open visits and
     "Appointment cancelled" for the cancelled one. Nothing read.
   Assertions: exactly these (title, read) pairs per recipient, so at least two unread and two read.
6. `returns_an_audit_entry_per_seeded_change_when_seeded`: each appointment has `appointment.book`;
   each non-default status has its action (`check_in`, `complete`, `no_show`, `cancel`); entries
   `waitlist.join`, `waitlist.offer`, `waitlist.accept` exist.
7. `returns_no_mail_and_no_pending_rows_when_seeded`: with on-commit callbacks executed, outbox empty,
   no `email_pending` row, no `notification.email_sent` entry.
8. `returns_no_change_and_no_audit_entry_when_run_twice_on_one_day`: all row counts equal, versions
   equal, audit count equal (replaces "+1").
9. `returns_same_counts_and_no_duplicates_when_run_on_a_later_day`: counts equal; every seeded
   appointment is on or after the new today for open ones and before for finished ones; a booking made by a person
   in between survives.
10. `returns_run_without_the_taken_seed_when_a_person_booked_its_slot`: a person's booking on a
    seeded slot, then a later-day run: no raise, the person's booking unchanged, the seed skipped with
    its dependent steps, a second run a no-op.
11. `returns_clinician_with_today_appointments_in_every_reachable_status`: `clinician@example.test`
    has today `COMPLETED`, `NO_SHOW`, `CHECKED_IN`, `BOOKED`, `CANCELLED`.
12. Kept: DEBUG off refuses, no `DEMO_PASSWORD` refuses, passwords, correlation ids, privacy of
    metadata, only `example.test` and reserved phones, three zones.
Each is run red against the current writer (and for 8 and 9 against the model-writing code) before
the fix; the test proves-to-fail step covers 1 to 4 by reverting the constants.

Also run the seed on a Saturday, a Sunday and a Monday clock (parametrised): all pass.

## What a person finds on first sign-in (all passwords `DEMO_PASSWORD`, `.env.example`)

- Visitor (no account): three hospitals in Berlin, New York and Sydney (one without coordinates),
  five clinicians, six types (some not bookable online), open Monday to Friday slots; no booking
  data visible.
- Patient `patient@example.test` (has a password): a completed visit, a no-show, a checked-in visit
  today with the second cardiologist, a waitlist entry offered, and unread "Waitlist slot offered".
  `passwordless@example.test` (no password, signs in by emailed link): a booked visit, a booked skin
  check, a cancelled visit, a waiting entry, and unread notifications. Four more passwordless patients
  across New York and Sydney.
- Clinician `clinician@example.test` (Berlin cardiology): today `COMPLETED`, `NO_SHOW`, `CHECKED_IN`,
  `BOOKED`, `CANCELLED`, upcoming bookings, Monday to Friday 09:00 to 17:00, a conference as time off.
  Four more clinicians with a smaller diary.
- Admin `admin@example.test`: every hospital, every appointment, the audit trail of the seed's
  bookings, the waitlist with waiting, offered, booked and expired entries.

## Decisions to look at

- `CONFIRMED` leaves the demo world. No action sets it (spec 5.6, 16) and `change_status` has no
  action name for it, so no use call can make one. The earlier test "every status" becomes "every
  reachable status". This is a loss the owner may want to know; I do not change a use case.
- A database seeded by the old seed has unmarked rows. They are never touched, so a reset
  (`docker compose down -v`) is needed once. Not handled in code.
- Retire deletes seeded appointments, waitlist entries and notifications (demo, `DEBUG` only). The
  audit log keeps their ids.
- The seed's patient is its own actor for online and round robin bookings, so the product's lead
  time, open-bookings limit and first-available ranking decide, as for a person.

## Not doing

No new abstraction beyond `booking.py` and `marker.py` (each has two callers: build and retire/tests),
no dependency, no model, migration, page, route or use case change, no README, no refactor of
`_upsert` or the catalogue, no reschedule of existing rows (finished states cannot move; rebuild is
simpler).

## Risks

- `make test` time: the seed is run in about eight tests and each build now makes about thirty use
  calls. Keep the later-day loop at two days instead of five, share one seeded database where
  tests only read; measure before and after, budget 5 seconds.
- Round robin choice relies on the named clinician being busy at the slot; a test pins it.
- `scheduling/demo_seed/` files stay under 300 lines each (`writer.py` is 251 now); the build moves
  to `booking.py`.

## Revision after architect review (round 1)

1. Marker moved off every page: see "Marker" (entity type `DemoSeed`, history-equality test).
2. Time off now goes through `create_time_off` (audited, validated): see the "Time off" block.
3. A person's booking in a seeded slot is skipped, not fatal: see "Later day and taken slots".
4. Test 5 names the read and unread notifications.

## Architect review

Round 2. Verdict: approve.

- Ladder: change stays in `scheduling/demo_seed/`; no model, migration, page, API, use case or
  dependency change. `booking.py` and `marker.py` each have two callers. Fine.
- Verified against code: `place_appointment`, `change_status`, `cancel_appointment`, `join_waitlist`,
  `accept_offer`, `expire_waitlist`, `send_reminders`, `mark_read`, `create_time_off` and
  `bind_request_context` exist. The only non-test reader of `AuditLogEntry` in the product is
  `clinician_appointment.py`, which filters by `Appointment`, so a `DemoSeed` mark does not leak.
- Clock: one context manager in one function, restored in `finally`, past clock never after now. Clear.
- No email: pending flag cleared before commit for rows new in this run only. Clear, and tested (7).
- Repeat and marker: audit mark, no schema change, no-op when current, later-day retire then build, taken
  slots skipped. Clear, tested (8 to 10).
- Tests are first, named as behaviours, with expected values; DEBUG and DEMO_PASSWORD refusals kept.
- Notes for the implementer, not blockers:
  - `CONFIRMED` leaves the demo world (no action sets it). Say so in the final reply; the task says to stop
    and say so if a use case cannot do what the seed needs, so report it plainly.
  - Time off: state which periods are seeded relative to today (past or future) so a later-day run does not
    stack stale periods; the plan's "same label" rule covers duplicates only.
  - The world-current check crosses three zones; test a run just before and after a zone's local midnight.
  - Measure `make test` before and after (5 second budget).
  - Final reply must list "Closes #32".
