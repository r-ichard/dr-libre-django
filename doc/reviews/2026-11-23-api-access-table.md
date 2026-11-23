# Review: access table for the /api/v1 routes (task 26b3, items 1 and 2)

Reviewed: `git diff main...HEAD` on `fabro/run/01M83ZDSN1SX4PTXP1N08C9F85`, 3 files, all added:
`doc/plans/2026-11-23-api-access-table.md` (plan), `scheduling/views/test_api_access_rows.py`
(table data, 187 lines), `scheduling/views/test_api_access_table.py` (two tests, 51 lines).
No product code, no migration, no change to `drlibre-specs.md`.

## Read

- Table block: one sentence: a frozen `AccessRow` list of 27 `(method, route, four statuses,
  basis)` rows in URL order, read by nothing at runtime. Confirmed at a glance; the ANY row
  is `^api/v1/`, matching `drlibre/urls.py:117`.
- Walker block: one sentence: walk the resolver, keep `api/v1/` and `^api/v1/`, key each route
  by the declared handler methods (`get`, `post`, `put`, `patch`, `delete`) or `ANY`. Traced:
  `pattern.callback.cls` and `HANDLER_METHODS`, `test_api_access_table.py:14-33`.
- Two tests: one sentence each. Confirmed at a glance.

## Checks run by the reviewer

- `uv run --env-file .env.example pytest scheduling/views/test_api_access_table.py` with
  `DEBUG=true` (the published-key startup refusal otherwise): 2 passed in 0.15 s.
- In-memory set comparison (no file edited): walked keys 27, table keys 27, difference both
  ways empty.
- Red, in memory: dropping the `POST api/v1/jobs/reminders` row gives unlisted
  `[('POST', 'api/v1/jobs/reminders')]`; adding a stale `GET api/v1/no-such-route` row gives
  removed `[('GET', 'api/v1/no-such-route')]`. Both tests would fail as the plan says. The
  history has no red-stage commit, so this is the only evidence of red.
- Cited code, read: `use_cases/sign_in.py:58` returns `Failure.unauthenticated()`;
  `use_cases/sign_in_link.py:31` is the `REFUSAL` constant (`invalid_input`);
  `domain/waitlist_rules.py:94` `authorize_join`; `use_cases/waitlist.py:106` refuses non-admins
  on offer; `views/failure_response.py:95-100` maps `MethodNotAllowed`/`NotFound` to 404,
  `NotAuthenticated` to 401, `PermissionDenied` to 403; `views/access.py:32-38` `roles()` is a
  role-set check, so a patient on a `roles(CLINICIAN, ADMIN)` route gets 403;
  `views/api_view.py:23,67-70` `ApiView` uses session auth and `NotFoundView` is `public()`.
- Prove commit `267ee69` changed only `test_api_access_table.py` (+`assert walked`). Test-only
  after verify, allowed by §13 item 7. No product or migration line changed.
- Commits: `91552f3` write (tests + data), `393779d` check, `267ee69` prove. Plan commits
  `43ded1c`, `9e93841`. No product line in any of them.

## Findings

Severity: `important` = a bug the change adds; `nit`/later = minor or data.

1. **later** `scheduling/views/test_api_access_rows.py:1` file name. The plan said
   `scheduling/views/api_access_table.py`, "not collected by pytest". The name is
   `test_api_access_rows.py`, so pytest collects it (no tests in it) and §10 reads it as a test
   module. Risk: none at runtime; misleads the next reader. Fix: rename to
   `api_access_rows.py` and change the import at `test_api_access_table.py:7`.

2. **later** `scheduling/views/test_api_access_rows.py:23-186` cells. Only the cited lines
   listed above were checked. Cells such as `HealthView` AllowAny, `LinkView` 202, `ResendView`
   200 and `VerifyView` 201 were not traced in this run. Risk: a wrong cell passes until item 3
   walks it. Fix: none now; item 3 owns the cells. Item 3 must also build the caller with a
   password and the owned record in the state the cell assumes (plan Risks).

3. **later** `scheduling/views/test_api_access_rows.py:36-44` `POST api/v1/auth/link/verify`,
   visitor cell 200. A visitor is a caller with no account and no link (§2, §7). The cell means
   "a caller holding a valid link", which is a passwordless patient. Risk: a reader takes the
   visitor column as the anonymous caller. Fix: say so in the docstring at line 1-3 or in the
   basis text at line 43.

4. **later** `doc/handover.md:28` says "about 4900 tests". The check stage passed 5278. Plan
   block "Files deliberately not touched" asked for a check. Risk: a stale recipe. Fix: update
   the count in the commit that changes the state, or leave as "about" if the orchestrator
   accepts it.

5. **later** `scheduling/views/test_api_access_table.py:14-33` the walker duplicates about ten
   lines of `_api_views` in `test_api_bodyless_writes.py` (plan accepted this). Risk: two copies
   drift. Fix: the owner's later extraction to `scheduling/views/api_routes.py`.

6. **later** Time, measured here: the two tests run in 0.15 s on this shared sandbox. The
   orchestrator measures on a quiet machine. Not a blocker (§ budget rule).

No `important` finding. No swallowed error, no type escape, no authorization in the diff, no
audit or transaction in the diff, no double-booking surface, no specification change.

## Left for the orchestrator

From the plan, "Not in this run" and the task items outside the slice:
- Item 3: the walk that sends requests to each route, own record and another user's record,
  with password, owned record state, and session/token sharing (plan "Costs and counts": about
  122 requests).
- Item 4: the access section in `doc/security-review.md`, generated by a Makefile command, and
  the test that compares it to the table.
- `/fhir` rows and token columns (another run; §15).
- Not run by the reviewer: `make mutate`, `make fhir-validate`. The check stage ran
  `make lint`, `make test` (5278 passed) and `make gate`; those are the only gates I can cite.

## For the owner

1. **§14 has no row for `POST /waitlist/{id}/offer`.** §5.8 gives "Manual offer" to admins, and
   `use_cases/waitlist.py:105-106` refuses non-admins, so the table follows §5.8 (admin 200,
   others 403). Decide whether §14 should list it.
2. **§4 does not give a status for an undeclared method or an unknown `/api/v1` path.** The code
   answers 404 `not_found`, because `MethodNotAllowed` maps to `not_found`
   (`views/failure_response.py:95`). The ANY row records the code's answer. Decide whether §4
   should say 404 or 405.
3. **§14 `POST /auth/link/verify` says "Link holder" and §7.3 says patients only.** The table
   gives a clinician or admin 400 `invalid_input` (`use_cases/sign_in_link.py:31`), not 401 or
   403. The spec gives no status for that case. Decide whether the answer should be 403.

## Blocking

None.

## Later

See findings 1 to 6 above.
