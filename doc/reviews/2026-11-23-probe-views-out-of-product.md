# Review: probe views out of the product package (task 26c, item 14, second part)

Diff: `git diff main...HEAD`, 11 files, 139 insertions, 7 deletions, plus the plan.
Commits: `write` (f9d2c32) holds the move and the caller edits; `prove` (e0374a1) changes
only `drlibre/test_product_imports.py`. No product or migration line changes after `check`.

## Plan in one sentence per block (§2.5)

- `test_support/__init__.py`: empty package marker. Confirmed at a glance.
- `test_support/probe_views.py`: pure rename (similarity 100%), content unchanged. Confirmed at a glance.
- `test_support/probe_urls.py`: rename, import switched to `test_support`, routes unchanged (96% similar, one import line and one import moved). Confirmed at a glance.
- Five test callers (`conftest.py`, `test_middleware.py`, `test_json_logging.py`, `test_process_output.py`, `test_failure_response.py`): string or import path swapped, assertions untouched. Confirmed by `git diff`.
- `pyproject.toml:58` `also_copy` gains `"test_support"`. Confirmed; needed so mutmut's copy keeps the probe routes importable.
- `drlibre/test_product_imports.py`: AST walk over `drlibre/` and `scheduling/`, skipping `test_*.py` and `conftest.py`. Traced: it parses `ast.Import`/`ast.ImportFrom` names and also string constants equal to or starting with `test_support.`. The string branch is stricter than the plan text (the plan says imports only). Traced, not a defect.

## Checks run by the reviewer

- `make lint`: ruff check, ruff format, mypy `.` strict: clean (694 source files).
- `make gate`: comment cap, size cap, escape hatches: clean.
- `pytest` on `drlibre/test_product_imports.py` plus the four probe-using test files
  (`test_middleware`, `test_json_logging`, `test_failure_response`, `test_process_output`):
  57 passed, run with the `make test` environment (`SECRET_KEY`, `DEMO_PASSWORD=`).
- Not run: full `make test` (the `check` stage ran it on the `write` tree, before the
  `prove` change to the boundary test), `make mutate` (slow; plan allows skipping).
- Not re-run: the red proof (planted `import test_support.probe_urls` in `drlibre/urls.py`).
  Reader reasoning: `ast.Import` alias `test_support.probe_urls` matches
  `_names_support`, so the test would name `drlibre/urls.py:<line>`. The reviewer did not
  edit product files to confirm.

## Findings

Walk in the order of §12 / §13.3.

1. **Trust boundaries (views, API, middleware, forms, serializers, models).** No change to
   any of them. Probe routes are not in `drlibre/urls.py`; `grep` over `drlibre/` and
   `scheduling/` for `probe_urls`/`probe_views` returns only the boundary test and
   `test_*.py`/`conftest.py` callers. Severity: none.
2. **Correctness and error handling.** The moved module imports stay the same names; no
   `except` added or removed. No swallowed error. Severity: none.
3. **Authorization, sensitive data.** Unchanged. The probe views are `AllowAny` test
   fixtures, reachable only under an overridden `ROOT_URLCONF`. Severity: none.
4. **Double booking.** Not touched. Severity: none.
5. **Tests.** Assertions in the moved-caller tests are unchanged. The boundary test's
   assertion (`offenders == []`) is not a pass-forever test: it reads the tree, and it
   would fail on a planted import (reasoned above, not re-run). Severity: none for
   blocking; see Later for the test name.
6. **Names and comments.** `returns_no_product_module_importing_test_support` follows the
   `returns_` prefix but has no `_when_` clause, which CLAUDE.md asks for. Module docstring
   on the new test is one line and states the role. `probe_views.py` docstring unchanged.
   Severity: nit. See Later.
7. **Proof left no trace.** Commits after `verify_green` are `check` (no diff) and
   `prove` (test file only). The `write` commit holds the move and caller edits, which is
   the write stage, before green. Clean. Severity: none.
8. **Scope and dependencies.** Only item 14 second part. No dependency added. `pyproject.toml`
   change is the mutmut `also_copy` line the plan requires. No contract or wire change.
   `drlibre-specs.md` not in the diff. Severity: none.

## Blocking

None.

## Later

- `drlibre/test_product_imports.py:40`: name lacks the `_when_` clause CLAUDE.md asks
  for (`returns_X_when_Y`). Smallest fix: rename to a `returns_..._when_...` form in the
  next test-naming pass. Risk: style only.
- `drlibre/test_product_imports.py:8-30`: the string-constant branch flags any product
  string equal to `test_support` or starting `test_support.`, including docstrings. None
  exists today. Risk: a future docstring that names the package would fail the gate with
  no clear reason. Smallest fix: leave as is, or restrict the string branch to strings
  containing `.` after the package name.
- `drlibre/test_product_imports.py`: the scan covers Python files only. A product template,
  a settings string read from the environment, or `.env.example` naming
  `test_support.probe_urls` would pass. Risk: low; the router is the only consumer of
  `ROOT_URLCONF`. Smallest fix: none now.
- `doc/plans/2026-11-23-probe-views-out-of-product.md:5`: says "a test enforces that
  [product code never imports it]". The test also catches string references, so the plan's
  "imports only" wording (block 7) is out of date. Plan is a throwaway doc; fix in the next
  plan edit.
- `doc/backlog/26c-gates-that-hold.md` line 126 (per plan) still names the old path; the
  orchestrator updates it with the squash, per plan.
- `doc/plans/2026-11-21-audit-writer-security-headers.md:90` and
  `doc/plans/2026-11-21-log-and-error-path-hardening.md:41` name the old
  `scheduling/views/probe_*` path. Historical plans; leave.
- Docker image still ships `test_support/` (plan acknowledges). Not a behaviour change.
- `make mutate` not run by the reviewer. The `also_copy` change is untested by a mutant run;
  the orchestrator should confirm it on a quiet machine (plan says it is required).
- Full `make test` not re-run by the reviewer after the `prove` change. The changed file
  passes; the `check` gate ran on the `write` tree, the only difference being the test
  file. Orchestrator should run `make test` on the squash.

## For the owner

None. No decision the specification leaves open.

## Left for the orchestrator

- Item 14, second part, of `doc/backlog/26c-gates-that-hold.md`: the slice is this run.
  The plan has no `## Not in this run` section; its `What I will not do` list (no rename,
  no backlog or handover edit, no other task 26c item) is respected by the diff.
- Orchestrator to run `make test` and `make mutate` on the squash (see Later).
- Orchestrator to update `doc/backlog.md` and the backlog file line 126 with the squash.
