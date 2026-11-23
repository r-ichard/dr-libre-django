# Review: hospital time-zone change asks for confirmation (task 27b item 10, issue #36)

Reviewer: second reader, by reading the diff `git diff main...HEAD` (7 files, +556 / -4) and the
plan `doc/plans/2026-11-22-hospital-time-zone-confirmation.md`. Tests and gates were not re-run
here; the stage records show `make test` 5211 passed, `make lint`, `make gate` clean.

## Verdict

`revise`. One blocker: the confirmation is not bound to the zone the admin was shown.

## Findings

### 1. Blocking: confirmation skips the warning for any zone (correctness)

- `scheduling/views/pages/admin_records.py:264-269`: the warning is computed for the zone in the
  POST (`values["time_zone"]`), but the skip test is only `"confirm_time_zone" not in request.POST`.
- `scheduling/templates/admin/form.html:24`: the single submit button carries `confirm_time_zone=1`,
  and it is the only submit button of the form, so Enter in any text field also sends it.
- Failure scenario: the hospital is Berlin, one upcoming appointment. The admin saves Pacific/Auckland
  and sees the warning (1 appointment, example 07:00 Berlin → 19:00 Auckland). The admin then changes
  the time-zone select to Asia/Tokyo, which shifts three upcoming appointments, and clicks
  "Save with the new time zone" (or presses Enter in the name field). The POST carries
  `time_zone=Asia/Tokyo` and `confirm_time_zone=1`. Line 265 is false, so `writers.update` saves Tokyo.
  The admin never saw the Tokyo count or example. This is the write the finding asked to stop.
  Established by reading the code; not reproduced by running it.
- Smallest fix: the warning carries the zone it was shown for. Render a hidden
  `confirmed_time_zone` with the warned zone key (through `_form`, next to `confirm_text`), and skip
  only when `request.POST.get("confirmed_time_zone") == str(values["time_zone"])`. Keep
  `confirm_time_zone` only if the button still needs it.
- Missing test (promised in spirit by the plan's "guards that confirm does not block the save"):
  warn for Pacific/Auckland, then POST Asia/Tokyo with the confirm flag set. Expect 200, the Tokyo
  warning sentence, and the stored zone still Europe/Berlin.
- **Outcome: fixed.** Test `returns_200_with_new_warning_and_no_save_when_zone_changes_after_the_warning`
  was red first (`303 == 200`: Tokyo saved unwarned). Fix: the confirm button's value is the warned
  zone (`form.html`, `confirm_zone` from `_form`); the warning is skipped only when
  `confirm_time_zone` equals the POSTed zone (`admin_records.py`). Tests
  `returns_200_with_warning_and_confirm_button_when_zone_changes_with_upcoming` and
  `returns_303_and_stores_the_new_zone_when_time_zone_change_is_confirmed` now assert the zone value.

### 2. Later: warning shown on a stale page, conflict only after confirm (correctness, low)

- `scheduling/views/pages/admin_records.py:264` runs `_zone_warning` before `writers.update` at
  line 269, which owns the version check. A stale form with a zone change gets the 200 warning;
  confirming then answers 409 with `STALE_TEXT`. Nothing is written. Smallest fix if wanted: read the
  record's current version in `_zone_warning` and return the 409 first. Not a blocker: no data loss.

### 3. Later: the warning query runs on every hospital save (efficiency)

- `scheduling/use_cases/admin_record_reads.py:117-122`: loads every future active start of the
  hospital into memory on every save, including saves that keep the zone. Unbounded list; the plan
  accepts it at current size. Smallest fix: return `""` when `new_zone_key` equals the stored zone
  before querying. Measured: not measured in this sandbox.

### 4. Later: any value of `confirm_time_zone` confirms (plan deviation, low)

- `scheduling/views/pages/admin_records.py:265`: the plan said `request.POST.get(...) != "1"`. The
  current test is presence only. Only skips a warning; authorization is untouched.

### 5. Later: plan deviations to reconcile with the plan (docs)

- The plan's new module `scheduling/views/pages/admin_time_zone_warning.py` was not created. The
  sentence lives in `scheduling/domain/time_zone_shift.py:16-26` (`zone_change_sentence`). The
  count query is `zone_change_warning` in `admin_record_reads.py:117`, not `upcoming_starts`.
  The domain placement is the purer choice and the layering still holds; the plan should be updated
  or the orchestrator accepts the drift.
- `_form` takes `problem` and `confirm_text` instead of the planned `time_zone_warning` keyword
  (`admin_records.py:288-310`). Parameter count is now nine (§5 asks for about three). The plan
  defers that.
- The button replaces the hidden `confirm_time_zone` input the plan asked for
  (`form.html:24`). Behaviour is fine; the Enter-key path is the blocker in item 1.
- The tests moved from `test_admin_records_pages.py` to `test_admin_hospital_zone_pages.py`
  (refactor commit `79d6249`). Names differ slightly from the plan (for example
  `..._when_zone_changes_with_upcoming`). Every promised case exists. Not a missing test.

### 6. Later: naming and comment nits

- `scheduling/views/pages/test_admin_hospital_zone_pages.py:25`: autouse fixture named
  `returns_frozen_clock`; the `returns_X_when_Y` pattern is for tests. Name it `frozen_clock`.
- `scheduling/domain/time_zone_shift.py:1` and the test modules' first lines cite "Task 27b item 10,
  issue #36". Provenance in code goes stale; the commit already names the issue. Delete the reference.
- `scheduling/templates/admin/form.html:24` is one line of about 150 characters. Split it.

### 7. Later: file size (debt, not a new breach)

- `scheduling/views/pages/admin_records.py` is 426 lines (412 on `main`, so this diff adds 14): under
  the 500 gate, over the §5 target of 300. The plan records the debt.

## Checked and clean

- Proof trace (§13, item 7): commits between `verify_green` (`afb8671`) and `prove` (`4aa4ffb`) touch
  only `scheduling/domain/test_time_zone_shift.py` and `scheduling/views/pages/test_admin_records_pages.py`.
  No product or migration line changed there. `refactor` (`79d6249`) changed
  `admin_record_reads.py` after `prove`; that is outside the rule and behaviour-preserving (the
  `_upcoming_hospital_appointments` extraction keeps the same filter and ordering).
- Escape hatches: no `Any`, `cast`, bare `# type: ignore` or bare `# noqa` in added lines.
- Authorization: `RecordFormPage.allowed_roles = {Role.ADMIN}` (`admin_records.py:56`). The record comes
  from `record_or_404` before the warning. The warning reads hospital and appointment data only for
  the admin. `writers.update` still checks role and version. The writer path is not in the diff; I did
  not re-read its audit line, I relied on it being unchanged.
- Audit and transactions: the warning path writes nothing. The confirmed save uses the existing
  `writers.update` path, so its audit entry is unchanged.
- Double booking: no appointment is written; the feature reads only.
- Time: `current_request_context().now` is used (`admin_records.py:358-359`); times are aware UTC
  and converted with `astimezone` (`time_zone_shift.py:29-30`). Half-open window: `starts_at__gt=now`
  excludes the start that is exactly now (test `returns_303_without_warning_when_the_only_appointment_starts_exactly_now`).
- Wall-clock comparison: Berlin → Paris yields no shifts (same wall clock), as the plan states.
- Tests: the two domain tests and the five page tests of the plan exist, assert full sentences, and
  cover past, cancelled and other-hospital rows. Guard tests pass before the change by design.
- Scope: `drlibre-specs.md` not in the diff; no dependency added; no migration; no other backlog item.
- Layers: count in use case, shift in domain, sentence in domain, page in view; no ORM in domain.

## Left for the orchestrator

- Layout at 375 px and 1440 px (plan `## Layout`): not measured here; the sandbox has no browser.
  The orchestrator measures the invariants on the warning page.
- Confirm the blocker in item 1 with a test before the fix lands.

## Blocking

1. `scheduling/views/pages/admin_records.py:265` with `scheduling/templates/admin/form.html:24`: the
   confirmation flag is not bound to the zone the warning was shown for, so a changed zone is saved
   without its warning. Bind the flag to the warned zone and add the Auckland-then-Tokyo test.

## Later

1. Warning shown on a stale page before the version check (`admin_records.py:264-269`).
2. Warning query runs on every hospital save; skip when the zone is unchanged (`admin_record_reads.py:117-122`).
3. `confirm_time_zone` accepts any value; plan said `"1"` (`admin_records.py:265`).
4. Plan drift: module `admin_time_zone_warning.py` not created; sentence in domain; `_form` kwarg replaced; hidden input replaced by button; tests moved file. Update plan or accept.
5. `_form` now takes nine parameters (`admin_records.py:288-310`); defer as the plan says.
6. Fixture named `returns_frozen_clock` (`test_admin_hospital_zone_pages.py:25`); rename.
7. Task and issue references in module docstrings (`time_zone_shift.py:1`).
8. Template line over 150 characters (`form.html:24`).
9. `admin_records.py` 426 lines (412 on `main`), over the §5 target of 300.

## For the owner

- Whether patients are told about a time-zone change. Still open in `doc/backlog.md` (questions). This
  change sends nothing to patients. No ADR was written for it; the backlog entry carries the question.
- Copy: the existing note ("moves nothing that is stored") and the new warning ("will show another local
  time") both show on the warning page and read as a contradiction. The owner decides the wording.
- Count read outside the save transaction: an appointment booked between the warning and the confirmed
  save is not counted (plan open point). Accepted by the plan; owner may want it stated to admins.
