# Whole-day time off reads "All day"; impossible dates are refused as such

Slice: item 4 (#40) of task 27b only. Nothing else of `doc/backlog/27b-qa-round-3-pages.md`.

## Focal point

Two messages on the clinician's time-off path are wrong for one reason each:

1. The week grid (`scheduling/views/pages/clinician_calendar.py`, `_time_off_items`) prints
   the clock span of the day's part of a time off. For a whole-day part the end is the next
   midnight, so it reads "00:00 to 00:00".
2. The time-off form (`scheduling/views/pages/clinician_time_off.py`, `post`) answers every
   value that `utc_from_local` refuses with the clock-change sentence. A date that does not
   exist (30 February, year 0001, year 10000) gets that sentence too.

## Plan, one sentence per block

- **Calendar label (`clinician_calendar.py`, `_time_off_items`):** when the day's part is a
  whole day (`DayPart.whole_day`, already computed by `cut_into_days`), the `when` line is
  "All day"; otherwise it stays `_span_text`.
- **Refusal wording (`clinician_time_off.py`):** a new constant `NOT_A_DATE = "That date does
  not exist"`; `post` picks per field between `NOT_A_DATE` and the existing `NOT_A_TIME`
  through a small `_refusal_of(raw)`. `NOT_A_TIME` stays for skipped clock times and for
  text that is not a date at all.
- **Date test (`local_time.py`):** a new `names_no_day(raw: str) -> bool` next to
  `utc_from_local`. It matches the date part of the value with a regex
  (`[0-9]+-[0-9]+-[0-9]+T`) and returns True when `date(...)` raises or `day_in_range` is
  False. This is the only way to tell an impossible date from a skipped hour: `fromisoformat`
  fails for both and cannot read year 10000.

Files, in order:

1. `scheduling/views/pages/test_local_time.py` (tests first, see below)
2. `scheduling/views/pages/test_clinician_qa_round_two.py` (tests first)
3. `scheduling/views/pages/test_clinician_schedule_pages.py` or the existing calendar test
   module next to it (test first; the orchestrator confirms which holds the calendar tests)
4. `scheduling/views/pages/local_time.py`: `names_no_day`
5. `scheduling/views/pages/clinician_time_off.py`: `NOT_A_DATE`, `_refusal_of`, use in `post`
6. `scheduling/views/pages/clinician_calendar.py`: `when` line in `_time_off_items`

Not touched, on purpose: `drlibre-specs.md`; `doc/backlog/27b-*.md` and `doc/backlog.md`
(the orchestrator ticks the item); `doc/handover.md` (no state change); `utc_from_local`'s
return type and callers (no `Failure` refactor); `create_time_off` and its use case (no write
changes); `scheduling/domain/` (the label rule is a view concern, the date check is a view
helper); the other 27b items; the FHIR and `/api/v1` time-off code; `DayPart` and
`cut_into_days` (the flag is already there).

## Invariants and blast radius

- No write changes. The 303 path, the stored `TimeOff` rows, the audit entry, and the
  overlap rules are untouched. A refused value still writes nothing (existing test
  `returns_422_and_no_row_when_time_off_starts_in_the_skipped_hour` stays green).
- The skipped-hour message is unchanged: "Enter a date and time that exists in the
  hospital's time zone; clocks skip one hour in spring." Only impossible dates change.
- Authorization: unchanged. `TimeOffPage` keeps `ClinicianPage` and `profile_or_refusal`.
- Blast radius: the clinician calendar grid (only `_time_off_items` builds time-off blocks)
  and the clinician time-off form POST. Nothing else reads these two strings.
- Multi-day time off: the label changes only for parts that cover a whole local day. A part
  that starts or ends mid-day keeps its clock span; the spoken text keeps the real period
  (`real` is built from the row, not the part, and is not changed).

## Trust boundaries

- `starts_at` and `ends_at` come from the POST body (browser, untrusted). They are read as
  text, matched against a fixed regex, parsed by `date()`, and range-checked by
  `day_in_range`. The refusal message is a constant: no input is echoed back.
- The role check comes from the session through `ClinicianPage` (§11, authorization from
  session, never payload). Unchanged.
- Calendar label: built from server-side `DayPart` values, not from input.

## Domain entities (CLAUDE.md §3 vocabulary)

Clinician (the signed-in actor), TimeOff (the period recorded), Hospital (its `time_zone`
gives the local day and the wall-clock read), Appointment (only in the existing overlap
preview; unchanged).

## Failing tests to write first

Behaviour names as `returns_X_when_Y`. Expected values in words from the specification.

In `test_local_time.py` (unit, pure helper):

- `returns_true_when_date_names_no_day_the_page_accepts`: parametrised over
  "2027-02-30T10:00" (30 February does not exist), "0001-01-01T10:00" (year 0001 is refused as
  a date that does not exist), "10000-01-01T10:00" (year 10000 does not exist).
- `returns_false_when_text_is_a_real_date_or_not_a_date`: parametrised over "2026-03-29T02:30"
  (a real date whose hour the clocks skip: the clock sentence applies), "tomorrow", "".

In `test_clinician_qa_round_two.py` (page, POST as a browser sends it, with Origin and cookie,
per the existing helper `browser_post`):

- `returns_422_and_date_message_and_no_clock_sentence_when_time_off_names_30_february`: body
  contains "That date does not exist" and does not contain "clocks skip"; no `TimeOff` row.
- `returns_422_and_date_message_when_time_off_year_is_0001_or_10000`: parametrised over both
  years; same assertions.

In the calendar test module (page, GET `/clinician/calendar?week=...` after a whole-day time
off is recorded for the clinician, e.g. 2026-11-29 00:00 to 2026-11-30 00:00 local):

- `returns_all_day_label_when_time_off_covers_a_whole_day`: the block's first line and its
  spoken text start with "All day"; the page does not contain "00:00 to 00:00".
- `returns_clock_span_when_time_off_starts_mid_day`: a part that starts at 10:00 keeps
  "10:00 to …" (guards the else branch).

Red proof: each new test fails on the current code for the stated reason (label text,
message text), before the fix. The orchestrator-visible proof is the failing pytest output.

## Layout

Item changes what a block shows, so the invariant and its measurement (CLAUDE.md, Layout):

- Invariant: the first line of a whole-day time-off block fits inside the block at 375 px
  and at 1440 px without overflow. "All day" is 7 characters against the 14 of
  "00:00 to 00:00", so it cannot be wider than the line it replaces.
- Measurement, for the orchestrator's browser pass: on `/clinician/calendar`, for the
  whole-day block, `scrollWidth <= clientWidth` and the first line's text box inside the
  column edges, at 375 px and 1440 px. The existing lane/line tests
  (`returns_three_visible_lines_when_block_is_one_row`) stay green; the line count is not
  changed.
- What must still fit beside it: the reason and the room/spoken lines of the same block; the
  label is the first line and the same length or shorter, so nothing beside it moves.

Impeccable mode: before the green edit, read `PRODUCT.md` and
`.claude/skills/impeccable/reference/craft-floor.md`. The change is copy, not a new
component; reuse the existing block lines.

## Trust, errors, logs

- Expected failures stay values in the 422 contract (§9): `_refusal_of` returns a message
  per field, as before. No exception is raised for user input.
- No logging added. No sensitive data (the reason is not echoed).

## What I will not do

- No `Failure` or result type on `utc_from_local`; a second helper is cheaper than changing
  its three callers.
- No change to `utc_from_local`'s behaviour; `test_local_time.py` stays green unchanged.
- No new CSS, no new component, no template change (the label is text in existing lines).
- No change to the domain layer, no mutation-test entry (the new helper is in the views
  layer, outside `make mutate`'s scope; the tests carry it, per the Hand-applied gaps note).
- No edit of the 422 test for the skipped hour.

## Risks and open points

- Years after 2100 (`LATEST_INSTANT`) also read "That date does not exist", because the
  task names 10000 and 0001 as the cases to refuse that way. A year such as 2150 is a real
  date the page does not take; the message says it does not exist. Left as the task says;
  if the owner wants a range message, that is a follow-up, not this run.
- A whole-day time off of one day in a DST-change day is 23 or 25 hours long; the label
  still reads "All day" (the part is whole). Intended.
- Unverified in this stage: the test module that holds calendar page tests. The orchestrator
  or the red stage confirms the path before writing.

## Reading budget spent

Read: CLAUDE.md, task 27b (item 4 and the surrounding file), QA finding #40 in
`doc/qa/2026-11-22-round-3.md`, `clinician_time_off.py`, `local_time.py` and its tests,
`clinician_calendar.py` (`_time_off_items`, `_span_text`), `period_days.py` (`DayPart`),
`request_limits.py` (`day_in_range`), `test_clinician_qa_round_two.py` (422 test). Not read:
the rest of the tree, lock files, migrations, ADRs (none named by the task).

## Architect review

Verdict: approve. Slice (item 4 of task 27b only) is coherent and one green stage can finish it:
two small view-layer helpers, one conditional, no domain, write or schema change.

Checked against the code:

- `DayPart.whole_day` exists (`scheduling/domain/period_days.py`) and `cut_into_days` returns it.
  `_time_off_items` already iterates those parts, so the label change is one conditional.
- `utc_from_local` returns None both for a skipped hour and for an out-of-range or impossible date.
  `names_no_day` is needed to split them. Checked: `date(2027, 2, 30)` raises; `fromisoformat` fails
  on `10000-...`, so `date()` must catch it; `0001-01-01T10:00` parses and `day_in_range` refuses it.
- `day_in_range` lives in `scheduling/domain/request_limits.py` and accepts 2000-01-01 up to but not
  including 2100-01-01. The view helper calls the domain function; no layer is crossed the wrong way.
- `browser_post` (`scheduling/views/pages/browser_support.py`) already sends Origin and the token;
  the 422 tests can use it as the plan says.

Points for the red and green stages (not reasons to revise):

1. Years 1999 and 2100 to 2149 are real dates that `day_in_range` refuses. `names_no_day` returns
   True for them, so they would read "That date does not exist", which is false. The plan's risk
   section already records this. Do not add a test that pins it. Surface it under "For the owner";
   a range message is a follow-up.
2. The calendar test module is not fixed. The plan offers two names. Candidates present:
   `scheduling/views/pages/test_time_grid_blocks.py`, `test_clinician_workspace.py`. The red stage
   picks the file by grep for `_time_off_items` or the time-off block tests before writing.
3. Two flags sit side by side in `_time_off_items`: the row-level `whole` (drives `real`) and
   `part.whole_day` (drives the new label). Use `part.whole_day` for the label only and leave `whole`
   unchanged, as the plan says, so the two are not merged.
4. No security hole: `starts_at`/`ends_at` are matched against a fixed regex and parsed; the refusal
   text is a constant and never echoes input; the role check stays on `ClinicianPage` (session).
   Nothing is logged.
5. Errors stay values in the 422 contract (§9). No write, audit or overlap path changes.
6. Layout invariant is stated and measurable (7 characters replacing 14). Line count unchanged.
