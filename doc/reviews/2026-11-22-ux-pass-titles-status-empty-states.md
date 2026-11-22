# Review: task 25d, titles, status words, empty states (slice: items 1 to 3)

## Plan in one sentence per block
- Title fix (`admin/appointments.html:2`): form out of `{% block title %}`. Confirmed at a glance. The form no longer renders anywhere on the page (see B2).
- Findings (`page_quality_findings.py:37-166`): markup, 80 characters, token outside form. Clear; `_form_depth` clamps at 0.
- Badges (`admin_records.py:76-100`, `admin/list.html:19`, `admin_appointments.py:127`): bool columns become `(label, cell, kind)` triples. Traced `_active_kind`: skips `extra`, non-bool.
- Dashboard empty state (`admin/dashboard.html:20`): shown when `busiest` is falsy, but the empty table below still renders.

## Findings
- **Blocker** `scheduling/views/pages/test_page_quality.py`: the promised test `returns_no_two_pages_with_one_title_when_every_page_is_walked` and the "two different pages share a title" rule (task item 1, plan block 2) do not exist. No title uniqueness is checked, nor fixed.
- **Blocker** `scheduling/templates/admin/appointments.html:1-5`: the export form was deleted from the title, not moved. The diff has no `<form` in `content`. The task says "The form belongs in the page, once"; the plan test `returns_the_admin_appointments_title_as_plain_text_when_the_page_opens` asserts the form appears once in `<main>`. CSV export is unreachable from the UI. Fix: put the form at the end of `content` and assert it once. Check with `grep -n "export_action" scheduling/templates`.
- **Blocker** item 2: no single status table (`status_words.py` absent). `STATUS_BADGES` and `STATUS_BADGE_TEXT` are not merged, and there is no test over every vocabulary value (user, clinician, hospital, room, appointment type, specialty, waitlist status). Tests cover only admin lists' Active/Inactive and appointment statuses. The task states "a test lists every status value ... and fails when one has no word and no badge".
- **Later** `scheduling/templates/admin/dashboard.html:20-23`: empty table (header only) remains under the empty state; wrap in `{% else %}`.
- **Later** `admin/dashboard.html:20`: hard-coded `/admin-console/appointments/new`; use `{% url %}` if a name exists.
- **Later** `admin_records.py:_cell`: still returns "Active"/"Inactive" strings used as badge text; wording lives in two places.
- **Later** empty-state walk lists only three admin pages plus patient and clinician lists; admin hospital, clinician, room and type lists rely on a separate per-kind test. Search finding nothing is covered for the public search.
- No type escape hatch other than `# noqa: S105` with a code (`page_quality_findings.py:11`), allowed. No authorization, audit, or booking-path change. Commits after `verify_green` to `prove` touch only a test file; no product line changed there.
- Item 4 is deliberately left out of the slice.

## Blocking
- Duplicate-title rule and test missing.
- Admin appointments export form removed from the page, not moved.
- Status table and the every-status-value test missing.

## Later
- Dashboard `{% else %}` for the empty table; `{% url %}` for the link.
- Single source for Active/Inactive wording.
- Walk every admin list in one test.
- Test timing: not measured (shared sandbox, 4145 tests passed in ~60s).

## Left for the orchestrator
- Item 4: refused forms keep what was typed (inventory, test posting a refused value to each form, password excepted).
- Chrome check of five tab titles and the emptied database per role, after merge.
- Not finished in the slice: the three blockers above.

## Outcomes (address stage)
| Blocking finding | Outcome |
|---|---|
| Duplicate-title rule and test | fixed: `returns_no_two_pages_with_one_title_when_every_page_is_walked` in `test_page_title_rules.py` (the test lives there, not in `test_page_quality.py`; it was already in the tree and passes) |
| Export form removed from the page | fixed: form sits once at the end of `content` in `admin/appointments.html`; guarded by `returns_the_admin_appointments_title_as_plain_text_when_the_page_opens` (already in the tree) |
| Status table and every-status-value test | fixed: `status_words.py` is the one table; `test_status_words.py` covers every `AppointmentStatus` and `WaitlistStatus` value plus Active/Inactive; the old tables now import it |
