# Task 05b: screens hardening

Focal point: `PageView` (`scheduling/views/pages/page_view.py`) renews the session cookie. The other six items are one-line fixes beside it.

## Blocks (one sentence each)

1. **Page cookie renewal.** `PageView._resolve_user` also keeps the `ResolvedSession` (as `self.resolved`); `PageView.dispatch` wraps `super().dispatch(...)`/403 response and, when `resolved.extended` the status is < 400 and `SESSION_COOKIE not in response.cookies`, calls `set_session_cookie(response, token, resolved.session.expires_at)`. The `not in` guard keeps `SignInPage.post`'s fresh cookie from being overwritten by the old token. Same rule as `ApiView.finalize_response`. Redirects (302) count, since they are < 400.
2. **Shared edges.** In `static/css/base.css`, header and footer get the same inner width as `.page`: `.site-header` and `.site-footer` use `padding-inline: max(var(--space-4), (100% - var(--page-width)) / 2 + var(--space-4))`, with the 48rem media query raising `--space-4` to `--space-6`. `.page` padding is unchanged. This is a CSS change, so the orchestrator checks it in Chrome at 1440 px. Verified: `.page` is `max-width: var(--page-width)` (72rem, defined in `tokens.css`) with `margin: 0 auto`; header/footer are full width, so `100%` in padding is the viewport width and the formula matches. Declare the inline padding once as `--page-gutter` in `base.css` so all three share it. The footer `p` keeps no extra max-width needed; drop its `max-width`/auto margin.
3. **Favicon.** Add `static/favicon.svg` (hand-drawn plus/cross on the brand colour from `tokens.css`; no healthicons file needed). Add `<link rel="icon" href="{% static 'favicon.svg' %}" type="image/svg+xml">` to `base.html`. Add a `/favicon.ico` route in `drlibre/urls.py` as `RedirectView(url="/static/favicon.svg", permanent=False)`, because browsers ask for that path regardless of the link.
4. **Lockout message.** `LOCKED_OUT` in `sign_in.py` becomes "Too many attempts. Try again in 15 minutes." The minutes come from `LOCKOUT_WINDOW` in `domain/lockout_rules.py` so the number cannot drift.
5. **CSRF cookie.** `CSRF_COOKIE_HTTPONLY = True` in `drlibre/settings.py`. The hidden `csrf_token` form field still works because the template tag does not need script access.
6. **Card spacing.** `components.css`: `.card > :first-child { margin-top: 0; }`, so the heading's `margin-top: var(--space-6)` stops adding to the card padding. Checked in Chrome.
7. **Scrollable table region.** The `/style` specimen already has `tabindex="0" role="region" aria-label`. Pin it with a test. If any other template renders `.table-wrap` without these, fix it there. Today `style.html` is the only user. CSS: add `.table-wrap:focus-visible` outline if `craft-floor.md` requires a visible focus ring. Read it before the CSS edit.

## Files to touch, in order
`scheduling/views/pages/test_pages.py` (tests first), `page_view.py`, `sign_in.py`, `drlibre/settings.py`, `drlibre/urls.py`, `base.html`, `static/favicon.svg`, `static/css/base.css`, `static/css/components.css`, maybe `tokens.css`.

Not touching: `ApiView`, `session_cookie.py`, `use_cases/session.py` (the extension rule is right), models, migrations, API schemas, ADRs, the `/style` page markup (unless item 7 turns out to be missing there).

## Failing tests first (`returns_X_when_Y`)
- `returns_renewed_session_cookie_when_page_request_comes_after_half_the_lifetime`: sign in as ADMIN (12 h, clock at START), move `clock.now_utc` to START + 7 h, GET `/admin-console/`. The `drlibre_session` cookie's `expires` attribute (what `set_session_cookie` emits via `http_date`; `max-age` is unset) equals `http_date((START + 19 h).timestamp())`. Existing tests assert `httponly`/`samesite` through `response.cookies[COOKIE]`, same access path.
- `returns_no_session_cookie_when_page_request_comes_before_half_the_lifetime`: same, at START + 1 h, no Set-Cookie for the session.
- `returns_renewed_cookie_on_forbidden_page`: PATIENT (session past half life per the domain rule for patients; if patients never extend, use CLINICIAN) opens `/admin-console/`; 403 still carries the renewed cookie.
- `returns_new_session_cookie_when_signed_in_user_past_half_life_posts_other_credentials`: signed in as ADMIN, clock START + 7 h, POST `/sign-in` valid credentials of another user; the final `drlibre_session` value is the new token, not the old one. Fails without the guard.
- `returns_icon_when_favicon_is_requested`: `/favicon.ico` answers 302 to `/static/favicon.svg`, which answers 200 `image/svg+xml`. Follow-up GET `/static/favicon.svg` uses the existing `serve` route in `drlibre/urls.py:29` (document_root `static/`), which works in the test client regardless of DEBUG; no staticfiles finder. The sign-in page HTML contains `rel="icon"`.
- `returns_lockout_message_with_wait_stated_once_when_account_is_locked_out`: after 10 failures the page contains "Try again in 15 minutes." and does not contain "later".
- `returns_httponly_csrf_cookie_when_sign_in_form_is_requested`: GET `/sign-in`; `csrftoken` cookie has `httponly` true. Needs the CSRF cookie to be set: the form renders `csrf_token`.
- `returns_focusable_labelled_region_when_table_is_wider_than_its_wrapper`: `render_to_string('style.html')` (no DEBUG route needed), parse with `html.parser`, find the element with class `table-wrap`: `tabindex="0"`, `role="region"`, non-empty `aria-label`. This proves the attributes, not the overflow itself. Passes today, so it is a pin, not a red test; prove it can fail by removing `tabindex` once.

Each test except the table pin must fail before its fix (red proven).

## Invariants and blast radius
- Session authorization still comes from the cookie token resolved server-side; the renewed cookie reuses the same token, no new token. Sliding rule stays in `domain` (`extended_expiry`); views only format.
- Cookie attributes stay: HttpOnly, SameSite=Strict, Secure when `HTTPS_ONLY`.
- No effect on booking, double-booking or audit log. Blast radius: all pages that resolve a session; CSS affects every page layout.
- Lockout text change: no other code reads the string (grep showed one use).

## Trust boundaries
Cookie in, session lookup by hash (existing). Nothing new accepted from the client; the favicon route redirects to a fixed path.

## Domain vocabulary
Session, User, Admin, Patient, Clinician (roles in tests); no new entities.

## Will not do
No new abstraction, no middleware for cookie renewal (one base class already owns page dispatch), no shared helper between `ApiView` and `PageView` (two callers, three lines; revisit if a third appears), no new dependency, no icon pipeline, no refactor of `sign_in` or CSS.

## Architect review

Verdict: approve.

- Ladder: smallest change, in the right place (`PageView` owns page dispatch; no middleware, no shared helper, no dependency). Each of the seven items maps to one block.
- The earlier objections are addressed: the `SESSION_COOKIE not in response.cookies` guard protects `SignInPage.post` (and any cookie deletion on sign-out), with a named failing test. Item 7 uses `render_to_string('style.html')`. The expiry assertion names the `expires` attribute via `http_date`.
- Tests are named as behaviours, include the edge cases (before half life, 403, other-credentials sign-in) and a red-proof for the pin test.
- Security: the same token is reused, authorization stays server-side, cookie attributes unchanged, CSRF cookie becomes HttpOnly, favicon redirect is a fixed path.
- Watch in implementation: the PATIENT 403 test must use a role that actually extends (the plan names the CLINICIAN fallback). Derive the "15 minutes" from `LOCKOUT_WINDOW`. Keep the CSS `calc` inside `max()` valid with the `--space-4` media-query override, and confirm it in Chrome.
