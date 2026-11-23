# Task 26c item 14 (last part): task-numbered test docstrings say what they hold

Slice: item 14, last part only (first docstring line of the 194 test and conftest modules under `scheduling/` and `drlibre/` that begin with a task number, plus the gate test). The probe-view move out of the product package stays out of this run.

## Focal point

`doc/backlog/26c-gates-that-hold.md` item 14: "Module docstrings that name a task ("Task 10a: ...") say what the module is for instead."

Measured on this checkout with `.venv/bin/python` (Python 3.13):

- 194 module docstrings match `^"""Task \d` under `scheduling/` and `drlibre/`. All 194 are `test_*.py` or `conftest.py`. 93 continue on further lines.
- `test_support/` does not exist on this branch.
- `drlibre/test_product_imports.py` does not exist on this branch.

Nothing at runtime changes. The only effect is the text people read.

## Blocks

1. **Gate test (new file `drlibre/test_module_docstrings.py`).** One test, `returns_no_task_numbered_module_docstrings_when_modules_are_parsed`. Walk `scheduling/`, `drlibre/` and `test_support/` under the repository root with `rglob("*.py")`, skipping roots that do not exist. Parse each file with `ast.parse(source, filename=str(path))`, no try/except. Read the docstring with `ast.get_docstring(tree, clean=False)`. Fail with the list of offending paths when its first line matches `^Task \d`. A file that does not parse fails the test with its path, as the parser reports it. Written first; on the current tree it must fail with exactly 194 paths (red, proven).
2. **First-line rewrite of the 194 docstrings.** A throwaway script in `scratch/` (not committed), run with `.venv/bin/python`, rewrites line 1 only using the rule below. Lines it cannot make clean are listed and edited by hand.
3. **Verification.** For each file, `ast.dump` of the module with the docstring node removed must equal the original, and every docstring line after the first must equal the original. Then `make lint`, `make test`, `make gate`.

## Files, in order

1. `drlibre/test_module_docstrings.py` (new), beside the other `drlibre/test_*.py`.
2. `scratch/rewrite_docstrings.py` (throwaway). Reads the file list from `git ls-files`, rewrites line 1 only.
3. The 194 files under `scheduling/` and `drlibre/`, first docstring line only. The test's regex finds them.
4. Hand edits for the first lines the script reports: prefixes with words outside the list, QA-round or finding history, `#N` left after the rule. Grep, then edit.

## Rewrite rule

- Drop `Task <id>` and the designators up to the colon: `item`, `items`, `point`, `finding`, `issue`, `slice`, `#N`, `(#N)`, `and`, `to`, commas, the ids.
- `spec N.N` and `section N.N` become `Section N.N` (keep the numbers; `spec 15.1, 15.2` becomes `Sections 15.1 and 15.2`).
- Capitalise the first letter of what remains, unless it is inside backticks.
- Keep the text after the colon as written, except history (QA rounds, finding numbers, "review of N").
- Specification section (owner's request): if the line already names a section, keep it as above. If it names none, add one only when a single heading of `drlibre-specs.md` clearly governs what the file's tests hold, judged from the first line and the test names, and cite it as `Section N` or `Section N.N`. If no heading clearly applies, add none. Each addition is listed in the review (decision 5).
- Target: first line under 90 characters. Hard cap 100 (ruff `line-length = 100`, `pyproject.toml:38`). The rewrite must not add a line over 100.
- Any prefix with a word outside this list (for example `Task 21, code page:`, `Task 20, times:`, `Task 17c: ... QA round 2`) is edited by hand: drop the history, keep what the tests hold.

Examples, before → after:

- `Task 19, sections 3.2 and 10: the clinician profile rules that need no stored data.` → `Sections 3.2 and 10: the clinician profile rules that need no stored data.`
- `Task 18, item 11 and section 12.3: only an admin reaches the admin console.` → `Section 12.3: only an admin reaches the admin console.`
- `Task 22, spec 15.1, 15.2, 15.4: the public FHIR door, read and search, no token.` → `Sections 15.1, 15.2 and 15.4: the public FHIR door, read and search, no token.`
- `Task 27a, finding #33: every whole number has the bounds of its column.` → `Every whole number has the bounds of its column.` (no section named, none added: the bounds rule is in §4 but only if the file's tests say so; check before adding)
- `Task 21, item 15: busy cancelled times are left out in the query, ...` → `Busy cancelled times are left out in the query, ...`
- `Task 17c: the clinician workspace defects of QA round 2, each as a browser meets it.` → `The clinician workspace, each defect as a browser meets it.` (hand edit: the QA round is history)

## Not touched

- Every docstring line after its first, including the continuation lines of the 93 multi-line files. Two of them name a task number in continuation text (`scheduling/views/test_fhir_schedule_writes.py`, `scheduling/views/test_search_limits.py`). The gate reads only line 1; the owner asked for the first line. Reported in the review, not edited.
- Any code, assertion, fixture, import, comment or test body in those files.
- Product modules, including `scheduling/views/probe_views.py` and `scheduling/views/probe_urls.py` (item 14, first part). Their importers `scheduling/views/test_failure_response.py` and `scheduling/views/test_json_logging.py` stay as they are.
- `drlibre-specs.md`, ADRs, `doc/backlog/`, `doc/handover.md`. The backlog entry is closed by the orchestrator after verification.

## Invariants

- No runtime behaviour, schema, route or test result changes except the new test.
- Every test in the 194 files keeps its name and body, proven by the `ast` comparison in block 3.
- `make mutate` covers `scheduling/domain` source only; docstring edits cannot move a mutant count.
- The new test is the only new test. It guards the next file; it is not a product check.

## Trust boundaries and authorization

None crossed. The test reads repository files from the working tree during `pytest`. No input comes from a user, a request or the network.

## Domain entities

None. Test and documentation text only.

## Tests

Red first, then green:

- `returns_no_task_numbered_module_docstrings_when_modules_are_parsed`: on the current tree it fails with the 194 paths in its message. It must fail for the right reason (194 real docstrings), not a parse error or a missing directory. After the rewrite: no offenders. The red output is recorded in the run.

No behaviour tests beyond it. The item is documentation.

## What I will not do

- No new abstraction and no shared helper module for the scan. The test scans inline in one function.
- No rewrite of continuation lines.
- No LLM agent per file. A deterministic script rewrites the lines; hand edits fix what it cannot; the orchestrator reads a sample.
- No edit of `drlibre-specs.md`.
- No creation of `drlibre/test_product_imports.py` (decision 1).

## Decisions for the orchestrator to check

1. **`drlibre/test_product_imports.py` does not exist.** The test goes beside it as `drlibre/test_module_docstrings.py`. If the owner wants it in a file of that exact name, that file is created first; this plan does not create it.
2. **`test_support/` does not exist.** The test scans it when present and skips it when absent, because the owner named it.
3. **Continuation lines kept.** Only line 1 changes, as instructed. Where a kept continuation line no longer reads with a rewritten first line, the file is listed in the review; the rule does not allow an edit there.
4. **"One or two lines".** Applies to line 1 as the owner asked; continuation text stays, so a file can run longer than two lines.
5. **Specification sections added where one applies.** The owner asked for the section where one applies. Lines that already name a section keep it. Lines that name none get a section only when one heading of `drlibre-specs.md` clearly governs the file's tests; the implementer judges this per file and lists every addition and every file left without one in the review. Judgment per file, not a script mapping.
6. **Superseded plan closed.** `doc/plans/2026-11-23-module-docstrings-purpose.md` (item 14 first part, product modules) carried a rule "No section where there was none" that conflicts with decision 5. It is marked superseded for this rule and is not to be run as written. Its product-module scope needs a fresh plan.

## Done when

- `make lint`, `make test`, `make gate` pass in the sandbox on this branch.
- The `ast` comparison finds no change except module docstring first lines in the 194 files.
- The new test fails before the rewrite with 194 offenders and passes after it.
- A sample of 20 rewritten first lines is read by the orchestrator, drawn across single-line and multi-line files. Every hand edit and every added section is listed in the review.

## Not in this run

- Item 14, first part: the test-only probe views leave the product package (`scheduling/views/probe_views.py`, `scheduling/views/probe_urls.py`). Next run.

## Changes from the architect's revise

1. Revise reason 1 (section rule dropped without a decision): the rule now adds a section where one clearly applies, judged per file, and records the judgment as decision 5. The "Do not add a section" rule is removed.
2. Revise reason 2 (conflicting plan): `2026-11-23-module-docstrings-purpose.md` is marked superseded for the section rule (decision 6). This plan is the one to run.
3. Nit: the test reads the docstring with `ast.get_docstring(tree, clean=False)`, matching the verification regex.
4. Nit: the sample of 20 is drawn across single-line and multi-line files.
5. Target first-line length tightened to under 90 characters, hard cap 100, for the reader.
6. Spec references use `Section(s)` in the docstrings, not `spec`.

## Architect review

Checked on this checkout with `.venv/bin/python` (3.13): 194 docstrings match, 93 multi-line, all test or conftest files. The red expectation of 194 paths is right. Placement as `drlibre/test_module_docstrings.py` is acceptable (decision 1). Ladder, layer, security and trust boundaries: fine. Script and test are test/doc text only.

## Architect review (round 2)

Revise reasons 1 and 2 of the previous review are resolved: the section rule now adds a section where one clearly applies (decision 5), and plan `2026-11-23-module-docstrings-purpose.md` is marked superseded for that rule. Counts re-verified: 194 offenders, 93 multi-line, 0 parse failures on `.venv` 3.13. Notes, none blocking: the owner's "beside `drlibre/test_product_imports.py`" names a file that does not exist, so the plan's placement is the right call; the test should read files with `encoding="utf-8"`; the per-file section judgment is the main risk, which the 20-line sample and the review listing cover.
