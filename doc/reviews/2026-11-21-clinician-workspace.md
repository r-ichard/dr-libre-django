# Review: task 16, clinician workspace (today, calendar, appointment, notes)

Diff `main...HEAD`, 58 files. `make gate` re-run: clean. Proof commits (`verify_green`..`prove`) touched tests and `mutation-equivalents.txt` only: no product line left behind.

## What I confirmed at a glance
- Plan per block states in one sentence: domain (`calendar_grid`, `workspace_day`, `staff_actions`, `clinical_note_rules`, `audit_labels`) pure; use cases own the note write and own-appointment guard; views thin and format only.
- `clinical_notes.py:21-45`: authorization from the session user and a row lock; validation, upsert and audit in one `transaction.atomic`; audit metadata names the field only. Admin, patient and other clinician refused (`test_clinical_notes.py`).
- Note moved to its own table (`models/booking.py:110`, migration 0011 with forward and backward data move), so API serializers and emails no longer see it.
- `clinician_support.py:48-56`: missing is 404, someone else's is 403 with one sentence. Tested (`test_clinician_workspace.py:245`).
- Status, cancel and reschedule go through the task 08 use cases; `StatusActionPage` takes the return page from a fixed list, not a payload URL.
- Caching: `page_view.py:44` adds never-cache; tested for today, calendar, appointment.
- Colour reaches the page via a same-origin stylesheet (`clinician_calendar.py:130-144`), values validated by `COLOUR_PATTERN`, no inline style.

## Findings

1. **Blocker, test missing.** `test_clinician_workspace.py:321` plants a note and checks patient pages, API, admin console, mail, notifications and audit metadata. The spec says "not in ... log line" and "prove each 'not' with a planted note". No test captures logs (`caplog` appears nowhere in the diff). Risk: a later log line carrying the note passes unseen. Smallest fix: run `save_clinical_note` plus the notes POST and a page GET under `caplog.at_level(DEBUG)` and assert `PLANTED_NOTE not in caplog.text`.
2. **Medium, `clinical_notes.py:48-53`.** `read_clinical_note` runs no audit and no lock; fine per spec, but `NotesPage.render_details` (`clinician_appointment.py:93-94`) turns a read `Failure` into an empty note silently. Unreachable after the ownership check, still a quiet swallow. Fix: render the refusal.
3. **Low, `clinician_appointment.py:131`.** `NOTE_TOO_LONG` is shown for any `INVALID_INPUT`, including future causes. Fix: use the failure's message.
4. **Low, `clinician_today.py:69-73`.** `_hours` groups by `starts_at` dict key; two appointments of one clinician at the same start (cancelled plus rebooked) work, but the grouping is roundabout. Simplify to group rows directly.
5. **Low, tests.** `test_clinician_workspace.py:321` admin surface is `/admin-console/` landing page only; it cannot show an appointment, so the "not to an admin" proof rests on the use-case test. Add an admin GET of the notes URL expecting 403 and no content.
6. **Low, `age_in_years` (`clinician_appointment.py:34`).** Tested only indirectly; Feb 29 birthdays fall to the generic tuple compare, correct. No action.

## Second pass
Re-read after `address`: the planted-note log test (`test_clinician_workspace.py:344`) is real (asserts records exist, then the note absent). Proof commits touched tests and `mutation-equivalents.txt` only. Finding 2 re-judged: `clinician_appointment.py:93-94` drops a returned `Failure` and renders an empty note. If the read fails (appointment removed between guard and read), the clinician sees a blank note box and can save over a real note. That is a swallowed error (§9, hard rule), so it is a blocker.

## Blocking
- Finding 2 (second pass): `clinician_appointment.py:93-94` swallows a note read `Failure`. Smallest fix: when `stored` is a `Failure`, return `self.refusal_of(request, stored)`; test it by patching the read to fail. **Outcome: fixed**, test `returns_refusal_instead_of_empty_note_box_when_note_read_fails`; red first (200 with empty note box).
- Missing planted-note proof for "not in any log line" (finding 1). **Outcome: fixed**, test `returns_note_out_of_every_log_line_when_clinician_saves_and_opens_it`; proven red by a temporary `logging.warning(note)` in the use case, then reverted.

## Later
- Finding 3: use the failure message for the note error.
- Finding 4: simplify hour grouping.
- Finding 5: admin notes URL test.

## Third pass
Re-read after the second `address`: `clinician_appointment.py:93-96` now returns `refusal_of` for a failed note read; no swallow left. `git diff 75ac242 e6cef65` (verify_green..prove) touches tests and `mutation-equivalents.txt` only. `check` after `address` passed lint, 2178 tests and gate. No new blocker.

## Blocking
None.

## Later
Unchanged: findings 3, 4, 5.
