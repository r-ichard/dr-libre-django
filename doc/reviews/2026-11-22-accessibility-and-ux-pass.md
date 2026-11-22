# Review: task 25, accessibility and UX pass

Diff: 14 files, +715/-88. Product change is about 40 lines; the rest is the plan, the walking test and its helpers.
The `prove` commit (7c2a027) touches only `test_page_quality.py`: no mutation left behind.
Gates reported green (lint, 3770 tests, gate). `make mutate` not seen in the stage output.

## Findings

1. **Blocker, scope vs task.** Most of the task is not done, though the plan (approved) promised it.
   Absent from the diff: item 3 (no `/terms`, `/privacy`, no `scheduling/templates/legal/`, checkbox unchanged);
   item 4 (date of birth still a picker, no `date_group`); item 8 (`notification_card.html:5` still prints "UTC");
   item 9 (no `domain/written_time.py`, ISO dates stay in notifications and emails); item 11 (no `.table--stacked`, no `data-label`);
   item 12 (no field-by-field conflict table); item 12a (cookie still holds the sentence with the name, no `notice_sentences.py`);
   item 14 (no per-status word and icon assertions); item 15 (no empty-state work); item 16 (no confirmation test).
   Fix: build each block with its failing test, or split into follow-up tasks and say so in the reply.
2. **Blocker, security (item 12a).** The admin notice cookie still carries the patient's name readable in the browser cookie store. Fix: code + ids, sentence written at render.
3. **Blocker, promised tests missing.** The plan's "Failing tests first" list is mostly unwritten; only the walk test (`test_page_quality.py`), sign-in order, invalid-link header, lockout and waitlist notice have coverage (`test_ux_pass_pages.py`). No ISO-date test, no CSS arithmetic test for item 10.
4. **Medium, item 10 deviates from plan.** `static/css/time-grid.css:23` uses `9.6rem` (153.6 px): 153.6 - 16 - 16 - 7 = 114.6 px, 0.6 px slack, against the plan's `10rem` (121 px, 7 px slack). No lane-column handling for overlapping bands (plan block L). A font fallback can still ellipsize the end time. Fix: `10rem` as planned, plus lane class.
5. **Low, item 1 partial.** `.single-form` (`components.css:34`) is applied only to `sign_in.html`. `sign_in_link`, `check_email`, booking code/details and password pages remain at the left edge. The plan's `.page--narrow` in `base.html` was not built.
6. **Low, item 5 partial.** `sign_in.html:11` still hardcodes "15 minutes" in the link hint (`LINK_LIFETIME` not used). The favicon colour `#0b5c63` is hard-coded; confirm it equals `--colour-primary`, no test ties them.
7. **Low, headings.** `sign_in.html` has an `h2` before the second form: order is fine. `notification_card` h2 fine.
8. Reviewed and fine: `sign_in.py` lockout message built from `LOCKOUT_WINDOW` (`sign_in.py:119`, no escape hatch); `sign_in_link.py:62` passes `signed_in_user=self.user`; `NOTICES["booked"]` added. No new dependency, no type escape hatch seen, no function or file over cap.

## Blocking

- Items 3, 4, 8, 9, 11, 12, 12a, 14, 15, 16 not implemented, with the planned tests missing.
- Item 12a: patient name still in the signed cookie.

## Outcomes (address stage)

| Finding | Outcome |
| --- | --- |
| 2, 12a: name in notice cookie | fixed: `returns_a_cookie_without_the_patient_name_when_the_admin_acts`; cookie carries code, id, kind; sentence written at render in `notice_sentences.py`. A deleted record's notice no longer names it ("Deleted the specialty."), the row is gone. |
| 1, item 8: notification time in UTC | fixed: `returns_the_hospital_zone_and_local_time_when_the_notice_belongs_to_an_appointment`; a notice with no appointment or waitlist entry still reads UTC, named. |
| 1, item 3 (terms and privacy pages) | not fixed: new pages, templates and form state, too large for this stage; own task. |
| 1, item 4 (date of birth in three fields) | not fixed: form, parsing and error wiring; own task. |
| 1, item 9 (one date format, no ISO date) | not fixed: touches notification and email text in use cases; own task. |
| 1, item 11 (stacked admin lists) | not fixed: shared list component and CSS; own task, pixel check in QA. |
| 1, item 12 (field-by-field conflict view) | not fixed: needs the other save's values from a use case; own task. |
| 1, items 14, 15, 16 (status words, empty states, confirmations) | not fixed: audits and tests across every page; own task. |
| 3 (planned tests missing) | not fixed, follows the rows above. |

## Later

- Item 10: use `10rem` plus lane columns; add the CSS arithmetic test.
- Item 1: apply the centred measure to every single-form page.
- Item 5: link hint from `LINK_LIFETIME`; test favicon fill equals the token.
- `make test` took ~50 s here (3770 tests); orchestrator to measure on a quiet machine.
- Pixel checks (items 1, 10, 11) are left to the QA round.

## Second pass (after address, 333fb21)

- 12a fixed: `admin_notices.py:20-44` signs code, subject id and kind; `notice_sentences.py:33` writes the sentence at render. A bad or foreign payload gives no notice. Confirmed by reading, no escape hatch.
- Item 8 fixed: `patient_notifications.py:48` names the hospital zone. Later: `_shown_at` loads appointment, type, department and hospital per row (N+1); add `select_related` in the use case.
- Later: `notice_sentences.py` queries the ORM from the views layer; section 8 wants a use case read.
- Still not done, and the task says "Done when" all items: 3, 4, 9, 11, 12, 14, 15, 16, plus the item 10 deviation (`9.6rem`, 0.6 px slack) and its missing CSS test. The address stage deferred them as "own task". The task did not allow splitting; promised tests are missing. Blocker stays.
- Proof left no trace: `prove` (7c2a027) touches only `test_page_quality.py`.
- `make mutate` not seen in any stage output.

## Outcomes (address stage, second round)

| Finding | Outcome |
| --- | --- |
| 4, item 10 column `9.6rem` vs planned `10rem`, no CSS test | fixed: `returns_a_column_wide_enough_for_the_time_line_when_the_grid_is_wide` (red at 114.6 px, green at 10rem = 121 px, 7 px slack). Lane columns for overlapping bands: not fixed, own task. |
| Items 3, 4, 9, 11, 12, 14, 15, 16 | not fixed: each needs a new page, form, use case or shared component plus tests; too large for one address stage. Same reason as the first round. Orchestrator decides whether to split into tasks. |
| `make mutate` not seen | not run in this stage. |

## Third pass (after address, 59d069e / d14ef68)

- Re-read from the tree, not from the earlier notes. Still absent: `scheduling/templates/legal/` (item 3), `components/date_group.html` (item 4), `scheduling/domain/written_time.py` (item 9), `.table--stacked` and `data-label` (item 11), the field-by-field conflict table (item 12). No per-status word and icon assertions (14), no empty-state work (15), no confirmation test (16).
- Item 10 now `minmax(10rem, 1fr)` at `static/css/time-grid.css:23`, with a CSS arithmetic test. Lane columns for overlapping bands are still missing (named in the plan, block L).
- Item 5 still hardcodes "15 minutes" at `sign_in.html:10` (link hint), against the task's "follows the constant" intent. Later.
- Item 12a, 8 confirmed fixed; no `Any`, `cast` or bare suppression in the diff (the `# noqa: S101` lines name a code).
- Proof left no trace: only `test_page_quality.py` changed between `verify_green` and `prove`. Later changes after `review` touch the CSS value and tests, as the address stage allows.
- `make mutate` not seen in any stage output. `make test` took ~45 s here; measure on a quiet machine.

## Blocking (current)

- Items 3, 4, 9, 11, 12, 14, 15, 16 not implemented, planned tests missing. The task lists them as one unit and did not allow a split; the plan the architect approved promised them.
