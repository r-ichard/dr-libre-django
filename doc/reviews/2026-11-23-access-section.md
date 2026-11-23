# Review: task 26b3 item 4, access section from the tables

Date: 2026-11-23. Second reader, diff `git diff main...HEAD` (10 files, 899 insertions, 22 deletions).
Only commit with content: `37e9650` (write). `efe05f8` (check) and `3e12266` (prove) are empty, so no
product or test line changed after the gates ran.

## What the diff does, by block

- `scripts/access_table.py`: renders the three access tables into one Markdown section and splices it
  into `doc/security-review.md` between `## Access` and the next `## `. Plan in one sentence: read the
  tables by import, render three tables, splice. Confirmed at a glance: no Django import; `Any`, `cast`,
  bare suppressions absent from the added Python. Traced: `splice` (line search, errors on zero or two
  headings), the cell escape, the page-table row list.
- `scripts/test_access_table.py`: 13 tests. The drift test is `returns_unchanged_document_when_section_is_current`
  (splice of the current render equals the file). Run here with the Makefile's safe env: 13 passed.
- `doc/security-review.md`: one hunk, lines 14 to 241, replacing the old two-line `## Access` paragraph.
  The rest of the file is untouched (checked: no other hunk in `git diff`).
- `scheduling/views/pages/test_page_access_rows.py`, `test_page_access_walk.py`: `KNOWN_DIFFERENCES` and
  `Caller` move from the walk to the rows module. Diff of the moved dict is line-for-line identical.
- `test_support/fhir_access_rows.py`: `KNOWN_DIFFERENCES: tuple[()] = ()`.
- `Makefile`: `access-table` runs `uv run python -m scripts.access_table` from the root. `-m` puts the
  root on `sys.path`, so the imports resolve. I ran it once (with a stray `--help` argument, which the
  script ignores); the file came out unchanged and `git status` is clean.
- `doc/handover.md`: four lines on how to rerun the target. CLAUDE.md requires the handover to move with
  the state it describes. In scope.

## Checked against the rules

- Authorization, injection, logging, dependencies: none in the diff. No new package; stdlib only.
- Type escapes (§7): none. Function and file size: `make gate` passed in the check stage.
- Tests: the drift test fails on a changed row (`returns_changed_document_when_table_row_differs`
  covers the renderer side). Every promised test in the plan exists: splice edge, both error paths,
  `|` escape, the glob identity test. Each page-row tuple (six of them, across the five page modules)
  is in `current_tables()`, so no tuple is silently skipped.
- Scope: no change to any other review section; no change to `drlibre-specs.md`; no change to the
  table contents (the moved dict is identical).

## Findings

Severity follows the card: no finding here breaks a hard rule.

1. **Stale sentence in the review.** `doc/security-review.md:12` still says the access table (item 10)
   "is written by another run". It is now false. Risk: the review contradicts itself. Smallest fix:
   reword that sentence to say item 10 is in the Access section. Left alone because the brief says
   nothing else of the review changes. Later.
2. **Comment promises a review entry that does not exist.** `scheduling/views/pages/test_page_access_rows.py:58-59`
   says each `KNOWN_DIFFERENCES` entry "is a question for the owner, listed under 'For the owner' in the
   review". The `## For the owner` section (`doc/security-review.md:413`ff, the owner list starting at
   item 1) names none of the eight page differences. The backlog header (`doc/backlog/26b3-access-table.md`
   lines 3 to 6) asks for exactly that. Risk: a false comment, and an owner question that never reaches
   the owner. Smallest fix: either add the eight as a `For the owner` entry, or change the comment to
   say they are not yet listed. Later; the orchestrator decides (see the owner note below).
3. **Unused parameter.** `scripts/access_table.py`, `render_fhir_table(rows, differences)`: the
   `differences` argument is never read; the function always writes `_differences(())`. The type
   `tuple[()]` makes non-empty input a type error, so the output stays right today. Risk: a reader
   takes the parameter as rendered. Smallest fix: drop the parameter and keep the comment in
   `test_support/fhir_access_rows.py` that explains why `KNOWN_DIFFERENCES` is typed empty. Later.
4. **Two hand-kept lists of page tuples.** `scripts/access_table.py` `current_tables()` and
   `scheduling/views/pages/test_page_access_table.py` `_all_rows()` both list the six page tuples. The
   drift test compares the document with the renderer's own list, so a new tuple added to a page module
   and to `_all_rows()` but not to `current_tables()` would pass both checks while the section stays
   silent about it. The plan records that the renderer cannot import `_all_rows()` (it pulls in Django).
   Smallest fix: a test that counts the `Row` tuples in the five modules against `current_tables()`
   (module attributes whose value is a tuple of `Row`). Later.
5. **Two plan files for one task.** `doc/plans/2026-11-23-access-section.md` (verdict `approve`) and
   `doc/plans/2026-11-23-access-section-from-tables.md` (the earlier `revise` review appended to the
   plan) differ only in that appended review. Risk: a reader picks the wrong one. Smallest fix: delete
   the `-from-tables` file and keep the approved one. Later.
6. **Splice is a line search.** `scripts/access_table.py` `splice` ends the section at the next line
   starting `## `. A `## ` line inside a fenced block in a later section would cut the Access section
   short. No such line exists today (the drift test would catch it: the render would not equal the
   file). Smallest fix: none needed now. Nit.

## Measured

- `scripts/test_access_table.py`: 13 passed in 0.10 s on this machine, shared with other runs. Not a
  budget finding; the orchestrator measures on a quiet machine.
- The Access section adds about 210 generated lines to the document; the diff is 224 lines.

## Blocking

None.

## Later

1. `doc/security-review.md:12` stale "another run" sentence (finding 1).
2. `scheduling/views/pages/test_page_access_rows.py:58-59` comment promises a `For the owner` entry that
   does not exist; add the eight entries or fix the comment (finding 2).
3. `render_fhir_table` ignores its `differences` argument (finding 3).
4. No test ties the page-row tuples to `current_tables()` (finding 4).
5. Stale plan `doc/plans/2026-11-23-access-section-from-tables.md` (finding 5).
6. `splice` section end on any `## ` line (finding 6, nit).

## Left for the orchestrator

Item 4 of `doc/backlog/26b3-access-table.md` (the access section, the make target, the drift test) is
finished in this run; nothing of the slice is left. No `## Not in this run` list was in the plan.

## For the owner

The page table holds eight differences where the table says `ok` and the product redirects (favicon
to `/static/favicon.svg`, sign-in to each role's home, one admin service page to the appointments form).
The backlog header asks that such routes be named under this section. Whether a redirect counts as
"answers differently from the specification" is the owner's call: the spec text these rows cite
decides it, and this review did not read section 14 for redirects.
