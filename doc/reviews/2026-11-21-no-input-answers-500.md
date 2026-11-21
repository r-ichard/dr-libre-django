# Review: task 17a, no input answers 500

Diff read: `git diff main...HEAD` (8 files). Stage trace: after `verify_green` only `prove` (tests only) and `refactor` (`booking_schemas.py` tidy, behaviour same) changed files. No mutation left behind.

Plan in one sentence per block, confirmed at a glance: sign-in email check (`sign_in.py:87`), date range in `OffsetDateTimeField` (`booking_schemas.py:31`), page cap (`booking_schemas.py:59`), size/field/depth refusal in `ApiView.initial` (`api_view.py:32`, `input_limits.py:16`), Django limits for pages (`settings.py:108`). Needed a trace: `json_depth` string/escape state machine (correct: escape flag resets after any byte), and that `request.body` is read before DRF parsing (fine, DRF reuses it).

## Findings

1. **Blocker, promised test missing.** `scheduling/views/test_hostile_input.py:104`. Task item 5 and the plan require hostile values "with and without a session" (actors patient, clinician, admin). The test uses one anonymous `Client`. Every authorized route returns 401/403 before reaching its parsing, so signed-in handlers (appointments, waitlist, time off, availability, admin writes) are never sent hostile input. Issues #13 and #14 were reported on signed-in routes. Fix: loop the existing session helpers in `views/conftest.py` over the same requests; page POSTs with CSRF as a browser sends them.
2. **Blocker, promised test missing.** Plan: hypothesis property test, and the test deliberately skips routes containing `(?P` (`test_hostile_input.py:55`), including the `^api/v1/` catch-all the plan said to keep. No `hypothesis` import anywhere in the diff. Task item 5 says "a property-based test fits"; the plan committed to it. Fix: add the sampled-route/actor/recursive-JSON property test as planned, and cover the catch-all by substituting `x`.
3. **Important, plan vs code mismatch (item 6).** The plan's limits table says body 100 KiB, 100 fields, dates 1900 to 2200, `BoundedJsonParser`, `domain/input_limits.py`, `failure_from_exception` mapping. Code has 1 MiB, 200 fields, years 2000 to 2099, a check in `ApiView.initial`, no parser, no domain module. Item 6 asks the plan to state the limits and where enforced; the plan states ones that are not the shipped ones. Fix: rewrite the table to the shipped values and places.
4. **Important, `make mutate` not exercised on new logic.** `json_depth` and the range check are pure but live in `views/`, outside `scheduling/domain`, so `make mutate` proves nothing about them. Plan promised domain functions with mutation-clean tests. Mitigated: boundary tests exist (at-limit and one-past nesting). Fix: move `json_depth` and the date bounds to `scheduling/domain/input_limits.py`.
5. **Low, `input_limits.py:20`.** `int(CONTENT_LENGTH)` raises `ValueError` (500) on a non-numeric header such as `abc`; the hostile test cannot send it (test client sets the header itself). Fix: treat unparsable as invalid_input field `body`, add a test with a raw `CONTENT_LENGTH`.
6. **Low, `input_limits.py:17`.** Field count is `"&"` count; `;`-free but a query of 200 empty `&` counts as fields. Over-strict only, harmless. Chunked body with no `Content-Length` is bounded by Django's `DATA_UPLOAD_MAX_MEMORY_SIZE` in `request.body` (raises `RequestDataTooBig`); confirm it maps to the contract's `invalid_input`, not a bare Django 400. Plan test "chunked" absent.
7. **Low, `input_limits.py:1`.** Docstring starts "Task 17a:"; task numbers in code rot. Reword.
8. Authorization, audit, double booking, dependencies: unchanged; no new dependency; no type escape hatch in product code. `test_hostile_input.py:84` uses `# type: ignore[call-overload]` with a code, allowed.

## Blocking

- Hostile test does not run with sessions (patient, clinician, admin), required by item 5 (`test_hostile_input.py:104`). **fixed**: `returns_no_500_when_any_route_gets_hostile_input[ANONYMOUS|PATIENT|CLINICIAN|ADMIN]`. Red for the right reason: as patient it found real 500s, GET on the POST-only pages `/patient/notifications/read-all`, `/patient/notifications/<id>/read`, `/patient/waitlist/<id>/accept` (`PageView.get` inherited, no template or a `TypeError` on the path id). Root cause fixed in `PageView._guarded_dispatch`: GET on a page without `get` or template answers 405.
- Promised hypothesis property test absent; routes with `(?P` including the API catch-all are skipped (`test_hostile_input.py:55`). **fixed**: `returns_no_500_when_any_actor_sends_generated_json_to_any_route` (hypothesis: actor, route, method, recursive JSON); the `^api/v1/` catch-all is now covered through a path under it, only the static file server is skipped.

## Later

- Rewrite plan limits table to shipped values and enforcement points (finding 3).
- Move pure limit logic into `scheduling/domain/input_limits.py` so `make mutate` covers it (finding 4).
- Non-numeric `Content-Length` answers 500 (finding 5); chunked-body test (finding 6).
- Drop "Task 17a" from the module docstring (finding 7).

## Second read (after `address`)

Both blockers confirmed fixed: `test_hostile_input.py:125` runs the four actors, `:149` is the hypothesis property test, static file server the only skip (`:27`). The `address` commit changed product code (`page_view.py:75`, GET on a POST-only page answers 405); that stage is after `prove`, so it is a fix, not a mutation left behind. No new blocker.

Still open, none blocking:
- Plan table (`doc/plans/2026-11-21-no-input-answers-500.md:11-16`) states 100 KiB, 1900 to 2200, `BoundedJsonParser`, `domain/input_limits.py`; shipped is 1 MiB, 200 fields, depth 20, years 2000 to 2099, `ApiView.initial` check in `views/input_limits.py`. Task item 6 wants the real limits in the plan: rewrite before merge.
- `input_limits.py:19` `int()` on a non-numeric `Content-Length` raises; WSGI servers normally reject it first.
- Pure limit logic outside `scheduling/domain`, so `make mutate` does not cover it.
- Docstring `input_limits.py:1` names "Task 17a".

## Blocking

None.
