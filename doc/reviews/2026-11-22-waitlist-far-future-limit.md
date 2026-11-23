# Review: task 27b item 3, waitlist form names the year limit (#37)

Branch `fabro/run/01M82SW0598BD9MQ2BTTYF4CJR`, diff `main...HEAD`: 3 files, 130 insertions, 1 deletion.
Plan: `doc/plans/2026-11-22-waitlist-far-future-limit.md`.

## Diff, in plan order

- `scheduling/views/pages/test_admin_waitlist_pages.py:84-101` (new test
  `returns_422_and_the_accepted_years_when_latest_is_after_2099`). Posts a well-formed window
  (`2030-05-01T09:00` to `2130-05-01T09:00`) through `admin_post` with an admin session. Asserts
  422, the text "Enter a date and a time between 2000 and 2099.", and zero `WaitlistEntry` rows.
  Literals `2000` and `2099` are written in the test, not read from the constants, so a change of
  range breaks the test on purpose.
- `scheduling/views/pages/admin_waitlist.py:46-48` (`REAL_MOMENT`) now an f-string built from
  `EARLIEST_INSTANT.year` and `LATEST_INSTANT.year - 1`. `LATEST_INSTANT` is exclusive
  (`2100-01-01`) and `day_in_range` is `< LATEST_INSTANT.date()`, so 2099 is the last accepted
  year. Correct.
- `scheduling/views/pages/admin_waitlist.py:10` import of the two constants from
  `scheduling.domain.request_limits`. Pure module, no new dependency.

## Plan in one sentence per block (§2.5)

- Test block: an admin posts a well-formed window whose latest value is past 2099; the page answers
  422, names 2000 to 2099, and writes nothing. Confirmed at a glance.
- `REAL_MOMENT`: the single message for an unparsed or out-of-range moment now states the accepted
  years. Confirmed at a glance; the one caller is `_checked` at `admin_waitlist.py:164`, and
  `grep` finds the text only in this file and its test. The use sits in `_checked`
  (`admin_waitlist.py:146`, defined there).
- Import: brings the two range constants into the view. Confirmed at a glance.

## Checks

1. Correctness. Message and range check come from the same constants (`day_in_range`,
   `request_limits.py:51`), so the text tracks the check except for the literal `- 1` offset,
   which is correct for an exclusive upper bound. No error is swallowed; `utc_from_local` returns
   `None` and the caller records the message, as before.
2. Red for right reason. The `verify_red` output (run `red_gate`) shows the 422 status assertion
   passing and the years-text assertion (`test_admin_waitlist_pages.py:98`) failing against
   `"Enter a date and a time."`. The failure is the missing years, not a crash.
3. Authorization and boundary. Unchanged: `AdminWaitlistPage`, `Role.ADMIN` from the session.
   Form values are still parsed by `utc_from_local` (`local_time.py:17`). The new text is a
   constant; no input is echoed into the page, so no new escaping surface.
4. Transaction and audit. No write on refusal, and the test asserts zero rows. Nothing to audit.
5. Double booking. Not touched; the window check after parsing (`admin_waitlist.py:170` onward)
   is unchanged.
6. Names and comments. `REAL_MOMENT` keeps its name. No new comments. No `Any`, `cast`, bare
   `# type: ignore` or `# noqa` in the diff.
7. Proof left no trace. `git diff 9c823de fa3419f --stat` (verify_green to check) is empty.
   Commits `05bb849` (prove), `9f50bad` (refactor) and `fa3419f` (check) change no file. The
   product line and the test were both in place before `verify_green` (`fc21724`, `effcca3`).
8. Scope. Only the one constant, its import and one test. `drlibre-specs.md`, `local_time.py`,
   `request_limits.py`, `clinician_time_off.py` and the backlog are not in the diff. No dependency
   added.

## Gates (from the run's stage outputs)

- `verify_green`: `make test`, 5201 passed.
- `check`: `make lint`, `make test` (5201 passed), `make gate` (escape hatch gate clean, comment
  and size caps passed).
- Not run in this review: `make mutate` (covers `scheduling/domain` only, and this change is in
  views) and `make fhir-validate` (no FHIR surface touched).

## Blocking

None.

## Later

1. `scheduling/views/pages/admin_waitlist.py:46-48` `REAL_MOMENT` also answers a well-formed
   value on a skipped clock time (for example a spring-forward local time) and an unparseable
   value such as `tomorrow`. For those, "between 2000 and 2099" is true but does not name the
   fault. The plan accepts this. Task 27b item 4 (QA #40, the clock-change sentence) should give
   these cases their own message. Risk: an admin reads the range as the cause of a DST refusal.
   Smallest fix: when 27b item 4 lands, split the message there, not here.
2. `test_admin_waitlist_pages.py:98` asserts the sentence with `in html`, so it passes if the
   text appears anywhere on the page. Risk: low. Smallest fix: none needed for this slice.
3. The test asserts both date fields through one message only implicitly (the same constant is
   used for both). QA #37 says "on both date fields". Not asserted per field. Smallest fix: if
   wanted, assert the message sits inside the `latest_at` field's error element.
4. Measured on this shared sandbox, not a budget: `make test` 105 s (`verify_green`), 131 s
   (`check`, including lint and gate). The orchestrator measures on a quiet machine.
5. Plan line references are off by two lines (`admin_waitlist.py:45`, now 46 to 48). Cosmetic.

## Left for the orchestrator

- Plan `## Not in this run` list, copied unchanged:
  - Item 4 of 27b (`NOT_A_DATE` and "All day"), items 1, 2, 5 to 10: separate runs.
- Items of the slice the run did not finish: none. Item 3 is done in full.

## For the owner

Nothing. `drlibre-specs.md` is not changed, and no decision was left open for an ADR. The message
wording ("between 2000 and 2099") is a code-owned constant; QA #37 suggested either a limit or the
accepted window, and the plan chose the window.
