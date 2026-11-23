# Review: report counts an appointment on its hospital's day (task 26c, item 15)

Reviewer: second reader, diff `main...HEAD` (commits 18f194b plan, d5a5b7a write, 7aa86e9 prove).
Changed: `scheduling/use_cases/test_admin_report.py` (85 lines, new) and
`doc/plans/2026-11-23-report-utc-zones-test.md` (plan). No product code, no migration, no
view, no endpoint, no template, no dependency, no `drlibre-specs.md` change, no
`doc/backlog` change.

Verdict: **approve**. No blocker.

## Trust boundaries

Nothing changed in views, API endpoints, middleware, forms, serializers, models,
migrations, or templates. The test calls `build_report` directly, with values built in
the test. Authorization stays in the view, which this diff does not touch. Nothing is
logged, put in a URL, or written. The use case is read-only: no transaction, no audit
entry, which matches the plan.

## Per-block plan check (§2.5)

| Block | Plan in one sentence | Read at a glance? |
| --- | --- | --- |
| Module docstring, imports `test_admin_report.py:1-18` | Says what the file covers; imports only what the tests use. | Yes. |
| `_clinic_in` `:21-26` | Hospital in a zone, department in it, type, clinician, patient, narrowed by `isinstance`. | Yes. `hospital=` passed to Department (`:23`), so the Berlin default does not apply. |
| `_book_local` `:29-38` | Turns a local naive start into an aware UTC instant and books one appointment for 30 minutes. | Traced: `replace(tzinfo=ZoneInfo(...))` on a naive local time is correct here (no DST transition 17-26 Nov in either zone). |
| `_report` `:41-43`, `_counted_per_day` `:46-47` | Runs the use case inside a bound request context; keeps non-zero days. | Yes. Matches `request_context.py:16-21`. |
| Parametrised midnight test `:50-66` | Six rows, one appointment each, asserts exactly `{expected_day: 1}`. | Traced each row against `admin_report.py:62-64` and `report_figures.py:40-41`; all six expected days are right. |
| Both-zones test `:69-76` | Two hospitals, one local day, expects one shared day with count 2. | Traced: Sydney 23 Nov 13:30 UTC and NY 25 Nov 04:30 UTC both fall in the fetch window. |
| Before-range test `:79-85` | A visit one local day before the window is not counted. | Traced: fetched (17 Nov 12:59 UTC is after `since`), dropped by the `in days` filter. |

I confirmed the rows with a glance except where noted. I traced the superset bounds
(`admin_report.py:62-64`), the `current_report_date` max over zones
(`report_range.py:15-18`) and the window (`NOW` 24 Nov 12:00 UTC gives today 24 Nov and
range 18-24 Nov), because a wrong bound would still give plausible counts.

## Correctness and error handling

No error paths in the diff. No swallowed errors. `make` and `_typed` raise only on an
invariant break, which is the right use.

## Tests (§10.1)

- Assertions are exact (`== {day: 1}`, `== {date: 2}`, `== {}`), so they fail on a wrong
  day, a dropped row, and an extra row. They would not pass forever.
- The plan's two mutants (A: UTC day in `hospital_day`; B: superset `before` at `+1`)
  predict failures that I reasoned through against the assertions. A fails the midnight
  cases where the UTC date differs from the local date and the both-zones test. B fails
  the 25 Nov 04:59 UTC row and the both-zones test. The corrected expectations in the plan
  (its "Architect review" section) are right.
- The prove commit added two things beyond the plan's table, which the diff shows:
  - `:55` Sydney 18 Nov 00:00: guards the `days[0] - 1` lower bound of the superset.
  - `:79-85` before-range test: guards that `report.appointments` drops visits outside
    `days`. Removing the `in days` filter at `admin_report.py:64` fails it.
  Both are real guards. Neither is a blocker; see Later 2.

## Double booking (§8, spec 5.2)

Not touched. The test writes rows through the ORM, not the booking use case, so it
bypasses conflict checks. That is correct for a report test and does not affect product
behaviour.

## Names and comments (§3, §4)

Names state roles (`_clinic_in`, `_book_local`, `_counted_per_day`, `local_start`,
`expected_day`). Test names follow `returns_X_when_Y`. No comments in the file; the
docstring states the subject in one line. The comment gate and escape-hatch gate passed
in the check stage (`5269 passed`, comment cap, size cap, escape hatches clean).

## Proof left no trace (§ step 7)

Commit order from `git log`:

- `18f194b` plan_review, `24ba47b` plan_gate, `ebfa2df` check: plan file or no file
  changes.
- `d5a5b7a` write: the test file.
- `7aa86e9` prove: test file only (+10 lines, a case and a test).

The prove commit changes only the test file. `git diff main...HEAD --stat` shows no
product line. `scheduling/use_cases/admin_report.py` is unchanged from `main`, so no
mutant is left behind. The mutant runs themselves are not in the diff (Later 3).

## Scope (§8)

Only item 15 of task 26c. The plan's "Not doing" list holds: no change to
`builders.py`, `admin_report.py`, `report_figures.py`, `report_range.py`, the page test,
or the backlog. No dependency added. Contract sync across layers: no contract changed.

## Findings

1. **nit** `scheduling/use_cases/test_admin_report.py:37-38` (`_book_local`): the plan
   (block 2) says each appointment is booked as `BOOKED`, `ONLINE`. The helper does not
   pass `status=` or `source=`, so the values come from `_appointment_defaults`
   (`scheduling/models/builders.py:69-70`). Risk: if a builder default changes, the
   midnight tests change meaning without any visible sign in the test file. Smallest fix:
   add `status="BOOKED", source="ONLINE"` to the `make("Appointment", ...)` call. Not a
   blocker: the values are right today.

2. **nit** `scheduling/use_cases/test_admin_report.py:55` and `:79-85`, against
   `doc/plans/2026-11-23-report-utc-zones-test.md` block 3 (five cases) and the table
   (`:30-36`). The prove commit added a sixth case and a seventh test that the plan does
   not list. Both guard real edges (see Tests). Risk: the plan no longer describes the
   file, so a later reader who checks the plan against the file finds a mismatch. Smallest
   fix: add the two rows and the test name to the plan table, or accept the plan as a
   lower bound. Not a blocker: nothing promised is missing, and the diff is tests only.

3. **nit** Mutant proof (plan "Failing tests first"): the plan asks for the failing names
   of mutants A and B to be recorded in the test-stage output. That record is not in the
   diff, and I did not re-run the mutants (this review does not edit source). Risk: the
   guard claim rests on reasoning, not on a recorded run. Smallest fix: the orchestrator
   runs the two mutants on a clone of `verify/<task>` with
   `pytest scheduling/use_cases/test_admin_report.py -k ...` and keeps the output with the
   squash message. Not a blocker: the reasoning above checks out, and the mutants are
   described as test-stage work, not as part of the diff.

4. **nit** `scheduling/use_cases/test_admin_report.py:69` test name is 84 characters
   (`returns_both_appointments_on_their_hospital_day_when_zones_lie_on_both_sides_of_utc`).
   It states the role and passes the linter. Leave it as is unless the orchestrator
   prefers a shorter name.

## Blocking

None.

## Later

- 1 (`_book_local` explicit status and source). See finding 1.
- 2 (plan table out of step with the file). See finding 2.
- 3 (mutant records not in the diff). See finding 3.
- 4 (long test name). See finding 4.
- Timing, measured here and not a blocker: the check stage ran the full suite in
  156.53 s (`5269 passed`) on a shared sandbox. The orchestrator measures any budget on a
  quiet machine.

## Left for the orchestrator

Copied from the plan's `## Not in this run`:

- Item 11 (time gate), 11a (mutants), 12, 13, 14, 16 to 20: other items of task 26c.
- Review 21's other "Later" items (the export stream).

Slice status: item 15 is complete. Blocks 1 to 4 of the plan are in the file. Item 15
needs no further work in this run. The backlog tick for item 15 is the orchestrator's
(the plan says the orchestrator ticks `doc/backlog/26c-gates-that-hold.md`).

## For the owner

Spec §13 does not say that "the day an appointment is counted on" is the hospital's local
date. The tests take that reading from §4 (`drlibre-specs.md:148`, "times are shown in
the time zone of the hospital the appointment is in") and from `hospital_day`
(`scheduling/domain/report_figures.py:40-41`). If the owner means another day (for
example UTC), the tests change, and the decision belongs in an ADR. No spec change is
in this diff.
