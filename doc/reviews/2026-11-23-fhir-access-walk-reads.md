# Review: task 26b3 item 3, /fhir reads and searches walk

Branch `fabro/run/01M847628PQDNXN7FQS4JTJDRE`, base `main`. Diff: `test_support/fhir_access_rows.py`
(+44 lines), three new test modules under `scheduling/views/` (`test_fhir_access_world.py`,
`test_fhir_access_requests.py`, `test_fhir_access_walk.py`), and the plan. No product file, no
migration, no `drlibre-specs.md` change.

## Verdict

approve. No blocker: no hard rule broken, no product line changed after `write`, no escape hatch,
no swallowed error, no authorization read from a payload. Findings below are Later.

## Plan, block by block (§2.5)

- Rows file: adds `Caller`, `answer_for`, `KnownDifference`, `KNOWN_DIFFERENCES`. Confirmed at a
  glance. The Slot search row was not corrected as the plan's decision 1 said (see Later 2).
- World: builds two clinicians, an admin, two patients, direct bookings, one waitlist booking per
  patient, one notification per patient, two audit entries, and the free slot id. Confirmed at a
  glance; traced `_build_world` (`test_fhir_access_world.py:107-137`) to the builders it calls.
- Requests: maps each walked row to a path and sends it through the caller's client. Confirmed at
  a glance (`test_fhir_access_requests.py:14-51`).
- Walk: three tests, each a loop over the rows and callers. Traced `_expected` and `_walk_mismatches`
  (`test_fhir_access_walk.py:42-62`): a listed pair is held to its product answer, an unlisted pair
  to its row cell. Traced `_other_user_mismatches` (`:65-77`).

Request count: 14 types x 2 walked rows = 28 rows, x 4 callers = 112, plus 5 personal types x 4
callers = 20 other-user requests. Total 132, 33 per caller. Matches the plan.

## Checked in the order of the brief

1. Plans per block: above.
2. Correctness and errors: `_send` (`test_fhir_access_requests.py:50-51`) returns the response
   unchanged; no exception is caught. `_difference_problems` (`test_fhir_access_walk.py:80-90`)
   checks that each listed pair's row cell matches and its product answer differs. Correct.
3. Authorization: the walk sends real bearer tokens made by `token_of` (`fhir_test_support.py:25`,
   which calls `issue_token`). Clients come from `client_for` with `enforce_csrf_checks=True`
   (`fhir_test_support.py:30-33`). No role or user set in the test to get an answer. Correct.
4. Double booking: the world's bookings are on different clinicians or times (`_booking`,
   `_waitlist_booking`, `test_fhir_access_world.py:52-83`). The free slot id is an hour after the
   booked one (`:26`, `:135`). Not a booking path under test.
5. Tests: the expectations come from the row table, which is the spec-derived data, and the
   product's answer is held only for listed pairs. Assertions are not vacuous: `_walk_mismatches`
   and `_other_user_mismatches` return lists that the tests compare with `[]`. Ran the walk and
   table modules on this sandbox: 6 passed (see Not run). Mutation of a row cell was not repeated in
   this stage (the reviewer does not edit source); the prove stage recorded it.
6. Names and comments: names state roles. One comment is wrong (Later 1). One test name does not
   state what it returns (Later 4).
7. Proof trace: `git log --oneline` names each stage. `9b1f4c1 write` holds every test change.
   `52c0d19 check` and `fb479d4 prove` have no file changes (`git show --stat` empty). No product or
   migration line changed after write. Clean.
8. Scope: no dependency, no generator, no change to `test_fhir_access_table.py`, no write rows.
   The Caller and KnownDifference shapes are a copy of the API walk's (Later 3).

## Findings

### Blocking

None.

### Later

1. **Wrong comment.** `scheduling/views/test_fhir_access_walk.py:30`: "Admin reads every record."
   The row says admin gets 403 on another user's Communication (`test_support/fhir_access_rows.py:142`),
   and the walk expects that row answer. Smallest fix: "Admin gets its row's answer."
2. **Plan and build disagree on Slot search.** The plan (decision 1) said the Slot search row
   becomes 400. The build kept 200 (`test_support/fhir_access_rows.py:109`) and lists four
   `KNOWN_DIFFERENCES` entries (`:154-157`). The goal's rule ("keep the row, add the pair") supports
   the build, so no fix to the code. Fix the plan's decision 1 text, or accept the build's reading.
3. **Duplicated shapes.** `Caller` (`test_support/fhir_access_rows.py:11-16`) is the same StrEnum as
   `scheduling/views/test_api_access_rows.py:11-15`. `KnownDifference` (`fhir_access_rows.py:33-45`)
   repeats `test_api_access_rows.py:39`. Smallest fix: import `Caller` from
   `test_api_access_rows` (or move both to `test_support/`). Not blocking: two identical enums do
   not change an answer.
4. **Test name.** `test_fhir_access_walk.py:111`:
   `returns_no_problem_when_each_listed_difference_differs_from_its_row` does not state the returned
   value. Smallest fix: `returns_no_problems_when_...`. Two test names also differ from the plan's
   "Behaviour names" (`returns_401_or_403_when_...`, `returns_the_row_cell_and_...`); the build's
   names at `test_fhir_access_walk.py:93-111` are fine, the plan text is stale.
5. **Narrower than the goal.** The goal says another user's record answers 403 or 404 for a token.
   `OTHER_USER_REFUSALS` (`test_fhir_access_walk.py:31`) pins exactly 401 and 403. The product
   answers 403 and spec 12.3 says "forbidden", so the pin matches the spec. Keep, but say in the
   plan that the 404 option is not accepted by this test.
6. **Status only.** The other-user loop (`test_fhir_access_walk.py:65-77`) checks the status, not
   the body. A 403 that carried the other user's name would pass. Smallest fix: in that loop, assert
   the other record's id and name are absent from `response.content` when the status is not 200.
7. **Private imports across modules.** `test_fhir_access_walk.py:13-16` imports `_path_of`,
   `_send`, `_build_world`, names with a leading underscore. Smallest fix: drop the underscore on
   those three names in `test_fhir_access_requests.py` and `test_fhir_access_world.py`.
8. **Four arguments.** `_booking` (`test_fhir_access_world.py:52-54`) takes four arguments, above
   the ~3 rule. Nit: it reads fine; leave it or pass the type and clinician as one value.
9. **Plan wording.** The plan (`doc/plans/2026-11-23-fhir-access-walk-reads.md:43`) says "600 per
   address and user". The rule is per address only (`scheduling/domain/rate_limit_rules.py:39`).
   Fix the plan text.
10. **Time, measured here.** The walk and table modules ran in 1.95 s on this sandbox (6 tests, 132
    walk requests included). The sandbox is shared, so the orchestrator measures on a quiet machine.
11. **Commit messages.** The commits are fabro checkpoints (`fabro(01M8...): <stage>`) with no
    attribution trailer. The squash to `main` must use a hand-written message and disclose tooling
    (CLAUDE.md, hand-applied gap 1). Not a review finding; the orchestrator's step.

## For the owner

Three pairs where the product answers differently from the row. The walk holds the product's
answer; each is a decision for the owner, not a code fix.

1. **Slot search without parameters.** Row says 200 for all four callers
   (`test_support/fhir_access_rows.py:109`). Product answers 400 (`scheduling/use_cases/fhir_slot_reads.py:112-114`).
   Spec 15.5: a start range of at most 31 days "is required". The product matches the spec's text.
   Owner: confirm the row becomes 400 for every caller. Listed as four entries in `KNOWN_DIFFERENCES`
   (`fhir_access_rows.py:154-157`).
2. **Communication search for clinician and admin.** Row says 403 (`fhir_access_rows.py:144`).
   Product answers 200 with an empty bundle (`scheduling/use_cases/fhir_communication_reads.py:38-41`):
   the search runs over the caller's own notifications, and a clinician or admin has none. Spec 15.4
   says the recipient only. Owner: a 403 or an empty 200 for a caller who is not the recipient?
   Listed at `fhir_access_rows.py:158-159`.
3. **AppointmentResponse search for clinician.** Row says 403 (`fhir_access_rows.py:125-132`).
   Product answers 200 with an empty bundle (`scheduling/use_cases/fhir_response_reads.py:70`,
   `booked.none()`). ADR 0007 says a clinician's search is an empty set; the row cites ADR 0007
   too. One ADR, two readings. Owner: which reading holds? Listed at `fhir_access_rows.py:160`.

## Left for the orchestrator

Copied from the plan's `## Not in this run`:

- Writes (create, update, delete) of every `/fhir` type: the next run, item 3 for writes.
- Item 4: the access section of `doc/security-review.md`, the Makefile generator and the drift test.
- Admin-specific records (an appointment or a patient only admin sees): not needed.

Finished in the slice, not in the plan's list: the Slot search row is held at 200 with four listed
differences, not corrected to 400 (Later 2; the plan's decision 1 is not what was built).

## Not run

- Full `make test`, `make lint`, `make gate`, `make mutate`, `make fhir-validate`: not part of
  this stage; the check stage recorded `make lint && make test && make gate` as passing (5410 tests).
- Mutation of a row cell to prove the walk fails: the reviewer does not edit source. Trusted from
  the prove stage, not re-run here.
- `make setup`: reused the existing sandbox PostgreSQL.
