# Review: module docstrings say what the module is for (task 26c item 14, first part)

Date: 2026-11-23. Reviewer: second reader (§12, §13.3). Process: `tests-and-docs` (no behaviour change, no red gate, 27a3). Base: local `main`. Branch: `fabro/run/01M83XDEES0J96C4ZPPYAKB6SK`.

## Scope read

`git diff main...HEAD --stat`: 115 files. One is the plan `doc/plans/2026-11-23-module-docstrings-purpose.md`. The other 114 are product modules under `scheduling/` (domain, use_cases, views, views/fhir, views/pages, jobs). Nothing under `drlibre/`, no test file, no `conftest.py`, no migration, no probe view, no `drlibre-specs.md`, no backlog, no handover, no dependency file.

Each changed hunk is one line (`@@ -1 +1 @@`, 114 hunks, all at line 1). The line count is 114 insertions and 114 deletions, one per file.

## Plan and block, one sentence each (§2.5)

Every changed block is line 1 of a module docstring. Its plan is: replace the `Task NN[a-z], spec/sections ...:` prefix with a purpose phrase, keep the spec citation as `spec N.N`, and leave the rest of the line and every later line alone.

- Confirmed at a glance: 46 of 114 openers close on the same line (`"""...."""`). Each reads as a clean noun phrase, and the removed `Task`/item/point/issue/ADR tokens are gone.
- Traced (§2.3): the 68 openers that run on into line 2 (e.g. `scheduling/domain/fhir_appointment.py:1`, `scheduling/use_cases/fhir_reads.py:1`, `scheduling/domain/fhir_slot_id.py:1`). Each was read with its second line. None produces a broken sentence. The line-1 text leads into line 2 in every case.

## Checks run by the reviewer

1. Residual task tokens: `grep -rln '^"""Task [0-9]'` over `scheduling/` excluding tests, conftest and migrations prints 0 files. Line 1 of every changed file contains no `Task`, `#`, `ADR`, `item` or `issue`.
2. Length: longest new line 1 is 99 characters. None over `line-length = 100`.
3. Spec citations: a script compared line 1 before and after. No docstring gained a `spec` reference it did not have before, and none lost one it had. The `section` to `spec` rewrites were read line by line in the 114-line list.
4. `ruff check` on the 114 changed files: `All checks passed!`.
5. `scripts/comment_cap.py --files` on the changed files: exit 0.
6. No runtime reader of module docstrings: `grep __doc__` finds only `scripts/comment_cap.py:32` (its own usage text). No test or gate matches the `Task` prefix.
7. Commits (§13.4 proof trace): `8e833a9 start`, `57784fe setup`, `fac0992 understand`, `31b1806 plan_review`, `64e1730 plan_gate`, `21b6e0b write` (the only commit that changes product code: 114 files, one line each), `819535e check` (no product line change), `c0d578d prove` (no product line change). The commits after `write` touch no product line, so nothing was left behind by proof.
8. Gates from the `check` stage, as recorded: `make lint` and `make test` (5263 passed), `make gate` (comment cap, escape hatches clean). I did not re-run the full `make test` or `make mutate`; the test suite does not depend on docstrings (see 6), and the `check` stage ran after the only product change.

## Findings

No finding is a blocker.

### Later

- `scheduling/domain/fhir_appointment.py:1`. The new line 1 is `The FHIR \`Appointment\` for three origins, spec 15.3:`. It drops the phrase "one resource type", so a reader cannot tell that one type covers the three origins. Smallest fix: `One FHIR \`Appointment\` type for three origins, spec 15.3:`. Nit.
- `scheduling/views/fhir/samples_staff.py:1`, `scheduling/use_cases/fhir_loading.py:1` and similar: the new lines are accurate and short. No change needed. Recorded only so the orchestrator knows I read them.
- Line 2 onward still cites items, issues and sections in places (e.g. `issue #36` and `review of 21` in bodies, and `(section 4)` in `scheduling/domain/fhir_audit_event.py:2`). The plan said later lines stay untouched, and item 14 asks only for line 1. Left as is. A later pass could fix them, but not in this slice.
- Measured on the shared sandbox, not a blocker: the `check` stage's `make test` took 157.05 s for 5263 tests. The orchestrator measures on a quiet machine.

## For the owner

- The four helpers `scheduling/views/fhir_specialty_support.py`, `scheduling/views/fhir_role_support.py`, `scheduling/views/fhir_organisation_support.py` and `scheduling/views/pages/admin_support.py` are test-only in use but live in the product package. The plan includes them, since they are not `test_*` files. If you want them left for the second half of item 14 (moving test-only code out of the product package), those four lines drop out and the count goes from 114 to 110. Their docstrings are changed here and would need changing back or again in that other run.

## Blocking

None.

## Left for the orchestrator

From the plan's `## Not in this run`:

- Item 14, second part: move the test-only probe views (`scheduling/views/probe_views.py`, `probe_urls.py`) out of the product package. Not in this diff.
- Docstrings of `test_*.py` files and `conftest.py` that begin with a task number. Not in this diff.
- `drlibre/test_deployment_checks.py`, `drlibre/test_startup_checks.py`, `drlibre/test_warnings_fail.py`. Not in this diff.
- Item 15 onward of `doc/backlog/26c-gates-that-hold.md`. Not in this diff.

Slice completed in this run: item 14, first part, all 114 files. Re-running the plan's grep returns 0 product files. Backlog item 14 stays open for the second part; the orchestrator ticks only the first part.

## Verdict

`approve`. No blocker. The diff is one line per file, changes nothing but line 1 of 114 docstrings, and the stage gates passed on the commit that made the change.
