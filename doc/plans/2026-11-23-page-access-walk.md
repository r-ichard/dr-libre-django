# Plan: page access walk over GET rows without a record (task 26b3, item 3, part 1)

Slice: items 1 to 3 of task 26b3, pages only, GET only. One test walks every table row whose route
names no record and that answers a GET, as each of four callers (visitor, patient, clinician,
admin), and checks the answer of the row. Sign-out, the form-only routes and the record-named rows
are left for later runs (see `## Not in this run`).

## Focal point

The access table (`scheduling/views/pages/test_page_access_rows*.py`) already says what each
caller gets for each page. Nothing yet sends a request and compares. This run adds the comparison
for the GET rows and records every place the product answers differently, without changing the
table.

## Measured facts (read-only introspection, no request sent)

- Table rows: 113. Rows with `names_record` false: 52, of which 1 is `style` (debug only).
- Form-only or sign-out among the 51 non-debug, non-record rows: `sign-out`, `sign-in/email-link`,
  `patient/notifications/read-all`, `admin-console/appointments/export`,
  `admin-console/settings/reminders`. These answer 405 to a GET. They are excluded.
- Walked routes with DEBUG off: 51 - 5 = **46**. With DEBUG on: 47 (`style` included).
- Requests: 46 routes x 4 callers = **184 GETs**. Setup: `signed_in_patient` sends a `GET /sign-in`
  and a login POST for each of the 3 signed-in callers, so **6 setup requests**. Total **190**
  with DEBUG off, 194 with DEBUG on. The walk creates one world and four clients, and shares them
  across all rows (task item 5).
- Rate limits (`scheduling/domain/rate_limit_rules.py`, `scheduling/use_cases/read_limits.py`):
  a signed-in caller is counted by user, a visitor by network address. The walked pages with
  `read_scope` (SCHEDULE, 1200 per hour per counter) are hit at most once per GET. Each counter
  sees at most 46 requests in the walk, far under 1200. Search (120 per hour per address) would be
  hit only by a search with a query; even if `/` took one hit per GET, 46 stays under 120.
  Counters live in `RateLimitHit` rows, so each test's transaction rolls them back.
- Wall time: not measured. The green stage measures it and reports the number.

## Blocks and files, in order

1. **`scheduling/views/pages/test_page_access_table.py`**: rename `_all_rows` to `all_rows` (two
   call sites). The walk needs the full row list, and importing a private name across modules is
   unclean. No rows change.
2. **`scheduling/views/pages/test_page_access_walk.py` (new, one file, about 150 lines)**:
   - `LEFT_FOR_LATER_RUN`: the five routes above, one comment line saying why.
   - `walked_rows() -> list[Row]`: rows of `all_rows()` with `names_record` false, not in
     `LEFT_FOR_LATER_RUN`, and `debug_only` rows only when `settings.DEBUG` is on.
   - `answer_of(response) -> str`: 200 gives `ok`, 403 `forbidden`, 404 `not-found`, a 302 or 303
     to a path starting `/sign-in` gives `sign-in`, any other redirect gives `"<status> <Location>"`.
     Other statuses give the status code. The strings compare equal to `Answer` (StrEnum).
   - `expected_answer(row, caller) -> Answer`: a `match` over the four caller names, returning
     the row's field.
   - `KNOWN_DIFFERENCES: dict[tuple[str, str], str]`, keyed by (route, caller), value = the
     product's answer, with a comment that each entry is an owner question.
   - Test `returns_every_get_route_in_walk_when_resolver_lists_it`: the set of walked routes must
     equal the set of non-record, non-debug table routes whose view answers GET. The resolver
     answers that: `resolve(path).func.view_class`, `is_form_only`, and `"get" in
     http_method_names` for plain views. The favicon lambda counts as GET.
   - Test `returns_row_answer_when_caller_gets_walked_page`: one world, four clients. For each
     walked row and caller: GET, `answer_of`, and compare with `KNOWN_DIFFERENCES` if the pair is
     listed, else with `expected_answer`. Collect every mismatch, then assert one list, so a
     failure shows all pairs at once. One test, one walk.
   - Test `returns_product_answer_when_pair_is_known_difference`: each KNOWN_DIFFERENCES pair
     sends its request again and must give the recorded answer, so a change in either direction
     fails.
   - Test `returns_known_difference_only_when_answer_differs_from_row`: each recorded product
     answer differs from its row's answer, so a pair cannot stay listed after the product matches
     the table.
   - Module docstring: "Section 12.3: each page that answers a GET without a record in its address
     gets, from each caller, the answer its row in the access table gives. Pairs the product
     answers differently are listed with the product's answer." No task number.
3. **`doc/plans/2026-11-23-page-access-walk.md`** (this file) and **`scratch/plan.path`**.

Not touched: product code (`scheduling/views/**`, `drlibre/urls.py`), every row file, the
`Row` dataclass, `drlibre-specs.md`, `doc/adr/0012-page-access-readings.md`, `doc/security-review.md`,
the Makefile, the gate scripts, `doc/handover.md` (no product state changes).

## Red, then green

1. **Red for the walk's own list first.** Write the new file. `walked_rows()` first omits one row
   (`terms`). Run `returns_every_get_route_in_walk_when_resolver_lists_it`. It must fail with
   `missing_from_walk=['terms']`. Then restore the list.
2. **Red for the walk.** Run the walk with an empty `KNOWN_DIFFERENCES`. It must fail and list the
   mismatches. Predicted from code, to be confirmed by this run and not assumed:
   - `favicon.ico`, all four callers: the lambda at `drlibre/urls.py` redirects 302 to
     `/static/favicon.svg`; the table says `ok`. ADR 0012 reading 6 calls that OK; the redirect is
     not a page, so it is a listed pair and an owner question.
   - `sign-in`, patient, clinician and admin: `SignInPage` redirects a caller with a session to
     their home (`scheduling/views/pages/sign_in.py:71-72`); the table says `ok` for every caller.
     That contradicts ADR 0012 reading 2 and section 12.3.
   - Any other pair the run lists is recorded the same way; none is hidden by a filter.
3. **Green.** Fill `KNOWN_DIFFERENCES` with exactly the pairs red showed, each with the product's
   answer string. Rerun: all tests pass.
4. **Prove the difference guard.** Change one recorded answer by hand, confirm the
   product-answer test fails, restore.
5. **Gates.** `make lint` (ruff, mypy strict), `make test`, `make gate`. Report the walk's wall time
   and whether any test in the file is over the function size cap.

## Invariants and boundaries

- No product behaviour changes. The walk only reads responses.
- Authorization: callers are real sessions from the login API (`signed_in_patient`), not
  forged cookies. Each answer checked is the server's answer.
- Input: the request paths are built from the table's route strings with `path_of`; no caller
  input reaches the walk.
- Rate limits: the sums above; no test resets a counter; each test's transaction rolls back its
  `RateLimitHit` rows.
- Audit log: a GET writes none; not affected.
- Vocabulary (§3): Visitor, Patient, Clinician, Admin, User, Session.

## Not in this run

- Form-only routes and sign-out (the five routes in `LEFT_FOR_LATER_RUN`): POST walk with the
  cross-site token and `Origin`, as in the form walks. Note for that run: the sign-out row says
  `ok` but the view answers 405 to a GET, and ADR 0012 reading 5 says redirect; the table and the
  ADR disagree.
- Record-named rows: one own record and one other user's record each, per task item 3.
- API and FHIR routes (`api/`, `fhir`): other test files, another run.
- `doc/security-review.md` access section and its consistency test (task item 4).
- The review's "For the owner" section for the KNOWN_DIFFERENCES pairs: written by the review
  stage from this run's output, not by this plan.
- `make fhir-validate`, `make mutate`: outside this slice.

## Architect review

Verdict: approve. Checked against the table, the URL configuration and the rate-limit rules.

Counts confirmed from the source: 113 rows, 61 with `names_record=True`, 52 without, one of those
`style` (debug only), so 51 walkable non-debug rows, 5 excluded, 46 walked. 46 x 4 = 184 GETs,
plus 6 setup requests from the two sign-ins per signed-in caller. Setup is correct only if the
clinician and admin callers also come from `signed_in_patient` or an equivalent helper; name it.

Notes for the green stage (none is a reason to revise):

1. `_all_rows` has three call sites in `test_page_access_table.py` (lines 33, 62, 68), not two.
   The rename still holds.
2. The request count leaves out the difference re-send test. It sends one GET per
   `KNOWN_DIFFERENCES` pair, about 5 to 8 more. State the per-test counts in the plan.
3. The resolver test compares walked routes with "routes whose view answers GET". State how
   it treats `LEFT_FOR_LATER_RUN`, and how it reads `http_method_names` for the favicon lambda,
   which is a function view with no `view_class`. Otherwise the test can fail for a reason the
   plan does not name.
4. Cost is "not measured". The task asks the plan to say what the walk costs. Give the green
   stage's measured wall time in the review; the request count above is the plan's share.
5. Scope and layer: one test file plus a rename, no product code, no spec edits, no new
   dependency. Test names follow `returns_X_when_Y`. The docstring names no task. The
   KNOWN_DIFFERENCES entries carry the owner questions through the review, as the task requires.
6. Predicted differences match the code: `favicon.ico` redirects 302 (`drlibre/urls.py:121`),
   and `SignInPage.get` redirects a signed-in caller home (`sign_in.py:71-72`), against the table's
   `ok`. The walk's red run must confirm these, as the plan says.
7. Security: callers are real sessions from the login API, no caller input reaches the walk
   beyond table strings, no sensitive data is logged. Visitor counts by address stay at 46 against
   a limit of 120 for search and 1200 for schedule.

## Write stage: measured

- Walked routes: 46 (DEBUG off). Walk test: 46 x 4 = 184 GETs, plus 6 setup requests from the
  three `signed_in_patient` callers, 190 in all, 0.29 s.
- Re-send test: one GET per `KNOWN_DIFFERENCES` pair, 8 GETs, plus the same 6 setup requests, 0.02 s.
- Resolver test: no request, 0.11 s.
- Visitor GETs per test: 46 (walk), 8 (re-send), against 120 per hour for search by address.
- Deviations from the plan, both forced by the repository: `_all_rows` stays private
  (`conftest.py` rejects public functions in test modules), so the walk imports the private
  name and the table file is unchanged. Walk helpers are private for the same reason.
  `KNOWN_DIFFERENCES` values hold both answers, `(table answer, product answer)`, as the task asks.
- Recorded pairs (all table `ok`): `favicon.ico` for four callers (302 to `/static/favicon.svg`),
  `sign-in` for patient, clinician, admin (302 to each home), and
  `admin-console/appointments/new/service` for admin (302 to `/admin-console/appointments/new`).
