# Plan: task 27b, items 5a and 5 (waitlist form), patient page

Date 2026-11-22. Backlog `doc/backlog/27b-qa-round-3-pages.md` items 5a and the first half of 5 (issue #43 and the
label bug seen under 27a2). Spec 8 (Waitlist date window), 16 (errors tied to their field, say what to do; precise
wording). Impeccable mode: spec 16 is product truth (no `PRODUCT.md`); the build stage reads
`.claude/skills/impeccable/reference/craft-floor.md` before editing the template.

Slice: items 5a and 5 (the two empty-day errors on the patient's waitlist form only). Two small changes, each with
tests.

## Focal point

`/patient/waitlist` (`scheduling/views/pages/patient_waitlist.py`) and its entry card
(`scheduling/templates/components/waitlist_card.html`). Both are read-only text changes; no write path changes.

## Blocks

1. `waitlist_card.html:6`: the `<dt>` reads `Wanted between`, and `window_words` already writes `from X to Y` or the
   one day. Change the label to `Wanted`. The value stays as `window_words` writes it (no change to
   `scheduling/domain/waitlist_window.py`, which is already correct for both shapes).
2. `patient_waitlist.py:38` `REAL_DATE` (one text for both fields, used at lines 118 and 120). Replace with two
   constants: `FIRST_DAY_MESSAGE = "Enter the first day, for example 2030-03-27."` and
   `LAST_DAY_MESSAGE = "Enter the last day, for example 2030-03-27."`, assigned to `earliest_day` and `latest_day`
   respectively. The summary links already use `id_<field>` (`portal_forms.summary_items`), so each link now has its
   own text.

Choice made: one message per field, used for both an empty value and a malformed one. Splitting empty from malformed
would add a second constant per field for no finding in the QA report. A malformed value still gets a message that
names the field.

## Files to touch, in order

1. `scheduling/views/pages/test_patient_waitlist_page.py`: failing tests (red first).
2. `scheduling/views/pages/patient_waitlist.py`: the two constants and two assignments.
3. `scheduling/views/pages/test_patient_waitlist_window.py`: failing test for the label (red first).
4. `scheduling/templates/components/waitlist_card.html`: label `Wanted`.

Not touched: `window_words` and its domain tests, `portal_forms.py`, `components/field.html`, the admin waitlist form
(`admin_waitlist.py`, finding #37), any other form (item 5's "every form" assertion is another run), the FHIR and API
layers, the use case `use_cases/waitlist.py`, the spec and the backlog file (the orchestrator updates `doc/backlog.md`).

## Failing tests (behaviour names, expected values in words)

In `test_patient_waitlist_page.py` (the page is posted as a browser sends it, `browser_post`, with a valid appointment
type so that only the day errors show):

- `returns_422_naming_first_day_when_first_day_is_empty`: first day empty, last day set. Expect status 422, the
  message "Enter the first day, for example 2030-03-27." in the summary and the field's error, the link
  `href` target `#id_earliest_day`, and no "Enter the last day" text.
- `returns_422_with_two_different_day_messages_when_both_days_are_empty`: both days empty. Expect 422, the summary
  contains "Enter the first day, for example 2030-03-27." and "Enter the last day, for example 2030-03-27.", and these
  two texts are not equal (the QA defect was two identical lines).

In `test_patient_waitlist_window.py`:

- `returns_wanted_label_when_entry_covers_several_days`: entry spans 23 to 29 November 2026. Expect the HTML to hold
  `<dt>Wanted</dt><dd>from Monday 23 November 2026 to Sunday 29 November 2026 (Europe/Berlin)</dd>` and not
  "Wanted between".
- `returns_wanted_label_when_entry_covers_one_day`: entry on Thursday 26 November 2026 only. Expect
  `<dt>Wanted</dt><dd>Thursday 26 November 2026 (Europe/Berlin)</dd>`.

Each must fail before its block is written. Red for the right reason is judged by the reviewer: the label tests fail
on "Wanted between"; the day tests fail on "Enter a real date".

## Trust boundaries

- Form POST body (`earliest_day`, `latest_day`): already validated by `day_or_none` (ISO regex and `fromisoformat`)
  and by `window_instants`. This change only changes the text returned for an invalid value. No new input.
- Authorization: `WaitlistPage.allowed_roles = PATIENT`, patient from the session. Unchanged.
- CSRF and Origin: the existing `browser_post` test covers the form as a browser sends it. Unchanged.
- Output: the message text is a constant; the window text is built from the entry's own instants. No user text is
  echoed into the page by this change.

## Domain entities (spec vocabulary, CLAUDE.md §3)

Patient, WaitlistEntry (`earliest_at`, `latest_at` read as the window), AppointmentType, Hospital (time zone).

## Invariants and blast radius

- Double booking, audit log, server-side authorization: no write path, no use case and no model changes. A 422
  still writes nothing (existing test `returns_422_when_...` covers the 422 with no entry).
- Blast radius: the patient waitlist page text (label and two error messages). The admin waitlist card is not built
  from this template (grep: only `patient/waitlist.html` includes `components/waitlist_card.html`).
- Layout: text change in a `<dt>` and in error text; the label is shorter than before, so no line grows. Layout
  invariant at 375 px and 1440 px is unchanged (no CSS touched); the orchestrator checks the page in a browser.

## What I will not do

- No new message helper, no mapping table, no refactor of `_join_errors`.
- No change to the empty-vs-malformed split (see Choice above).
- No change to other forms or to the admin waitlist (#37).
- No change to `window_words` or its wording beyond the label on the card.
- No new dependency, no migration, no test helper.

## Not in this run

- Item 5, rest: every other form the product renders, submitted empty, asserted to give no two identical links.
- Items 1 to 4, 6 to 10: messages (#34, #35), admin waitlist (#37), time off (#40), sign-in 405 (#42), patient
  reschedule 404 (#49), week strips (#44), reschedule to same start (#39), time zone confirmation (#36).

## Architect review

Verdict: approve. Checked against the code: `REAL_DATE` is at `patient_waitlist.py:38`, used at lines 118 and 120;
`waitlist_card.html:6` holds `Wanted between`; `window_words` already writes `from X to Y` or the one day; the card is
included only from `patient/waitlist.html`, so the admin waitlist is untouched; no existing test asserts "Enter a real
date", so no existing test breaks.

1. Ladder: two constants, two assignments, one label word. No helper, no refactor, no dependency. Smallest change in the
   right layer (view text and template text).
2. Plan knowledge: each block states its purpose in one sentence (label, per-field error text). Vocabulary is spec
   vocabulary (WaitlistEntry, Patient, AppointmentType).
3. Test first: both red tests name the behaviour and the expected text; the two-message test guards the QA defect
   (identical lines). Edge path covered: both days empty. Gap, not a reason to revise: no test pins the malformed-value
   message (`2030-02-30` or `27/03/2030`); the same branch serves it, so the build stage should add one such test
   next to the empty-day test.
4. Security: no new input; form values already pass `day_or_none` and `window_instants`; server-side role check
   unchanged; the message is a constant, and the window text comes from the entry's own instants. Nothing sensitive
   logged or in a URL.
5. Architecture: view and template only; no write path, no transaction or audit change; 422 writes nothing.
6. Scope: slice is coherent (the waitlist page is whole after the change); item 5 "every form" is explicitly under
   `## Not in this run`. The backlog file is left to the orchestrator, as the plan says.

Build-stage notes: read `.claude/skills/impeccable/reference/craft-floor.md` before the template edit; check the
label's `<dt>` in a 375 px layout is not wider than before (it is shorter, so expect no change).
