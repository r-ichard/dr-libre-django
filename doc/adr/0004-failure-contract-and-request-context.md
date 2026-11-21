# ADR 0004: Failure contract and request context

Status: accepted, 2026-11-21.

## Decisions

- **Expected failures are values.** `scheduling/domain/failure.py` holds `Failure` (a code and
  its details, one constructor per code so a code cannot carry another code's details),
  `Success` and `Result = Success | Failure`. Use cases return a `Result`; they raise only on a
  broken invariant (§9).
- **One wire shape.** Every non-2xx API response, and nothing else, has this body plus the
  header `X-Correlation-Id`. `details` is always an object. `message` is fixed text per code,
  never built from data.

      {"error": {"code": "<code>", "message": "<fixed text>", "correlation_id": "<id>",
                 "details": {...}}}

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

  Nested validation paths join with `.` (`address.city`); DRF `non_field_errors` keeps that name.
  The screens and the FHIR `OperationOutcome` mapper both read this shape: `code` maps to
  `issue.code`, `details` to `issue.details` and `issue.expression`, `correlation_id` to
  `issue.diagnostics`.
- **Transport failures reuse the ten codes** (the one judgement call). Unknown path and wrong
  method are `not_found` 404, with no `Allow` header. Unreadable body and unsupported media type
  are `invalid_input` 400 with field `body`. Failed validation, and an unknown field on a write
  (`StrictSerializer`), are `invalid_input`. A view without an access rule is `forbidden` 403;
  once a view declares authenticators the same path answers `unauthenticated` 401. Any other
  exception, `APIException` subclasses included, is `internal_error` 500 with a generic message
  and the correlation id; the trace goes to the log only, whatever `DEBUG` says. Content
  negotiation is always JSON for API views, so 405, 406 and 415 do not occur.
- **Request context.** `RequestContextMiddleware` (first in `MIDDLEWARE`) takes the correlation
  id from `X-Correlation-Id` when it is 1 to 64 characters of `[A-Za-z0-9._-]`, generates one
  otherwise, reads the clock once, binds a frozen `RequestContext(correlation_id, now)` in a
  `ContextVar`, and returns the id on every response. Use cases read it through
  `current_request_context()` and never touch the system clock; tests bind their own context.
  `scheduling/views/clock.py` is the only place the wall clock is read.
- **Logs.** One JSON object per line from an allowlist of record fields (time, level, logger,
  message, correlation id, request fields); exception text is dropped and only trace frames are
  kept. One `request` line per request carries method, matched route pattern, status and
  duration, never the raw path or query string.
- **Closed by default.** DRF's default permission refuses; a view must declare who may call it.
  The health endpoint declares itself public.

## Consequences

- A later FHIR mapper adds a second renderer for the same `Failure`; it does not parse bodies.
- Known gaps, tracked in the review: log message text is not scrubbed (callers must not
  interpolate sensitive data), nested serializers are not strict, non-API paths under `DEBUG`
  still show Django's technical page.
