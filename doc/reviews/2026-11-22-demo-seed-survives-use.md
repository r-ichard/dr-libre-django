# Review: task 17e, the demo seed survives a person using the demo

Base: `e84591e` (local `main` does not exist in the sandbox, so the diff is `e84591e..HEAD`).
Scope read: `scheduling/demo_seed/{marker,retire,writer,booking,scenarios}.py`,
`scheduling/management/commands/seed_demo.py`, the three test files, the plan.

## Stage trace (§13.3)

Commits after `verify_green` up to `prove` (`cefda95..7446d88`) touch only
`scheduling/demo_seed/test_survives_use.py`. No product or migration line was changed there.
Product code changed in `green` and `refactor` only. No model, use case, view, API route,
migration or dependency changed.

## One-sentence plans

- `marker.py`: a mark is one audit entry per seeded row holding its version and counts; a row that
  differs from its mark was changed by a person. Confirmed at a glance.
- `retire.py`: keep set = changed, depended on by an unmarked row, closed to a fixed point;
  delete the rest children first. Needed a trace for `_close_over`; it terminates because both
  sets are bounded by the seeded sets.
- `writer.py`: once a UTC day, retire, rebuild, silence only seeded mail, mark, report.
- `scenarios.working_day`: weekend start goes backward for finished visits, forward otherwise.

## Findings

1. **Low**, `scheduling/demo_seed/writer.py:212`. Any `INVALID_INPUT` from `create_time_off` is
   recorded as "skipped" and never raised. The failure is reported, not swallowed, but it could
   also hide a real seed bug such as a bad date, which the output would then call "used by a
   person". Fix: only treat the repeated-period failure as a skip.
2. **Low**, `scheduling/demo_seed/test_survives_use.py`. The plan promised "a person's booking on a
   seeded slot survives and the report lists the scenario as skipped" and "an unseeded row is
   never changed". No test does this; only the `kept` side is tested through unmarked dependents
   (lines 280 and 302), and `test_seed_demo_command.py:146` covers a manual row. Fix: add the
   test.
3. **Low**, `scheduling/demo_seed/test_survives_use.py:162`. The person's "Annual leave" sits 90
   days out, so it never competes with a seeded period. The test proves the row is not deleted
   but not that a seeded period with the same reason and clinician is still replaced. Fix: add
   the assertion.
4. **Low**, `scheduling/demo_seed/test_survives_use.py:253`. The reminder test (item 8) passes on
   any unread notification of the patient, not one for the upcoming appointment. It is weaker
   than the promise. Fix: filter on `appointment__in=upcoming`.
5. **Nit**, `scheduling/demo_seed/marker.py:57`. `marks()` loads every mark entry on each run.
   The audit table grows by about seventy rows a day. Harmless for a demo; filter by key in SQL if
   it grows.
6. **Nit**, `scheduling/demo_seed/test_survives_use.py` is 346 lines (under the 500 hard cap, over
   the 300 guideline in §5). Split by theme.
7. **Nit**, scope: `scheduling/management/commands/seed_demo.py` is outside
   `scheduling/demo_seed/`. It is print-only and the plan names it. Accepted.
8. **Risk, declared in the plan**: a finished visit later on the same weekday than `now` stays in
   the future. The plan accepts it.

## Checks

- Correctness: the accepted-offer crash is fixed by keeping the entry, the accepted appointment
  and the offered slot as one closed group. Deletion order covers every PROTECT relation.
  Unmarked rows are never queried for delete or update; only the seed's own notifications are
  silenced.
- Authorization: every write goes through a use case with a demo user as actor. The command
  refuses with `DEBUG` off.
- Audit: marks and the run entry are inserted in the run's transaction. Nothing audit-related is
  deleted. Marks hold ids and counts only.
- Double booking: unchanged. Only `place_appointment` creates appointments, and a taken slot is
  skipped and listed.
- Hard rules: no `Any`, `cast`, `type: ignore` or `noqa`; no function near 100 lines; no file
  over 500; no swallowed error.
- Not run by me: `make mutate`, and the 10-second budget for `scheduling/demo_seed/` tests. The
  `check` stage ran lint, tests and gate green, but nobody has shown `make mutate` or the timing.

## Blocking

None.

## Later

- Findings 1 to 6 above, in that order.
- Run `make mutate` and time `scheduling/demo_seed/` before merge; both are in the done-when and
  neither has evidence in the stage logs.
- Squash-merge with a hand-written message ending "Closes #32", with no Fabro byline (hand-applied
  gap 1).
