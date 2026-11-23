# Task 27c item 2: smoke step runner, `make smoke`, health and start-page steps

Slice: items 1 to 2 of the smoke list (step runner, `make smoke`, health step, start-page step). The booking flow is under `## Not in this run`.

## Focal point

`scripts/smoke.py`: a step runner. Each step runs in order. The first step that raises `SmokeFailure` stops the run, the runner prints `Smoke step failed: <step name>: <reason>` to stderr and returns 1. Steps are plain functions that take a `fetch` callable, so the unit tests replace only the HTTP boundary.

## Blocks and one-sentence plans

- `scripts/smoke.py` `SmokeFailure` (exception) and `run_steps(steps) -> int`: run in order, stop at the first `SmokeFailure`, name the step, return 1; return 0 when all pass.
- `scripts/smoke.py` `fetch(path) -> tuple[int, str]`: GET `BASE_URL + path` with `urllib.request`, 10 s timeout; `OSError` (refused, timeout) becomes `SmokeFailure` with the reason, no body echoed.
- `scripts/smoke.py` `health_step(fetch)`: GET `/api/v1/health` must answer 200 and JSON `{"status": "ok"}`.
- `scripts/smoke.py` `start_page_step(fetch)`: GET `/` must answer 200 and contain a link to `/providers/<uuid>` (the demo provider the start page lists).
- `scripts/smoke.py` `main()`: build the step list `[("health", ...), ("start page", ...)]`, call `run_steps`, exit with its code. `BASE_URL = "http://127.0.0.1:8000"` constant; no CLI arguments.
- `Makefile`: new `smoke` target running `python3 scripts/smoke.py`, added to `.PHONY`. Not a dependency of `test`.
- `scripts/test_smoke.py`: unit tests of the runner and the two steps, with a fake `fetch`.

## Files, in order

1. `scripts/test_smoke.py`: the red tests (below).
2. `scripts/smoke.py`: signatures only, bodies `raise NotImplementedError`, so the red run fails by the expected error, not by an import error (§10). Then the real bodies at green.
3. `Makefile`: `smoke` target and `.PHONY` entry.

Deliberately not touched: `README.md` (item 1, another run), `doc/handover.md` (orchestrator's), `compose.yaml`, `drlibre-specs.md`, `doc/backlog/27c-readme-smoke-test.md` (orchestrator updates it), everything under `scheduling/`, `drlibre/`.

## Invariants and blast radius

- Read-only slice: both steps are GETs. The smoke run writes nothing to the stack, creates no hold, no appointment, no audit entry.
- Loopback only: `BASE_URL` is a constant at 127.0.0.1; no host or port from the environment or argv.
- No secrets in this slice. Failure messages carry the step name and a short reason only; a response body is never echoed (the start page body is large and may later hold codes).
- Blast radius: a new script, a new unit-test file that `make test` collects (fast, no network, no database), one Makefile target. `make lint` (ruff, mypy strict) and `make gate` (comment cap, size cap, escape hatches) cover the new files; no `Any`, `cast`, bare `type: ignore` or bare `noqa`.
- The live `make smoke` run needs a running, seeded stack. The sandbox has no Docker; the orchestrator runs it on the host. This run proves the runner by unit tests only.

## Trust boundaries

- Response from the local stack (untrusted input): status code checked exactly; health JSON parsed with `json.loads` inside a try and compared to the exact value `{"status": "ok"}`; start page matched by one regular expression on `href` values, never executed or rendered.
- Authorization: none needed; both routes are public (health: `AllowAny`; start page: visitor).
- The script reads no credentials and sends no request body.

## Domain entities (CLAUDE.md §3 vocabulary)

- Visitor: the smoke client, unsigned, reads the start page.
- Clinician (public word "provider"): the demo provider the start page must list. The step asserts a `/providers/<uuid>` link, not a name.
- Hospital, Patient, Appointment: not used in this slice.

## Failing tests to write first (behaviour names, expected values in words from the task and the health view)

In `scripts/test_smoke.py`:

1. `returns_zero_when_every_step_passes`: two passing steps give exit code 0 and nothing on stderr.
2. `stops_at_first_failing_step_and_names_it`: step two raises `SmokeFailure("answered 500")`; step three is never called; exit code 1; stderr contains `Smoke step failed: two` and `answered 500`.
3. `returns_one_when_first_step_fails`: step one fails; stderr names step one.
4. `raises_failure_when_health_status_is_not_ok`: fetch answers `(200, '{"status": "down"}')`; `health_step` raises `SmokeFailure`.
5. `passes_when_health_answers_ok`: fetch answers `(200, '{"status": "ok"}')`; no exception.
6. `raises_failure_when_health_answers_not_200`: fetch answers `(503, '{"status": "ok"}')`; `SmokeFailure`.
7. `raises_failure_when_stack_refuses_connection`: `fetch` against a port that was bound and closed just before; `SmokeFailure`, and the message does not contain a traceback.
8. `passes_when_start_page_links_a_provider`: `(200, '<a href="/providers/<uuid>">')` with a real UUID; no exception.
9. `raises_failure_when_start_page_lists_no_provider`: `(200, '<p>No providers</p>')`; `SmokeFailure`.
10. `raises_failure_when_start_page_answers_not_200`: `(500, '<a href="/providers/...">')`; `SmokeFailure`.

Red proof: each test must fail with `NotImplementedError` from the stub (or the assertion, after stub bodies return wrong values). Then, at green, break the runner on purpose (continue after failure) and confirm test 2 turns red for the right reason, then restore.

## What I will not do

- No retry, no polling, no wait-for-stack loop (the orchestrator starts the stack first).
- No argparse, no URL or port configuration, no environment variable.
- No HTTP client dependency: `urllib.request` only.
- No generic step framework or base class: a list of tuples and a function.
- No edits to `scheduling/`, `drlibre/`, templates, or the specification.

## Open points for the red stage (look up, do not guess)

- The start page's provider link markup. A grep of `scheduling/templates` and `search_page.py` found no literal `/providers/`. Read the search-results component the start page (`drlibre/urls.py:120`, `SearchPage`) renders, and assert the href it really emits. If the link is built from a template tag, the regex follows that output.
- The health view: `scheduling/views/health.py` returns `{"status": "ok"}` with 200, read directly.

## Not in this run

- Item 2 step 3: visitor holds a free slot through `/api/v1` (`/api/v1/slots`, `/api/v1/booking/holds`, body `HoldRequest` in `scheduling/views/hold_schemas.py:33`). Needs the seeded appointment type and clinician ids.
- Item 2 step 4: read the verification code from the smtp4dev API on 127.0.0.1:8025. The API route and message shape are not in this repository; confirm against `rnwood/smtp4dev:3.16.1` in the container before writing the step.
- Item 2 step 5: `POST /api/v1/booking/holds/<id>/verify`, `GET /api/v1/appointments` lists the new patient's appointment, `POST /api/v1/appointments/<id>/cancel` (routes in `drlibre/urls.py:104-108`).
- Item 1 (README) and the orchestrator's `make smoke` run against a fresh stack.

## Architect review

Verdict: approve. Reviewed against CLAUDE.md §1, §2.5, §10, §11, §8, §9 and the task file.

- Ladder: a stdlib script, one Makefile target, one test file, no dependency, no base class, no config. Smallest sufficient slice of item 2. Placement matches existing `scripts/` precedent (`scripts/test_audit.py` and others are already collected by `make test`).
- Slice: the booking flow (steps 3 to 5) is deferred under `## Not in this run`. The slice runs as `make smoke` on its own and leaves the product whole. Item 2 is not complete after this run: its done-when needs the full flow, so a second run must finish it.
- Facts verified in the repo: `scheduling/views/health.py` returns `{"status": "ok"}` with 200 (`AllowAny`). The start page is `SearchPage` at `/` (`drlibre/urls.py:120`). `scheduling/views/pages/search_context.py:141` emits `provider_href = /providers/{id}`, so the `/providers/<uuid>` regex is grounded. `mypy .` in `make lint` is strict and covers `scripts/` (only `comment_cap.py` excluded).
- Test-first: ten named behaviours with expected values; covers the error paths (non-200, bad JSON or wrong status, refused connection with no traceback, failing step stops the run and is named). Red proof and the deliberate break at green are specified.
- Security: both steps are GETs to a constant loopback URL; no argv, env or request body; response body never echoed; JSON parsed in a try. Authorization is not needed (both routes public). Nothing sensitive logged.
- Architecture: no ORM, no clock, no domain code touched; the script is outside the layers in §8, which is correct for a standalone tool.

Points the red stage must settle, not blocking:
1. Runner contract. `run_steps(steps)` takes no `fetch`, yet the plan says steps "take a fetch callable". Pick one: either `run_steps` takes `fetch` and passes it, or steps are zero-argument closures built in `main()`. Test 1 and test 2 depend on this choice; write the choice into the test file, not only into the code.
2. Error type. The plan does not say how `run_steps` catches `SmokeFailure` versus other exceptions. Catch only `SmokeFailure`; an unexpected exception is a broken invariant and should propagate (§9), not be reported as a step failure.
3. Test 8 uses `/providers/<uuid>` for a real provider. The red stage should confirm that the demo start page (seeded data) emits that link, or document that the check is markup-only.
4. Plan's own `## Open points` list still asks the red stage to read `SearchPage`; that look-up is done above and needs no repeat.
