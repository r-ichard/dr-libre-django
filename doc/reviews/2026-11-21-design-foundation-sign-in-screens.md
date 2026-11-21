# Review: task 05a, design foundation, sign-in screens, role homes, error pages

Diff `main...HEAD`, 42 files. Commits `verify_green..prove` (65fca48) touch only
`scheduling/views/pages/test_pages.py`: no product line left behind. Gates pass per the check stage
(717 tests, lint, comment gate, escape hatches clean). Visual result unverified: no browser.

## Plan in one sentence per block (§2.5)
- `page_view.py`: resolve session cookie to user, redirect anonymous to sign-in with `next`, 403 on wrong role. Confirmed at a glance.
- `sign_in.py` (views): validate presence, call use case, same message for unknown email and bad password, lockout message, safe redirect. Traced `is_locked_out` and `focus` flow.
- `safe_redirect.py`: refuse non-slash, `//`, backslash, control characters, then Django's host check. Confirmed.
- Templates and CSS: reusable includes; field and summary wiring traced for aria ids.

## Findings
1. **Low** `scheduling/use_cases/sign_in.py:80`. `is_locked_out` is a second query after the failed sign-in, so the page and the use case can disagree for one request (race at the threshold). Risk: wrong message once. Smallest fix: return the lockout reason in the use case's `Failure`.
2. **Low** `drlibre/urls.py:29`. Static files via `django.views.static.serve` with DEBUG off. Acceptable for a local-only product (owner decision, comment says so); revisit before any hosted deployment.
3. **Low** `scheduling/views/session_cookie.py` SameSite=Strict: a link from an external site (for example the sign-in link in email) lands anonymous on first navigation. Not new to this task; matters for task passwordless links.
4. **Nit** `scheduling/templates/components/field.html:8` single very long line; hard to read and diff. Split with template comments or whitespace.
5. **Nit** `scheduling/views/pages/sign_in.py:21` `SummaryItem` and the `SignInForm` focus properties are sign-in specific; extract when a second form needs them (rule of two callers).
6. **Info** `scheduling/views/pages/errors.py:9` handlers render without a signed-in user, so the header shows no name on 404 and 500. Acceptable; note for consistency.

## Checked, no defect
- Authorization from the session cookie only; `next` never trusted (`safe_redirect.py:11`), tested with hostile values.
- CSRF middleware active; sign-out is POST-only with a token; sign-in form carries `{% csrf_token %}`.
- CSP-compatible: no inline script or style; focus script is a static file.
- No sensitive data in logs or URLs (`next` is a local path only). Same message for wrong email and password.
- No new dependency. Pages never cached (`add_never_cache_headers`).
- No escape hatches; functions and files within size limits.

## Blocking
None.

## Later
- Fold lockout reason into the sign-in `Failure` (finding 1).
- Revisit static serving and SameSite for any non-local deployment (2, 3).
- Split long template lines (4); extract shared form helpers on second use (5).
- Browser checks by the orchestrator at 375, 768, 1440 px, keyboard only, accessibility audit.
