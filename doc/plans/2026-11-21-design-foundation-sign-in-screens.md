# Plan: task 05a, design foundation, sign-in screens, role homes, error pages

Spec: 12.1, 12.3, 16. Impeccable operate mode; `craft-floor.md` read (no kicker, no nested cards, no
coloured side borders, no decorative shadows/gradients, drawn SVG not glyphs, themed focus ring and
selection, tabular numerals). Sandbox has no browser: visual result unverified.

## Focal point

`scheduling/views/pages/sign_in.py` (`SignInPage`): the one new flow. It calls the existing
`sign_in_with_password`, maps `Failure` to a field-tied message, sets the cookie, redirects. Everything
else is layout, CSS and thin guards.

## Blocks, one sentence each

1. `PRODUCT.md`: who (patients, clinicians, admins, visitors), what they come to do, voice.
2. `DESIGN.md`: tokens, type scale, spacing, radius, focus ring, component list with states.
3. `static/css/tokens.css`: custom properties only (colour with checked contrast pairs, type, space, radius, focus).
4. `static/css/base.css`: reset, typography, layout shell, skip link, focus ring, selection, tabular numerals, reduced motion.
5. `static/css/components.css`: buttons, field, select, checkbox, error summary, notices, card, table,
   pagination, badge, empty, loading. Status = icon (drawn inline SVG in template, `aria-hidden`) + word + colour.
6. `static/js/focus_first_error.js`: 5 lines, external file (CSP): focuses the element marked `data-autofocus`.
   Sign-in works without it; the marker is the server-provable part.
7. `scheduling/templates/base.html`: `lang="en"`, skip link, header (name, user name, sign-out POST form with
   CSRF), one `main`, footer, blocks `title` and `content`, CSS links.
8. `scheduling/templates/components/*.html`: includes for field, notice, error_summary, badge, empty_state,
   pagination, button; each takes explicit parameters so later tasks reuse them.
9. `scheduling/views/pages/page_view.py`: plain-Django base `PageView`: resolves session cookie via
   existing `resolve_session`, sets `request.user`-like `signed_in_user` (not Django auth), re-sets cookie
   when extended, adds `correlation_id` and user to context. One pattern for every page.
10. `scheduling/views/pages/guards.py`: `require_roles(*roles)` mixin: anonymous -> redirect
    `/sign-in?next=<path>`; wrong role -> 403 page; correct role -> proceeds. Authorisation from the session only.
11. `scheduling/views/pages/safe_redirect.py`: `local_path_or_home(candidate, home)` using
    `url_has_allowed_host_and_scheme` with no allowed hosts plus rejection of `//`, `\`, control characters
    and non-`/` starts. Pure, so mutation-testable.
12. `scheduling/views/pages/sign_in.py`: GET form (signed-in user is sent to their home); POST validates
    required fields (field errors), calls use case, success -> session cookie + redirect to safe `next` or role home.
    Failure -> one message "Email or password is not correct." attached to the form summary and to
    both fields' `aria-invalid`/`aria-describedby`, focus on email; lockout -> separate message.
13. Lockout signal: use case returns `Failure.unauthenticated()` for lockout (API contract and test pin that).
    Add `is_locked_out(email) -> bool` in `use_cases/sign_in.py` (same window query); the page calls it only
    after a failure. No API change.
14. `scheduling/views/pages/homes.py`: three views `PatientPortal`, `ClinicianWorkspace`, `AdminConsole`,
    templates `homes/*.html`, each `h1` "Hello, <name>". Mapped from `Home` enum to URL names so sign-in redirect and
    role homes share one table (`HOME_PATHS`).
15. `scheduling/views/pages/sign_out.py`: POST only, `sign_out(token)`, clear cookie, redirect to `/sign-in`.
    CSRF enforced by `CsrfViewMiddleware` (already installed); GET gives 405.
16. `scheduling/views/pages/errors.py` + `templates/errors/{403,404,500}.html`: `handler403/404/500`,
    plain message, correlation id from `current_request_context()` (fall back to nothing if unbound),
    status code correct. `/api/v1/` keeps its JSON failures (middleware, `NotFoundView`, untouched).
    Forbidden page also used by the role guard.
17. `scheduling/views/pages/home.py` + `templates/home.html`: `/` shows product name `h1` and link to sign-in.
18. `scheduling/views/pages/style_page.py` + `templates/style.html`: `/style` registered only
    `if settings.DEBUG`; renders every component in every state.
19. `drlibre/settings.py`: `TEMPLATES` (DIRS none, APP_DIRS, no auth/messages context processors),
    `STATIC_URL`. `drlibre/urls.py`: page routes; `/static/` through `django.views.static.serve` from
    `static/` (no `staticfiles` app, no whitenoise, no new dependency; works with DEBUG off so error
    pages are styled). Check `Dockerfile`/`.dockerignore` copy `static/`.
20. `CLAUDE.md`: record that with `DEBUG` on a developer sees Django's technical 404/500 pages (handlers
    unused by Django in DEBUG) and on 403 our page; DEBUG off shows ours. Plus `/style` route and
    "Layers" line for `scheduling/views/pages/`.

## Files in order

`PRODUCT.md`, `DESIGN.md`, static css/js, `settings.py`, templates, `pages/*`, `urls.py`, `sign_in.py`
(one function), `CLAUDE.md`, `doc/backlog.md` left to orchestrator.

Deliberately not touched: models, migrations, domain, API views, `failure_response.py`, middleware,
CSP settings (already forbid inline), lockout rules, session rules, `doc/backlog.md`, `doc/retro.md`.

## Invariants and blast radius

- Server-side authorisation on every role page; role from the session's user, never a request field.
- CSRF on sign-in POST and sign-out POST (token in form); SameSite=Strict cookie reused unchanged.
- Same message and same use-case timing for unknown email and wrong password; the page adds no branch
  that depends on whether the email exists. Lockout check runs only after a failure and keys on the
  email hash, which exists for unknown addresses too, so no account enumeration.
- Audit entries stay inside the use case's transaction (unchanged). Open redirect closed.
- CSP: no inline script or style anywhere, no `style=""` attributes, no `data:` images, no `on*` handlers.
- Blast radius: new routes, templates, static files; one added function in `sign_in.py`; settings
  `TEMPLATES`/`STATIC_URL`. The `handler500` must not change `/api/v1/` JSON 500 (middleware replaces it).
  Response `Cache-Control: no-store` on authenticated pages.

## Failing tests first (`returns_X_when_Y`, beside code, `test_*.py`)

Redirect (pure, `safe_redirect`):
- returns_home_when_next_is_an_external_url (`https://evil.test/x` -> role home)
- returns_home_when_next_is_protocol_relative (`//evil.test`) ; ..._backslash (`/\evil.test`)
- returns_home_when_next_is_empty_or_has_a_newline
- returns_path_when_next_is_a_local_path (`/clinician/` -> `/clinician/`)

Sign-in page:
- returns_form_with_labelled_email_and_password_when_get (200, one `h1`, each input has a `label for`)
- returns_redirect_to_role_home_and_cookie_when_credentials_are_right, for each of three roles
- returns_redirect_to_next_when_next_is_local_and_signed_in; returns_role_home_when_next_is_external
- returns_same_message_when_email_is_unknown_and_when_password_is_wrong (identical body text, 200 form)
- returns_lockout_message_when_ten_failures_in_window (message differs, says to try again later)
- returns_field_errors_referenced_by_aria_describedby_when_fields_are_empty
- returns_first_invalid_field_marked_data_autofocus_when_errors (only the first; email before password)
- returns_403_when_csrf_token_missing (client `enforce_csrf_checks=True`)
- returns_no_password_in_response_when_sign_in_fails (value of password never echoed)
- returns_home_redirect_when_already_signed_in

Role homes and sign-out:
- returns_redirect_to_sign_in_with_next_when_anonymous (each home)
- returns_greeting_with_user_name_when_role_matches (each role)
- returns_forbidden_page_when_role_differs (6 combinations, status 403)
- returns_redirect_to_sign_in_when_session_is_expired_or_user_deactivated
- sign-out: returns_405_when_get; returns_redirect_and_cleared_session_when_post (session row deleted,
  next request to a home redirects to sign-in); returns_403_when_csrf_missing

Layout and errors:
- returns_language_one_main_skip_link_and_stylesheet_when_any_page_is_rendered (`lang="en"`, one `<main id>`,
  skip link targets it, header shows name and sign-out form only when signed in)
- returns_404_page_with_correlation_id_when_path_is_unknown (`DEBUG` off, header value equals page text)
- returns_403_page_with_correlation_id; returns_500_page_with_correlation_id_and_no_trace_when_view_raises
- returns_json_404_when_api_path_is_unknown (regression, unchanged)
- returns_product_name_and_sign_in_link_when_root_requested
- returns_404_when_style_requested_and_debug_off; returns_every_component_when_debug_on
  (each component's class name appears; notice kinds and badge states each with text label)
- returns_no_inline_script_or_style_when_any_page_is_rendered (no `<style`, `style=`, `on\w+=`, inline `<script`)
- returns_css_file_when_static_is_requested (200, `text/css`, with DEBUG off)
- css contrast test (pure): a token-pair table in a test parses `tokens.css` and asserts ≥4.5:1 text,
  ≥3:1 for focus ring and borders of controls; proves contrast the server can prove.

Each test proven red for the right reason before green; mutate `safe_redirect` when `make mutate` exists.

## Trust boundaries

- Form POST (email, password, `next`, CSRF token): required-field check, email lower-cased by the use case,
  `next` through `local_path_or_home`; password never rendered back or logged.
- Query `next` on GET is re-validated when rendered into the hidden field and again on POST.
- Session cookie: resolved by `resolve_session` (unknown/expired/deactivated = anonymous).
- Correlation id from header already validated by middleware (`is_sane_correlation_id`), auto-escaped in templates.
- Template output auto-escaped; no `|safe` except none.

## Vocabulary used

Visitor, Patient, Clinician (public word "provider" only where users read it), Admin, User, Session,
SignInFailure, AuditLogEntry (via use case). Home enum values: patient portal, clinician workspace, admin console.

## Not doing

No new dependency (no whitenoise, no Node, no icon font), no CSS framework, no JS beyond the one tiny
file, no Django auth/messages/sessions apps, no DRF for pages, no change to API contract or lockout
rules, no public search, no dark mode, no web fonts (system stack, so no `font-src` change), no health-icons
use yet (specialty icons arrive with search), no abstraction without a second caller except the
components the task names, no real home content.

## Open risks

Visual result unverified (no browser): layout at 375/768/1440, contrast in practice, focus ring appearance.
Django 6.1 DEBUG shows technical error pages, so our 404/500 are only reachable with DEBUG off; tests set it off.

## Architect review

Verdict: approve.

- Ladder: no new dependency, one tiny JS file, `serve` for static avoids whitenoise. Components limited to the ones the task names. Fine.
- Tests: named as behaviours, include edge and error paths (open redirect variants, CSRF, lockout, enumeration, 6 role pairs, CSP-clean HTML). Fine.
- Security: authorization from session, `next` validated on GET and POST, password never echoed, CSP respected. Lockout check keys on the email hash, so unknown emails lock out the same way: no enumeration.
- Notes for the writer (not blocking): (a) `Dockerfile`/`.dockerignore` currently do not mention `static/`; verify it is copied. (b) Keep `is_locked_out` window logic shared with the use case (`is_locked`, `window_start`), not duplicated. (c) `django.views.static.serve` is documented as not for production; note this in an ADR line or comment since the product is local-only. (d) Handler views must tolerate an unbound request context.
