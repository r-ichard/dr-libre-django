# Review: page access table (task 26b3, items 1 and 2, page routes)

Reviewer: second reader, on the diff `git diff main...HEAD` (8 files, +828, all added, no product code, no migration, `drlibre-specs.md` untouched).

Verdict: **approve**. No blocker. Items below are Later.

## Checks, in order

1. **Plans of changed blocks.** Read at a glance: `test_page_access_rows.py` (types), each `test_page_access_rows_*.py` (a tuple of `Row` literals, one family each), `test_page_access_table.py` (route list, coverage tests), ADR 0012 (readings). Needed a trace: `test_page_access_table.py:36-48` (route string building and the `^` strip) and `:67-78` (DEBUG branches), because the DEBUG reading depends on when settings are read (see Later 1).
2. **Correctness and errors.** No runtime code. No `try`, no swallowed error. Test helpers are plain set comparisons.
3. **Authorization, schema, logging.** Nothing in the diff runs in a request. No payload, no URL, no log. Not applicable beyond the table's own content.
4. **Double booking.** Not touched.
5. **Tests.** Derived from the specification (`drlibre-specs.md` 12.3, 14, 16) through the table rows, and from the URL configuration through `get_resolver()`. Three named tests from the plan exist (`test_page_access_table.py:51, 61, 67`). A fourth, `returns_debug_row_expected_when_debug_is_on` (`:75`), was added at the prove stage. See Later 5. The cell values (200, 302, 403) are not exercised by any test in this slice: a wrong cell stays green until item 3 walks it (Later 4).
6. **Names and comments.** Names state roles (`Row`, `Answer`, `NO_SESSION_ROWS`, `CLINICIAN_ROWS`). Test names follow `returns_X_when_Y`. No task numbers in docstrings (grep: none in the new files). Comments: three, all short, each says why. Lines all ≤ 100 columns (checked with awk). Largest file 195 lines (`test_page_access_rows_admin.py`), under 300. Functions all under 15 lines.
7. **Proof left no trace.** `git log`: `write` (3c6a1df) added the tests, rows and ADR. `check` (d3d8e5b) has no file change. `prove` (b0956cb) changed only `scheduling/views/pages/test_page_access_table.py` (+6 lines, a test function). No product or migration line changed after the write stage. Rule 7 holds.
8. **Scope and contracts.** Changed files are the planned set, nothing else. No dependency added. No Makefile, `drlibre/urls.py`, view, template, or spec change. The plan's "Not touched" list holds (checked by `git diff --stat`). Row count re-derived by reading: 18 + 15 + 19 + 38 + 22 = 112 non-debug rows, plus `style` = 113. The `make test` in check (5279 passed, DEBUG off) proves the 112 match the URL configuration exactly.

## Findings

No Blocking findings.

## Blocking

(none)

## Later

1. **DEBUG-on coverage is not run by the suite as written.** `scheduling/views/pages/test_page_access_table.py:32-33` reads `settings.DEBUG` at call time, but the URL configuration is built at import (`drlibre/urls.py:194-195` appends `style` only when DEBUG is on at import). So `override_settings(DEBUG=True)` in `:75-78` changes the expected list only, not the URL configuration. In a process started with DEBUG on (the container's `make test` may be; the plan says `seed_demo` needs DEBUG on), `returns_no_failure_when_every_page_route_has_a_row` does run the DEBUG-on comparison. The docstring at `test_page_access_table.py:1-3` says the on-branch is not run by any test run. Risk: the docstring can be wrong for one of the two ways the suite runs. Smallest fix: measure `DEBUG` in the container's `make test`, then correct the docstring to say which one runs it.
2. **Wrong section references in docstrings.** `scheduling/views/pages/test_page_access_rows.py:1` cites section 14, which is the JSON API table; only `sign-out` in it is a section 14 row. `test_page_access_table.py:1` cites section 16 (product qualities), but no row derives from it. Smallest fix: cite 12.3 and, for sign-out only, 14.
3. **Dead enum member.** `scheduling/views/pages/test_page_access_rows.py:12` defines `Answer.NOT_FOUND`; no row uses it (grep: one occurrence). The plan reaches it only through the `names_record` rule, which item 3 applies. Risk: none now. Smallest fix: keep it with a comment that item 3 uses it, or drop it until item 3 lands.
4. **The cells are unverified in this slice.** Every 200, 302 and 403 in the rows (for example `test_page_access_rows_clinician.py:6-18`) is a reading of the specification, not a checked answer. The coverage tests check names only. A wrong cell passes `make test` until item 3's walk. Smallest fix: none in this run; item 3 must send the requests. Recorded so the orchestrator does not read a green suite as proof of the cells.
5. **The fourth test has no red proof.** `test_page_access_table.py:75-78` was added at the prove stage (b0956cb). It can only fail if `_expected_routes` ignores `settings.DEBUG`. Smallest fix: mutate `or not row.debug_only` in `:33` to confirm `returns_no_debug_row_expected_when_debug_is_off` and this test each fail; note the result in the run log.
6. **Prefix filter too broad.** `test_page_access_table.py:18` uses `"fhir"` without a slash. Any future page route beginning `fhir` (for example `fhirs/...`) is silently treated as not a page and gets no row. Smallest fix: `"fhir/"`, plus an equality check for the plain `fhir` path.
7. **`sign-out` reads `OK`.** `test_page_access_rows.py:43` and the rows use `OK` for a 302 to sign-in with the cookie cleared (plan, "Row shape"). The name says 200. Smallest fix: a comment on the row, or a separate answer, before item 3 uses the cells.
8. **Overlapping walker on `main`.** `scheduling/views/pages/page_walk_support.py` already walks every page route for each role, with its own `NOT_PAGES` (`favicon.ico`, `style`). The plan defers the decision to item 3. Smallest fix: item 3's plan decides which walker stays; the duplicate `NOT_PAGES` lists should not both survive.
9. **Red proof is not in the repository.** The plan says the red run's evidence is in the run log, not in the diff. Nothing in the diff shows the first test failing with the empty table. Smallest fix: the orchestrator reads the run log before merge.
10. **Timing, measured here (not a blocker).** `make test` in the check stage: 5279 passed in 204.57 s on the shared sandbox. Orchestrator measures on a quiet machine.
11. **Enum aliases.** `test_page_access_rows.py:15-17` (`OK = Answer.OK` and two more) give the same value two names. Smallest fix: use `Answer.OK` in the rows, or keep the aliases and drop the enum prefix. Nit.

## For the owner

Conflict and readings from the plan and ADR 0012 (`doc/adr/0012-page-access-readings.md`). Nothing in `drlibre-specs.md` was edited.

1. **Record existence (conflict).** `drlibre-specs.md:615-616` (12.3): another user's record gives `forbidden`, a missing record gives `not_found`. Those two answers reveal existence. The task's item 3 says the second caller "never tells whether the record exists". The table follows 12.3; the owner picks one. The divergence is already in the code: `scheduling/views/pages/booking_code.py:42-43, 78` answers `not_found` for another visitor's hold (`not made_this_hold`), not `forbidden`.
2. Signed-in staff on no-session pages (`drlibre-specs.md:610-611`): the table reads OK for every caller.
3. Appointment confirmation and calendar file: patient-only reading (clinician and admin get `forbidden`). The spec names no area.
4. `account/password`: patient `forbidden`, staff OK. Matches the code, not the spec.
5. `sign-out`: OK for every caller (section 14, `drlibre-specs.md:648`: "Anyone"); redirect in practice.
6. `favicon.ico`: OK for every caller, no session check.
7. `style`: debug-only row; spec silent.
8. `/static/`: not a page, no row.
9. A method the view refuses answers 405; spec silent.
10. Hold routes: the hold cookie, not the session, identifies the caller; spec 12.3 gives no rule.

## Left for the orchestrator

From the plan's "Not in this run" and the task's items:

- Item 3: the walk. Every caller sends every route's request as its real client sends it; own-record and other-record cases; checks the cleared cookie on sign-out. Risk: `PageView.read_scope` can answer 429 on repeated GETs.
- Item 1 for `/api/v1` and `/fhir` (tokens, 401, the API rows): a separate slice.
- Item 4: the access section in `doc/security-review.md`, its generator command, its test, and the review's "For the owner" section.
- Item 5: request count and timing of the walk.
- The reference files `test_api_access_rows.py` and `test_api_access_table.py` are absent on this branch and on `main`; decide the rename when they merge.
- Later 9: the red run log.
- Later 8: decide between `page_walk_support.py` and the new table in item 3.
