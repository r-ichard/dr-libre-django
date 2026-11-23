# Review: hospital time-zone change asks for confirmation, second reader (task 27b item 10, issue #36)

Reviewer: second reader, by reading `git diff main...HEAD` on `fabro/run/01M82SW1B0JW77HM3A3XKMGDE6`
after the `address` stage, and the plan `doc/plans/2026-11-22-hospital-time-zone-confirmation.md`.
Gates are not re-run here: the stage records show `make test` 5212 passed, `make lint`, `make gate`
and `escape_hatches` clean at `check` (541f1b5). This file sits beside the earlier round
`doc/reviews/2026-11-23-hospital-time-zone-confirmation.md`, which is kept as the record of round 1.

## Verdict

`approve`. No blocker. The round-1 blocker (confirmation not bound to the zone shown) is fixed and
the fix holds on re-read, including the Enter-key path.

## Step 1: block plans (§2.5)

- `shifted_starts` (`scheduling/domain/time_zone_shift.py:10-13`): keeps the starts whose wall clock
  differs between old and new zone. Read at a glance.
- `zone_change_sentence` (`time_zone_shift.py:16-26`): one singular or plural sentence, first shifted
  start as the example. Read at a glance; the `shifted` precondition is in the docstring.
- `_wall` (`time_zone_shift.py:29-30`): local wall clock as a naive value. Read at a glance.
- `_upcoming_hospital_appointments` / `zone_change_warning`
  (`scheduling/use_cases/admin_record_reads.py:105-123`): hospital's active future appointments, sorted,
  reduced to the warning text or `""`. Traced the filter: `starts_at__gt=now`, `ACTIVE_STATUSES`,
  `clinician__department__hospital_id`, the same as `upcoming_appointment_count`.
- `RecordFormPage.post` warning branch (`scheduling/views/pages/admin_records.py:264-268`): traced.
  Skip the warning only when the POSTed `confirm_time_zone` equals the stripped saved zone.
- `_zone_warning` (`admin_records.py:358-362`): hospital only, `now` from `current_request_context()`.
- `_form` additions (`admin_records.py:298-310`) and the button (`scheduling/templates/admin/form.html:24`):
  read at a glance, but the button branch was traced for the value it carries.

## Step 2: correctness and error handling

- No swallowed error. `zone_change_sentence` indexes `shifted[0]`; the only caller guards with
  `if shifted` (`admin_record_reads.py:123`), so the index cannot fail. An invariant, not an expected error.
- `Hospital.objects.get(pk=hospital_id)` (`admin_record_reads.py:119`) cannot miss: `record_or_404`
  already loaded the record (`admin_records.py:246`).
- `ZoneInfo(new_zone_key)` (`admin_record_reads.py:120`) is safe: `parse_form` only passes keys that
  `check_time_zone` accepted against `available_timezones()` (`admin_record_forms.py:45-46`,
  `record_fields.py:92-96`), and the warning path runs only when `errors` is empty (`admin_records.py:262`).
- Zone equality: `values["time_zone"]` is stripped (`record_fields.py:93`); the button value is the
  raw typed text (`admin_records.py:310`). A padded zone can never match, so the admin is asked again.
  It cannot bypass the warning: the confirm must equal the saved zone exactly. See Later 4.
- Enter-key path, traced in the template: the only submit button in the form is the confirm button
  (`form.html:23-26`), so Enter in any field sends `confirm_time_zone` equal to the warned zone. If
  the admin changed the select to another zone, the POST zone differs and the new zone is warned
  (`test_admin_hospital_zone_pages.py:140-155`). Read, not run in a browser.

## Step 3: authorization, boundaries, sensitive data (§7, §11)

- `RecordFormPage.allowed_roles` is admin only (`admin_records.py:56`). The record comes from
  `record_or_404` before the warning. Nothing new reads a value from the payload for authorization:
  the POSTed zone is the requested new value, validated by the existing `parse_form` path.
- The warning reads hospital and appointment rows for the admin's own record only. No new route, no
  new URL parameter, nothing logged. The warning text (appointment count, two local times) goes
  into the page only, not the URL and not a log.
- Schema at the boundary: unchanged; `parse_form` and `check_time_zone` still validate the zone.
- `confirm_time_zone` only skips the warning. It does not authorize a write: `writers.update` still
  checks role and version (`admin_records.py:269`, not in this diff).

## Step 4: double booking

- Nothing new is written. The feature reads appointments; no appointment is created or moved, so no
  conflict check is affected. Room and patient conflicts are not touched.

## Step 5: tests (§10.1)

- Domain tests (`scheduling/domain/test_time_zone_shift.py:15-43`) assert full values: the list of
  starts, and the complete singular and plural sentences. They are derived from the plan's text.
- Page tests (`scheduling/views/pages/test_admin_hospital_zone_pages.py`) send through `admin_post`,
  which sends `Origin` and the CSRF token (`admin_support.py:42-49`), as the rule requires.
- The filter test (`:79-93`) pins past, cancelled and other-hospital rows; each excluded row changes
  the count or the example, so the assertion can fail.
- Boundary: `returns_303_without_warning_when_the_only_appointment_starts_exactly_now` (`:111-122`)
  pins the half-open `starts_at > now` rule.
- Confirm and mismatch paths are both asserted (`:125-137`, `:140-155`).
- Gap: nothing asserts that the warning step writes no audit entry. The stored zone is asserted
  unchanged (`:76`, `:155`), which shows no hospital write, but not the absence of an `AuditLogEntry`.
  Later 5.

## Step 6: names and comments (§3, §4)

- Names state roles: `zone_change_warning`, `shifted_starts`, `zone_change_sentence`,
  `_upcoming_hospital_appointments`. Test names use `returns_X_when_Y`, except the fixture (Later 6).
- Comments: no narration found in the added lines. Provenance references in docstrings (Later 7).
  Every added line is under the 255-character cap; the gate passed.

## Step 7: proof trace (§13)

- `git log --oneline`: `verify_green` is `afb8671`, `prove` is `4aa4ffb`. The commit that touched
  files in that range is `4aa4ffb` alone, and its files are `scheduling/domain/test_time_zone_shift.py`
  and `scheduling/views/pages/test_admin_records_pages.py`. Both are tests. No product or migration
  line changed there. Blocker check clears.
- `refactor` (`79d6249`) changed `admin_record_reads.py` and moved the page tests to
  `test_admin_hospital_zone_pages.py`. It came after `prove`, so the rule does not apply. The
  `_upcoming_hospital_appointments` extraction keeps the same filter and ordering.

## Step 8: scope and contracts

- `drlibre-specs.md` not in the diff. No migration. No dependency added. No other backlog item touched.
- No notification, email, FHIR, or patient page changed. The plan's "What I will not do" holds.
- Layer placement: count in the use case, shift and sentence in the domain, page in the view. No ORM
  in the domain. The domain placement is purer than the plan's view module (see Later 8).
- Escape hatches: none in added lines (`noqa`, `type: ignore`, `cast`, `Any`). The existing
  `# noqa: S101` lines are unchanged.
- Size: `admin_records.py` 427 lines (under 500, over the §5 target of 300; pre-existing debt).
  `admin_record_reads.py` 175 lines. Longest function added is `post`, about 28 lines.

## Findings

Severity: `later` for every item. None is a blocker.

1. `admin_records.py:264-269`: the warning is shown before `writers.update` checks the version, so a
   stale page with a zone change gets the 200 warning, and confirming then answers 409. Nothing is
   written; no data loss. Smallest fix: read the record's current version in `_zone_warning`, or
   accept as is.
2. `admin_record_reads.py:117-123`: every hospital save loads all future active starts into memory,
   including saves that keep the zone. Smallest fix: return `""` when `new_zone_key` equals the stored
   zone before querying. Not measured here; the sandbox shares its machine.
3. `admin_records.py:288-300`: `_form` takes nine parameters (§5 asks for about three). The plan
   deferred this. Smallest fix later: pass the warning and confirmation as one small value.
4. `admin_records.py:310`: `confirm_zone` is the raw typed text, but the check at `:265` compares the
   stripped zone. A padded zone never matches and the warning repeats. Not a bypass. Smallest fix:
   use `str(values["time_zone"])` for the confirm value.
5. `test_admin_hospital_zone_pages.py:111-122` and `:125-137`: no assertion that the warning step writes
   no `AuditLogEntry`. Smallest fix: count `AuditLogEntry` rows before and after the warning POST.
6. `test_admin_hospital_zone_pages.py:25`: autouse fixture named `returns_frozen_clock`; the
   `returns_X_when_Y` pattern is for tests. Smallest fix: `frozen_clock`.
7. Provenance in docstrings: `time_zone_shift.py:1`, `test_time_zone_shift.py:1`,
   `test_admin_hospital_zone_pages.py:1-2`. The commit already names the issue, and the reference goes
   stale. Smallest fix: delete "Task 27b item 10, issue #36".
8. Plan drift: plan named `admin_time_zone_warning.py`, `upcoming_starts`, `time_zone_warning`, a
   hidden input `value="1"`, and `test_admin_records_pages.py`. Built: domain module `time_zone_shift.py`,
   `zone_change_warning`, a button carrying the zone (a deliberate fix from round 1), and
   `test_admin_hospital_zone_pages.py`. Smallest fix: update the plan, or accept the drift.
9. `form.html:24`: one line of about 150 characters. Smallest fix: split the `{% if %}` and button over lines.
10. `time_zone_shift.py:29`: `_wall` is short for a role that is "wall clock". Smallest fix: `_wall_clock`.
    Nit.

## Checked and clean

- Confirmation bound to the warned zone: `admin_records.py:265`, `form.html:24`, and the mismatch test
  `test_admin_hospital_zone_pages.py:140-155`. Round-1 blocker closed.
- Warning writes nothing; the confirmed save uses the existing `writers.update` path.
- Half-open window: `starts_at__gt=now` (`admin_record_reads.py:108`).
- Time: `current_request_context().now` (`admin_records.py:361`); aware UTC converted with `astimezone`
  (`time_zone_shift.py:29-30`).
- Authorization: admin only, record loaded before the warning.

## Left for the orchestrator

- Layout at 375 px and 1440 px (plan `## Layout`): not measured; the sandbox has no browser. The
  orchestrator measures `scrollWidth`/`clientWidth`, notice and form edges, and `.button-row` edges.
- Enter-key path verified by reading the template, not in a browser. The orchestrator may confirm it
  in the browser with the layout measurement.
- `make mutate` and `make fhir-validate` (last scripted gates): not run by this stage.
- Timing: `make test` took 158 s and 155 s in the stage records. Measured on a shared machine; not a
  finding. The orchestrator measures on a quiet machine.
- The plan has no `## Not in this run` section. Its slice line (`plan:3`) is item 10 only; nothing
  outside that slice is in the diff.

## Blocking

(none)

## Later

1. Warning shown on a stale page before the version check (`admin_records.py:264-269`).
2. Warning query runs on every hospital save; skip when the zone is unchanged (`admin_record_reads.py:117-123`).
3. `_form` takes nine parameters (`admin_records.py:288-300`); defer as the plan says.
4. `confirm_zone` uses the raw typed zone; a padded zone repeats the warning (`admin_records.py:310`).
5. No assertion that the warning step writes no audit entry (`test_admin_hospital_zone_pages.py`).
6. Fixture named `returns_frozen_clock` (`test_admin_hospital_zone_pages.py:25`); rename to `frozen_clock`.
7. Task and issue references in docstrings (`time_zone_shift.py:1`, `test_time_zone_shift.py:1`, `test_admin_hospital_zone_pages.py:1-2`).
8. Plan drift: module, function, input and test-file names differ from the plan (see finding 8).
9. Template line about 150 characters (`form.html:24`).
10. `_wall` name (`time_zone_shift.py:29`). Nit.
11. `admin_records.py` 427 lines, over the §5 target of 300 (pre-existing debt, the plan records it).

## For the owner

- Patients: this change sends nothing to patients. Whether they should be told about a zone change is
  still an open question in `doc/backlog.md`. No ADR was written; the backlog entry carries it.
- Copy: the existing note on the edit page ("Changing the time zone moves nothing that is stored",
  `admin_records.py:373`) and the new warning ("will show another local time") both show on the
  warning page and read as a contradiction. The owner decides the wording.
- Race: an appointment booked between the warning (`admin_records.py:264`) and the confirmed save
  (`:269`) is not counted. The plan accepted this; the owner may want admins told.
