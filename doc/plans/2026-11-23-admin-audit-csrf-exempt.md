# Plan: remove `csrf_exempt` from the admin audit page

Slice: one finding, one task item. Covers the whole finding; nothing else in this run.

## Focal point

`scheduling/views/pages/admin_audit.py:87`: `path("admin-console/audit", csrf_exempt(AuditPage.as_view()))`.
The page takes GET only (`http_method_names = ["get"]`, line 35). The exemption means a POST
added later skips the cross-site check silently. Every other admin page gets the default
CSRF middleware (`drlibre/settings.py:30`).

## Ladder

Rung 1 holds: delete the wrapper. No new abstraction, dependency or helper in production code.

## Blocks

1. `scheduling/views/pages/admin_audit.py:8`: delete the import `from django.views.decorators.csrf import csrf_exempt`.
2. `scheduling/views/pages/admin_audit.py:84-87`: delete the comment (it explains the exemption,
   which will no longer exist) and return `path("admin-console/audit", AuditPage.as_view())`.
3. `scheduling/views/pages/test_admin_audit_page.py`: add the red test (below) beside the other
   method tests.
4. Same file, `returns_405_when_the_log_route_is_asked_to_change_something` (line 123-130): the
   test client now enforces the cross-site check on this route. Without a token the write methods
   answer 403 (CSRF middleware), not 405, so the test would fail for a reason it does not guard.
   Change it to send a valid token and a site `Origin` (`X-CSRFToken` header, `Origin: SITE_ORIGIN`),
   so it still proves the view answers 405. The `_fill(1)` count assertion stays.

## Files, in order

1. `scheduling/views/pages/test_admin_audit_page.py` (red test, then the parametrized test change)
2. `scheduling/views/pages/admin_audit.py`

## Files deliberately not touched

- `doc/security-review.md`: named in the task, but absent from the tree. The finding is recorded
  in `doc/reviews/2026-11-22-admin-appointments-waitlist-audit-settings.md:17`, which calls the
  exemption "deliberate and safe"; that review is a dated record (§13.1 throwaway class). Not edited.
- `drlibre-specs.md`, ADRs, `doc/handover.md`: no behaviour or state change to document.
- `scheduling/views/pages/admin_support.py`, `browser_support.py`: reused as is; the new test
  builds its header directly (see below).
- Other admin pages, FHIR `csrf_exempt` (`scheduling/views/fhir/views.py:55`): out of scope.

## Invariants and blast radius

- Audit log append-only: unchanged; no write path added or removed.
- Server-side authorization: unchanged. `PageView` role guard (`allowed_roles = {ADMIN}`) still runs
  from the session.
- Behaviour change: a POST to the audit route without a valid token or from another site now answers
  403 (the browser refusal every other admin page gives), instead of 405. A POST with a valid token
  and a site origin still answers 405. GET is unchanged (200 for an admin).
- Blast radius: one URL. No other route, template or use case changes.

## Failing tests to write first (red)

Expected values from the spec's protected-page rules (CSRF check on every unsafe method, read-only log):

- `returns_403_to_a_cross_site_post_and_200_to_a_get_when_the_log_is_opened`
  - `admin_client()` (cross-site check enforced) POSTs to `/admin-console/audit` with
    `OTHER_SITE_ORIGIN` and a valid token: expects 403.
  - the same admin client GETs the page: expects 200.
  - Red today: the POST answers 405 because the exemption skips the middleware. Must fail before the fix.
  - Use `OTHER_SITE_ORIGIN` from `browser_support.py`, the same origin `test_destructive_routes.py` uses.
- Changed (not new): `returns_405_when_the_log_route_is_asked_to_change_something`, with a valid token
  and site origin. Passes before and after; it guards the 405 for a browser that has a token.

Green check: the red test passes; the parametrized test passes; the existing
`returns_the_post_refusal_with_the_csrf_flow_of_a_browser_when_posting_to_the_log` (line 146, uses
`admin_post`, valid token, site origin) still answers 405.

## Trust boundaries

- Browser to POST route: cross-site check (Origin + CSRF token) enforced by `CsrfViewMiddleware`
  after the fix. Before the fix it was skipped for this route only.
- Session to role: `PageView` resolves the user from the session cookie, never the payload.

## Domain entities (CLAUDE.md §3)

Admin (the only role allowed), AuditLogEntry (read only here).

## Not doing

- No `require_GET` decorator or extra method guard: `http_method_names` already limits the view;
  the finding is about the exemption, not the method list.
- No new helper in `admin_support.py` for non-POST methods; the header is built in the test.
- No edit to the 2026-11-22 review or the missing `doc/security-review.md`.
- No test for the POST-without-token case beyond the parametrized one (not asked).

## Notes for the orchestrator

- The finding's file name in the task (`doc/security-review.md`) does not exist; the source is the
  2026-11-22 review above. Confirm which document the finding should close against.
- The change is two product files and one test file. Expected diff: about 6 lines removed, 15 added.

## Architect review

Verdict: approve.

- Ladder: rung 1 (delete the wrapper and its import). No abstraction, dependency or refactor. Right layer: the route list in the page module.
- Premise checked: `admin_client()` builds `Client(enforce_csrf_checks=True)` (`browser_support.py:19`), so the red test is meaningful. The current exemption answers a cross-site POST 405; after the fix the middleware answers 403 before the view runs.
- Test-first: the red test names a behaviour with expected values (403 for cross-site POST, 200 for GET) and fails before the fix. Edge path (token-less or cross-site write) is covered by the parametrized test and the red test.
- Gap to close in block 4: the plan says "send a valid token" for `put`/`patch`/`delete` but names no way to get one. `admin_support._form_token()` is private and only reads a token from a visitor GET on `TOKEN_SOURCE_PATH`. The implementer should either make that token helper usable (a single small import, not a new helper) or set the CSRF cookie and `X-CSRFToken` header from the same source. Name the choice in the test; do not invent a token.
- Line references: the comment is at line 86 and the return at line 87, not "84-87" as a block. Block 2 should say "delete line 86 and change line 87". Cosmetic.
- Security: authorization unchanged (`PageView` role guard from session). Audit log unchanged. No sensitive data in the new test. Trust boundary (browser POST) is restored to the default middleware.
- Scope: one URL, two product files, one test file. Docs decision (no edit to `doc/security-review.md`, which is absent; the source is `doc/reviews/2026-11-22-admin-appointments-waitlist-audit-settings.md:17`) is correct and flagged for the owner. The stale `admin_audit.py:79` reference in that review is not this task.
- Behaviour change is named and bounded: a POST without a valid token or from another site answers 403 instead of 405. A POST with a valid token and site origin still answers 405.
