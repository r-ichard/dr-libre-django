# Review: whole-day time off label and impossible-date refusal (task 27b item 4, #40)

Reviewer: second reader stage. Scope: `git diff main...HEAD`, four files: the plan
(`doc/plans/2026-11-22-whole-day-time-off-label.md`), `clinician_calendar.py`,
`clinician_time_off.py`, `test_clinician_qa_round_two.py`. Read at block level, then line by line
where the diff touches a trust boundary or a date.

Verdict: **approve**. No blocker found.

## 1. Plan per changed block

- `clinician_calendar.py:124`: picks "All day" when `part.whole_day`, else the clock span.
  Confirmed at a glance: `DayPart.whole_day` is computed in `period_days.py:28` from the day's own
  bounds, so a 23 or 25 hour DST day is handled by the same flag.
- `clinician_time_off.py:26-39`: `NOT_A_DATE` constant and `_unreadable_message`. Needed a trace:
  `utc_from_local` (`local_time.py:9-18`) returns None for a bad string, a skipped hour, and an
  out-of-window date alike. The helper re-reads the date part and calls `day_in_range`. Traced:
  `2027-02-30T10:00` fails `fromisoformat` → NOT_A_DATE; `0001-01-01T10:00` parses, fails
  `day_in_range` → NOT_A_DATE; `10000-01-01T10:00` gives `raw[:10] == "10000-01-0"` → ValueError →
  NOT_A_DATE; `2026-03-29T02:30` is in range → NOT_A_TIME (clock sentence kept).
- `clinician_time_off.py:80-84`: `post` now maps each refused field through `_unreadable_message`.
  The early return, the write path and the 303 are unchanged.
- Tests: read; see section 5.

## 2. Correctness and error handling

- Whole-day part with the row also whole (`clinician_calendar.py:124`, `whole` on the line above):
  label "All day", `real` stays empty. Multi-day row, whole-day middle part: label "All day",
  spoken text still carries the real dated period (`real` built from the row). Matches the plan.
- Part that starts or ends mid-day: `whole_day` False, clock span kept. Guard test exists (§5).
- `_unreadable_message` (`clinician_time_off.py:30-39`): the `except ValueError` returns the
  contract message. This is an expected user-input value, not a swallowed error (§9). Nothing is
  logged or lost.
- Invalid hour on a real date (`2027-02-01T25:00`): `utc_from_local` refuses it, `day_in_range`
  passes, so it reads the clock sentence. Browser `datetime-local` cannot send it. Pre-existing
  wording, out of #40. See Later 3.
- Timezone-aware input (`...+01:00`): refused by `utc_from_local`, read as NOT_A_TIME. Browser
  cannot send it. Pre-existing. Not raised.

## 3. Authorization, boundaries, sensitive data

- `TimeOffPage.post` (`clinician_time_off.py:72-94`) still goes through `ClinicianPage` and
  `profile_or_refusal`; ownership is from the session. Unchanged.
- `starts_at` and `ends_at` come from the POST body. They are parsed by `fromisoformat` and
  `date.fromisoformat`, range-checked by `day_in_range`. The refusal text is a constant. No input is
  echoed into a message. No logging added.
- No dependency change. `pyproject.toml` and the lock file are not in the diff.
- `drlibre-specs.md` and `doc/backlog*` are not in the diff.

## 4. Double booking and writes

- No domain, use case or write change. `create_time_off` and the audit entry are untouched.
  Overlap rules are untouched. A refused value writes nothing (existing test at
  `test_clinician_qa_round_two.py:206`, plus the new 30 February and year tests assert no row).

## 5. Tests

Derived from the specification or the finding? The message and label expectations come from QA
finding #40 (`doc/qa/2026-11-22-round-3.md:199`: "All day" or "00:00 to 24:00"; no clock blame).
They match.

- `test_clinician_qa_round_two.py:110-127`: `returns_all_day_label_when_time_off_covers_a_whole_day`
  asserts the label and that `00:00 to 00:00` is absent. Fails on the old code (red log). Good.
  `returns_clock_span_when_time_off_starts_mid_day` guards the else branch.
- `:217-256`: 30 February, years 0001/9999/10000, and empty start. Each asserts status 422, the
  message, no clock sentence, and no `TimeOff` row. These are real assertions, not vacuous.
- Red proof: verify_red showed four failing tests (`returns_all_day_label...`, 30 February, 0001,
  10000). The 9999 case and the empty-start test were added in the `prove` commit (`429fa5b`),
  after green. Neither was seen failing. See Later 2.
- Plan promised unit tests in `test_local_time.py` for a helper `names_no_day`. That helper was
  not built; see Later 1. The behaviours are covered at page level, so the promise is met in
  substance.

## 6. Names, comments, size

- `_unreadable_message`, `NOT_A_DATE`, `NOT_A_TIME`, `FORM_FIELDS` state roles. Local `day` is
  clear within two lines. Test names follow `returns_X_when_Y`.
- Docstring at `clinician_time_off.py:31-32` says why (the clock sentence only for a real date).
  Within the 255-character cap; `make gate` passed in the check stage.
- Sizes: `clinician_time_off.py` about 130 lines; `_unreadable_message` 9 lines. Under the caps.
- Type escapes: none added. `date.fromisoformat` is typed. The `# noqa: S101` on `post` predates
  the diff.

## 7. Proof trail

`git log` after the stages (oldest first):

- `157b3c1` red: test file, +50.
- `f786169` verify_red: test file, +15/-2 (before green; allowed).
- `3a382d4` green: `clinician_calendar.py`, `clinician_time_off.py` (product).
- `5412d7c` verify_green: no file change.
- `429fa5b` prove: test file only, +15/-2 (adds the 9999 case and the empty-start test). Allowed.
- `91c0fe9` refactor: no file change.
- `bec7ba1` check: no file change.

No product or migration line changed after `verify_green`. No mutation left behind.

## 8. Scope and contract

- The diff touches only the slice: label, refusal message, tests. No other 27b item.
- The plan file is in `doc/plans/**` (throwaway class). Its file list and helper names no longer
  match the code; see Later 1.
- No contract change across layers: no FHIR, `/api/v1` or domain change.

## Blocking

None.

## Later

1. **Plan drift (`doc/plans/2026-11-22-whole-day-time-off-label.md`, sections "Plan" and "Files").**
   The plan names `names_no_day` in `local_time.py` with unit tests in `test_local_time.py`, and a
   `_refusal_of` helper. The code has `_unreadable_message` at `clinician_time_off.py:30-39`, and no
   unit test for it. The page tests cover the same behaviours (30 February, 0001, 9999, 10000,
   skipped hour, empty start). Fix: update the plan to the code as built, or add a unit test on
   `_unreadable_message` when the helper next changes. Not a blocker.
2. **Late tests (`test_clinician_qa_round_two.py:230-256`).** The 9999 parametrised case and the
   empty-start test came in the `prove` commit (`429fa5b`) and were never seen failing. The
   empty-start test would also pass on the old code (the old message was NOT_A_TIME), so it guards
   the branch, not a change. Fix: none needed; the orchestrator may note it in the retro.
3. **Invalid hour reads the clock sentence (`clinician_time_off.py:39`, via `utc_from_local`).**
   A real date with a bad time (`25:00`) gets "clocks skip one hour in spring". Browser cannot send
   it. Pre-existing. Fix, if wanted: a separate task for time-of-day validity.
4. **Calendar tests placed in the round-two file (`test_clinician_qa_round_two.py:110-127`).** §10
   says tests sit beside the code they cover. The label code is in `clinician_calendar.py`. The plan
   asked the orchestrator to confirm the calendar test module; the run used the round-two file.
   Fix: move both tests to the calendar test module when the file is next touched.
5. **Non-date text reads "That date does not exist" (`clinician_time_off.py:38`).** For example
   `10:00` or `2027-02-3T…`. The plan said NOT_A_TIME for non-dates. Browser cannot send these. Nit.
   Fix: none needed, or return NOT_A_TIME when `fromisoformat` fails on a non-date shape.
6. **Layout not measured.** The plan's invariant (`scrollWidth <= clientWidth` at 375 px and
   1440 px, label inside the column) needs a browser. The sandbox has none. Orchestrator browser
   pass.
7. **Measured here, not a blocker.** `make test` in verify_green: 5182 passed in 267.74 s. `make
   lint && make test && make gate` in check: 5184 passed in 236.75 s. The sandbox shares its machine;
   the orchestrator measures on a quiet machine.

## Left for the orchestrator

- Tick item 4 (#40) in `doc/backlog/27b-qa-round-3-pages.md` and `doc/backlog.md`. The run does not.
- Browser layout pass (Later 6).
- `make mutate` and `make fhir-validate`, the last scripted gates. Not run in this stage. Mutation
  scope is `scheduling/domain`, which this diff does not touch.
- Squash with a hand-written message, no "Generated with Fabro" or `Co-Authored-By: Fabro` lines.
- Other 27b items: not in this run.

## For the owner

- **"That date does not exist" is false for some real dates.** `day_in_range`
  (`scheduling/domain/request_limits.py:51-53`) accepts only 2000-01-01 to 2099-12-31. A real date
  in 1999 or 2100 to 2149 is refused and read as "does not exist". QA finding #40 names 9999 and
  10000 as the impossible cases, and 0001. The task text asks for the refusal wording. Decision
  needed: keep "That date does not exist" for everything outside the window, or give out-of-window
  years their own message ("outside the dates this page takes"). The plan records the same risk.
  Not changed here; no test pins it. A follow-up task if the owner wants a range message.
