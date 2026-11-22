# Review: HEAD counts as GET on public schedule pages (task 26b2)

Reviewed: `git diff main...HEAD` on `fabro/run/01M82NR1MFSH80XB3X4MF38Y20`. Three files:
`scheduling/views/pages/page_view.py` (3 lines), `scheduling/views/test_read_limits.py`
(+54, -5), `doc/plans/2026-11-22-head-counts-as-get-26b2.md` (+148). No migration, no
dependency, no change to `drlibre-specs.md`.

## Plan, one sentence per block

- `page_view.py:80-82`: a HEAD takes the same SCHEDULE read hit as a GET; the hit is taken
  before the view runs, so a limited HEAD never computes a schedule. Confirmed at a glance.
- `test_read_limits.py:195-220`: seven page routes, 1200 HEADs answer 200, the 1201st HEAD
  and the next GET answer 429 with `Retry-After`. Traced: the test drives the real client
  with `client.head`, so it exercises Django's HEAD-to-`get` alias.
- `test_read_limits.py:223-233`: API twins and `/api/v1/slots`, 1200 HEADs then 1200 GETs.
  Traced to `api_view.py:22` (no `head` in `http_method_names`) and `failure_response.py:95`
  (DRF `MethodNotAllowed` is mapped to the project's not-found failure).
- `test_read_limits.py:235-242`: anonymous `/fhir/Location`, 600 HEADs then 600 GETs.
  Traced to `fhir/views.py:85-86`: the method check runs before `take_read_hit` at line 91.

## Findings

Ordered by the review's checklist.

1. **Correctness, page path: holds.** `page_view.py:81` takes the hit for `GET` and `HEAD`.
   Every `read_scope` user (`detail_pages.py:29,51,63`, `booking_steps.py:14,42`,
   `booking_times.py:29`, `booking_details.py:44`) inherits this guard. `request.method` is
   upper-cased by Django, so the exact string compare is safe. No swallowed error.
2. **Correctness, `/search`: holds by shared path, untested.** `search_page.py:23-26`
   `get` calls `search_for_visitor`, which takes the hit (`use_cases/search_limited.py`).
   HEAD reaches `get` through the alias, so HEAD is counted. No test pins it. Later, item 4.
3. **Authorization and sensitive data: holds.** The counter key is still
   `counter_key(user, address)`; the method is not a key input. A signed-in caller counts
   by user id. Nothing new is logged or placed in a URL.
4. **Double booking: not touched.** No write path, no hold, no appointment. Reads write
   no audit entry, as before.
5. **Tests: derived from the specification and the routes, not from the implementation.**
   The page test fails on the 1201st HEAD returning 200 (the red stage listed exactly the
   seven `test_read_limits` HEAD cases in `verify_red`). The API and FHIR cases pass before
   and after the fix, as the plan required. Their assertions are not vacuous: each one
   requires the GET fill to still answer 200 after the HEADs, which fails if HEAD is counted.
   Confirmed on HEAD by re-running the 13 `head` tests: 13 passed.
6. **Test plan versus test code, status codes.** The plan (line "Facts checked", API bullet
   and block 1b) says HEAD on the API twins answers 405. The code and the test answer 404,
   and that is right: `failure_response.py:95` maps `MethodNotAllowed` to not-found, so
   the test name and assertion (`test_read_limits.py:224`, `returns_404_...`) match the
   running system. The plan is wrong, the code is not. Later, item 1.
7. **Brief versus slice.** The brief asked for 429 on the API twins and anonymous FHIR after
   the budget. Those routes do not serve HEAD and do not compute a schedule, so they do not
   bypass the limit. The run pins the refusal and states the owner decision. See
   `## For the owner`.
8. **Names and comments (§3, §4).** `page_view.py:80` comment states why (Django aliases
   HEAD to `get`), under 255 characters, no narration. New test names follow
   `returns_X_when_Y`. The page test name differs from the plan's name. Later, item 2.
9. **Proof trail (§13 stage check).** `git diff --stat f4141b1 HEAD` (green to HEAD) shows
   only `scheduling/views/test_read_limits.py` (4 deletions, the unused `TYPE_CHECKING`
   import and its empty `if` block). The product line `page_view.py:80` was introduced by
   the `green` commit `f4141b1`, and the red tests by `red` commit `abbe77e`. Nothing after
   `verify_green` changes product code or migrations. No mutation left behind.
10. **Scope.** The removed `TYPE_CHECKING` block in the test file is unrelated cleanup
    bundled into a test-only proof commit. It is harmless. Later, item 3.
11. **Hard rules.** No `Any`, `cast`, bare `# type: ignore` or bare `# noqa` added (the one
    existing `# type: ignore[arg-type]` at `test_read_limits.py:37` predates this diff and
    names its code). Functions and files are far under 100 and 500 lines (`test_read_limits.py`
    242 lines; `page_view.py` 131). No swallowed error. No authorization from payload.
12. **Budget.** The 13 HEAD tests took 39.29 s with `-n 4` on this shared sandbox. Not a
    blocker (time budgets are never blockers here). The orchestrator measures on a quiet
    machine. Later, item 5.

## Blocking

None.

## Later

1. Correct `doc/plans/2026-11-22-head-counts-as-get-26b2.md`: the API twins and
   `/api/v1/slots` answer 404 for HEAD (not 405), via `failure_response.py:95`; the anonymous
   FHIR read answers 405. Plan text only.
2. Rename the plan's page test to the name in the code, or the reverse, so the plan and
   the suite agree. Also fix the plan header "Slice: items 1 to 3" to match blocks 1a, 1b, 2.
3. Remove the unrelated `TYPE_CHECKING` cleanup from a separate commit, or accept it in the
   next test-file change. Harmless now.
4. Add one HEAD test on `/search` (`search_page.py`, `search_limited.py`), to pin the shared
   path the plan relies on. Shared code, so low risk.
5. Measure the HEAD test cost on a quiet machine. Measured here: 13 tests, 39.29 s, `-n 4`,
   shared sandbox.
6. Pre-existing, not in this diff: `test_read_limits.py:37` `_read` carries
   `# type: ignore[arg-type]`. Check whether the ignore is still needed (`client.get`
   takes `**extra: str`, so a type-only fix may remove it).

## Left for the orchestrator

- Slice (plan "Not in this run"): serving HEAD on `/api/v1` and `/fhir` as a counted read
  (owner decision). Not a blocker; the run pins 404/405 with no counter taken.
- Slice (plan "Not in this run"): a test that `/search` counts HEAD (Later item 4).
- Slice (plan "Not in this run"): review Later items 4 and 5 (validation order,
  `RateLimitHit` growth). Not in this run.
- Finished in the run: blocks 1a, 1b, 2. Not finished: none of the slice.
- Brief deviation, declared by the run: 429 on API twins and anonymous FHIR HEAD was not
  shown; the run shows the routes refuse HEAD before any work and count nothing. The
  orchestrator decides before merge whether to serve HEAD there instead.

## For the owner

- Should HEAD be a served method on `/api/v1` read routes and on anonymous `/fhir` reads
  (counted, 429 after the budget), or should it keep refusing (404 on the API, 405 on
  FHIR)? The spec (`drlibre-specs.md` section 7.5) says nothing about HEAD. The run chose
  refusal, which adds no public surface. No ADR written: this review leaves the choice open
  for the owner.
