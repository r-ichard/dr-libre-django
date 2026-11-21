# Task 13a: sign-in link works in a browser

Focal point: `LinkContinuePage` in `scheduling/views/pages/sign_in_link.py`, plus one setting.

## Why the policy works
`no-referrer` makes browsers send `Origin: null` on a form POST, which Django's origin check refuses.
Choose `Referrer-Policy: strict-origin` on the three responses of this page (replaces `no-referrer`).
- Browser sends the real `Origin: https://site` on the POST, so the check passes.
- Referrer is cut to the bare origin (scheme, host, port), on every request, same-site or not: the
  `?token=` query never appears in a referrer, so it cannot reach another site (or our own asset logs).
- `strict-` sends nothing on an https to http downgrade.
Rejected: dropping the override (site default `same-origin` keeps the full URL, token included, on
same-origin sub-requests); `origin` (same, but sends over downgrade).

## Blocks (one sentence each)
1. `sign_in_link.py`: `_without_referrer` sets `strict-origin`; rename to `_origin_only_referrer`, constant for the value.
2. `drlibre/settings.py`: `CSRF_FAILURE_VIEW = "scheduling.views.pages.errors.csrf_failed_page"`.
3. `scheduling/views/pages/errors.py`: `csrf_failed_page(request, reason="")` renders `errors/403.html` status 403 via `render_page` (correlation id included); reason is dropped, never shown or logged with values.
4. `scheduling/use_cases/background_mail.py` `_send`: keep `except OSError`, add `except Exception` (broad catch justified: future would swallow it) logging `"background mail not sent"` with `exc_info` of the type only, no address or body. Log the exception class name, not the message (SMTP errors can echo the address).
5. New test helper `scheduling/views/pages/browser_client.py` (below).

## Test helper (reused by later page tasks)
`scheduling/views/pages/browser_client.py`: `browser_client() -> Client` (`enforce_csrf_checks=True`) and
`browser_post(client, path, data, origin=SITE_ORIGIN)` that first GETs `path`'s form page to obtain the csrf cookie,
puts `csrfmiddlewaretoken` from the cookie/page in data, sets `HTTP_ORIGIN` to origin (`"null"` or another site allowed).
Helper is test support, beside tests (not a production module; excluded from nothing special, name does not match `test_*`).

## Failing tests first (`returns_X_when_Y`)
In `test_sign_in_link_pages.py`, `test_pages.py`, new `test_browser_forms.py`:
- `returns_303_when_continue_pressed_as_browser_does` : POST /sign-in/link with token + csrf + own Origin: 303 to patient home, link used. (Fails today? Test client passes; red comes from the next ones and the header test.)
- `returns_origin_only_referrer_policy_when_link_page_is_opened` (GET, invalid 400, success 303): header == `strict-origin` (replaces the `no-referrer` test).
- `returns_403_when_continue_posted_with_origin_null`, `..._with_other_site_origin`: 403, link `used_at` None.
- same trio (own origin passes; `null` and other origin 403) for sign-in POST `/sign-in`, sign-out POST `/sign-out`, link request POST `/sign-in/email-link` .
- `returns_product_403_page_with_correlation_id_when_csrf_check_fails`: body contains the 403 page heading and the correlation id; no "DEBUG" or "template tag" text; run with `DEBUG` on and off (`settings.DEBUG`).
- `returns_logged_error_without_address_or_body_when_send_raises_other_exception` (backend raises `RuntimeError("x@example.test body-secret")`): log record "background mail not sent", text lacks address and body; `wait_until_idle` returns.
Red proof: restore `no-referrer`/remove setting and see them fail.

## Files, in order
`test_browser_forms.py` (+ helper), `test_background_mail.py`, `test_sign_in_link_pages.py`, `sign_in_link.py`, `errors.py`, `settings.py`, `background_mail.py`.
Not touched: `base.html`/templates, `api_view.py` (own origin logic for API), middleware, security headers setting `same-origin`, models, domain.

## Invariants / blast radius
Tokens still spent only by POST; GET reads nothing; audit untouched; authorization untouched. Failure view only runs on CSRF refusal. Mail logging runs in background thread only.

## Trust boundaries
Browser POST: CSRF token + Origin checked by Django middleware (still enforced, `null` refused). Token from the form/query validated by `use_link` as before. Log output excludes address, body, exception message.

## Domain entities
Patient, SignInLink, Session, Notification (mail), Visitor.

## Not doing
No custom CSRF middleware, no `CSRF_TRUSTED_ORIGINS` change, no new dependency, no refactor of tests outside the four forms. Mutate: no `scheduling/domain` change, `make mutate` expected unchanged.

## Architect review
Verdict: approve.
- Ladder: smallest fix (one header value, one setting, one view, one `except`, one helper). No new dependency or abstraction; helper has the required second callers (four forms).
- Policy reasoning answers the task: `strict-origin` gives a real `Origin` on POST and strips the query, so the token cannot leave in a referrer.
- Tests first, as behaviours, with `null` and other-origin refusals, both `DEBUG` values, and a log test that checks address and body are absent.
- Security: CSRF stays enforced; log omits message text; failure view drops `reason`.
- Notes for the build stage (not blocking):
  - `browser_client.py` imports `django.test` inside a production package. Prefer a test-only location (for example a `conftest.py` fixture or `scheduling/testing/`) and check `make gate` and mypy accept it.
  - `/sign-out` is POST-only, so `browser_post` needs a way to fetch the csrf cookie from a page that renders the form (the patient home), not `GET path`.
  - Broad `except Exception` needs a rationale comment and must name its lint code if ruff flags `BLE001`.
  - Keep the `no-referrer` test replaced, not deleted, and confirm the red run fails for the stated reason.
