# Plan: task 17e, the demo seed survives a person using the demo

Focal point: `scheduling/demo_seed/marker.py` and a new `scheduling/demo_seed/retire.py`.

One sentence: a mark records what the seed left behind (version, notification count, read count);
at the next rebuild a seeded row whose state differs from its mark, or that an unmarked row
depends on, is kept, every other marked row is deleted, and the run reports built, kept and skipped.

## The rule (item 3)

Seeded = marked. One `demo_seed.mark` audit entry per seeded Appointment, WaitlistEntry and
TimeOff (new key `time_off_id`). Marks are written at the end of the build, so the snapshot is the
seed's own final state. Metadata counts of a mark (counts only, audit metadata cannot hold text):
`version_count` (row `version`), and for appointment and entry `notification_count` and
`read_count` (their notifications, total and read).

"Changed by a person" = the row differs from its mark. Everything a person does goes through a use
case that bumps `version` (reschedule, cancel, status change, accepted offer) or adds or reads a
notification (new notification on cancel, a read). A clinical note has no version link, so
"has a ClinicalNote" counts as changed (the seed never writes one). Seed's own steps all happen
before the snapshot, so none of them looks like a person.

Keep set, computed in `retire.py` before any delete, to a fixed point:
1. changed by a person (above);
2. depended on by an unmarked row: an unmarked Appointment with `waitlist_entry` = marked entry
   (accepted offer), an unmarked WaitlistEntry offering a marked appointment, an unmarked
   Notification or ClinicalNote on a marked row (covered by 1 for counts, kept as a safety net);
3. closure: kept appointment keeps its `waitlist_entry`; kept entry keeps its `offered_appointment`
   and its accepted appointment; a kept row keeps its notifications and note.
Retire deletes marked rows not in the keep set, children first (as today). Unmarked rows are never
queried for delete or update. A kept row keeps its old mark, so it stays kept on later runs (its
version still differs), until the dependent is gone, then it is replaced.

Time off: recognised by mark, not by clinician and reason (item 6). Delete through
`delete_time_off` only marked rows whose `version` equals the mark. A person's own "Annual leave"
is unmarked, never touched. A new period equal to a kept or a person's period is skipped and counted
as skipped (the unique constraint would refuse it).

Slots a kept row holds make `place_appointment` answer a taken-slot failure: that scenario and its
follow-ups are skipped, as in 17d, and listed.

## Weekend (item 2)

`scenarios.working_day` takes a direction: backward (last working day up to today) when
`day_offset < 0` or the seed's status is COMPLETED, NO_SHOW or CHECKED_IN; forward (next working day
from today) otherwise. `starts_at_for` gets the status. Weekday runs are unchanged.

## Once a day (item 7)

The world is current when the newest `demo_seed.run` entry has the same **UTC date** as `now`
(replaces the per-zone comparison of marks). A run writes that entry whenever it rebuilds, even
when every scenario was skipped, so a day with nothing built still counts. UTC day chosen: one
clock shared by the three zones; the scenarios still use each hospital's local date at the
moment of the rebuild. Run entry counts add `kept_count` and `skipped_count`.

## Mail (item 5)

Silence rows with `email_pending=True` whose `appointment` is in the built appointments or whose
`waitlist_entry` is in the built entries. Pending rows of anything else, before or during the
run, are untouched. The "pending before" snapshot goes.

## Report (item 4)

`seed_demo` returns `SeedReport(built: dict[str,int], kept: dict[str,int], skipped: list[str])`
(a frozen dataclass in `seed_support`-free production code: `writer.py`). `WorldBuilder` records a
skipped seed as `"appointment <type_code> <day_offset> <hour>"`, `"waitlist <type_code> <patient role>"`
or `"time off <reason>"`, each with its follow-ups. Command prints `built <Model>: n`,
`kept <Model>: n (used by a person)`, `skipped: <text>` one per line.

## Reminder (item 8)

Test `returns_an_unread_notification_when_a_demo_patient_has_an_upcoming_appointment`. If it is
green, nothing to do. If red, the seed leaves the booking notification unread for that patient
(only finished visits are marked read). The seed does not call `send_reminders`: it is global and
would notify and mail people's own appointments.

## Files, in order

1. tests (red first, run and shown failing for the right reason): new
   `demo_seed/test_survives_use.py`; edits to `test_seed_world.py`, `test_seed_demo_command.py`.
2. `scenarios.py` (direction), `booking.py` (skip list, `starts_at_for` call).
3. `marker.py` (snapshot, run day), new `retire.py` (keep set, delete), `writer.py` (mail filter,
   time off by mark, report), `seed_demo.py` command (print only).
Not touched: models, use cases, views, API, migrations, domain, `mutation-equivalents.txt`,
`catalogue.py`. `writer.py` is 213 lines: keep-set logic goes to `retire.py` to stay under 300.

## Failing tests first (expected values in words)

Each person case is done through the use case between two runs (run, act as patient or clinician,
run with `now` + 2 days), seeded `FIXED_NOW` Wednesday 2026-11-18 12:00 UTC unless stated:
- `returns_report_and_keeps_both_rows_when_patient_accepted_the_seeded_offer` (item 1): second run
  does not raise; the accepted Appointment and its entry still exist, same status and version.
- `keeps_appointment_when_clinician_rescheduled_it` (reschedule_appointment): moved time stays.
- `keeps_appointment_when_cancelled_by_patient`: status CANCELLED, reason stay.
- `keeps_appointment_when_clinician_changed_status` (BOOKED to CHECKED_IN).
- `keeps_appointment_and_note_when_clinician_wrote_clinical_note`.
- `keeps_notification_when_patient_read_it` (parent kept, read stays read).
- `replaces_untouched_rows_when_world_rebuilds`: untouched seeded appointment has a new pk, new date.
- `leaves_person_rows_unchanged_when_world_rebuilds`: a person's booking on a free slot and a
  person's "Annual leave" time off keep pk, version and values; a person's booking on a seeded
  slot survives and the report lists the scenario as skipped.
- `keeps_pending_notification_pending_when_it_belongs_to_no_seeded_row` (item 5).
- `returns_no_skipped_scenario_when_database_is_empty`: for each of Wednesday, Saturday, Sunday
  clocks, every `APPOINTMENTS` entry exists (patient, clinician, type, start) and every
  `WAITLIST_ENTRIES` entry exists (patient, type, window); `skipped` is empty.
- `places_finished_visits_on_friday_and_upcoming_on_monday_when_clock_is_saturday` (and Sunday):
  no completed, no-show or checked-in appointment starts after `now`; BOOKED ones start after it.
- `rebuilds_once_when_run_in_three_zones_on_one_utc_day`: runs at 00:30, 09:00, 23:30 UTC of one day
  after a prior day: audit entry count grows once; the next UTC day rebuilds.
- `ends_run_without_error_when_every_scenario_skipped` still records the day.
- existing: second run at same moment changes no row, no audit; refuses with DEBUG off; sends no
  email, no pending row afterwards.
- command test: output has `built`, `kept` and `skipped` lines.

Test cost: one seed build per scenario costs real seconds; measure first. Share a built world
through one fixture where a test only reads it. The folder must stay under 10 seconds; if a test
needs a second build, it asserts several outcomes of it.

## Invariants and blast radius

- Double booking: only `place_appointment` creates appointments; constraints unchanged.
- Authorization: every call has a demo user as actor, the use cases decide. Seed runs only with
  `DEBUG` on and `DEMO_PASSWORD`.
- Audit append-only: seed only inserts audit rows (marks, run entry); retire deletes no audit.
- One transaction per run; a raise rolls back everything.
- Blast radius: `scheduling/demo_seed/` and `seed_demo.py` print lines. Marks stay invisible to
  pages and API (only `appointment_history` reads audit, filtered on `Appointment`; test from 17d).

## Trust boundaries

None crossed: a management command, no request input. The marks are read back by the seed only, as
ids and counts, parsed with `UUID(...)`; audit metadata carries no names or text.

## Vocabulary

Appointment, WaitlistEntry, Notification, TimeOff, ClinicianProfile, Patient, Clinician,
AuditLogEntry, Hospital (time zone), ApiClient not used.

## Not doing

No model or column (no `seeded` flag), no use case change, no `send_reminders`, no new
dependency, no change to the 17d clock handling, no fix of finished visits later than `now` on a
weekday morning (a finished visit at 16:00 with `now` at 08:00 stays; noted as a risk).

If a use case cannot do this (for example `reschedule_appointment` creating a new row instead of
changing in place, which the keep rule handles through the unmarked-dependent test), stop and say so.

## Architect review

Verdict: approve.

- Ladder: no model flag, no use case change, no dependency. Marks via existing audit entries is the smallest way to say "seeded". `retire.py` split is justified by the size cap.
- Rule is stateable: seeded = marked; person-changed = differs from mark (version, notification counts, clinical note); unmarked dependents force keep; closure to a fixed point. Each item 3 case has a named through-the-use-case test.
- Tests first cover items 1, 2, 4, 5, 6, 7, 8 plus the edge cases (person row on a seeded slot, all scenarios skipped, Saturday and Sunday, three zones in one UTC day).
- Security: no boundary crossed; audit only inserted; marks hold ids and counts; actor is a demo user.
- Risks to watch in the red stage (not blocking):
  1. The plan assumes every person action (cancel, status change, accept, reschedule) bumps `version` in place. The red tests must prove it per use case; if one does not, the notification-count or unmarked-dependent test must cover it, or stop and report.
  2. Old marks for deleted rows stay in the audit log; lookups must tolerate ids that no longer exist.
  3. The weekday-morning finished-visit-after-`now` gap is declared and accepted.
