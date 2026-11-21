# Review: task 13a, sign-in link in a browser

Diff `main...HEAD`: 9 files, product change is small (header value, one setting, one view, one `except`).

## Stage trace (§13.3)
`verify_green`..`prove` has an empty diff: proof left no trace. The `refactor` commit touched product lines
(settings, background_mail, sign_in_link), which is allowed at that stage.

## Findings

1. **Low**, `scheduling/use_cases/background_mail.py:48`. Plan block 4 promised logging the exception class name.
   The code logs only "background mail not sent", so a non-`OSError` failure cannot be told from a mail-server outage.
   Risk: hard to diagnose. Fix: `logger.error("background mail not sent", extra={"error_type": type(error).__name__})`
   (class name only, never the message). Not a swallow: the failure is logged, and the test proves no address or body leaks.
2. **Low**, `scheduling/views/pages/browser_support.py:12-18`. The helper sits in a production package, and the
   architect note suggested a test-only location. It imports `django.test` at import time, but nothing in production imports it.
   Fix, later: move it beside a `conftest.py` or into `scheduling/testing/`.
3. **Low**, `scheduling/views/pages/browser_support.py:27`. `browser_post` always fetches the token from `/sign-in`, so
   a form behind another page works only because the cookie is global. Fine for the four forms, and worth noting for later page tasks.
4. **Info**, `scheduling/views/pages/errors.py:12`. `csrf_failure_page` drops `reason`, so a CSRF refusal leaves no
   server-side trace beyond the request log (status 403). Fix, later: log the reason category, without values.
5. **Info**, plan names `csrf_failed_page`, code has `csrf_failure_page`. Setting and view agree, so there is no defect.

## Checked, no defect
- `Referrer-Policy: strict-origin` on GET, 400 and 303 of the link page, so the browser sends the real `Origin`
  and the referrer is cut to the origin. The token in the query cannot leave in a referrer. The plan says why.
- CSRF stays enforced: tests assert 403 for `Origin: null` and another site's origin, on all four forms, and that the link stays unused.
- Refusal page: product 403 with the correlation id, tested with `DEBUG` on and off, and without "DEBUG" or "template tag" text.
- `except Exception` carries a named code (`BLE001`) and a reason. It is not a swallow, and no `Any`, `cast` or bare ignore is added.
  (`# type: ignore[attr-defined]` and `[operator]` in tests name their codes.)
- No dependency added, no model or migration, no write path changed, so no audit or double-booking impact.
- Gates reported green by the check stage: lint, test (1765), gate. `make mutate` not re-run here, and no `scheduling/domain` change.

## Blocking
None.

## Later
- Finding 1: log the exception class name.
- Finding 2: move the browser helper to a test-only location.
- Finding 4: log the CSRF failure reason category.
