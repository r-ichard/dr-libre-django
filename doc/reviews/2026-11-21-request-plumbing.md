# Review: task 04 request plumbing (2026-11-21)

Scope: `git diff main...HEAD`, 28 files. Gates in the run log pass (lint, 496 tests, gate). Commits `verify_green`..`prove` touch tests, test helpers and `probe_views.py`/`probe_urls.py` only (test-only views), so no mutation left behind.

## Confirmed at a glance
- Failure contract (`scheduling/domain/failure.py`): pure, ten codes, one constructor per code.
- Mapper (`scheduling/views/failure_response.py:47-90`): one body shape, generic 500, trace logged.
- Middleware (`scheduling/views/middleware.py:20-40`): sane id or uuid, one clock read, route pattern logged, never path or query.
- Closed by default (`access.py`, `settings.py`), health declares `AllowAny`.
- No new dependency. No type escape hatches.

## Traced
- Logging path: `json_logging.py:21-38` is an allowlist of record fields, exception text dropped, only frame source lines kept. Holds.
- `django.request` silenced, middleware writes the single request line. OK.

## Findings
1. **Blocker.** Missing file `doc/adr/0004-failure-contract-and-request-context.md`. Task item 1 requires the wire shape recorded in an ADR; plan lines 18, 129, 237 promise it; diff has no `doc/adr` change. The screens and the FHIR `OperationOutcome` mapper are to read it, and the 404 transport judgement (wrong method / unknown path as `not_found`, bad body as `invalid_input`) is recorded nowhere durable. Fix: write the ADR from the plan's "Wire shape" section.
2. Low, `json_logging.py:28`: `message` is `str(record.msg)`, so `logger.info(f"... {email}")` by a later author leaks; the allowlist covers fields, not the message text. Fix later: lint rule or review check against f-strings in log calls.
3. Low, `schemas.py:20`: `StrictSerializer` rejects unknown keys at top level only; nested serializers are not strict. Fix when the first nested schema appears.
4. Low, `probe_views.py`, `probe_urls.py`: test-only views live in the product package. Move to a test-only location or `conftest` when a second probe user appears.
5. Low, `settings.py` / `middleware.py`: a 500 or 404 outside `/api/v1/` under `DEBUG` still gets Django's technical page. Item 2 of the task covers API requests only; revisit when server-rendered screens land.
6. Info: DRF `Throttled` and other `APIException` subclasses fall to generic 500; fine until throttling exists.

## Blocking
- Missing ADR `doc/adr/0004-failure-contract-and-request-context.md` (task item 1, plan promise). **fixed**: ADR written from the plan's wire shape and transport judgement. No test: documentation only, nothing executable to fail.

## Later
- Log message text not guarded against interpolated sensitive data (finding 2).
- Nested serializers not strict (finding 3).
- Probe views inside product package (finding 4).
- Non-API paths under `DEBUG` (finding 5).
- Non-listed `APIException` types map to 500 (finding 6).

## Second pass (after address, 2026-11-21)

ADR `doc/adr/0004-failure-contract-and-request-context.md` now exists (commit aaa752b, 62 lines). Blocker closed. Re-read middleware, mapper, formatter, schemas, access: no new defect. `probe_views.py` change between `verify_green` and `prove` is test-only views, no product line. No escape hatches in new code (existing `noqa` with codes are outside this diff).

New Later items:
- `middleware.py:28`: an exception escaping outside DRF (non-API view, middleware error) gets no `X-Correlation-Id` header or request line from Django's own 500 path. Revisit with server-rendered screens.
- `schemas.py:19`: unknown-field names from the client are echoed in `details`; harmless (JSON-encoded) but keep out of logs.

## Blocking
- none
