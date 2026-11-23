# Report counts an appointment on its hospital's day, zones on both sides of UTC

Slice: item 15 of task 26c only. One new test file, no product code.

## Focal point

`scheduling/use_cases/admin_report.py` `build_report` reads a one-UTC-day superset
(`:57-64`) and keeps each appointment by `hospital_day` (`scheduling/domain/report_figures.py:40-41`,
the hospital zone's local date). Review 21 (`doc/reviews/2026-11-22-admin-dashboard-reporting-export-2.md`,
and `-export.md` "Important") says this is untested with zones on both sides of UTC. Nothing in
`scheduling/use_cases/` tests `build_report` at all. This plan adds that test and nothing else.

## Blocks

1. **New file `scheduling/use_cases/test_admin_report.py`**: one-line module docstring stating
   what it covers (no task number, per item 14). Imports only. One plan line: tests call
   `build_report` inside `bind_request_context(RequestContext(...))` (pattern of
   `scheduling/use_cases/test_change_password.py:38`), since the use case reads `current_request_context()`.
2. **Helpers `_clinic_in(time_zone)` and `_book_at(clinic, starts_at)`**: build a hospital with
   the given `time_zone` (`make("Hospital", time_zone=...)`), a department in it, an
   AppointmentType, a clinician via `add_clinician`, a patient via `make_user()`; book one
   `Appointment` (`BOOKED`, `ONLINE`, 30 minutes) as `_book` does in
   `scheduling/views/pages/test_admin_dashboard_page.py`. `make` returns `Model`, so each
   result is narrowed with `isinstance` as that file does. Not added to `builders.py`
   (product-classed; "tests only").
3. **Parametrised test `returns_the_hospital_day_when_the_start_is_at_midnight`**: five cases,
   one appointment each, asserting the non-zero entries of `report.per_day` equal exactly
   `{expected_day: 1}`. The table (2026 November, Sydney AEDT UTC+11, New York EST UTC-5):

   | Hospital | Local start | UTC instant | Counted on |
   | --- | --- | --- | --- |
   | Australia/Sydney | 24 Nov 00:00 | 23 Nov 13:00 | 24 Nov |
   | Australia/Sydney | 23 Nov 23:59 | 23 Nov 12:59 | 23 Nov |
   | America/New_York | 24 Nov 00:00 | 24 Nov 05:00 | 24 Nov |
   | America/New_York | 23 Nov 23:59 | 24 Nov 04:59 | 23 Nov |
   | America/New_York | 24 Nov 23:59 | 25 Nov 04:59 | 24 Nov |

   The fifth row sits at the last day's upper edge, so it guards the `+2` bound of the superset.
4. **Test `returns_both_appointments_on_their_hospital_day_when_zones_lie_on_both_sides_of_utc`**:
   two hospitals in one report (so `current_report_date` takes the max over both zones). Sydney
   24 Nov 00:30 (UTC 23rd 13:30) and New York 24 Nov 23:30 (UTC 25th 04:30). Expected
   `per_day` non-zero entries `{24 Nov: 2}` and `report.appointments == 2`. Two appointments
   on the same local day, on UTC days 23 and 25: a UTC reader would split them.
   (Not a swap test: swapping two single-day counts looks the same in a count summary, so
   this test uses one shared day.)

Report window used by every test: `build_report("7")`, `now = 2026-11-24 12:00 UTC`
(Sydney today 24 Nov 23:00, New York today 24 Nov 07:00, so today = 24 Nov, range 18 to 24 Nov).

## Files

- Touch, in order: `scheduling/use_cases/test_admin_report.py` (new). Nothing else in the diff.
- Do not touch: `admin_report.py`, `report_figures.py`, `report_range.py`, `builders.py`,
  `test_admin_dashboard_page.py`, `doc/backlog/26c-gates-that-hold.md` (orchestrator ticks it),
  `doc/backlog.md`, `doc/handover.md`, `drlibre-specs.md`, `mutation-equivalents.txt`.
- Mutation-equivalents: no new entries. Tests add no survivor exemptions.

## Invariants and blast radius

- Each appointment counted exactly once, on its hospital-local date, cancelled excluded (not in these cases).
- Read-only use case: no write, no audit entry, no transaction in the test.
- Product behaviour unchanged. Blast radius: one test file; runtime a few ms (six queries).
- Authorization is in the view, not `build_report`; the test calls the use case directly and
  crosses no trust boundary. No input from outside.

## Trust boundaries

None crossed. Values are constructed in the test.

## Domain entities (CLAUDE.md §3)

Hospital (`time_zone`), Department, AppointmentType, Clinician (ClinicianProfile), Patient
(User), Appointment (`BOOKED`, `ONLINE`), Report (the use case's output).

## Failing tests first, and how the guard is proven

No behaviour changes, so the tests are expected to pass on current code. This is a
"tests-and-docs" task (no red gate, 27a3). Proof they can fail, done by hand during the
test stage and reverted before commit:

- Mutant A: `hospital_day` returns `visit.starts_at.astimezone(UTC).date()`. Expected to fail
  cases 1, 2, 3, 4, 5 and the both-zones test.
- Mutant B: superset `before` changed from `days[-1] + 2` to `days[-1] + 1` days. Expected to
  fail case 5 only.

Record the failing names of both mutants in the test-stage output. Revert both; `git diff`
must show only the new file.

Test names `returns_X_when_Y`, expected values as in the table above, which follows the
spec's own wording: §13 "appointments that start in the chosen range"; §3 "Times are shown
in the time zone of the hospital the appointment is in" (`drlibre-specs.md:148`).

## Trust and types

Typed: `-> None` on every test, typed helpers, parametrised `(str, datetime, date)`. Strict
mypy: `isinstance` narrowing for `make` results. No `Any`, no `cast`, no suppressions.
`ZoneInfo` for local times, converted to UTC with `astimezone(UTC)` before `_book_at`.

## Not doing

- No change to report code, no new abstraction, no helper in `builders.py`.
- No page test; no sync of the superset with a live browser (not in item 15).
- No refactor of `_book` from the page test file.
- No `NOW` taken from the clock module (the use case reads the request context).

## For the owner

- Spec §13 does not say "the day an appointment is counted on" is its hospital's local date.
  The plan reads it that way from §3 (hospital zone for times, line 148) and from review 21 and
  `hospital_day`. If the owner means another day (for example UTC), the tests change, and the
  decision goes into an ADR.

## Not in this run

- Item 11 (time gate), 11a (mutants), 12, 13, 14, 16 to 20: other items of task 26c.
- Review 21's other "Later" items (the export stream).

## Architect review

Verdict: approve. One new test file, item 15 only, layer right (use case test beside `admin_report.py`), no product code, no new abstraction, no dependency. Every citation checked against the tree: `admin_report.py` superset at 61-64, `report_figures.py` `hospital_day` at 40-41, `test_change_password.py:38` `bind_request_context`, `RANGE_DAYS["7"] = 7`, spec §13 quote at line 621, `make_user`/`add_clinician` in `builders.py`. Table UTC instants and the `now` window recomputed: correct.

Corrections for the test stage (not reasons to revise; the stage records real results):

1. Mutant A (`hospital_day` in UTC) fails cases 1, 4, 5 and the both-zones test. Cases 2 and 3 pass under it: Sydney 23 Nov 12:59 UTC and New York 24 Nov 00:00 local (05:00 UTC) are on the same date in both readings. The plan's "1, 2, 3, 4, 5" is wrong.
2. Mutant B (superset `before` at `days[-1] + 1`) fails case 5 and also the both-zones test: New York 25 Nov 04:30 UTC falls outside the window. The plan's "case 5 only" is wrong.
3. Test name `returns_the_hospital_day_when_the_start_is_at_midnight` covers 23:59 starts in three of five rows. Rename to something that names the edge (for example `..._when_the_start_is_near_midnight`), or drop "at midnight".
4. Spec citation: `drlibre-specs.md:148` sits in §4 ("Rules that apply everywhere"), not §3. Fix both mentions.
5. `_clinic_in` must pass `hospital=` to the Department. The `Department` builder otherwise makes a `Europe/Berlin` hospital and every case silently runs in Berlin. `make_clinic` cannot take a hospital, so do not reuse it; build the chain by hand as the plan says.

Security, audit, transactions, types: nothing new crosses a boundary. Test-only, read-only use case, values built in the test. Scope: nothing dropped from item 15.
