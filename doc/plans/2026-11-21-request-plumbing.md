# Plan: task 04, request plumbing

Focal point: `scheduling/views/middleware.py`. It opens the request context (correlation id,
one clock instant), closes it, stamps the response and writes the request log line. Everything
else is a small piece it or the exception handler calls.

One sentence: a pure result/failure type in the domain, a context variable use cases can read,
and a thin view layer (middleware, exception handler, strict schema base, deny-by-default
permission, JSON log formatter) that renders every outcome in one body shape.

## Ladder

No new dependency. DRF already gives the exception hook, serializers (the request schema),
permission classes and content negotiation; Django gives middleware, `LOGGING`, `contextvars`
comes from the standard library. Nothing needs a new package (pydantic, structlog rejected: one
consumer each, DRF and `logging` cover it).

## Wire shape (recorded in ADR 0004)

Every non-2xx API response, and nothing else, has this body, plus header `X-Correlation-Id`:

    {"error": {"code": "<code>", "message": "<fixed text>", "correlation_id": "<id>",
               "details": {...}}}

`details` is always an object. Per code:

| code | status | details |
| --- | --- | --- |
| `invalid_input` | 400 | `{"fields": [{"field": "start", "message": "..."}]}` |
| `unauthenticated` | 401 | `{}` |
| `forbidden` | 403 | `{}` |
| `not_found` | 404 | `{}` |
| `conflict` | 409 | `{"resources": ["clinician", "room"]}` (clinician, patient, room) |
| `no_room_available` | 409 | `{}` |
| `no_clinician_available` | 409 | `{}` |
| `invalid_transition` | 409 | `{"current_status": "completed"}` |
| `has_dependents` | 409 | `{"dependents": ["appointments"]}` |
| `rule_violation` | 422 | `{"violated_rules": ["lead_time"]}` |
| `internal_error` | 500 | `{}`; message "Something went wrong."; only for the unexpected |

`message` is fixed text per code, never built from data. Nested validation paths join with
`.` (`address.city`); DRF `non_field_errors` stays that name.

Transport failures reuse the ten codes, with the table's status (decision for the architect to
accept or veto; it is the only judgement call here): unknown path and wrong method are
`not_found` 404 (no such route for that method; no `Allow` header); unreadable body and
unsupported media type are `invalid_input` 400 with field `body`; failed validation is
`invalid_input`; a missing access rule is `forbidden` 403 (no authenticators exist yet, so DRF
raises `PermissionDenied`; once a view declares authenticators the same path yields
`unauthenticated` 401). Any other exception, `APIException` included, is `internal_error`.
Content negotiation becomes always-JSON for every API view, so 406 cannot occur.

## Where each piece lives

Domain, pure (`scheduling/domain/`, new):
- `failure.py`: `FailureCode` (ten values), frozen `FieldMessage`, `FailureDetails`, `Failure`
  (code + details), one constructor per code so a code cannot carry another code's details,
  `Success[T]`, `type Result[T] = Success[T] | Failure`.
- `request_context.py`: frozen `RequestContext(correlation_id, now)` (`now` aware UTC;
  construction refuses a naive instant) and `is_sane_correlation_id` (1..64 chars,
  `[A-Za-z0-9._-]`; anything else, including empty, is regenerated).

Use cases (`scheduling/use_cases/`, new):
- `request_context.py`: `ContextVar`, `current_request_context()` (raises on an unbound read:
  invariant break), `bind_request_context(context)` context manager (used by the middleware
  and by use case tests, which need no HTTP to replace the clock).
- `test_no_wall_clock.py`: AST scan over `scheduling/domain` and `scheduling/use_cases` that
  fails on `datetime.now`, `utcnow`, `time.time`, `timezone.now`.

Views (`scheduling/views/`):
- `clock.py`: `now_utc()`, the one place the wall clock is read. Middleware calls it as
  `clock.now_utc()` so tests monkeypatch the module attribute.
- `middleware.py`: `RequestContextMiddleware`, first in `MIDDLEWARE`: choose id, take `now_utc()`
  once, bind, call the rest, set `X-Correlation-Id`, unbind in `finally`, log one line.
- `failure_response.py`: status table keyed by `FailureCode` (exhaustive), `failure_response(
  failure)` building body from the current context, `handle_exception` (DRF `EXCEPTION_HANDLER`;
  translates DRF/Http404 exceptions, returns the 500 response itself for anything else so
  Django's DEBUG page never renders; logs the unexpected one at ERROR with trace).
- `schemas.py`: `StrictSerializer` (rejects keys not among writable fields, naming each as
  `Unknown field.`), and `validate_body(schema_class, data) -> Result[Mapping[str, object]]`
  returning `Failure` instead of raising. No feature schema exists yet, so no typed boundary
  dataclass is derived here; the first feature builds its input type from its serializer fields.
- `access.py`: `DenyUnlessDeclared` default permission (always false). `HealthView` sets
  `permission_classes = [AllowAny]`.
- `negotiation.py`: `AlwaysJsonNegotiation` moved from `health.py`, set as the default class.
- `json_logging.py`: `JsonFormatter`.
- `probe_views.py` + `probe_urls.py`: views and urlconf used only by tests via
  `override_settings(ROOT_URLCONF=...)` (view declaring nothing, view raising with sensitive
  data, view returning each failure, view using the context twice, strict-schema POST view).

Project (`drlibre/`): `settings.py` (`MIDDLEWARE`, `REST_FRAMEWORK`, `LOGGING`), `urls.py`
(catch-all `re_path(r"^api/v1/", NotFoundView)` after health so unknown API paths run through
DRF and the one body shape, also under `DEBUG`; non-API paths keep Django's handling).

## Correlation id

Header `x-correlation-id` if `is_sane_correlation_id`, else `uuid4().hex`. On every response
(success, failure, unknown path, 500), in every error body, in the context, on every log line
emitted while the context is bound; `null` outside a request (the unbind resets the variable,
tested).

## Structured logs

`LOGGING`: one stdout handler, `JsonFormatter`, root level INFO, `disable_existing_loggers`
false. One JSON object per line: `time` (ISO 8601 UTC from `record.created`), `level`,
`logger`, `message`, `correlation_id`. Request line (logger `drlibre.request`, message
`request`) adds `method`, `route`, `status`, `duration_ms`.

Sensitive data out by construction, three rules in the formatter, not by reviewer discipline:
1. Allowlist: only the fixed keys and the four request keys are read from the record. Any
   other `extra=` field is dropped.
2. `record.args` is never interpolated; the raw message template is written. Django's and
   drivers' messages put paths, values and queries in args (`Not Found: %s`), so they never
   reach the line. Our own messages are constant strings.
3. Exceptions: type name and traceback frames (file, line, function, source line) only; the
   exception message and locals are dropped, because messages carry values (an
   `IntegrityError` detail names the email).
The request line is built from `request.resolver_match.route` (the pattern, `<unmatched>` when
none), never `path`, `get_full_path`, query, headers or body.

## Files, in order

1. `scheduling/domain/__init__.py`, `failure.py`, `request_context.py` (+ tests first)
2. `scheduling/use_cases/__init__.py`, `request_context.py`, `test_no_wall_clock.py`
3. `scheduling/views/clock.py`, `negotiation.py`, `access.py`, `schemas.py`,
   `failure_response.py`, `json_logging.py`, `middleware.py`, probe files
4. `scheduling/views/health.py` (drop negotiation class, add `AllowAny`), `drlibre/urls.py`,
   `drlibre/settings.py`
5. `doc/adr/0004-failure-contract-and-request-context.md`

Not touched: models, migrations, demo seed, `Makefile`, compose, scripts, pyproject (no
dependency), the audit writer and security headers (task 04a), `doc/backlog*.md`, `doc/retro.md`
(orchestrator). `settings.DEBUG` handling for `ALLOWED_HOSTS` unchanged.

## Invariants and blast radius

Double booking and audit log untouched (no model, no write). Server-side authorization: the
default flips from "anyone" to "nobody"; the only existing consumer, `HealthView`, declares
itself public, so health stays 200. Blast radius: every API request now passes the middleware
and the exception handler; a bug there fails every endpoint. Logging config changes all
process output format (also management commands and the test runner; `pytest` captures it).

## Trust boundaries

- Header `x-correlation-id`: untrusted; length and charset checked, else replaced.
- Request body and query: parsed by DRF, unreadable body becomes `invalid_input`; writes go
  through `StrictSerializer` (unknown fields refused, never silently dropped).
- Identity: nothing here reads identity from the payload; permission default is deny.
- Output: errors never carry exception text, class names, paths or stack frames, whatever
  `DEBUG`.
- Logs: allowlist, no args, no exception messages (above).

## Failing tests to write first (`returns_X_when_Y`)

Domain, `scheduling/domain/test_failure.py`, `test_request_context.py`:
- `returns_invalid_input_with_field_messages_when_invalid_input_constructor_is_called`
- `returns_one_constructor_per_code_when_failure_codes_are_listed` (ten codes exactly as the
  section 4 table)
- `returns_false_when_correlation_id_is_empty_too_long_or_has_spaces_or_newlines` (65 chars,
  `a b`, `a\nb`, `é`); `returns_true_when_correlation_id_is_64_letters_digits_dot_dash_underscore`
- `raises_when_request_context_instant_is_naive` (invariant break)

Views, `scheduling/views/test_failure_response.py`:
- `returns_status_of_the_table_when_each_of_ten_failures_is_mapped` (400, 401, 403, 404, 409 x5,
  422 in the order of the spec table)
- `returns_error_body_with_code_message_correlation_id_and_details_when_failure_is_mapped`
  (conflict: `details == {"resources": ["clinician", "room"]}`; invalid_transition:
  `{"current_status": "completed"}`)
- `returns_404_not_found_when_path_under_api_is_unknown` (same body shape, with `DEBUG=True` too)
- `returns_404_not_found_when_method_is_not_allowed` (POST to `/api/v1/health`)
- `returns_400_invalid_input_naming_body_when_json_is_unreadable`
- `returns_400_invalid_input_with_field_messages_when_serializer_validation_fails`
- `returns_400_invalid_input_naming_each_unknown_field_when_write_has_extra_keys`
  (`{"start": ..., "role": "admin"}` names `role`, message `Unknown field.`)
- `returns_500_internal_error_with_generic_message_and_correlation_id_when_view_raises`,
  asserting no traceback text, no exception class name, no exception message in the body, run
  with `DEBUG` on and off
- `returns_403_forbidden_when_view_declares_no_access_rule`
- `returns_200_when_health_declares_itself_public`

Correlation id and clock, `test_middleware.py`:
- `returns_same_correlation_id_when_header_is_sane` / `returns_generated_id_when_header_is_too_long_or_has_bad_characters`
- `returns_correlation_id_header_when_response_is_error_unknown_path_or_500`
- `returns_context_correlation_id_to_use_case_when_request_is_handled` (probe view reads it)
- `returns_one_instant_when_context_is_read_twice_in_a_request` (patched clock advances on each
  call; both reads equal the first)
- `returns_patched_instant_when_clock_is_replaced`
- `returns_no_context_when_request_has_finished` (`current_request_context()` raises)

Logs, `test_json_logging.py`:
- `returns_one_json_object_per_line_with_time_level_logger_message_correlation_id`
- `returns_request_line_with_method_route_pattern_status_and_duration_when_request_ends`
  (`GET /api/v1/health` gives route `api/v1/health`)
- `returns_route_pattern_without_path_or_query_when_request_has_identifier_and_token`
  (`?token=SECRET-TOKEN&email=ana@example.org`, 404 path under `api/v1/` carrying an email)
- `returns_no_email_token_or_clinical_note_when_logged_through_args_extra_and_exception_message`:
  `a@b.example`, `tok_abc123`, `patient reports chest pain` passed via `%s` args, `extra=`
  and an exception message; none of the three appears anywhere in captured output, and the
  500 line carries the traceback frames and the exception type name
- `returns_correlation_id_on_every_line_when_request_logs_several_lines`
- `returns_null_correlation_id_when_logged_outside_a_request`

Architecture, `scheduling/use_cases/test_no_wall_clock.py`:
`returns_no_wall_clock_read_when_domain_and_use_case_sources_are_scanned`; its scan is proven to
fail on a fixture string containing `datetime.now()`.

Red proof: each test fails first for the missing module or behaviour, not for a typo.

## Domain entities (CLAUDE.md vocabulary)

None stored. Vocabulary used: Visitor, ApiClient (callers of the plumbing, not modelled here),
AuditLogEntry (only mentioned: the correlation id will be stored by task 04a from the same
context). No model change.

## Will not do

No audit writer, security headers, authentication, session, throttling, FHIR
`OperationOutcome` (ADR states the shape it will read). No `Allow` header, no 405/406/415
codes. No dependency, no request-scoped cache, no abstraction without a second caller (the
probe views are test code). No refactor of models or seed. No mutation testing (`make mutate`
not configured until task 06).

## Risks

Judgement on transport codes (405 as `not_found`) may be vetoed. The catch-all route covers
only `api/v1/`; an exception raised in a middleware below ours, or on a non-API path, is
outside the contract (Django's handler; still gets the header and request line). Replacing log
args hides useful Django warnings; accepted, safe by default.

## Architect review

Verdict: approve.

- Ladder: no new dependency, no refactor beyond moving the negotiation class. Probe views are test-only. Holds.
- Layers: result type and context value in domain (pure), ContextVar in use cases, clock read only in views, AST test guards §8. Correct places.
- Contract: ten codes and statuses match spec section 4; `internal_error` is an eleventh, 500-only code outside the spec table, which the plan says plainly. Accepted.
- Transport judgement (wrong method and unknown path as `not_found` 404, bad body as `invalid_input`): accepted. It stays inside the ten codes; ADR must record it so the FHIR mapper does not guess.
- Security: log allowlist, no args, no exception messages, route pattern only, 500 never leaks, deny by default, correlation id validated. Threats named and tested with email, token and clinical note.
- Tests: behaviour-named, with edge and error paths, red proof stated.
- Non-blocking notes for the implementer:
  1. The unknown-field test should also cover a nested or read-only field, and `validate_body` must not mutate its input.
  2. Prove `DenyUnlessDeclared` with a view that declares nothing, as the task says (test is listed).
  3. A `HEAD`/`OPTIONS` on a known route also goes through the same 404 path; keep it covered by the wrong-method test.
