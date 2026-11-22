# Review: task 25a, the week fits again

Base: `ece5dce`. Diff read: `git diff ece5dce..HEAD` (no local `main` in the sandbox).

## Proof trace
Commits after `verify_green` (a70e264) up to `prove` (2967135) touch only
`test_notice_sentences_layer.py` and `test_patient_notifications_page.py`. No product line
changed under proof. OK.

## Plan in one sentence, per block
- `static/css/time-grid.css:3,7,23`: column min 8.75rem, block padding 4 px, rail 8 px; derived
  from 1088 - 56 - 48 = 984 / 7 = 140.57. Confirmed at a glance; arithmetic re-traced: 7x140+48 =
  1028 <= 1032; beside the rail 140 - (8+4+4+7) = 117 >= 114.
- `sign_in.py:25,115-132`, `sign_in.html`: hint follows `LINK_LIFETIME`; intro sentence no longer
  false. Confirmed at a glance.
- `use_cases/notice_subjects.py`: three lookups moved out of the views layer, same fallbacks.
- `notification_inbox.py:25-29`: `select_related` through appointment and waitlist entry; recipient
  filter stays first.
- Item 5 (favicon): test already exists, `test_ux_pass_pages.py:81`; no change.

## Findings
- **Low**, `scheduling/use_cases/` : the plan listed `use_cases/test_notice_subjects.py` (name of
  patient, "gone" gives `None`). It was not written. Behaviour is covered through
  `test_admin_notices.py` and the new layer test, so no hole in behaviour, only a direct unit test
  missing. Smallest fix: add the file, three cases.
- **Low**, `scheduling/templates/check_email.html:5`: still says "15 minutes" as text, same drift as
  item 2. Plan named it as follow-up. Fix: pass the same hint minutes.
- **Low**, `static/css/time-grid.css:3`: rail narrowed 16 to 8 px; the time off band is a thinner
  strip. Colour is not the only signal (text in band), but the orchestrator should look at it in
  Chrome.
- **Low**, `test_time_grid_css.py`: the pixel result is arithmetic over parsed CSS; nothing here
  measured a browser. Orchestrator re-measures `scrollWidth` at 1440 px.
- **Nit**, `notice_subjects.py`: `.first()` after `filter(pk=...)` is fine; no authorization
  needed, input is a parsed UUID from a cookie that carries code and id only.

No write path, audit, authorization, boundary, dependency or type-escape change. Gate and tests
passed in `check` (3780 passed). Timing: `make test` about 34 s in the sandbox (not a budget).

## Blocking
None.

## Later
- Add `use_cases/test_notice_subjects.py`.
- Make `check_email.html` follow `LINK_LIFETIME`.
- Orchestrator: measure the week at 1440 px in Chrome (grid and line `scrollWidth`) and look at the
  8 px time off rail.
