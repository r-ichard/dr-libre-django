# Module docstrings say what the module is for (task 26c item 14, first part)

> Superseded for the section rule by `doc/plans/2026-11-23-task-26c-item-14-test-docstrings.md` (decision 5 there). Do not run this plan as written: it forbids spec sections where none was named. Its product-module scope needs a fresh plan.

Slice: item 14, first part. First lines of the 114 product module docstrings that begin with a task number. Nothing else. Process: `tests-and-docs` (no behaviour change, no red gate, 27a3).

## Focal point

114 module docstrings under `scheduling/` start with `Task NN...`. The owner's rule (backlog 26c item 14) is that a module docstring says what the module is for. The change touches line 1 of each file and nothing else.

## Files

- Set, exactly: `grep -rl '^"""Task [0-9]' scheduling --include=*.py | grep -v -E '(^|/)test_|conftest|migrations/'`. Gives 114 files. Re-run the command at implementation time; the list is not stored.
- Not in the set, by design: `drlibre/test_*.py` (3 files, test files, other run). `scheduling/views/probe_views.py` and `probe_urls.py` (test-only probe views, the second half of item 14, other run; their docstrings do not start with a task number anyway). All `test_*.py` and `conftest.py` (other run).
- Included although test-only in use: `scheduling/views/fhir_specialty_support.py`, `fhir_role_support.py`, `fhir_organisation_support.py`, `scheduling/views/pages/admin_support.py`. They are helper modules named `*_support.py`, not `test_*`, and the 114 count includes them. Flagged for the owner, see "Choices".
- Touched: 114 files, one line each. Not touched: every other line, including the rest of each docstring, comments, code, `drlibre-specs.md`, `doc/backlog/`, `doc/handover.md`.
- Order: any; edit by directory (`scheduling/domain/`, `scheduling/use_cases/`, `scheduling/views/`, `scheduling/views/fhir/`, `scheduling/views/pages/`, `scheduling/jobs/`), so the orchestrator reads the diff per layer.

## Block plan

Block: the first line of a module docstring that starts with `Task NN` (also `Task 17a/17b`, `Task 27b item 10, issue #36`, `Task 22a, point 3`, `Task 04b, section 16`).

One-sentence plan: replace the task prefix (task number, item/point numbers, issue `#N`, ADR number, "review of N") with a short purpose phrase, keep the spec reference as `spec N.N` where the original had one, and keep the rest of line 1 and every later line unchanged.

Rules for the new first line:
- One line, at most 100 characters (`line-length = 100`), still a valid docstring opener (`"""` then text, closing on the same line when the original did).
- It names what the module holds or does in plain words. A noun phrase is enough.
- It cites the spec section where the original cited one, as `spec N.N` (`sections 3.2 and 10` becomes `spec 3.2 and 10`). No section where there was none.
- It contains no `Task`, no item, point, issue, ADR or review number, no task-file names.
- When the old line 1 ends mid-sentence, the new line 1 must still lead into line 2 unchanged. The implementer reads the whole docstring before rewriting line 1.
- Comments and code: untouched.

Examples (from the real files):
- `"""Task 22, spec 15.2: a clinician profile as a PractitionerRole."""` becomes `"""A clinician profile as a PractitionerRole, spec 15.2."""`
- `"""Task 19, sections 3.2 and 10: the clinician profile rules that need no stored data."""` becomes `"""Rules of the clinician profile that need no stored data, spec 3.2 and 10."""`
- `"""Task 14: a patient's own appointments, upcoming and past, and the record rule on one of them."""` becomes `"""A patient's own appointments, upcoming and past, and the record rule on one of them."""`
- `"""Task 22a: FHIR forbids an empty array, object or string and a null. Every response passes` (line 2 continues) becomes `"""Output cleaning: FHIR forbids an empty array, object or string and a null. Every response passes`, line 2 unchanged.

## Invariants and blast radius

- No runtime effect: no code reads module `__doc__` (grep of `scheduling` and `drlibre` finds none).
- Comment cap (`scripts/comment_cap.py`, 255 chars per block) only gets shorter. Docstrings are counted, so the gate still runs on them.
- Lint: a new line over 100 characters fails ruff. The implementer keeps each under.

## Failing tests first

None. A docstring change has no behaviour to test (27a3). Proof that nothing changed except the docstrings is the diff check below, not a test. Red gate skipped by the workflow choice, stated in the review.

## Trust boundaries and authorization

None crossed. Docstrings only.

## Domain entities

Not applicable to the code. Names used in the new text follow the vocabulary of CLAUDE.md §3 where a docstring names one (Clinician, Patient, Appointment, Room, Hospital, Department, Specialty, WaitlistEntry).

## Verification (the implementer runs, and reports the output)

1. `grep -rln '^"""Task [0-9]' scheduling --include=*.py | grep -v -E '(^|/)test_|conftest|migrations/'` prints nothing.
2. `git diff --numstat` shows `1 1` for each of the 114 files and nothing else.
3. `git diff -U0 | grep '^+' | grep -v '^+++' | grep -vc '^+"""'` prints 0: every added line is a docstring opener.
4. `make lint`, `make test`, `make gate` pass. Report the real output.

## What I will not do

- No script that rewrites docstrings. Each first line is written by hand, then the diff is read. 114 short edits.
- No change to test files, probe views, `drlibre/`, specs, backlog, handover, ADRs, reviews.
- No new helper, module, or move of the test-only helpers out of the package (that is the second half of item 14, other run).
- No rewrite of docstring bodies past line 1.

## Choices I made (orchestrator may redirect)

1. The four test-only `*_support.py` helpers are in the set (named by the 114 count, not `test_*`). If the owner wants them left for the probe/test move, drop those four files and the count is 110.
2. Spec reference kept as `spec N.N` everywhere, including the old `section N` wording.
3. Backlog item 14 stays open after this run; the orchestrator ticks only the first part.

## Not in this run

- Item 14, second part: move the test-only probe views (`scheduling/views/probe_views.py`, `probe_urls.py`) out of the product package.
- Docstrings of `test_*.py` files and `conftest.py` that begin with a task number (other run).
- `drlibre/test_deployment_checks.py`, `drlibre/test_startup_checks.py`, `drlibre/test_warnings_fail.py` (other run, test files).
- Item 15 onward of `doc/backlog/26c-gates-that-hold.md`.

## Risks

- Hand editing 114 lines risks a line that reads wrong with its second line. Mitigation: the orchestrator reads the diff per directory; each docstring is read whole before its line 1 is rewritten.
- A line over 100 characters fails `make lint`; caught by the gate.

## Architect review

Verdict: approve.

Checked against the repo on 2026-11-23:
- Set: the plan's grep gives 114 files, none a test file, conftest or migration. `drlibre/` has no product file starting with `Task`, so the scope is complete.
- Probe views: `probe_views.py` already starts with a purpose line, `probe_urls.py` has no docstring. Both correctly out of scope.
- No code reads `__doc__` in `scheduling` or `drlibre`, so the change has no runtime effect.
- Existing first lines are at most 100 characters (`line-length = 100`), so the new-line limit is no tighter than today's.
- Ladder: one line per file, by hand, no script. Smallest change that meets item 14's first part.
- Test-first: no failing test. Reason stated (docstring only, tests-and-docs workflow, 27a3). Accepted.
- Security, trust boundaries, transactions, errors: none touched. Stated.
- Scope: the four `*_support.py` helpers are in the set. They are product-package files, not `test_*`, so they meet "product modules (not test files)". The plan flags them for the owner. Not a revise reason.

Notes for the implementer, not conditions:
- The rule "no `Task` in the new line 1" does not cover later lines. Some bodies still cite items or issues (e.g. `issue #36`, `review of 21`). Item 14 asks only for line 1 here, so leave them. Say so in the review.
- Verification step 1 greps only `^"""Task [0-9]`. Lines like `"""Task NN` with a leading space or other prefix would slip past it. Column 0 is the module-docstring position, so the grep is sufficient.
