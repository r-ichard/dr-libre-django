# Task 27b item 3: the waitlist form names the year limit (#37)

Slice: item 3 only (#37). Nothing else of `doc/backlog/27b-qa-round-3-pages.md`.

## Focal point

`scheduling/views/pages/admin_waitlist.py:45`, `REAL_MOMENT = "Enter a date and a time."`.
Every moment `utc_from_local` refuses gets that one text. `utc_from_local`
(`scheduling/views/pages/local_time.py:17`) refuses a day outside
`day_in_range` (`scheduling/domain/request_limits.py:51`: 2000-01-01 up to and including
2099-12-31). The window `2030-05-01T09:00` to `2130-05-01T09:00` is well formed, so the
latest moment is refused by the range and reported as a format error.

## Ladder

1. Do nothing: rejected, the message misleads (QA #37).
2. Change the text of the one constant to name the accepted years. **Holds. Chosen.**
3. Split "out of range" from "not a date" inside `utc_from_local`: needs a reason in its
   return value, changes the contract shared with time off (`clinician_time_off.py`), and
   task 27b item 4 owns those messages. Rejected.
4. Widen the range to 2130: a product decision, and `day_in_range` exists so that date
   arithmetic cannot overflow. Rejected.

## Blocks

- `admin_waitlist.py:45` (`REAL_MOMENT`): one sentence, built from the existing range
  constants so the text and the check cannot drift:
  `f"Enter a date and a time between {EARLIEST_INSTANT.year} and {LATEST_INSTANT.year - 1}."`
  Renders "Enter a date and a time between 2000 and 2099." The same text also answers an
  unparseable value (`tomorrow`, a skipped clock time). That is accepted: the sentence
  still tells the admin the accepted form, and it stops pointing at a non-existent limit.
- `admin_waitlist.py` imports: add `EARLIEST_INSTANT`, `LATEST_INSTANT` from
  `scheduling.domain.request_limits` (the domain module `local_time.py` already imports).
- `test_admin_waitlist_pages.py`: one new test beside `returns_303_...`.

## Files

Touch, in order:
1. `scheduling/views/pages/test_admin_waitlist_pages.py`: new test (red).
2. `scheduling/views/pages/admin_waitlist.py`: constant and import (green).

Do not touch: `local_time.py`, `request_limits.py`, `clinician_time_off.py` (item 4 owns
its messages), `drlibre-specs.md`, `doc/backlog/*`, any template, any CSS.

## Failing test first

- `returns_422_and_the_accepted_years_when_latest_is_after_2099` (in
  `test_admin_waitlist_pages.py`). Uses the field values of
  `returns_303_and_a_waiting_entry_when_an_admin_adds_a_patient`, with
  `latest_at` = `2130-05-01T09:00` and `earliest_at` = `2030-05-01T09:00`, posted with
  `admin_post`. Expected in words: the answer is 422; the page names the accepted years
  "between 2000 and 2099"; no waitlist entry is written.

It fails today: the page says "Enter a date and a time." with no years. Red for right
reason is checked by the reviewer: the failure must be the missing years text, not a
crash.

## Invariants and blast radius

- Validation unchanged: same parse, same range, same 422, same single-entry writes (none
  here). Nothing is written on a refusal.
- Authorization unchanged: `AdminWaitlistPage` with `Role.ADMIN` from the session.
- Audit log: no write, nothing to audit.
- Double booking: not touched.
- `REAL_MOMENT` has one caller (`_checked`, line 164). The patient waitlist form has its
  own parse path and is not affected (grep: the text appears only in this file).

## Trust boundaries

- Browser to `POST /admin-console/waitlist/new`: form values are read as strings and
  parsed by `utc_from_local` (unchanged). The new text is a constant; no input is echoed
  into the page, so no new escaping surface.
- Session to role: `PageView` `allowed_roles` (unchanged).

## Domain vocabulary

Waitlist entry (`WaitlistEntry`, status WAITING) and admin (`Admin`) only. No new entity.

## Not doing

- No new abstraction, no reason codes, no change to `utc_from_local`'s return type.
- No change to other messages, the time off page, or the patient form.
- No spec edit. The years come from code constants, which the spec does not state.

## Done when

`make lint`, `make test`, `make gate` pass. The new test fails before the constant change
and passes after. Diff: one test function, one constant line, one import line.

## Not in this run

- Item 4 of 27b (`NOT_A_DATE` and "All day"), items 1, 2, 5 to 10: separate runs.

## Architect review

Verdict: approve.

- Ladder: rung 2 is the smallest change that holds. Rungs 3 and 4 are correctly rejected: rung 3 changes a shared contract and item 4 owns those messages; rung 4 is a product decision.
- Plan knowledge: each block states its purpose in one sentence ("the admin waitlist form names the range the window may use"). Vocabulary is the CLAUDE.md set (`WaitlistEntry`, admin, WAITING).
- Test first: the named test `returns_422_and_the_accepted_years_when_latest_is_after_2099` is a behaviour in the `returns_X_when_Y` form. Its expected values come from the QA report (422, the accepted years), not from the code. Naming the years as literals `2000` and `2099` in the assertion, rather than reading the constants, keeps the test from following a changed constant. The plan should say that.
- Guard: the plan requires the test to fail on the missing years text. Confirmed: `REAL_MOMENT` at `scheduling/views/pages/admin_waitlist.py:45` has one caller (`_checked`, line 164). `EARLIEST_INSTANT` and `LATEST_INSTANT` exist in `scheduling/domain/request_limits.py` (2000-01-01 inclusive, 2100-01-01 exclusive), so `LATEST_INSTANT.year - 1` gives 2099 correctly.
- Security: no input is echoed; authorization and parse path unchanged. No new trust boundary.
- Architecture: the change stays in the view layer, which formats messages. No new abstraction, no new dependency.
- Scope: the diff is one test and one constant line plus one import. Nothing from items 1, 2, 4 to 10 is silently dropped; items 4 and 5 are named as separate runs.

Notes for the implementer, not reasons to revise:
- `REAL_MOMENT` also answers a value that parses but falls on a skipped clock time (in-range day, nonexistent local time) and an unparseable value. For those, "between 2000 and 2099" is true but does not explain the fault. The plan accepts this trade-off; keep it, and say so in the final message.
- The message must stay a constant with no input echoed, so no escaping change is needed.
