# Review: access table for the /fhir declaration (task 26b3, items 1 and 2)

Reviewed: `git diff main...HEAD` on `fabro/run/01M8425677TFTGKC3CG08BFYR4`. Three files added, 427 lines
(the plan, 267; `scheduling/views/fhir_access_rows.py`, 121; `scheduling/views/test_fhir_access_table.py`, 39).
No product file, no spec file, no ADR and no Makefile change.

Verdict: `approve`. No blocking item.

## Plan per block (§2.5)

- `scheduling/views/fhir_access_rows.py`: one frozen dataclass and one tuple of 51 rows, each row a
  (type, interaction) pair with four status codes and a basis. Stated in one sentence without re-reading: yes.
- `scheduling/views/test_fhir_access_table.py`: three tests. Compare the declared pairs with the row
  pairs both ways, and count duplicate rows. Stated in one sentence: yes.
- Plan doc: read to check the slice and the owner decisions. Not code.

Confirmed at a glance: the module docstrings carry no task number; the test file has no database mark
and makes no request; the table has the same 51 pairs as `FHIR_RESOURCES`.

Traced (§2.3): every row against `drlibre-specs.md` 15.4, ADR 0005, 0006, 0007, 0008, 0009 (the cited
passages), and the per-type counts against `scheduling/domain/fhir_declaration.py:85-190`.

## Checks, in the order of the brief

1. Plans per block: see above.
2. Correctness and errors: the test code has no error path to swallow. Nothing is caught.
3. Authorization, trust boundaries, sensitive data: no route, no request, no token, no input is read.
   Nothing is logged or placed in a URL. The table is data; the authorization is the walk's (item 3).
4. Double booking: not touched.
5. Tests: the three tests derive their expectations from the declaration (`FHIR_RESOURCES`), not from
   the code under test, and each can fail. Verified by reading and by a run (below). The cells are not
   checked by any test in this run; see Later.
6. Names: `FhirAccessRow`, `FHIR_ACCESS_ROWS`, `PairKey`, `_declared_keys`, `_row_keys`, `removed`,
   `unlisted`, `repeated` state roles. Test names follow `returns_X_when_Y`. Comments: the two module
   docstrings explain why (pytest must not collect the data module; what the tests hold). Under the
   255 cap.
7. Proof left no trace: commits after `write` (`8e87f8d`) are `check` (`ce274b2`, no file change) and
   `prove` (`522e542`, no file change). Nothing product-side changed after the tests were written.
8. Scope: no dependency added. No contract elsewhere needs to change (the table is read by nothing else).
   The owner decisions are not in the diff; they live in the plan and are repeated below.

Run by the reviewer: `uv run pytest scheduling/views/test_fhir_access_table.py -v` with the Makefile's
test environment (`SECRET_KEY` from the test-only key, `DEMO_PASSWORD=`, `.env.example`): 3 passed in 0.08s.
Counts: declared pairs 51, rows 51, distinct row pairs 51.

## Blocking

None.

## Later

1. **nit**: `scheduling/views/fhir_access_rows.py:1-2`. The docstring says "ADRs 0005 to 0010". ADR 0010 is
   proposed and no row cites it. Risk: a reader looks for 0010 in the cells and finds none. Fix: say
   "ADRs 0005 to 0009" or name 0010 where a cell uses it.
2. **For the owner, not a code defect**: `scheduling/views/fhir_access_rows.py:95`. The `AppointmentResponse`
   read row gives a clinician 403. §15.4 names "the patient (own), admin" only, so the letter gives 403.
   The plan's owner decision 3 covers search only (line 101), not read. Risk: the owner rules on search
   and never sees the read cell. Fix: add the read cell to owner decision 3 in the plan and in
   "For the owner" below.
3. **Process**: the red stage is not in git history. `8e87f8d` (`write`) adds the tests and the full 51-row
   table in one commit. The plan's red step (empty tuple, first test fails on 51 pairs) cannot be seen from
   the commits; only the stage log can show it. Risk: a test that passed before the table existed would go
   unnoticed. Fix: check the `write` stage log for the red run; nothing to change in the diff.
4. **Test coverage (by design)**: no test checks a cell. A cell that drifts from §15.4 passes this run. The
   walk (item 3, not in this run) must read these cells. Fix: none here; the walk owns it.
5. **Duplicate role matrix (plan Risks)**: `scheduling/views/fhir_spec_tables.py` and this table both
   carry the role matrix, the first as roles and ADR differences, the second as status codes. They agree
   on every row checked. Fix: a later run derives one from the other.
6. **Measured number (not a blocker)**: the sandbox's `make test` run in the check stage took 355.87 s
   (5282 tests) on a shared machine. The new file takes 0.08 s for its three tests. The orchestrator
   measures the suite on a quiet machine.

## For the owner

Each conflict below follows the letter of `drlibre-specs.md` 15.4. The spec is not edited. Each is a row in
`scheduling/views/fhir_access_rows.py`, and the test does not change if the owner rules otherwise.

1. `Communication` read, search and update, admin 403 (`fhir_access_rows.py:114-118`). §15.4 names "the
   recipient" only. ADR 0005 (line 75) gives "a clinician's or an admin's token: every record". Owner:
   accept 403, or grant admin read.
2. `Communication`, clinician 403 (`fhir_access_rows.py:114-118`). Notifications go to the patient only (§11),
   so a clinician is never the recipient. ADR 0005's "every record" would give 200. Owner decides.
3. `AppointmentResponse` search, clinician 403 (`fhir_access_rows.py:96-104`). §15.4 names the patient (own)
   and admin. ADR 0007 (lines 31-32) gives a clinician an empty search, 200 with total 0. Owner: keep ADR 0007's
   answer, or follow §15.4.
4. `AppointmentResponse` read, clinician 403 (`fhir_access_rows.py:95`). Same reasoning as item 3; ADR 0007
   says nothing about a clinician reading one id. Owner decides with item 3.
5. `AppointmentResponse` create, admin 201 (`fhir_access_rows.py:105-113`). §15.4 names "the patient (own offer),
   admin". ADR 0007 (line 30) says "Only the offered patient may accept". The letter gives 201. Owner decides;
   the walk shows the refusal if the owner keeps ADR 0007's wording.

## Left for the orchestrator

From the slice in the plan (`doc/plans/2026-11-23-fhir-access-table.md`, "Slice"):

- Item 3 of the task: the walk that sends requests, each caller against own and another user's record, and
  the body-level answers (400, 409, 412, 422) that the cells exclude.
- Item 4 of the task: the generated access section of `doc/security-review.md` and the test that compares it
  with the table. Also the Makefile target that generates it.
- Any change to the `/api` table: `scheduling/views/test_api_access_rows.py` and its naming (the task-number
  docstring). Separate change.
- Item 5 of the task: the request count and cost of the walk. Belongs to item 3.
- Owner decisions 1 to 5 above: decide, then edit the row if the owner rules otherwise.
- `make mutate`, `make fhir-validate`, and the fresh-clone order in the task's "Done when" line. Not run here.
