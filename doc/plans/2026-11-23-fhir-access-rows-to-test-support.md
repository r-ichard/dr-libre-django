# Move FHIR access rows from product to test_support

Slice: whole task (items 1 to 3). No `## Not in this run` items.

## Focal point

`scheduling/views/fhir_access_rows.py` is test data (a frozen dataclass and one tuple of
access rows) inside the product package `scheduling`. Its only importer is
`scheduling/views/test_fhir_access_table.py:7`. Move the module to
`test_support/fhir_access_rows.py` and point that one import at it. Contents do not change.

## Blocks

1. **Test file import** (`scheduling/views/test_fhir_access_table.py:7`): change the import to
   `from test_support.fhir_access_rows import FHIR_ACCESS_ROWS`. This is the red step: the test
   module fails to import until the file exists at the new path.
2. **Module move** (`scheduling/views/fhir_access_rows.py` to `test_support/fhir_access_rows.py`):
   `git mv`, no content edit. This is the green step: the three existing tests pass.
3. **Proof** (no file edited): run the gates, grep for the old module path, confirm the moved
   file is byte-identical to the old one.

## Files, in order

1. `scheduling/views/test_fhir_access_table.py`: line 7 only.
2. `scheduling/views/fhir_access_rows.py` to `test_support/fhir_access_rows.py`: `git mv`, so
   history follows the file. The docstring (`No test_ prefix: pytest must not collect this data
   module.`) stays true in the new package and stays unchanged.

## Files deliberately not touched

- `doc/plans/2026-11-23-fhir-access-table.md` and `doc/reviews/2026-11-23-fhir-access-table.md`:
  both cite `scheduling/views/fhir_access_rows.py` and review line numbers. They are records of a
  past review. Editing them is a second change, so they stay as they are. The old path in them is
  stale after the move; the final message says so.
- `drlibre/test_product_imports.py`: already guards product code from importing `test_support`.
  It checks imports, not file location, so it neither needs nor proves anything for this move.
- `test_support/__init__.py`: nothing to export; the test imports the module by path.
- `pyproject.toml`: the mutmut `also_copy` list (line 58) already includes `test_support`.
- `doc/handover.md`: no mention of the rows module (grep). No state change to record.
- `doc/backlog.md`, `doc/retro.md`: orchestrator's work at merge, not this stage.
- `scheduling/views/fhir_test_support.py`: a product-tree file with a similar name; not
  examined, not in scope.
- Row values, the `FhirAccessRow` class name, `FHIR_ACCESS_ROWS` name, the three test names,
  and the test bodies.

## Invariants and blast radius

- Row data is unchanged: the moved file is byte-identical to the old one (checked with `diff`
  against `git show HEAD:scheduling/views/fhir_access_rows.py`). The 51 rows remain in the same
  order.
- Product behaviour: nothing in product code imports the module (grep: only the test file), so
  no route, use case, audit entry, transaction, or double-booking guard changes.
- Authorization, server-side checks, and the append-only audit log are not touched.
- Blast radius: two paths in the git tree (one rename, one import line). No migration, no
  dependency, no settings change.

## Failing tests first

No new tests. The existing three in `scheduling/views/test_fhir_access_table.py` are the
behaviour under test. Their expected values, from drlibre-specs.md section 15.4 as encoded in the
table:

- `returns_no_interaction_unlisted_when_the_declaration_is_read`: every declared
  (type, interaction) pair has a row, so the unlisted set is empty.
- `returns_no_row_for_a_removed_interaction_when_the_declaration_is_read`: no row names an
  interaction the declaration does not declare, so the removed set is empty.
- `returns_one_row_per_interaction_when_the_table_is_read`: no (resource, interaction) pair
  repeats, so the repeated set is empty.

Red proof: after block 1 and before block 2, `make test` fails at collection with
`ModuleNotFoundError: test_support.fhir_access_rows`. That is the right reason: the module is not
yet at the new path. Green proof: after block 2, the same three tests pass.

What the guard proves: `drlibre/test_product_imports.py` passes before and after. It proves no
product module imports `test_support`. It does not prove the rows file left `scheduling/`. The
location is proved by the `git mv` and by `git grep scheduling/views/fhir_access_rows` returning
nothing outside the two stale docs.

## Trust boundaries

None crossed. Test data only: no request input, no route, no client, no stored data. Nothing to
validate or authorize.

## Domain entities (CLAUDE.md section 3)

No runtime entities. The table's columns name the actors `visitor`, `patient`, `clinician`,
`admin`, matching the vocabulary Visitor, Patient, Clinician, Admin. The `resource` values are
FHIR R4 type names (Organization, Patient, Appointment, ...), not domain entity names.

## What I will not do

- No test that asserts the file's location. That would be a new test, and the task says no other
  change. Listed as a possible follow-up for the owner.
- No edit to the stale path in the plan or review docs.
- No edit to the module docstring, including the reviewer's "ADRs 0005 to 0010" nit.
- No rename of the module, class, tuple, or test functions.
- No abstraction, dependency, or refactor. No commit, push, or merge in this stage.

## Gates for the run

`make lint` (ruff, mypy strict), `make test`, `make gate` (comment cap, size cap: the moved file
is 121 lines, under 300; the import line is well under the 100-column limit). `make mutate` covers
`scheduling/domain` only; not affected. `make fhir-validate` is the scripted last gate and is
run by the orchestrator.

## Architect review

Verdict: approve.

1. Ladder: one `git mv` and one import line. No abstraction, dependency, or refactor. Smallest change in the right layer.
2. Plan knowledge: each block states its purpose in one sentence (import redirect, file move, proof). Vocabulary (Visitor, Patient, Clinician, Admin) matches CLAUDE.md §3.
3. Test-first: the existing three tests are the behaviour under test. The red step is genuine (the import fails at collection until the module moves). The plan names expected values and the reason for each test.
4. Security: not applicable. Test data only, no trust boundary, no request input, no audit path.
5. Architecture: product code does not import the moved module (grep: only `scheduling/views/test_fhir_access_table.py:7`). The moved location is outside the `PRODUCT_ROOTS` of `drlibre/test_product_imports.py`, and `pyproject.toml:58` already copies `test_support` for mutmut.
6. Scope: whole task, one slice. Stale references in `doc/plans/2026-11-23-fhir-access-table.md` and `doc/reviews/2026-11-23-fhir-access-table.md` are named and deliberately left as records. Row count (51) and file length (121 lines) match the checkout.

Notes for the run, not blocking:
- The guard test proves no product import of `test_support`; it does not prove the file left `scheduling/`. The plan already says so and relies on `git mv` plus `git grep`.
- Post-move verification should include `git grep fhir_access_rows` showing only the two stale docs plus the test import.
