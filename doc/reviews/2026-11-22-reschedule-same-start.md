# Review: reschedule to the current start changes nothing (task 27b, item 9, issue #39)

Reviewer: second reader, diff `main...HEAD` (6 files, +322 / -2). Plan:
`doc/plans/2026-11-22-reschedule-same-start.md`. Product change: one comparison in
`scheduling/use_cases/appointment_changes.py:86-87`.

Verdict: **approve**. No blocking finding.

## 1. Plan per changed block (§2.5)

- `appointment_changes.py:86-87` (`if starts_at == appointment.starts_at: return Success(appointment)`).
  Stated in one sentence at a glance: a same-start call returns success before
  `replace_placement`. Confirmed at a glance; no tracing needed.
- `test_appointment_changes.py` (new, 4 tests). Stated at a glance from names and bodies.
  Traced: the "unchanged" test checks start, end, room, version, audit and notification
  counts; the "twice" test uses a different first start so the second call is the real no-op.
- Surface tests (API, FHIR, page). Traced the fixtures, because a wrong literal would make a
  test prove nothing:
  - API: `NEXT_MONDAY` = `STARTS_AT + 7d` = 2030-01-14 10:00Z, same value stored and sent.
  - FHIR: `_later` = `STARTS_AT + 30d` = 2030-02-06 10:00Z, matches the hard-coded `start`.
  - Page: `_booked` = `NOW + 7d 4h` with `NOW` = 2030-01-07 06:00Z, so 2030-01-14 10:00Z, matches the query.
  - The page POST goes through `browser_post` (`browser_support.py:22-28`): CSRF token and `Origin`.
- Traced: `clinician_reschedule.py:103`, `patient_reschedule.py:99`, `admin_appointment_reschedule.py:102`,
  `appointment_actions.py:50`, `fhir_appointment_writes.py:87` all end in `reschedule_appointment`.
  No other writer of `appointment.reschedule` or `SCHEDULE_CHANGED` outside tests.

## 2. Correctness and error handling

- Ordering is right. `_lock_for_change` (record rule, status table, stale version) runs first
  (`appointment_changes.py:80-82`), then the status check (`:84-85`), then the no-op (`:86-87`).
  The comparison runs under the `select_for_update` row lock. A non-owner, a stale version and
  a `CHECKED_IN` appointment keep their answers (tests in `test_appointment_changes.py:84-106`).
- Equality of aware datetimes compares instants, so UTC from the request and the database match.
  A naive `starts_at` compares unequal and falls through to the old path, as before. No new error path.
- No swallowed error. No new exception path.
- See Later L2 for what the no-op skips.

## 3. Authorization, boundaries, sensitive data (§7, §11)

- No new input. `starts_at` is parsed by the existing parsers before the use case, unchanged.
- Authorization stays server-side in `_lock_for_change`. The no-op comes after it.
- No logging, no URL or payload change, no new dependency, no `Any`, `cast`, or bare suppression.
- The one suppression added (`test_fhir_appointment.py:387`) names its code. See Later L1.

## 4. Double booking (§8, spec 5.2)

- The no-op runs before `replace_placement`, so no clinician, room or patient conflict check is
  re-run for a start the appointment already holds. Nothing is written, so no overlap can appear.
- Half-open intervals are not touched.

## 5. Tests (§10.1)

- Expected values come from the spec, not the implementation: §5.6 (status kept, start moved) and §4
  (every write audited, no audit row for a no-op). The audit and notification counts are the
  spec's, not a copy of the code's output.
- Red evidence: the `verify_red` stage output lists the four use-case and surface failures
  that the no-op should cause, and the FHIR test passes before the change as the plan predicted.
  The plan asked for the "one audit row" count of the first use-case test in the run log; the
  transcript shows only the API test's `assert 2 == 1`. Not verified here: see Later L5.
- Guard tests that pass on the old code too (status ordering, other patient, FHIR): intended
  by the plan; they keep the ordering from regressing.
- Assertions that could pass forever: none found. Each asserts a count or a code that the old code
  fails on (except the guards, which assert answers that must not change).
- Missing: a page test for the patient and admin reschedule pages. The use-case test covers them
  because they call the same function, but the item says "on the pages". See Later L6.

## 6. Names and comments (§3, §4)

- Names state behaviour: `returns_unchanged_appointment_and_writes_nothing_when_...`,
  `returns_invalid_transition_and_no_audit_when_...`. Test names follow `returns_X_when_Y`.
- The product change has no comment (plan: "the code states it"). Correct under the litmus test.
- Test docstring `test_appointment_changes.py:1` is one line, under 255 characters.
- Plan name drift: the plan named the other-patient test `returns_not_found_...`; the code asserts
  `FORBIDDEN`. See Later L4.

## 7. Proof trail (§13)

`git show --stat` per commit:

- `084443a` (red): test files only.
- `55c522b` (verify_red): no change.
- `ad23e9f` (green): `appointment_changes.py` +2. The only product line in the branch.
- `f4e2a73` (verify_green), `d33560d` (prove), `1f33997` (refactor), `eab4f6d` (check): no
  file change.

No product or migration line changed after green. No mutation left behind.
Commit messages carry the stage names and the fabro byline (hand-applied gap 1): the orchestrator's
squash message must replace them and disclose tooling in the body.

## 8. Scope and contract

- `drlibre-specs.md`, `doc/backlog/27b-*.md`, models, migrations, templates, `placement.py`,
  `fhir_appointment_writes.py`: not in the diff.
- No dependency added. Contract unchanged: the response shapes are the same (200 / 303 / FHIR 200
  with the stored resource), so the surfaces agree with the FHIR `NoChange` answer.
- The change is the minimum the plan allows.

## Findings

Severity: nit. None is blocking.

### L1 (nit): suppression copies an existing pattern
- `scheduling/views/test_fhir_appointment.py:387` `# type: ignore[attr-defined]`
- Risk: `_put` returns `object` (`test_fhir_appointment.py:351`), so every status assert in the file
  needs the suppression. The new line is a copy. The suppression names its code, so the gate passes.
- Smallest fix: later, type `_put` to return the test client's response type and drop the suppression
  in this file.

### L2 (nit, behaviour): the no-op skips what `replace_placement` did
- `scheduling/use_cases/appointment_changes.py:86-87`
- Risk: a same-start call no longer (a) re-chooses a room when `room_id` is None, which the plan's
  architect note recorded, or (b) re-applies booking rules for the held start (lead time, a start now
  in the past, availability changed since booking). The plan's Risks names (b) only. Nothing is
  written, so no invariant breaks; a same-start call succeeds where it would have been refused.
- Smallest fix: none in this run. Name (a) in the run log next to (b) and in the retro.

### L3 (nit): notification assert not scoped to the appointment
- `scheduling/use_cases/test_appointment_changes.py:68`
  `Notification.objects.filter(kind="SCHEDULE_CHANGED").count() == 0`
- Risk: stricter than needed, not vacuous. It would fail on any other appointment's notice in the DB.
  The surface tests scope by `appointment=`.
- Smallest fix: add `appointment=appointment`.

### L4 (nit): test name drifts from the plan
- `scheduling/use_cases/test_appointment_changes.py:95`
  `returns_forbidden_and_no_audit_when_other_patient_reschedules_to_current_start`
- Risk: none; the name matches the assertion (`FORBIDDEN`, line 105). The plan said `not_found`.
- Smallest fix: none; record the change in the plan or the run log.

### L5 (nit, unverified): red count not in the run log
- Plan: "the first use-case test must fail ... with a count of one audit row, and the failure output
  goes into the run log." The verify_red output shows the four failing test names and the API
  `assert 2 == 1`, not the use-case count.
- Risk: the red proof for the use-case test is asserted, not shown. The failing names prove it fails.
- Smallest fix: the orchestrator runs the first use-case test at the red commit `084443a`, where the
  product code is still `main`'s, and reads the audit count before squash.

### L6 (nit): no page test for patient or admin reschedule
- Item 9 says "on the pages". Only the clinician page has a surface test
  (`test_clinician_qa_round_two.py:306`). The patient and admin pages call the same function and are
  covered by the use-case test, not by their own POST.
- Smallest fix: one test each in `patient_reschedule` and `admin_appointment_reschedule` test files,
  same shape as line 306, POST via `browser_post`.

### L7 (nit, process): no ADR for a decision the spec leaves open
- The refusal-or-quiet-success choice is the owner's decision (`## For the owner`). CLAUDE.md asks
  for an ADR. None is in the diff. The plan records the decision.
- Smallest fix: the orchestrator writes `doc/adr/NNNN-reschedule-same-start.md`, or records the
  owner's ruling there.

### L8 (nit, known): mutation gate does not reach the use case
- `make mutate` covers `scheduling/domain` only (CLAUDE.md "Fabro gotchas", hand-applied gap 3).
  The change sits in `appointment_changes.py`. The tests above are the only guard.
- Smallest fix: none in this run; known.

## For the owner

1. Choice: a reschedule to the current start is a **quiet success** (200, 303, FHIR 200 with the
   stored resource), not a refusal. The spec (5.6, section 4) allows either, and the backlog asked
   the plan to say which and why. Reason in the plan: FHIR already answers `NoChange`; a refusal on
   the other surfaces would split the four answers; `invalid_transition` would misstate the case.
   If you prefer a refusal, the plan says the change is cheap.
2. Copy: the pages still show "Rescheduled" after a no-op, and the appointment history gets no row.
   The copy and any "nothing changed" notice need your decision. Not done here.
3. Booking rules: a same-start call no longer re-checks booking rules for the held start (L2).
   Confirm that is acceptable, or ask for a rule check before the no-op.

## Blocking

None.

## Later

- L1 suppression in `test_fhir_appointment.py:387`, copied from its file (nit).
- L2 no-op skips room re-pick and booking rules for the held start; name in run log and retro.
- L3 scope `Notification` assert in `test_appointment_changes.py:68` to the appointment.
- L4 plan name `returns_not_found_...` vs code `FORBIDDEN`; record the drift.
- L5 red count for the first use-case test not in the transcript; orchestrator confirms.
- L6 page tests missing for patient and admin reschedule.
- L7 ADR for the quiet-success choice.
- L8 mutation gate does not cover the use case (known).
- Commit messages carry fabro bylines: squash with hand-written message (hand-applied gap 1).

## Left for the orchestrator

From the plan's "Not in this run":
- Items 1 to 8 and 10 of `doc/backlog/27b-qa-round-3-pages.md`.
- A "nothing changed" notice on the pages. Needs an owner decision on copy (For the owner, item 2).

From the slice, not finished in this run: none. Item 9 is done for the API, FHIR and the clinician
page. The patient and admin pages are covered only by the use-case test (L6).
