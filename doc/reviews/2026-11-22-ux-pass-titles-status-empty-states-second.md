# Review 2: task 25d, titles, status words, empty states (slice: items 1 to 3)

## Plan in one sentence per block
- Title fix and export form (`admin/appointments.html:2,32-36`): title is plain text; the export form sits once at the end of `content`. Confirmed at a glance.
- Findings (`page_quality_findings.py`): markup, 80 characters, token outside a form. Clear.
- Status table (`status_words.py`): one table of kind and word per vocabulary status; old tables import it. Clear. `test_status_words.py` covers every `AppointmentStatus` and `WaitlistStatus` value and Active/Inactive.
- Admin lists (`admin_records.py:77-100`, `admin/list.html`): bool columns become badges via `_active_kind`. Traced once.
- Empty states (`admin/dashboard.html:20`, walk test): dashboard, three roles' list pages, admin record lists, public search.

## Findings
- **Fixed since review 1** all three blockers: duplicate-title test (`test_page_title_rules.py:64`), export form back in the page once (asserted at line 59-61 region), status table and every-value test.
- **Later** `scheduling/templates/admin/dashboard.html:20-23`: the header-only table still renders under the empty state; wrap in `{% else %}`.
- **Later** `admin/dashboard.html:21`: hard-coded `/admin-console/appointments/new`; use `{% url %}`.
- **Later** `status_words.py:12-18`: the patient word "Missed" vs staff "No-show" is two tables for one status; intended per plan note 2.
- **Later** `status_words.py:BADGE_KINDS` is not used by a visible check here; confirm a test uses it.
- Proof left no trace: `verify_green` to `prove` changed one test file only. `prove` to `refactor` touched product files, which is the refactor stage and allowed.
- No `Any`, `cast`, bare ignore, no swallowed error, no authorization, audit, booking path, or dependency change.
- Test timing: ~46 to 60 s for 4144 tests, measured in a shared sandbox; the orchestrator measures it again.

## Blocking
- None.

## Later
- Dashboard `{% else %}` and `{% url %}`.
- Check `BADGE_KINDS` is used.

## Left for the orchestrator
- Item 4: refused forms keep what was typed (inventory, test posting a refused value to each form, password excepted).
- Chrome check of five tab titles and the emptied database per role, after merge.
- `make mutate` and a fresh-clone run of the full "Done when" list; not run here.
