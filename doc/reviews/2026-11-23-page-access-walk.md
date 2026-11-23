# Review: page access walk over GET rows without a record (task 26b3, item 3, part 1)

Verdict: **approve**. No blocking items. Reviewed on branch `fabro/run/01M844FY0H4P6W2AGPNXPY7TZM`
against local `main`.

## Scope of the diff

`git diff main...HEAD --stat`: two files, 346 insertions.

- `scheduling/views/pages/test_page_access_walk.py` (new, 183 lines): the walk.
- `doc/plans/2026-11-23-page-access-walk.md` (plan, 163 lines, includes the write-stage section).

No product code, no migration, no dependency, no change to `drlibre-specs.md`, no change to the
table files, no change to `drlibre/urls.py`. The plan's rename of `_all_rows` was dropped (see Later).

Commits after `write` (`f8239dc`): `check` (`4177680`) and `prove` (`65b5d15`) change no file
(`git show --stat` empty for both). No product or test line was changed after the red and green
work, so no mutation is left behind.

## Method

1. Plan of each block, one sentence, from the source:
   - `_answer_of` (`test_page_access_walk.py:57-69`): maps a response to one of the table's answer
     strings, or to `"<status> <Location>"` for another redirect.
   - `_walked_rows` (`:84-91`): table rows with `names_record` false, not in `LEFT_FOR_LATER_RUN`,
     debug-only rows only when `settings.DEBUG`.
   - `_page_callbacks` (`:119-126`): resolver routes minus regex entries and API, FHIR and static prefixes.
   - `_answers_get` (`:129-136`): a view answers GET if it accepts `get` and `is_form_only` is false.
   - The four tests: the list equals the resolver's GET routes; the walk compares every row
     and caller; each recorded pair keeps its product answer; each recorded answer differs from the table.
   I did not need to trace any of these twice.
2. Trust boundary: the walk sends GETs built from table strings through `path_of`
   (`page_walk_support.py`); no caller input reaches the walk. Callers are real sessions from
   `signed_in_patient` (`booking_pages_support.py:40-52`), not forged cookies. No authorization
   logic is added; the walk only reads the server's answers.
3. Hard rules checked by grep and by reading: no `Any`, `cast`, bare `# type: ignore`, bare
   `# noqa` in the new file; every function under 50 lines; the file is 183 lines; no swallowed
   error; no audit or write path touched.
4. Reproduced the walk's red states outside the repository (a throwaway runner in `/tmp`, nothing
   written to the repo), see "Measured here".

## Findings

No finding is a blocker. The items below are ranked by how much they matter to the next reader.

### Later

- **L1. Red evidence not in the artifacts.** `doc/plans/2026-11-23-page-access-walk.md:75-88`
  asks for two red runs and says the second predicts the pairs. The write-stage section
  (`:150-163`) states the outcome but does not record the output. I reproduced both (see
  "Measured here"): dropping `terms` gives `missing_from_walk=['terms']`; an empty
  `KNOWN_DIFFERENCES` gives eight mismatches, the four `favicon.ico` pairs, the three `sign-in`
  pairs and `admin-console/appointments/new/service`. Smallest fix: paste those two outputs into
  the plan's write-stage section. The plan's step 4 (change one recorded answer by hand) is not
  recorded either; the re-send test (`:166-174`) fails on any change by reading, but nobody ran it.

- **L2. Test name states the wrong thing.** `test_page_access_walk.py:153`
  `returns_row_answer_when_caller_gets_walked_page` compares against `_wanted`
  (`:103-106`), which returns the product's answer for listed pairs. Smallest fix: rename to
  `returns_row_or_listed_answer_when_caller_gets_walked_page`, or keep the name and say so in
  the plan.

- **L3. Re-send test adds nothing today.** `test_page_access_walk.py:166-174` sends 8 GETs plus
  6 setup requests (0.02 s). All three recorded routes are walked rows, so the walk already
  asserts each pair's product answer. The test guards only a pair that leaves the walk, which
  nothing does today. Smallest fix: keep it if the owner wants the guard against future
  `LEFT_FOR_LATER_RUN` changes; otherwise delete it and the 14 requests go with it.

- **L4. Stale exclusion hides a route that starts answering GET.** `test_page_access_walk.py:146`
  subtracts `LEFT_FOR_LATER_RUN` from the expected set, so if a sign-out or form-only route
  starts to answer GET, the resolver test passes and the walk skips it. Today all five routes
  answer GET false by `_answers_get` (checked: `sign-out`, `sign-in/email-link`,
  `patient/notifications/read-all`, `admin-console/appointments/export`,
  `admin-console/settings/reminders`), so the subtraction is not needed. Smallest fix: drop
  `- LEFT_FOR_LATER_RUN` at `:146`; the test then fails on a LEFT route that starts answering GET,
  while `_walked_rows` still excludes it.

- **L5. Three copies of the resolver walk and of the prefix list.** `test_page_access_walk.py:109-116`
  (`_url_callbacks`) repeats `_routes` in `scheduling/views/pages/page_walk_support.py:31` and
  `_route_strings` in `scheduling/views/pages/test_page_access_table.py:36`. `NOT_PAGE_PREFIXES`
  is also repeated (`test_page_access_walk.py:54`, `test_page_access_table.py:18`). Smallest fix:
  one helper in `page_walk_support.py` that yields `(route, callback)`, used by all three. Not
  needed to merge this run; a repeat pattern for the process retro.

- **L6. Private name imported across modules.** `test_page_access_walk.py:19` imports `_all_rows`
  from `test_page_access_table.py`. The plan (`:36-38`) wanted a rename; the write stage
  (`:157-159`) kept it private because `conftest.py` rejects public functions in test modules.
  The deviation is recorded, so no action now. Smallest fix if the rule stays: move `all_rows`
  into a non-test helper module the walk and the table both import.

- **L7. Comments.**
  - `test_page_access_walk.py:26`: "answer a GET with 405 or nothing". The measured answer is 405
    for all five (plan `:18-20`). Write "405".
  - `:37-38`: "listed under 'For the owner' in the review" narrates process. Say why the entries
    exist: each is a question the owner answers.
  - `:121`: "they are the API and FHIR routes, not pages". `static/` (`drlibre/urls.py:192`) is
    also a regex entry. Name all three.
  - `:66`: `urlsplit(location).path.startswith("/sign-in")` also matches `/sign-inx`. No such
    route today. Smallest fix: `== SIGN_IN_PATH` with the constant from `page_view.py:25`.

- **L8. Shared sessions across rows.** One admin client serves every admin row, and one visitor
  client every visitor row. GETs can write session state (admin notices, the hold cookie). The
  answers are order-independent today, and nothing checks that. Smallest fix: none now; note it
  if a later run adds a GET that writes a cookie.

- **L9. Plan's rate-limit paragraph omits the login POSTs.** `doc/plans/...:26-31` counts read
  counters only. Each test makes three `POST /api/v1/auth/login` calls from one address (the setup
  in `booking_pages_support.py:44-50`). They pass. Smallest fix: add one sentence to the plan
  naming the login counter and its limit.

- **L10. Debug-on path not exercised here.** The plan claims 47 walked routes and 194 requests
  with DEBUG on. Under pytest `settings.DEBUG` stayed `False` even with `DEBUG=1` in the
  environment, so this review did not check that branch. The branch is consistent in principle:
  `drlibre/urls.py:195` registers `style` at import, and `_walked_rows` reads the setting at call
  time. Smallest fix: the orchestrator runs the file once with DEBUG on in the real environment.

- **L11. Commit trailers.** The four `fabro(...)` checkpoints carry "Generated with Fabro" and
  `Fabro-*` trailers. Per CLAUDE.md "Hand-applied gaps" (1), squash with a hand-written message and
  disclose the tooling in the body. Not a code defect.

## Blocking

None.

## Later

The list above (L1 to L11) is the review's Later list.

## For the owner

Each pair is a question. The product's answer is what the walk asserts today; the table's answer
is what the specification and ADR 0012 say. Owner decides which one stands; a change of either
side fails the walk until the table or the product changes.

1. **`favicon.ico` for all four callers: product 302 to `/static/favicon.svg`, table `ok`.**
   Code: `drlibre/urls.py:121`. ADR 0012 reading 6 says "OK for every caller", meaning a redirect
   with no session check. Question: is a redirect to a static file an `ok` answer, or should the
   table say "302 to the static file"?
2. **`sign-in` for patient, clinician and admin: product 302 to their home, table `ok`.**
   Code: `scheduling/views/pages/sign_in.py:71-72`. Specification 12.3 says sign-in "needs no
   session"; ADR 0012 reading 2 covers the table's reading that a signed-in caller sees the page.
   Question: should a signed-in caller who opens the sign-in page be redirected home (product), or
   shown the page (table)?
3. **`admin-console/appointments/new/service` for admin: product 302 to `/admin-console/appointments/new`,
   table `ok`.** Row: `scheduling/views/pages/test_page_access_rows_admin_operations.py:50`. Not
   covered by any ADR 0012 reading. Question: is the alias a valid answer for the table, or should
   the table name the redirect? If the owner keeps the redirect, ADR 0012 needs a new reading 11.

## Left for the orchestrator

From the plan's `## Not in this run`, carried over unchanged:

- Form-only routes and sign-out (the five routes in `LEFT_FOR_LATER_RUN`): POST walk with the
  cross-site token and `Origin`, as in the form walks. The sign-out row says `ok` but the view
  answers 405 to a GET, and ADR 0012 reading 5 says redirect; the table and the ADR disagree.
- Record-named rows: one own record and one other user's record each (task item 3).
- API and FHIR routes (`api/`, `fhir`): other test files, another run.
- `doc/security-review.md` access section and its consistency test (task item 4).
- `make fhir-validate` and `make mutate`: outside this slice.

Not finished from the slice, and not a blocker: the plan's step 4 (hand-change one recorded answer
and see the product-answer test fail) is not recorded; see L1.

## Measured here

Commands ran against the sandbox database, read-only with respect to the repository. Env:
`SECRET_KEY` and `DEMO_PASSWORD` as in `SAFE_ENV`, `DB_NAME=drlibre_run_review`.

- `uv run pytest scheduling/views/pages/test_page_access_walk.py`: 4 passed in 2.75 s
  (wall time of the file including database setup; the walk test is about 0.3 s per the write stage).
  Repeated twice more: 3.32 s and 3.46 s. This machine is shared; the orchestrator measures the
  number on a quiet machine.
- Walked routes with DEBUG off: 46. Confirmed by a read-only call to `_walked_rows()`.
- Red 1, `_walked_rows` without `terms`: `returns_every_get_route_in_walk_when_resolver_lists_it`
  fails with `missing_from_walk=['terms'] extra_in_walk=[]`. The other three pass.
- Red 2, `KNOWN_DIFFERENCES` cleared: `returns_row_answer_when_caller_gets_walked_page` fails with
  eight mismatches: visitor, patient, clinician and admin `favicon.ico` (302 `/static/favicon.svg`);
  patient, clinician and admin `sign-in` (302 to home); admin `admin-console/appointments/new/service`
  (302 `/admin-console/appointments/new`). The re-send and difference-only tests pass trivially,
  as expected.
- `ruff check` and `mypy` on the new file: clean. `scripts/comment_cap.py` on both new files:
  clean. No `Any`, `cast`, `# type: ignore` or `# noqa` in the new file.
- Requests: walk test 46 GETs x 4 callers = 184, plus 6 setup requests (one GET `/sign-in` and one
  login POST for each of the three signed-in callers), 190 in all. Re-send test 8 GETs plus the same
  6 setup, 14 in all. Resolver test none. DEBUG-on counts not measured (L10).
- Rate counters: visitor address sees 46 walk GETs and 8 re-send GETs; the walk's limit for
  `SCHEDULE` is 1200 per address (`scheduling/domain/rate_limit_rules.py:38`), for `SEARCH` 120 per
  address (`:36`). Counters are `RateLimitHit` rows in the test transaction, rolled back per test.
