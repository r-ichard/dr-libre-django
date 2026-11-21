# Plan: task 17a, no input answers 500 (closes #10, #12, #13, #14, #18)

Focal point: `BoundedJsonParser` (new, `scheduling/views/json_parser.py`) for body size and depth, and
`failure_from_exception` in `scheduling/views/failure_response.py` for Django's own refusals. No middleware. Plan in one sentence: refuse each unusable input where
it enters (parser, schema, form), then prove the class closed with one test that walks every route.

## Limits the product accepts, and where each is enforced (item 6)

| Limit | Value | Enforced at |
| --- | --- | --- |
| JSON request body (API) | 100 KiB (`BODY_BYTES_MAXIMUM` in `domain/input_limits.py`) | `BoundedJsonParser.parse`: refuses on `Content-Length` over the cap, then reads at most cap + 1 bytes from the stream (covers chunked bodies with no length); over the cap gives 400 `invalid_input` field `body`. `DATA_UPLOAD_MAX_MEMORY_SIZE` does not cover DRF's stream read, so it is not relied on for JSON |
| Form body (pages, form-encoded API) | 100 KiB (`DATA_UPLOAD_MAX_MEMORY_SIZE`, same value) | Django settings; pages: Django's own 400; API: `RequestDataTooBig` mapped in `failure_from_exception` to 400 field `body` |
| Fields in a query string or form | 100 (`DATA_UPLOAD_MAX_NUMBER_FIELDS`) | settings; API: `TooManyFieldsSent` mapped to 400 `invalid_input` field `query`; pages: Django 400 (already works on `/`) |
| JSON nesting depth | 20 | new `BoundedJsonParser` in `scheduling/views/json_parser.py`, set in `REST_FRAMEWORK["DEFAULT_PARSER_CLASSES"]`; refuses by scanning bracket depth of the raw text before `json.loads`, so no `RecursionError` ever starts. Answer 400 `invalid_input` field `body` |
| String lengths | per field, already in schemas (email 254, password 1000, token 200, reason 200, cancellation reason 1000); no new cap | schemas. NUL bytes (psycopg raises `ValueError` on `\x00`): `StrictSerializer` adds `ProhibitNullCharactersValidator` to every `CharField` it declares; page forms get Django's own `CharField` null check (found by the hostile test, fixed at the parse point) |
| Date range | years 1900 to 2200, inclusive | `OffsetDateTimeField.to_internal_value` in `booking_schemas.py` (one place for slots, appointments, holds, filters): 400 `invalid_input` naming the field |
| Page number | 1 to 1,000,000 (`PAGE_MAXIMUM`) | `AppointmentsQuery.page` `max_value`; page size stays 1..100 |
| Ids | UUID, by URL converter and `UUIDField` | already enforced; unchanged |

Page addresses (section 4): an unusable page number, filter or date in a page query falls back to its default. Any page that parses a date or number from `GET` keeps that rule; the hostile test checks it.

## Blocks to touch, one sentence each

1. `scheduling/views/pages/sign_in.py` (#10): validate email with Django's `validate_email` before `sign_in_with_password`, answer 400 with the field message `Enter a valid email address.`; `sign_in_with_password` itself also returns `Failure.invalid_input` instead of letting `email_domain` raise (use-case guards its own invariant). The email-link form already does this; reuse its check, no new helper unless it is a second caller there.
2. `scheduling/views/booking_schemas.py` (#12): `OffsetDateTimeField` refuses an instant outside the date range; hold request schema (`hold_schemas.py`) reuses this field so holds are covered; slots and booking need no change below the schema.
3. `AppointmentsQuery.page` (#13): add `max_value=PAGE_MAXIMUM`. Same for any other paged schema found by grep (`page = serializers.IntegerField`).
4. `settings.py` + `json_parser.py` (#14, #18): set `DATA_UPLOAD_MAX_MEMORY_SIZE` and `DATA_UPLOAD_MAX_NUMBER_FIELDS` (forms, query strings), register `BoundedJsonParser` (size, then depth, then `json.loads`) in `DEFAULT_PARSER_CLASSES`.
5. `failure_response.py` (#14, #18): `failure_from_exception` maps `django.core.exceptions.RequestDataTooBig` (form bodies), `TooManyFieldsSent` and `TooManyFilesSent` (all `SuspiciousOperation`, raised by lazy access to `request.data` or `query_params`) to `Failure.invalid_input` with fields `body`/`query`. Sub-class check, not a blanket `SuspiciousOperation`, so a real security signal stays a loud 4xx from Django.
6. Pages: a small `PageView.dispatch` guard is NOT added; Django already answers 400 for these on pages. The hostile test will tell whether any page still gives 500 (NUL bytes, huge numbers in `GET`); fix each one found at its parse point, then record it in the plan's limits table.
7. New `scheduling/views/test_hostile_input.py` (item 5).

Order: red tests first (hostile test, one test per issue), then blocks 2, 3, 4+5, 1, 6.

## Item 5: how the test finds every route

`drlibre.urls.urlpatterns` is walked recursively (`URLPattern` / `URLResolver`); each pattern is turned into a path by substituting every converter (`uuid` with a random UUID, `str`/`path` with `x`). A helper reads `pattern.pattern` and `converters`; an unknown converter type makes the test fail with its name, so a new kind of route cannot be skipped silently. Excluded by name, in one list with a reason each: `static/` (file server), `favicon.ico` (redirect), the `^api/v1/` catch-all is kept. Every other route is tested with every method in `GET, POST, PUT, PATCH, DELETE`, so a new route is covered when added with no edit to the test.

Actors: no session, patient, clinician, admin (sessions opened through the existing test helpers in `views/conftest.py`). Page POSTs send `Origin` and the CSRF token as the browser does (CLAUDE.md "Page forms"); API writes send `Origin`.

Hostile values, fixed catalogue (parametrized): empty string; 100 KB string; wrong type (list, number, null, bool for each field); invalid UTF-8 bytes and `\x00`; huge integer `10**30`, negative, `NaN`; dates `0001-01-01`, `9999-12-31T23:59:59Z`, `2024-02-30`; malformed ids (`not-a-uuid`, 10k chars); body nesting 100000 deep; 3 MB body; 1500 query fields and 1500 form fields. Hypothesis adds a property test: for a random route, actor and `st.recursive` JSON value (text includes NUL and surrogates-free unicode), body and query keys built from the field names seen in the route's own responses are not available, so the keys are random text plus a fixed list of common names (`email`, `password`, `page`, `from`, `to`, `starts_at`, `appointment_type_id`, ...). Assertion on every response, all actors: status != 500. Additionally, only for routes under `/api/v1/` and only for statuses >= 400, the body is JSON with `error.code` in the contract; run for every actor, since each hits the same error mapper. Settings: `max_examples=50`, `deadline=None`, `suppress_health_check=[function_scoped_fixture]`, `database` off for repeatability.

## Failing tests first (names `returns_X_when_Y`)

- `returns_400_with_email_message_when_sign_in_page_gets_a_malformed_email` (`a@b`, `not-an-email`, `a@b@c` → status 400, text "Enter a valid email address.", no session cookie, no 500).
- `returns_400_invalid_input_naming_starts_at_when_booking_year_is_9999` and `..._0001`; same for slots `from`/`to` naming the field, and holds `starts_at`.
- `returns_400_invalid_input_naming_page_when_page_is_huge` (`99999999999999999999`, `1000001`); `returns_200_when_page_is_the_maximum`.
- `returns_400_invalid_input_naming_body_when_json_is_nested_100000_deep` on `/booking/holds`, `/auth/link`, `/auth/login`, `/appointments`.
- `returns_400_invalid_input_naming_body_when_body_is_3_megabytes` (with `Content-Length`, and chunked with none; goes green only through the parser check) and `returns_200_when_body_is_just_under_the_cap`.
- `returns_400_invalid_input_naming_query_when_search_has_1500_fields`.
- `returns_200_when_json_is_nested_exactly_at_the_limit` (guards against an off-by-one that refuses real bodies).
- `returns_no_500_when_any_route_gets_hostile_input` and the hypothesis variant (item 5). Prove it can fail: run it first on the unfixed tree, expect red on the five issues.
- Mutation: parser depth scan and date-range check are pure; put them as functions in `scheduling/domain/input_limits.py` (`exceeds_depth`, `date_in_range`, constants) with unit tests, so `make mutate` covers them; add any equivalent mutant to `mutation-equivalents.txt` with a reason.

## Trust boundaries

Body, query, form, path: all client data. Refused before use case code runs. Authorization unchanged (session, never payload). The oversized-body refusal happens before authentication needs the body, so a visitor cannot make the server parse more than the cap. Logs: refusal logs the field name only, never the value.

## Domain entities

Visitor, Patient, Clinician, Admin (actors); Appointment, BookingHold, AvailabilityRule, TimeOff, WaitlistEntry, Notification (routes reached); Session (sign-in).

## Invariants and blast radius

Double booking, server-side authorization, append-only audit log: untouched; no write path changes except earlier refusal. Blast radius: every API request passes the new parser and body cap (100 KiB is far above any real body here; largest field is a 1000-char reason); every page form passes the 100-field cap; date range and page cap narrow what clients may send. The seed command and QA scripts send nothing near these.

## Files to touch

`drlibre/settings.py`, `scheduling/domain/input_limits.py` (+test), `scheduling/views/json_parser.py` (+test), `scheduling/views/failure_response.py`, `scheduling/views/booking_schemas.py`, `scheduling/views/hold_schemas.py` only if it has its own instant field, `scheduling/views/schemas.py` (NUL guard), `scheduling/views/pages/sign_in.py`, `scheduling/use_cases/sign_in.py`, `scheduling/views/test_hostile_input.py`, `scheduling/views/test_*` per issue, `doc/backlog.md` and `doc/retro.md` left to the orchestrator.

Deliberately not touched: models, migrations, `domain/audit_metadata.py` (its `ValueError` is a correct invariant check; the fix is not calling it with unvalidated input), middleware ordering, rate limiting, Docker setup, the generic 500 mapper (stays as the last resort).

## Will not do

No new dependency, no blanket `except Exception`, no catching `RecursionError`, no request-size middleware (the parser and Django settings do it), no refactor of page query parsing beyond fixing a failing route. Final reply of the last stage ends with: "Closes #10, #12, #13, #14, #18".

## Architect review

Verdict: approve.

- Ladder: fixes sit at the entry point (parser, schema field, form check, exception mapper). No new dependency (hypothesis already pinned), no middleware, no refactor.
- Scope: all five issues, route-walking test (derived from `drlibre.urls`, fails on unknown converter), and the limits table with the enforcement point per limit are present.
- Tests first: one named behaviour per issue, boundary cases (exactly at depth limit, just under body cap, page maximum), and an explicit "run on unfixed tree, expect red" step.
- Security: refusal precedes parsing, logs carry field name only, no authorization change.
- Notes for the build stage, not blockers:
  1. Hypothesis test: keep the runtime bounded (routes x actors x methods x examples); sample actors/routes via `st.sampled_from` and keep the fixed catalogue test as the exhaustive pass.
  2. Block 5: confirm the exceptions are raised inside the view (not in middleware reading `request.GET`/`POST`), otherwise map them in the middleware too. The hostile test will show it.
  3. Keep each new file under the 300-line convention; split `test_hostile_input.py` (route walker vs. catalogue) if it grows.
  4. Pure helpers in `domain/input_limits.py` need mutation-clean tests; explain any equivalent mutant in `mutation-equivalents.txt`.
