# Plan: task 04a, log and error path hardening (2026-11-21)

Sources read: task goal, `doc/reviews/2026-11-21-request-plumbing.md`, ADR 0004, `drlibre/settings.py`,
`scheduling/views/{middleware,json_logging,schemas,failure_response,probe_*,conftest}.py`,
`scripts/ensure_database.py`.

## Focal point
`LOGGING` in `drlibre/settings.py` plus `RequestContextMiddleware`. No new feature, no new dependency.

## Root causes
- `django.request` has `handlers: []`, `propagate: False`: no handler found, so Python's last-resort
  handler prints WARNING+ records as plain text (`Not Found: <path>`).
- `django.server` propagates to the JSON root, so runserver's per-request line becomes
  `{"message": "\"%s\" %s %s"}` (information-free; args are dropped by the formatter).
- A 500 raised outside DRF is converted to a response by Django *inside* our middleware, so the header
  is set, but the trace goes to the silenced `django.request` logger, and under `DEBUG` the body is
  Django's technical page (leaks code, settings, and the path).

## Blocks (one sentence each)
1. `drlibre/settings.py` `LOGGING`: `django.request` gets level `ERROR`, the `stdout` JSON handler and
   `propagate: False` (404/400 warnings dropped, the single request line stays with the middleware,
   every 500 gets one trace line; the formatter never reads `args`, so the path cannot leak);
   `django.server` gets a `logging.NullHandler` handler and `propagate: False` (request already logged once).
   Remove the stale comments, keep one "why" comment.
2. `scheduling/views/middleware.py`: after `get_response`, if the request path starts with `/api/v1/`
   and the status is 500 and the response is not JSON, replace it with
   `error_response(INTERNAL_ERROR_CODE, 500, INTERNAL_ERROR_MESSAGE, {}).render()` (reuses the one wire
   shape; runs inside the bound context so the id is in the body); header and request line follow as today.
   Non-API paths keep Django's handling (technical page under `DEBUG` is intended for dev until task 05;
   header and trace log are now guaranteed).
3. `scheduling/views/schemas.py` `StrictSerializer.to_internal_value`: replace the top-level check with a
   recursive `unknown_field_errors(serializer, data)` that walks nested `Serializer` fields and
   `ListSerializer` children (list index as key), so nested plain serializers are strict too; errors are
   nested dicts so `field_messages` yields `address.zip`, `items.0.sku`.
4. `scripts/ensure_database.py`: `require_port()` wraps `int(...)`, raises `SystemExit("DB_PORT must be a whole number")`
   (value not echoed); `main` calls it.
5. `doc/adr/0004-...md`: edit the Logs bullet and "Known gaps" (non-API 500 now traced, nested strict).
   Mark the review "Later" items 2-nested/5 closed only by commit message; do not rewrite the review.

## Files to touch, in order
1. `scheduling/views/probe_views.py`, `probe_urls.py` (test-only): add plain Django `def` views
   `/api/v1/probe/plain-explode` and `/pages/explode` raising `ValueError(SENSITIVE_MESSAGE)`; add
   nested schema + view `/api/v1/probe/nested-write`.
2. New tests (below), watched failing.
3. `drlibre/settings.py`, `middleware.py`, `schemas.py`, `scripts/ensure_database.py`, ADR 0004.

Not touched: `json_logging.py` (allowlist already holds; log message text guard stays a Later item),
`failure_response.py`, models, migrations, compose/Dockerfile, probe-views relocation (review finding 4,
no second user), DRF `APIException` mapping (finding 6).

## Failing tests first (names `returns_X_when_Y`)
- `scheduling/views/test_process_output.py` (new; runs a subprocess `python -c` that calls `django.setup()`,
  `setup_test_environment()`, uses the probe URLconf and `Client(raise_request_exception=False)`, so the
  real `LOGGING` applies; also emits one record on `django.server` as runserver does):
  - `returns_only_json_lines_when_requests_run_through_real_logging_config`: requests a 404 path, an
    identifier+query path, a 500 view, a 400 write; every non-empty line of stdout+stderr parses as a JSON
    object. Fails now: `Not Found: ...` line.
  - `returns_no_path_segment_query_or_email_when_requests_carry_them`: sent
    `/api/v1/patients/jane@example.test?token=x`; no line contains `jane@example.test`, `patients/`,
    `token=x`, `?`-query. Fails now.
  - `returns_one_request_line_per_request_when_django_server_also_logs`: exactly N lines with logger
    `drlibre.request` for N requests, none with logger `django.server`. Fails now.
- `scheduling/views/test_middleware.py`:
  - `returns_generic_json_500_with_correlation_id_when_plain_view_raises_on_api_path_under_debug`
    (`settings.DEBUG = True`): status 500, JSON `error.code == "internal_error"`, message "Something went
    wrong.", `error.correlation_id` equals header `cid-x`, body lacks the sensitive message. Fails now
    (technical page).
  - `returns_correlation_id_header_when_plain_view_raises_on_page_path`: header present on `/pages/explode`
    (pins the current behaviour).
- `scheduling/views/test_json_logging.py`:
  - `returns_trace_line_with_correlation_id_when_plain_view_raises`: a `drlibre`-formatted line with
    `exception.type == "ValueError"`, frame `probe_views.py`, correlation id `cid-x`, no sensitive text,
    for both the API and page path. Fails now (logger silenced).
- `scheduling/views/test_schemas.py` / `test_failure_response.py` (via nested probe view):
  - `returns_400_naming_nested_field_when_nested_object_has_unknown_key` (`address.zip`),
  - `returns_400_naming_indexed_field_when_list_item_has_unknown_key` (`items.0.sku`),
  - `returns_201_when_nested_body_has_only_known_fields` (guards over-rejection).
- `scripts/test_ensure_database.py`:
  - `raises_system_exit_naming_variable_when_port_is_not_a_number` (`DB_PORT=abc`, message names `DB_PORT`,
    does not contain `abc`); `returns_port_number_when_port_is_numeric`.

## Invariants and blast radius
Double booking, authorization, audit log: untouched (no model, use case, or permission code changes).
Blast radius: every request passes the middleware; the 500 replacement only fires on API paths with a
non-JSON 500. All existing 496 tests must stay green; `test_json_logging` fixtures attach to root, but
`django.request` no longer propagates: the new trace-line test must attach to that logger's handler
or use the subprocess instead.

## Trust boundaries
Request path, query, headers, body cross in. Path/query never reach a log field (allowlist, no `args`);
body keys are validated recursively by `StrictSerializer`; error bodies are fixed text. Correlation id is
validated by the existing `is_sane_correlation_id`. No authorization change.

## Vocabulary
Uses only request plumbing; `Patient` appears only as the example path segment. No domain entity read or written.

## Will not do
No new abstraction, dependency, or refactor; no log-message scrubbing; no Django 500 template; no
non-API DEBUG body change; no runserver banner changes (startup lines "Watching for file changes" are
written by management command to stdout, not by logging, and are outside this task's request check).

## Risks
Under `runserver` the reloader and banner still print non-JSON lines at start-up; the orchestrator's
leak check must look at request lines only. The ERROR-level `django.request` line has a fixed
message `%s: %s` (args dropped): low information, but frames and correlation id carry the value.

## Architect review
Verdict: approve.
- Ladder: smallest fix at the real cause (LOGGING config, one middleware branch, one recursive check, one port guard). No new dependency or abstraction.
- Items 1-6 of the task each map to a block and a failing test; the process-level test (item 3) runs the real `LOGGING` in a subprocess and asserts JSON-per-line, no path/query/email, one request line.
- Security: formatter reads an allowlist, never `args`, drops exception messages, so the ERROR line on `django.request` cannot leak the path. API 500 body is fixed text under `DEBUG`. DB_PORT value not echoed.
- Implementer notes (not blocking):
  1. In the subprocess test, also assert that the `django.request` 500 line carries `exception.type` and the correlation id, and that stderr is covered (handler `StreamHandler` writes to stderr, not stdout).
  2. Watch each new test fail for the stated reason before the fix (the `returns_correlation_id_header_when_plain_view_raises_on_page_path` test pins existing behaviour and will pass at once; say so in the red report).
  3. Frames include source lines (`frame.line`); acceptable, but a source line must never hold a secret.
  4. `django.security.*` and other `django.*` loggers still propagate to the JSON root; their messages can interpolate paths in rare cases (e.g. DisallowedHost, SuspiciousOperation). Out of this task's scope; list under Later in the review.
