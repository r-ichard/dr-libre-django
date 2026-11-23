# Review: task 27b items 5a and 5 (waitlist form), patient page

Date 2026-11-22. Reviewed `git diff main...HEAD` on `fabro/run/01M82QKA3DJTDSYG6Q27KR6P25`
(6 files, +192 −8). Plan: `doc/plans/2026-11-22-waitlist-day-errors-and-label.md`. Issue #43 and
the label bug seen under 27a2. Reviewed the diff and the code it touches; the gate results come
from the stage log (`check`: lint, 5182 tests, comment cap, size cap, escape hatches all passed).
I did not re-run them.

## Block by block (plan in one sentence, then what forced a trace)

1. `scheduling/templates/components/waitlist_card.html:6`: the label becomes `Wanted`. Confirmed
   at a glance: a one-word text change; `window_words` already writes `from X to Y` or the one day.
   The card is included only from `patient/waitlist.html:11`, so the admin waitlist is unchanged.
2. `scheduling/views/pages/patient_waitlist.py:38-39, 118-121`: each empty or malformed day gets a
   message that names its own field. Confirmed: `summary_items` (`portal_forms.py:26-27`) links
   `id_<field>`, and the template's field ids are `id_earliest_day` / `id_latest_day`
   (`components/field.html:4`). Traced: `REAL_DATE` has no remaining references in `scheduling/`.
3. `scheduling/domain/test_waitlist_window.py:127-134` (prove stage): one test of the end-instant
   boundary of `window_words`. Confirmed by hand: 26 Nov 23:00:00.000001 UTC minus 1 µs is
   26 Nov 23:00 UTC, which is 27 Nov 00:00 in Berlin, so the expected "Friday 27" holds.

## Stage checks

- **Commits after `verify_green` (7):** `c6e0d67 prove` changes only
  `scheduling/domain/test_waitlist_window.py`; `57e034c refactor` changes only
  `test_patient_waitlist_window.py`; `022ab12 check` is empty. No product or migration line moved
  after `verify_green` (`8459383`). Proof left no trace.
- **Red for the right reason:** the logged `verify_red` output shows the two label tests failing on
  `Wanted between` (the expected text is absent). The two day-message failures are in the omitted
  part of the log. By reading the old code (`REAL_DATE` for both fields), they fail on
  "Enter a real date", which is what the plan says.
- **Authorization:** unchanged. `WaitlistPage.allowed_roles = frozenset({Role.PATIENT})`
  (`patient_waitlist.py:46`); the patient comes from the session.
- **Input and boundaries:** unchanged. `day_or_none` (`portal_forms.py:30-36`) and `window_instants`
  still validate the posted days. Only the text returned for an invalid value changed.
- **Errors:** no swallowed error; the 422 path still returns before any write (`patient_waitlist.py:122-123`).
- **Writes, audit, double booking:** no write path, no use case, no model, no migration in the
  diff. `join_waitlist` runs only after the day checks pass, as before.
- **Names and comments:** `FIRST_DAY_MESSAGE` / `LAST_DAY_MESSAGE` state roles. No new comments.
  Test names follow `returns_X_when_Y`.
- **Scope and dependencies:** no dependency, no spec change (`drlibre-specs.md` is not in the diff),
  no contract change in the API or FHIR layers. The only out-of-slice item is the prove-stage
  domain test noted above.

## Findings

### 1. Malformed day now reads "Enter the first day", which is less precise than "Enter a real date"
- Severity: nit (Later)
- `scheduling/views/pages/patient_waitlist.py:38-39, 118-121`
- Risk: `day_or_none` returns `None` for an empty value and for a malformed or non-existent
  one (for example `2030-02-30`). Both now get "Enter the first day, for example 2030-03-27.",
  which tells someone who typed a date that they have not entered one. The old text said
  "Enter a real date", which covered that case. The plan chose one message per field and
  recorded this trade-off.
- Smallest fix: change both constants to "Enter a real first day, for example 2030-03-27." and
  "Enter a real last day, for example 2030-03-27." This keeps the field name and the precision.

### 2. No test pins the malformed-value message
- Severity: nit (Later)
- `scheduling/views/pages/test_patient_waitlist_page.py` (no malformed-day test)
- Risk: the malformed branch shares the constant that the empty-day tests cover. A later edit
  could split the two cases without a test failing. The plan's architect review suggested a
  test beside the empty-day test; it is not in the plan's test list, so it is not a promised test.
- Smallest fix: add `returns_422_naming_first_day_when_first_day_is_not_a_date` posting
  `earliest_day="2030-02-30"` and asserting the first-day link text.

### 3. Test names differ from the plan
- Severity: nit (Later)
- `scheduling/views/pages/test_patient_waitlist_window.py:23-55`
- Risk: none to behaviour. The plan lists `returns_wanted_label_when_entry_covers_several_days`
  and `..._covers_one_day`; the code uses `..._window_covers_...`. The orchestrator reading the plan
  against the diff will see a mismatch.
- Smallest fix: rename in the plan or in the test; either is fine.

### 4. Prove-stage test sits in a file the plan said it would not touch
- Severity: nit (Later)
- `scheduling/domain/test_waitlist_window.py:127-134`
- Risk: none for correctness. The plan's "Not touched" list names `window_words` and its domain
  tests. The commit is test-only and after `verify_green`, which the rules allow, and it guards a
  real boundary (end instant one microsecond past local midnight). It is outside this slice, so
  note it in the orchestrator's review.
- Smallest fix: none needed; keep, and mention it in the squash message.

## Blocking

None.

## Later

- Finding 1: split the wording or add "real" to both messages (`patient_waitlist.py:38-39`).
- Finding 2: add the malformed-date test (`test_patient_waitlist_page.py`).
- Finding 3: align the test names with the plan.
- Finding 4: note the out-of-slice domain test in the squash message.
- Mutation and FHIR gates were not part of this stage; the orchestrator runs them under the task's final gates.

## Left for the orchestrator

- Browser check of `/patient/waitlist` at 375 px and 1440 px (plan: "the orchestrator checks the page in a browser").
  The label is shorter than before and no CSS changed, so no layout change is expected; measure, do not assume.
- Confirm the build stage read `.claude/skills/impeccable/reference/craft-floor.md` before the template edit.
  The diff does not show this.
- Item 5 ("every form the product renders, submitted empty") is under the plan's `## Not in this run`; not reviewed here.
- Items 1 to 4 and 6 to 10 of task 27b are not in this slice; not reviewed here.
- Squash to `main` with a hand-written message that names #43 only with `Refs #43` or `fixes #43`, per the
  issue-number rule, and with no fabro checkpoint lines in the body.

## For the owner

None. No decision in this slice is left open by `drlibre-specs.md`; the malformed-date wording (finding 1)
is a product-text choice for the orchestrator, not a spec question.
