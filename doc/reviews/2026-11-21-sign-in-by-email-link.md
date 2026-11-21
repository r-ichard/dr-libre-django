# Review: task 13, sign-in by email link

Diff `main...HEAD`, 47 files. Commits after `verify_green` through `prove` touch only
`scheduling/use_cases/test_background_mail.py`: no product or migration line left behind.

## Confirmed at a glance
- `use_cases/sign_in_link.py`: ask does the same steps for every address; only an active Patient
  gets one INSERT and a mail, sent after commit from a pool (`background_mail.py`), so mail latency
  and failure cannot differ between answers. Answer is 202 `{}` for all but rate limit and invalid
  address, neither of which depends on the account.
- Token: `secrets.token_urlsafe(32)` (256 bits), only `hash_token` stored. `django.request` and
  `django.server` loggers discarded (`drlibre/settings.py:101-102`), so the runserver request line
  with the query string is not written. `test_sign_in_link_output.py` plants a token through page
  and API and reads logs, stdout/stderr, rows.
- Use: GET page reads nothing, POST spends, `select_for_update(of=("self",))` on the link row,
  303 to `/patient/` with no token, `Referrer-Policy: no-referrer`. Refusal is one message for
  expired, used, cancelled, unknown, non-Patient, inactive (`sign_in_link.py:28-29,82-92`).
- Session via `open_session(..., SessionKind.EMAIL_LINK)` (task 05 use case).
- Lock order: `_patient_of` no longer locks the user row (`booking_verification.py:102-106`);
  `test_booking_lock_order.py` races the two paths.
- Mail down: hold and resend roll back and answer 503 `mail_unavailable` (`booking_holds.py:79-82,
  104-107`, `failure_response.py:32,47`); link ask never fails on mail.
- Migration 0009 is minimal and reversible; `doc/data-model.md` updated.

## Findings

1. **Blocker (hard rule: write without audit)** `scheduling/use_cases/purge.py:32,34`.
   Expired `SignInLink` rows are deleted, but the audit entry is written only when
   `session_count or failure_count or hit_count`, and its metadata carries no link count. A purge
   that removes only links leaves no audit entry, and a purge that removes links and something else
   hides the link count. Smallest fix: add `link_count` to the condition and a
   `"sign_in_link_count"` entry to `counts`, plus a test in `test_purge.py` for a links-only purge.

2. **Later** `scheduling/use_cases/sign_in_link.py:47`: `_audit("auth.link_requested", link_id, ...)`
   reuses `link_id` for requests that created no link (non-Patient, unknown). The id is a fresh
   random value so it does not leak, but an entity id that names no row is surprising. A comment
   or a separate `new_identifier()` for the no-link case would remove the doubt.

3. **Later** `background_mail.py:50`: only `OSError` is caught. `smtplib.SMTPException` is an
   `OSError` subclass, so SMTP failures are covered; any other exception in a worker is held in the
   future and never logged. Log with `logger.exception`-free handling of `Exception` at the worker
   boundary if a backend other than SMTP appears.
4. **Later** mail queued but unsent when the process stops (pool is in-memory). Acceptable for a
   link the patient can ask for again; note it in the ADR if mail becomes a contract.
5. **Later** `views/pages/sign_in_link.py:47-48`: token is taken from POST or query; the form has
   no action, so the POST URL keeps the token in the address bar until the redirect. Fine now, but
   an explicit hidden `token` field would keep the token out of the posted URL.
6. **Later** timing is tested "as far as a test can" through call-count/step parity; a real latency
   comparison against a slow mail backend exists in `test_background_mail.py` and is adequate.

## Blocking
- `purge.py:32`: link purge deleted without an audit entry in the same transaction (finding 1).
  **fixed**: `test_purge.py::returns_audit_entry_when_only_links_were_purged` (counts tests updated for `sign_in_link_count`).

## Later
- Findings 2 to 6.

## Second pass (after `address`, commit 7fdeed2)

Diff since the first review touches `purge.py`, `test_purge.py` and this file only.
- `purge.py:34`: `link_count` now in the audit condition and in `counts["sign_in_link_count"]`;
  `test_purge.py::returns_audit_entry_when_only_links_were_purged` covers a links-only purge and
  the other counts tests carry the new key. Blocker 1 resolved.
- Re-read `sign_in_link.py`, `background_mail.py`, `views/auth.py`, `views/pages/sign_in_link.py`:
  authorization comes from the token row, not the payload; token hashed, never logged; every use
  and refusal audited in the transaction; no escape hatches; sizes within caps. `check` stage ran
  lint, tests (1746) and gate green after the fix. `make mutate` was not re-run in this review.

## Blocking
- none

## Later
- Findings 2 to 6 above. Finding 3 stays the one to pick up first: an exception other than
  `OSError` in `background_mail._send` is held in the future and never logged.
