# Plan: task 04b, audit writer, security headers, deployment checks (2026-11-21)

Sources read: task goal, specs §4, §12.1, §16, `drlibre/settings.py`, `environment.py`,
`scheduling/models/audit.py`, `use_cases/request_context.py`, `domain/request_context.py`,
`views/middleware.py`, `demo_seed/{writer,seed_support}.py`, `management/commands/seed_demo.py`,
Django 6.1 `django/utils/csp.py`, `middleware/csp.py`, `core/checks/security/*`.

## Focal point
`scheduling/use_cases/audit.py` (the writer) with `scheduling/domain/audit_metadata.py` (the safe
metadata type); `drlibre/settings.py` for headers and checks. No feature endpoint, no dependency; one
small model override and its migration (block 2).

## Design: metadata safe by construction (block 1)
`AuditMetadata` is a frozen dataclass, not a dict. The writer accepts only that type. Its fields are
closed and each has a type that cannot hold free text:
- `ids: Mapping[str, UUID | int]`, `counts: Mapping[str, int]`, `statuses: Mapping[str, StrEnum]`,
  `changed_fields: tuple[FieldName, ...]`, `email_domain: EmailDomain | None`.
- Keys are validated against `^[a-z][a-z_]{2,40}$` and must end in `_id`/`_ids` (ids), `_count`
  (counts), `_status` (statuses): a key cannot carry a value kind it does not name.
- Statuses take `StrEnum` members only (the code's own vocabulary), never `str`, so a reason or a
  note cannot be passed as a status. `bool` is rejected as a count/id (it is an `int`).
- `FieldName` is a `NewType` over `str` built by the pure `field_name(name)`: pattern
  `^[a-z][a-z_]{1,60}$` only (no spaces, capitals, digits, `@`, so "Jane Doe", an email or a phone
  number cannot pass). The model-aware check lives in the use case layer (block 2):
  `changed_field_names(model_class, names)` returns `FieldName`s only for real concrete fields of the
  Django model, else raises `ValueError`. The domain stays free of ORM (§8).
  `EmailDomain` built by `email_domain(address)`: takes the part after `@`, validates a hostname
  pattern (letters, digits, dots, hyphens, at least one dot), never keeps the local part.
- `to_json()` is the only way to serialise; it emits only those five sections. mypy strict makes the
  wrong call a type error; the constructors raise `ValueError` for runtime strays (broken invariant,
  programmer error, not user input). No `Any`, no `cast`.
Why not a regex scrubber over a dict: it guesses; the types make the forbidden kinds unrepresentable.

## Blocks (one sentence each)
1. `scheduling/domain/audit_metadata.py` (pure): the type and constructors above.
2. `scheduling/use_cases/audit.py` (also holds `changed_field_names`): `record_audit(event: AuditEvent, actor: User | None) -> None`, where the frozen
   `AuditEvent` holds action, entity_type, entity_id and `metadata: AuditMetadata` (keeps args at 2).
   Raises `TransactionRequired` (own exception, invariant break) if
   `not connection.in_atomic_block`; reads `current_request_context()` for `correlation_id` and
   `now`; creates the `AuditLogEntry` with `created_at` = context `now`.
   Settled: `Record.created_at` is `auto_now_add`, which overwrites any value passed on insert, and
   the log is append-only (trigger), so it cannot be fixed afterwards. Therefore `AuditLogEntry`
   redeclares `created_at = DateTimeField(editable=False)` (no `auto_now_add`, no default, so the
   writer must supply it) plus one generated `AlterField` migration (state only, no data rewrite,
   the trigger is untouched). This is the single model change; the earlier "no model change" is
   withdrawn.
   Never catches: a failed insert propagates, so the surrounding `atomic` rolls back.
3. `scheduling/demo_seed/writer.py` + `management/commands/seed_demo.py`: seed's audit entry goes
   through `record_audit` with `AuditMetadata(counts={"<model>_count": n})`; the command binds a
   `RequestContext(uuid4().hex, timezone.now())` around `seed_demo` (no request exists there);
   `uuid4` and ad-hoc `correlation_id` leave the writer.
4. `drlibre/settings.py` headers (see policy). Middleware order: `SecurityMiddleware` first,
   then existing `RequestContextMiddleware`, `ContentSecurityPolicyMiddleware`, `CommonMiddleware`,
   `CsrfViewMiddleware` (needed by Django check W003 and by the template front end),
   `XFrameOptionsMiddleware`. All are Django's own.
5. `drlibre/settings.py` env: `HTTPS_ONLY` flag (default off) turns on the transport block;
   `HSTS_SECONDS` read via `require_env` (int). Settings are read only from the environment.
6. `.env.example`: add `HTTPS_ONLY=false`, `HSTS_SECONDS=0`; `DEBUG` stays unset there as today
   (dev compose sets it). Dev `SECRET_KEY` stays and must fail the check (short, `W009`).

## Security header policy (full)
Every response, error pages and the JSON error contract included (SecurityMiddleware and the CSP
middleware run in `process_response`, which runs for responses made by Django's 404/500 handlers,
and for the middleware's own replaced 500):
- `Content-Security-Policy` (`SECURE_CSP`, enforce, not report-only):
  `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self';
  connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none';
  object-src 'none'`. No `'unsafe-inline'`, no `'unsafe-eval'`, no nonce: scripts and CSS are files
  served by the app (`'self'`). `frame-ancestors 'none'` forbids framing by anyone. `img-src 'self'`
  (vendored SVG icons; `data:` not allowed until a task needs it).
- `X-Frame-Options: DENY` (Django default, `XFrameOptionsMiddleware`), for old browsers.
- `X-Content-Type-Options: nosniff` (`SECURE_CONTENT_TYPE_NOSNIFF`, Django default True).
- `Referrer-Policy: same-origin` (nothing links out). Set `SECURE_REFERRER_POLICY` explicitly.
- `Cross-Origin-Opener-Policy: same-origin` (Django default via SecurityMiddleware).
- In production (`HTTPS_ONLY`): `SECURE_SSL_REDIRECT=True`, `SECURE_HSTS_SECONDS=HSTS_SECONDS`,
  `SECURE_HSTS_INCLUDE_SUBDOMAINS=True`, `SECURE_HSTS_PRELOAD=True`, `SESSION_COOKIE_SECURE=True`,
  `CSRF_COOKIE_SECURE=True`. Dev (off): none of these, so `127.0.0.1:8000` over HTTP keeps working.
- `/api/v1/health` is redirected too in production unless a proxy terminates TLS; see risks.

## Deployment check (block 7)
`drlibre/test_deployment_checks.py`: runs `python manage.py check --deploy --fail-level WARNING`
in a subprocess (clean settings import, no module reload pollution) with a production-like
environment: `DEBUG` unset, `HTTPS_ONLY=true`, `HSTS_SECONDS=31536000`, a 64-character random-looking
`SECRET_KEY` not starting `django-insecure-`, `ALLOWED_HOSTS=drlibre.example`, the DB and mail vars.
Second test: same environment but `SECRET_KEY` from `.env.example`: exit code non-zero and output
names `security.W009`. A third: same but `HTTPS_ONLY=false`: fails (guards the switch). A test
helper reads `.env.example` through the same parser `uv run --env-file` uses (plain `KEY=value` lines).

## Files to touch, in order
1. `scheduling/views/probe_urls.py` / `probe_views.py` (test-only): none needed; 404 and 500
   probe routes exist (`/pages/explode`, unmatched API path).
2. New tests (below), watched failing.
3. `scheduling/models/audit.py` + generated migration, `scheduling/domain/audit_metadata.py`, `scheduling/use_cases/audit.py`, `demo_seed/writer.py`,
   `seed_demo.py`, `drlibre/settings.py`, `.env.example`, ADR 0004 gets a short "Headers and audit"
   section (policy copy; one place the policy is written down).

Not touched: models other than the `created_at` override, other migrations (trigger already makes the log append-only), `middleware.py`
(the stock middlewares cover every response, so no custom header code), `compose.yaml` (dev values
default to HTTP; the orchestrator checks headers on the host), `json_logging.py`, feature views.

## Invariants that must not break
Append-only audit log (writer only inserts, never updates); audit entry in the same transaction as
the change (writer refuses outside one); correlation id from the request context, never from a
caller; no sensitive value in metadata; dev flow (`docker compose up`, `seed_demo`) still works over
HTTP; JSON error contract unchanged. Blast radius: settings (every request gets new headers and
CSRF middleware), seed (audit call site), `.env.example` (new required vars: compose and fresh
checkout need them; `make` already loads `.env.example`; compose `env_file` to check).

## Failing tests first (`returns_X_when_Y`, `raises_`/`rejects_` allowed by config)
`scheduling/domain/test_audit_metadata.py`
- `returns_json_with_ids_counts_statuses_fields_when_metadata_is_built`: expected
  `{"ids": {"appointment_id": "<uuid>"}, "counts": {"row_count": 3}, "statuses": {"new_status": "BOOKED"},
  "changed_fields": ["starts_at"], "email_domain": "example.test"}`.
- `rejects_free_text_status_when_a_plain_string_is_given` (a cancellation reason).
- `rejects_name_as_field_name_when_it_does_not_match_the_pattern` ("Jane Doe", an email, a phone
  number); the model check is tested in `use_cases/test_audit.py` (`rejects_field_name_when_model_has_no_such_field`).
- `returns_domain_only_when_address_is_given`: `jane@example.test` yields `example.test`; the
  local part is absent from `to_json()`. `rejects_email_domain_when_input_has_no_at_sign`.
- `rejects_phone_number_when_passed_as_id_or_count` (`"+33 6 12 34 56 78"` as id; bool as count).
- `rejects_birth_date_when_passed_as_value` (`date(1990,1,2)` as id/count/status).
- `rejects_key_that_does_not_name_its_kind` (`patient_name` in ids, `note_count` in statuses).
- `rejects_email_domain_with_clinical_note_text` ("patient has chest pain").
`scheduling/use_cases/test_audit.py` (db)
- `returns_entry_with_context_values_when_recorded_inside_transaction`: correlation id and `created_at`
  equal the bound context's (pins the instant decision); actor empty when none given; metadata equals `to_json()`.
- `raises_transaction_required_when_recorded_outside_transaction`: no entry written.
- `raises_lookup_error_when_no_request_context_is_bound`.
- `rolls_back_change_when_audit_write_fails` (test use case `rename_specialty` in the test file:
  changes a Specialty then calls the writer with a forced DB failure, e.g. an `action` of 101
  characters; `action` is `CharField(max_length=100)`, confirmed in `models/audit.py`, enforced by
  PostgreSQL `varchar(100)`; Specialty name unchanged afterwards; `transaction=True` test).
- `leaves_no_audit_entry_when_change_fails` (use case writes audit then the change violates a
  constraint; no `AuditLogEntry` remains).
`scheduling/demo_seed/test_seed_demo_command.py`
- `returns_one_entry_with_context_correlation_id_when_seed_runs` (entry correlation id is the one
  the command bound; metadata `counts` only).
`scheduling/views/test_security_headers.py`
- `returns_policy_headers_when_health_is_requested`: exact CSP string above, `X-Frame-Options: DENY`,
  `nosniff`, `Referrer-Policy: same-origin`.
- `returns_policy_headers_when_route_is_unmatched_and_when_view_raises` (404 and 500, API and page).
- `returns_no_inline_allowance_when_policy_is_parsed`: no `unsafe-inline`/`unsafe-eval`/`*`/`data:`.
- `returns_redirect_and_hsts_when_https_only_is_on` (subprocess or `settings` fixture with
  `SECURE_SSL_REDIRECT` etc.; secure cookie flags).
`drlibre/test_deployment_checks.py`: three tests above (production env passes with zero warnings;
`.env.example` key fails with `security.W009`; `HTTPS_ONLY=false` fails).

## Trust boundaries
- Caller to writer: only `AuditMetadata` accepted; constructors validate; actor comes from the use
  case (session identity), never payload. Nothing from the client reaches metadata unvalidated.
- Request headers: `X-Correlation-Id` already validated by task 04 pattern.
- Environment to settings: `HSTS_SECONDS` int-parsed (bad value raises at startup, fail fast).

## Domain entities
AuditLogEntry, User (actor), Specialty (test use case only), RequestContext. Seed writes
`DemoSeed` entity type.

## Will not do
No generic redaction layer, no audit-reading API, no logging of metadata, no `SECURE_PROXY_SSL_HEADER`
(no proxy exists yet: needs its own decision with the deployment task), no nonce CSP, no report-uri,
no dependency (`django-csp` not needed: Django 6.1 ships CSP), no other model or migration change.

## Open risks
- Behind a TLS-terminating proxy `SECURE_SSL_REDIRECT` loops without `SECURE_PROXY_SSL_HEADER`;
  deferred until the deployment topology exists.
- A strict `default-src 'none'` CSP breaks any page needing images from `data:` or inline SVG
  styles; the front end task adds sources deliberately, with a test change.
- Adding `CsrfViewMiddleware` affects later non-DRF POST views; DRF views stay exempt. Run the full
  suite (`make test`) right after adding it, before other settings work, to catch existing POST tests.

## Architect review: addressed
- Layer break: `field_name` is now pattern-only in the domain; model check moved to
  `use_cases/audit.py` (`changed_field_names`).
- `created_at`: settled above (override, migration, test pin). Email-domain test renamed, no-`@`
  rejection added. `action` max_length 100 confirmed. Full suite after CSRF middleware noted in risks.

## Architect review
Verdict: approve.
- Ladder: Django's own CSP, security and CSRF middleware, no dependency; one model override (`created_at`) is justified because `auto_now_add` would discard the context instant and the log is append-only.
- Metadata: closed frozen dataclass with typed, key-named sections makes each forbidden kind unrepresentable; each kind (name, email, phone, birth date, reason, note) has a named failing test. Domain stays free of ORM; model-aware check is in the use case layer.
- Same transaction: writer raises `TransactionRequired` outside `atomic`, never catches; both rollback directions have tests.
- Headers and checks: full CSP stated, applies to error responses, tested on 404 and 500; deployment check runs in a subprocess, with the `.env.example` key and `HTTPS_ONLY=false` failing.
- Notes for implementer (not blockers): the plan says "block 7" but defines six blocks; confirm `ALLOWED_HOSTS` and `SECRET_KEY` are already read from the environment (task says every setting comes from it); an integer phone number could pass as an id or count, key suffix naming is the only guard, so keep that test on the key rule; run `make test` right after adding `CsrfViewMiddleware`.
