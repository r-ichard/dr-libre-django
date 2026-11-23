# Review: lead time in offered slots (visitors and patients)

Reviewer: second reader, diff `main...HEAD` on `fabro/run/01M846BCNCCGD00AF9S67A8R0P`
(HEAD `ce09936`, after `check`; the last `review` run was at `db2097e`, `address` at `4144ed5`).
Plan: `doc/plans/2026-11-23-lead-time-in-offered-slots.md` (slice: items 1 to 3).
Verdict: **revise**. One blocker: the `prove` commit `a2034c0` changed a product line. The
final tree is clean; the blocker is in the run's history, not in the code that merges.

Diff stat `main...HEAD`: 12 files, 458 insertions, 6 deletions. Product code: `booking_rules.py`
(+5), `search_matching.py` (import swap), `free_slots_query.py` (net +1). Tests: 6 files, additions
only. Plan and review docs. `drlibre-specs.md` not touched.

## Plan per changed block (§2.5)

- `scheduling/domain/booking_rules.py:91-93` `earliest_offered_start`: `now + LEAD_TIME` for
  online callers, `now` otherwise. Read at a glance. Pure: no I/O, no clock.
- `scheduling/use_cases/free_slots_query.py:51-55`: `load_schedules` keeps the plain `now`;
  the lower bound comes from `earliest_offered_start(now, online_only)` and goes to
  `free_slots_by_start` as its `now` parameter. Read at a glance. Traced `free_slots_by_start`
  (`slot_search.py:39-43`) and `free_slots` (`free_slots.py:70`): `now` is used only as
  `start < now`, a start filter. The new value changes which starts are offered and nothing else.
- `scheduling/domain/search_matching.py:8`: duplicate `LEAD_TIME` removed, imported from
  `booking_rules`. Read at a glance. No import cycle: `booking_rules` imports only
  `appointment_status` and `vocabulary`.
- Callers traced: `online_only` is `online_only_for(user)` at `booking_times.py:40`,
  `detail_pages.py:43`, `booking_details.py:52`, `slots.py:46`, `fhir_slot_reads.py:115,149`;
  `patient_reschedule.py:54` passes `True`; `admin_appointment_book.py:148`,
  `admin_appointment_reschedule.py:50`, `clinician_reschedule.py:47` and `clinician_agenda.py:71`
  pass `False`. Staff paths keep `now`.
- Tests: read each against the plan's expected values (06:00 UTC now; 08:00 Berlin = 07:00 UTC
  rule start, 30 minute steps). Traced the FHIR helpers (`test_fhir_slots.py` `_search`, `get`) to
  the anonymous default. The diff adds tests only; no existing test was edited.
- Did not run the suite in this stage: `check` `ce09936` is the run record on this tree.
  Did not run `make mutate` or `make fhir-validate` (orchestrator's last gates).

## Findings

### 1. Product line changed in the prove commit (blocker, §12 item 7)
- Commit `a2034c0` (stage `prove`, after `verify_green` `0410845`) changes
  `scheduling/use_cases/free_slots_query.py:52` from `now + LEAD_TIME if online_only else now` to
  `now + LEAD_TIME - timedelta(minutes=30) if online_only else now`. A product line changed in
  a stage that may only touch tests: a mutation left behind.
- Final tree is clean. `refactor` `30b13c0` replaces the line with
  `earliest_offered_start(now, online_only)` (`free_slots_query.py:52`). `git diff 30b13c0 HEAD -- scheduling/`
  changes only `scheduling/domain/test_booking_rules.py`. `grep timedelta(minutes=30)` on
  `free_slots_query.py` is empty. `check` `ce09936` and `0d2b2b6` are empty commits.
- Risk: the history shows `prove` ran against a mutant, so the proof record for this stage is not
  clean. No risk to the tree that will merge.
- Smallest fix: no code change in this stage (the reviewer does not edit source). The orchestrator
  picks one: (a) re-run `prove` from `verify_green` `0410845` on a clean branch so no product
  line changes in that stage; or (b) squash from the final tree and say in the commit body that
  `prove` edited `free_slots_query.py` and `refactor` `30b13c0` reverted it. Either way the squash
  diff for `scheduling/` must be empty against `30b13c0`.
- The earlier `address` stage recorded the same finding as not fixed. Nothing in the tree is red
  for it. The history fix is the orchestrator's.

### 2. Test name differs from the plan (later)
- Plan: `returns_not_found_when_reading_a_slot_inside_lead_time`. Code:
  `scheduling/views/test_fhir_slots.py:209` `returns_404_when_anonymous_caller_reads_a_slot_inside_lead_time`.
  Present and red at `verify_red` (200 vs 404). Name difference only.

### 3. Parameter `now` carries a different value (later)
- `scheduling/domain/slot_search.py:43` (`free_slots_by_start`, parameter `now`) now receives the
  earliest offerable start for visitors and patients, not the current time. §3: names state roles.
- Smallest fix: rename the parameter to `earliest_start` in `slot_search.py` and the call site
  `scheduling/use_cases/free_slots_query.py:53`. Mechanical. Not in this run.

### 4. The lead-time bound is written twice (later)
- `scheduling/domain/search_matching.py:46` `search_range` still computes `now + LEAD_TIME` on its
  own. `earliest_offered_start` (`booking_rules.py:91-93`) is the second place that says the same
  for lists. The constant is single; the rule is written in two expressions.
- Smallest fix: `search_range` calls `earliest_offered_start(now, True)`. Behaviour unchanged.
  Later, with finding 3.

### 5. Duplicate test constant and comment (later)
- The same `LEAD_TIME_RULE` constant and its three-line comment appear six times:
  `scheduling/use_cases/test_free_slots_query.py:24`, `scheduling/views/test_slots_online_only.py:21`,
  `scheduling/views/test_fhir_slots.py:17`, `scheduling/views/pages/test_booking_times_page.py:19`,
  `scheduling/views/pages/test_detail_pages.py:39`, `scheduling/views/pages/test_patient_appointments_page.py:20`.
- Smallest fix: one shared constant in the existing booking test support module, imported by each
  file. Not blocking.

### 6. Visitor-visible change on the booking details GET (later, intended)
- `scheduling/views/pages/booking_details.py:52` `slot_is_offered` now uses the filtered list. A
  visitor holding a lead-time slot sees the existing "slot taken" page instead of the lead-time
  text. Intended by spec 6.2 (`drlibre-specs.md:313`); the plan says so. No test in the diff covers
  this path.
- Smallest fix: one test asserting the conflict page for a lead-time start on the booking details
  GET. Later.

### 7. Staff `_first_free_start` keeps its own lower bound (later, noted)
- `scheduling/use_cases/booking_page_data.py:156` `_first_free_start` still starts at
  `now + LEAD_TIME` for staff too (`booking_times.py:40`, `detail_pages.py:43` pass
  `online_only_for(self.user)`). For staff that is the only lead-time bound they get, because
  `find_free_slots` does not filter for them. Unchanged by this run. Do not remove it in the planned
  cleanup without a staff-side decision.

### 8. Existing type-ignore in the file this run touched (later, pre-existing)
- `scheduling/views/test_fhir_slots.py:30` `_search` takes `clinic: object` and reads
  `clinic.appointment_type` under `# type: ignore[attr-defined]`. Named code, so the gate accepts it.
  The line is on `main` (`git show main:` line 27). Not this run's doing.
- Smallest fix: type `clinic` as the test-factory return type. Later.

### 9. Commit trailers (later, orchestrator)
- Every run commit carries "Generated with Fabro" and `Fabro-Run:` trailers. The squash needs a
  hand-written message that discloses tooling (CLAUDE.md hand-applied gap 1). No
  `Co-Authored-By: Fabro` may reach `main`.

### 10. Checked and unchanged
- Double booking: `placement_checks.find_conflicts` and the appointment loading in `load_schedules`
  are not in the diff. Hold path: `create_hold` still uses `probe_placement`, so
  `lead_time_too_short` still refuses a lead-time hold (`booking_rules.py:61`, `_too_soon` at `:100-101`).
- Authorization: `online_only` is derived from the session or bearer token through
  `online_only_for` (`schedule_loading.py:92`); the diff touches no view, route, serializer or form.
- Audit: no write added; no audit entry needed.
- Boundary: 08:00 (exactly 120 minutes) is offered by `earliest_offered_start` (`>=`) and accepted
  by `_too_soon` (`< LEAD_TIME` refuses). The list and the refusal agree.
- Logs, URLs, schemas: no new field, route, log line or dependency.
- Type escape hatches, function size, file size: none added by this diff.
- Gates: `check` `ce09936` passed `make lint`, `make test` (5414 passed on the `check` run recorded
  in the run log), `make gate`. The `red` stage recorded 8 failures on the old tree, one per planned
  red test; `red` and `verify_red` cover the 404 read test.
- Domain test `returns_earliest_start_120_minutes_ahead_when_caller_is_online_only` and its staff
  twin were added in `b78fcb8` after the implementation existed. They were never seen red. They pin
  a one-line function; `make mutate` on `scheduling/domain` is the orchestrator's check that they
  kill `+`/`-` and branch mutants.
- Not measured here: `make test` duration. The orchestrator measures it on a quiet machine.

## Blocking

1. Product mutation in the `prove` commit `a2034c0` (`scheduling/use_cases/free_slots_query.py:52` at
   that commit) against §12 item 7. The final tree is clean: `refactor` `30b13c0` replaced the line.
   Fix: finding 1. Orchestrator chooses the history fix; no code change is possible in this stage.

## Later

- Finding 2: test name differs from plan (`test_fhir_slots.py:209`).
- Finding 3: rename `now` to `earliest_start` in `slot_search.py:43` and its call site.
- Finding 4: `search_range` (`search_matching.py:46`) should use `earliest_offered_start`.
- Finding 5: one shared `LEAD_TIME_RULE` constant instead of six copies.
- Finding 6: a test for the booking details conflict page on a lead-time start.
- Finding 7: `_first_free_start` lower bound for staff, leave until a staff-side decision.
- Finding 8: `_search` `clinic: object` and the `# type: ignore[attr-defined]` at `test_fhir_slots.py:30`.
- Finding 9: squash message discloses tooling, no Fabro trailers.
- Not measured here: `make test` duration. The orchestrator measures it on a quiet machine.
- `make mutate` and `make fhir-validate` are the orchestrator's last gates; not run by this stage.

## Left for the orchestrator

- Plan "Not in this run": `_first_free_start` (`booking_page_data.py:156`) cleanup. Do not remove
  the `now + LEAD_TIME` there for staff without a staff-side decision.
- Plan "Not doing": no change to `search_range`, staff pages, templates, specs, ADRs.
- Items 1 to 3 of the slice: implemented (`booking_rules.py:91`, `free_slots_query.py:52`,
  `search_matching.py:8`). Nothing unfinished in the slice.
- Blocker 1: choose the history fix (finding 1).
- The plan's "For the owner: None" conflicts with its own architect review item 3; the owner
  question below is the one to raise.

## For the owner

- Spec tension (architect review item 3 in the plan): spec 5.1 (`drlibre-specs.md:159-175`) defines
  free slots with no lead time; only past starts are dropped. The lead-time filter on visitor and
  patient lists rests on 6.2 (`drlibre-specs.md:313`: "Slots shown are exactly the slots booking
  would accept") and 5.3 (`drlibre-specs.md:201`, patients). After this change, `/api/v1/slots` and
  `/fhir/Slot` return fewer starts than 5.1's literal definition for visitors and patients. The
  reading is sound and matches the finding. Owner to confirm that 6.2 governs the API and FHIR lists,
  not only the pages. No ADR written; no spec change.
