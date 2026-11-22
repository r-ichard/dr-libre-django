# Review: task 24b2, FHIR specialty list writes

Diff `main...HEAD`: 18 files. Product commits after `verify_green` (`3fa0d03` prove, `d83b330` refactor, `3455579` check): prove changed tests only; refactor and check are post-proof cleanup, no mutation left behind in prove.

## Plan in one sentence per block (confirmed at a glance / traced)
- `use_cases/fhir_specialty_writes.py`: advisory lock, compare `If-Match`, diff, apply through console use cases, roll back on first refusal. Traced: `set_rollback(True)` after a refused inner `Result` is what makes "neither" hold (`:55-57`). Correct.
- `domain/fhir_specialty_write.py`: pure parse and diff. Glance.
- `views/fhir/writes.py:65-81`: CodeSystem branch before UUID parsing; id other than `specialty` is 404. Glance.
- `fhir_loading.py:140-150`: admin reads include inactive concepts so GET then PUT does not delete them. Traced.

## Findings
1. **Blocker, `doc/adr/0008-*.md` (not in the diff).** Task item 1 requires ADR 0008 to say which resource is written, what the body carries, how a concept is matched, how inactive is said in R4, and what ValueSet answers; the plan (files item 9) promised it; the architect asked for the shared-ETag/different-body note and the no-`If-Match` removal note. The ADR has no section. Fix: add the section "The specialty list" with the plan's decisions and fix the status line.
2. Important (Later), `scheduling/views/test_hostile_input.py`: plan item 8 promised `PUT /fhir/CodeSystem/specialty` bodies; file unchanged. The generic route-enumeration tests cover the route only with generic ids and bodies. Fix: add a case with an admin token and hostile concept lists.
3. Nit, `fhir_specialty_writes.py:27-28`: advisory lock key differs from the plan's `FOR UPDATE` on the revision row. Console writes do not take the advisory lock, so console and FHIR writes serialize only through the trigger's revision-row lock; the `If-Match` read is under the advisory lock, not the row lock. The race test passes for two FHIR writers. Fix: lock the revision row (`SELECT ... FOR UPDATE`) as planned.
4. Nit, `fhir_specialty_writes.py:27`: `LIST_LOCK_KEY` magic number unexplained beyond the name; add a why-comment.

## Checks
- Authorization from token user (`admin_of`), 403 before body read, 401 by existing token layer; console use cases re-check. Good.
- Audit: written by console use cases inside the same transaction. Good.
- Escape hatches: only `# noqa: S101` naming a code, in test support. No `Any`/`cast`. Sizes fine.
- No dependency, migration or Makefile change.
- Tests derive from spec: behaviours with values, 409 applies nothing, atomic rollback, 412, race, CapabilityStatement.
- Not run here: `make mutate`, `make fhir-validate` (stage output shows lint, test, gate passed).

## Second read (after `address`)
Finding 1 (ADR section) is fixed: `doc/adr/0008-*.md` now has "The specialty list (task 24b2)" covering resource, body, match, inactive, ValueSet answer. `address` touched docs only.
Finding 2 stands, and the task names it: item 6 says "the hostile-input test". `scheduling/views/test_hostile_input.py:370-420` (`returns_outcome_and_no_500_when_fhir_gets_hostile_write_bodies`) has no `PUT /fhir/CodeSystem/specialty` path, and `test_fhir_specialty_writes.py` has no hostile body case (grep for hostile/nested/oversize: none). A promised test is missing, so it is a blocker. Smallest fix: add `("put", "/fhir/CodeSystem/specialty")` to `paths` with an admin token, extend `FHIR_WRITE_BODIES` with concept lists (non-dict concept, 100k-char code and display, `property` of wrong shape, duplicate codes differing in case, `count` mismatch), and add `"CodeSystem"` to the allowed `resourceType` set.

## Left for the orchestrator
Plan "Not in this run": tasks 24c (Practitioner writes) and 24d stay in the backlog. Unfinished slice item: hostile-input bodies for the specialty PUT. Run `make mutate` and `make fhir-validate` (not run here).

## Blocking
- Hostile-input test for `PUT /fhir/CodeSystem/specialty` missing (task item 6, plan item 8). **fixed**: `returns_outcome_and_no_500_when_fhir_gets_hostile_write_bodies` now covers the path with seven concept bodies for every actor. The route answered no 500 already, so the test was green on arrival; reachability checked (admin gets 400 per body, not 404).

## Later
- Lock the revision row as planned, or keep the advisory lock and say why it suffices (console writes do not take it).
- Comment on `LIST_LOCK_KEY` (`fhir_specialty_writes.py:29`).
- Measured test time: not measured here (budget never blocks).

## Third read (after second `address`)
Commits after `verify_green` up to `prove` (`3fa0d03`) touch test files only; no product or migration line left behind. `address` (`6ed59c0`) changed `fhir_resources.py`, `fhir_specialty_writes.py`, `writes.py` (import moved to the specialty use case) and the hostile-input test: the previously blocking test is present (`scheduling/views/test_hostile_input.py:356-367, 399, 420`), covering admin and other actors. ADR 0008 section "The specialty list (task 24b2)" covers all five points of item 1. No blocker found: authorization from token user before body read, one transaction, rollback on first refusal, audit through console use cases, no escape hatches.
Not run here: `make mutate`, `make fhir-validate`.

## Blocking
None.

## Later
- Advisory lock (`fhir_specialty_writes.py:27,47`) is not taken by console writes; FHIR-vs-console races serialize only through the revision-row trigger lock. Lock the revision row as planned or say why it suffices.
- Why-comment on `LIST_LOCK_KEY`.
- Measured test time: 4232 tests in 35s in this sandbox (never a blocker).
