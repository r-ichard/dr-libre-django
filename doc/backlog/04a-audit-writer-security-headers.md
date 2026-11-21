Task 04a: audit writer, security headers, deployment checks.

The rest of the platform baseline (`drlibre-specs.md` sections 4 and 16), on top of the
request plumbing of task 04. No feature endpoint.

1. Audit writer: the one way a use case records an `AuditLogEntry`. It takes the actor
   (may be empty), the action, the entity type and id and the metadata, and reads the
   correlation id and the instant from the request context of task 04.
2. Same transaction (section 4). The writer refuses to write outside a transaction, so an
   audit entry can never be committed apart from the change it describes. Prove both
   directions with a test use case: when the audit write fails the change is rolled
   back, and when the change fails no audit entry remains.
3. Metadata is safe by construction. Section 4 allows ids, counts, status values and the
   names of changed fields, and the email domain for sign-in events. It forbids names,
   emails, phone numbers, birth dates, reasons and clinical notes. Design the metadata
   type so a forbidden value cannot be passed by mistake, say how in the plan, and prove
   it with tests that try each forbidden kind.
4. The demo seed writes its audit entry through the writer.
5. Security headers on every response, error responses included (section 16): a content
   security policy that forbids framing by other sites and allows no inline script or
   style, no content-type sniffing, a strict referrer policy, and in production HTTPS
   only (HSTS, redirect, secure cookies). Use what Django ships before writing anything.
   State the full policy in the plan: the front end will be server-rendered templates
   with CSS and small scripts served from the application itself.
6. Deployment checks. A test runs Django's deployment checks against production-like
   environment values and fails on any warning, so an unsafe production setting cannot
   slip in later. The development key in `.env.example` must fail that check. Every
   setting it needs comes from the environment; add them to `.env.example` with
   development values.
7. `scripts/ensure_database.py`: a non-numeric `DB_PORT` names the variable instead of
   raising a bare `ValueError` (carried from the review of task 01a).

Done when `make setup && make lint && make test && make gate` pass from a fresh clone.
The sandbox cannot run Docker; the orchestrator checks the headers on the host.
