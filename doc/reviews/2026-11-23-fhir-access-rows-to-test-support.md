# Review: FHIR access rows move to test_support

Second reader, run `fabro/run/01M844FXBASAYME5642ZFX9YWB`. Diff reviewed: `b147a2e..HEAD`
(the run's base; the sandbox has no local `main`, and `b147a2e` is the exit commit of the
`task/26b3-fhir-table` run that the plan builds on). Plan: `doc/plans/2026-11-23-fhir-access-rows-to-test-support.md`
(slice: whole task, no `## Not in this run` items).

## Diff

| Path | Change |
|---|---|
| `scheduling/views/test_fhir_access_table.py:7` | import changed to `from test_support.fhir_access_rows import FHIR_ACCESS_ROWS` |
| `scheduling/views/fhir_access_rows.py` to `test_support/fhir_access_rows.py` | rename, 100% similarity (`cmp` against `b147a2e` identical, 121 lines) |
| `doc/plans/2026-11-23-fhir-access-rows-to-test-support.md` | plan, 119 lines |

No product code, migration, dependency, settings, Makefile or specification change.
`drlibre-specs.md` is not in the diff.

## Checks, in the order of the review card

1. **Plans of the changed blocks, one sentence each, without re-reading.** Import redirect:
   the test reads the rows from the new package. File move: same bytes, new package. Both
   confirmed at a glance from the diff. No tracing needed.
2. **Correctness and errors.** No runtime path changes. The rows module is data only; it has
   no I/O, no exception handling and no error path. The three tests in
   `scheduling/views/test_fhir_access_table.py:24-39` are unchanged.
3. **Authorization, boundaries, sensitive data.** Not applicable. No route, use case, form,
   serializer, model or middleware is touched. The table is test data; it holds no request
   input and no stored data.
4. **Double booking.** Not applicable. No booking code is touched.
5. **Tests.** The three tests are unchanged and were written against the declaration
   (`scheduling/domain/fhir_declaration.py`, `FHIR_RESOURCES`). They compare sets and fail on
   a missing, removed or repeated row, so they can fail. The plan's red step (import fails
   until the module moves) is real, but it is not visible in history: the `write` commit
   `c9b1dab` contains both the red and the green change. See Later 2.
6. **Names and comments.** No name changes. The module docstring (`test_support/fhir_access_rows.py:1-4`)
   is four lines, under the 255-character cap. It names the module's role and says it is not
   collected by pytest. The `ADRs 0005 to 0010` reference carried over from the earlier table
   review is still in the file. See Later 1.
7. **Proof left no trace.** Commit list after `verify_green`: `c9b1dab` (write, the rename and
   the import, before check), `8a3d5ed` (check, empty), `28925a1` (prove, empty). `git show --stat`
   on the check and prove commits shows no file changed. Nothing product or migration was
   changed after the green proof.
8. **Scope and contracts.**
   - Only the planned paths changed. The plan lists the stale doc references it leaves in place.
   - No dependency added.
   - `pyproject.toml:58` (`also_copy`) already lists `test_support`, so the mutmut copy keeps working.
   - `Dockerfile:24` copies `.`; `.dockerignore` does not exclude `test_support`, so
     `docker compose exec web make test` sees the moved module.
   - `drlibre/test_product_imports.py:40-50` scans `drlibre` and `scheduling` for `test_support`
     imports. The test file importing `test_support` is excluded by the `test_` prefix, and
     nothing in product code imports the moved module. Guard passes (check stage: 5282 passed).
   - `git grep fhir_access_rows` finds the moved module only at its new path, in the test import,
     and in the two earlier docs (Later 3).

## Gate evidence

From the `check` stage (commit `8a3d5ed`, tree unchanged by `prove` `28925a1`): `make lint`,
`make test` (5282 passed), `make gate` (comment cap, size cap, escape hatches: clean). I did not
re-run the gates in this stage; I read the stage output and the tree.

## Blocking

None.

## Later

1. **nit**: `test_support/fhir_access_rows.py:2`. The docstring says "ADRs 0005 to 0010". The
   earlier review of the table (`doc/reviews/2026-11-23-fhir-access-table.md`, item 1) raised the
   same reference. Fix: check the range against `doc/adr/` and correct it in a separate task. The
   plan put this out of scope.
2. **nit, process**: the red and green steps share commit `c9b1dab`. The red proof (the
   `ModuleNotFoundError` at collection) is in the run's stage output, not in history. This is the
   known hand-applied gap (2) in CLAUDE.md. No fix in this run.
3. **nit, stale references**: the old paths `scheduling/views/fhir_access_rows.py` remain in
   `doc/plans/2026-11-23-fhir-access-table.md` (lines 47, 59, 260) and in
   `doc/reviews/2026-11-23-fhir-access-table.md` (lines 4, 11, 52, 55, 76, 78, 81, 83, 86, 88).
   The plan keeps them as records. The orchestrator should note the move in `doc/handover.md`
   or leave it.
4. **Later, not a defect**: nothing asserts the rows module's location. The guard
   `drlibre/test_product_imports.py` proves only that product code does not import `test_support`.
   A location test would be a new test; the owner can decide whether to add one.
5. **Commit hygiene (orchestrator)**: the run commits carry `⚒️ Generated with [Fabro]` and
   `Fabro-Run` trailers. Per CLAUDE.md gap (1), squash with a hand-written message that discloses
   the tooling. Nothing in this stage changes that.
6. **Measured, not a blocker**: `make test` took 350.95 s on the sandbox during `check`. The
   sandbox is shared, so the orchestrator should measure on a quiet machine.

## For the owner

Nothing. No specification or decision is left open by this change.

## Left for the orchestrator

No slice items. The plan declares the whole task as one slice, so nothing was carved out.
