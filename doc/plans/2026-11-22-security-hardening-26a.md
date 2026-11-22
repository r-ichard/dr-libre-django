# Task 26a: abuse limits and what an answer may be

Slice: items 3a, 3b, 3c, 4, 5, 6, 7 (all of 26a). Each is small and independent; order below puts the
two that need a migration or a cookie (5, 6) last, so if the run is short they are the ones to cut
and move to `## Not in this run`. Items 1-3, 8-12 of task 26 belong to later runs (26b..).

Focal point: `sign_in_with_password` (3a, 4) and `ApiView` (3b, 3c). No new dependency.

## Findings from reading (what is already true)
- `rate_limits.take_hit` already serialises per key with `pg_advisory_xact_lock` (hold, code, link, token
  scopes). Booking code attempts: `verify_hold` takes `select_for_update` on hold and code row. Link
  use: `select_for_update` on the link row. Sign-in lockout: no lock (the defect, #46).
- `ApiView.finalize_response` sets no cache headers; `/fhir` does (`fhir_entry`).
- `refuse_oversized` reads `request.body` (JSON depth) so a media-type check must run before it.
- `failure_response.handle_exception` already maps `UnsupportedMediaType` to the contract's invalid_input.
- Email: `user_rules.EMAIL_PATTERN` accepts `a@b`; `audit_metadata.HOSTNAME_PATTERN` (dotted host) and
  Django's `validate_email` (sign-in page, DRF `EmailField`) refuse it; three rules in three places.

## Blocks (one sentence each)
1. `use_cases/advisory_lock.py` (new): move `_lock_keys` out of `rate_limits.py` as `lock_keys(hashes)`; second caller makes it a real abstraction.
2. `use_cases/sign_in.py`: take the per-address advisory lock (key `hash_email(email)`) first in the transaction, in `sign_in_with_password` and `record_wrong_password`, so count, hasher verdict and failure write are one step per address.
3. Same file: write `auth.lockout` only when no `auth.lockout` entry exists for the newest failure row's id (stable until a new failure is written, so once per window), still under the lock.
4. `views/api_view.py`: `initial()` raises `UnsupportedMediaType` for a write whose `Content-Length` > 0 and media type is not `application/json`, before `refuse_oversized`; bodyless writes (logout, delete) pass, the Origin check and SameSite cookie still cover them.
5. `views/api_view.py`: `finalize_response` always `patch_vary_headers(("Cookie",))`, and `Cache-Control: no-store` when the request carries the session cookie.
6. `domain/visitor_rules.py`: one `is_valid_email(address) -> bool` (length <= 254, one `@`, no whitespace, dotted host via `HOSTNAME_PATTERN`); `user_rules.check_email`, `booking_holds._invalid_input`, `sign_in_link.ask_for_link`, `auth_schemas` (drop duplicate `email_domain` try) and page `sign_in.py` (drop Django `validate_email`) all call it. Local part stays free-form (no new TLD or quoting rules).
7. Search limit: `RateLimitScope.SEARCH` in `rate_limit_rules.py` (per_address only, 120 per hour window); `take_hit` takes `email: str | None` and skips the email counter when None; new `use_cases/search_limited.py::search_for_visitor(kind, query, now, address) -> Result[SearchPage]` calls `take_hit` then `search_public`; `views/search.py` and `pages/search_page.py` call it with `network_address(request)`; page answers refused via `refused_page`/rate-limited page, API via the failure contract (429).
8. Migration `0016_search_rate_limit_scope.py` (hand-written): replace the `ratelimithit` scope check constraint and choices with the new scope.
9. Query bound: if the measured count varies with catalogue size, fix `load_catalog`/`load_schedules` callers (the page's `load_filter_options` also loads the catalogue: share one catalogue load per request); otherwise only the test guards it.
10. Hold binding: `views/hold_cookie.py` (new): cookie `drlibre_hold` = HMAC(SECRET_KEY, "hold-browser:" + hold id), HttpOnly, SameSite=Strict, `secure=settings.HTTPS_ONLY`, expires with the hold (`HOLD_LIFETIME`); `booking_details._create_hold` sets it on the 303; `CodePage.get/post` and `ResendPage.post` answer `_expired` (the missing-hold page, same status and body) when the cookie does not match. No schema change.

## Files, in order
Tests first for each block, then: `use_cases/advisory_lock.py`, `use_cases/rate_limits.py`, `use_cases/sign_in.py`, `domain/visitor_rules.py`, `domain/user_rules.py`, `use_cases/booking_holds.py`, `use_cases/sign_in_link.py`, `views/auth_schemas.py`, `views/pages/sign_in.py`, `views/api_view.py`, `domain/rate_limit_rules.py`, `models` (choices follow the enum), migration, `use_cases/search_limited.py`, `views/search.py`, `views/pages/search_page.py`, `views/hold_cookie.py`, `views/pages/booking_details.py`, `views/pages/booking_code.py`. Update `doc/backlog.md` only via orchestrator.

Not touched: FHIR views, `fhir_entry` headers, `ClinicianProfile` and admin code, public detail pages (`public_details.py`) and their catalogue loads, `models` of `BookingHold` and `SignInFailure`, deployment settings (items 1-3 of 26).

## Invariants and blast radius
- Append-only audit: the lockout entry is still written inside the sign-in transaction, only less often. `auth.login_failed` and `auth.login` unchanged.
- Sign-in answers stay equal on every path, one hasher call per attempt (lock wait adds latency per address only).
- Authorization stays server-side: the hold cookie is proof of the browser, never the identity; verification still needs the mailed code. API tokens and session cookies unchanged.
- Double booking: untouched (no change to placement). Hold creation still replaces the earlier hold per email.
- Blast radius: every `/api/v1` response gets `Vary: Cookie`; every API write with a body now needs JSON (a client that sent form or text bodies breaks; the product's own clients send JSON; confirm by running the whole suite). Email rule tightens for the admin user form and holds: `a@b` refused everywhere.

## Failing tests to write first (name; expected value)
- `use_cases/test_sign_in_race.py` (`django_db(transaction=True)`, threads with a Barrier as `test_sign_in_link_race.py`):
  `returns_at_most_ten_hasher_runs_when_fifty_wrong_passwords_arrive_together` — a patient exists; 50 parallel wrong passwords for one address; exactly 10 `auth.login_failed` rows and 10 `SignInFailure` rows (spec 12.1: ten in fifteen minutes); the other 40 answered `unauthenticated` with the hasher counted by patching `check_password` (<= 10 calls). Same for an unknown address.
  `returns_one_session_when_right_password_races_with_failures` is not planned (not asked).
- Other counters, same file style, each shown serialised:
  `returns_five_holds_at_most_when_ten_threads_hold_for_one_email` (spec 7.5: five per email per hour);
  `returns_three_code_resends_at_most_when_ten_threads_resend` (three per hour);
  `returns_three_links_at_most_when_ten_threads_ask_for_a_link` (three per hour);
  `returns_five_failures_counted_when_twenty_threads_present_the_same_bad_token` (five per token per hour);
  `returns_attempt_count_five_at_most_when_ten_threads_post_wrong_booking_codes` (`MAXIMUM_ATTEMPTS`, from `domain/booking_codes.py`). If any of these fails, the fix is in that use case; if it passes it stays as proof.
- `test_sign_in.py`: `returns_one_lockout_entry_when_a_locked_address_tries_five_more_times` (exactly 1 `auth.lockout`, failure_count 10); `returns_second_lockout_entry_when_a_new_window_locks_again` (2).
- `views/test_api_cache_headers.py`: `returns_no_store_and_vary_cookie_when_signed_in_caller_reads_api` (header `Cache-Control: no-store`, `Vary` contains `Cookie`); `returns_vary_cookie_without_no_store_when_visitor_reads_public_search`; also an error answer (401) carries `Vary: Cookie`.
- `views/test_api_content_type.py`: `returns_invalid_input_when_write_body_is_text_plain` for a login post with `text/plain` and a cookie-authenticated write, asserted with the real browser headers (`Origin` set, cross-site check on); `returns_unchanged_answer_when_write_body_is_json`; `returns_success_when_write_has_no_body` (logout); and the body is never read: patch `request.body` access to fail / assert `refuse_oversized` not reached for text/plain.
- `domain/test_visitor_rules.py`: `returns_false_for_a_at_b`, `returns_false_when_address_has_space_or_two_at_signs_or_no_dot_host`, `returns_true_for_name_at_example_dot_org_with_plus_tag`, `returns_false_when_longer_than_254` (boundary 254/255). Mutation-tested (`make mutate`). `test_user_rules.py`: `returns_invalid_input_on_email_field_when_address_is_a_at_b`. Page and API sign-in, booking form and admin user form: each refuses `a@b` with its existing message.
- `use_cases/test_search_limited.py`: `returns_rate_limited_when_address_searches_121_times_in_an_hour`; `returns_page_again_after_the_hour`; a different address is not limited. `views/pages/test_search_page.py` and `views/test_search_api.py`: the 121st answer is the page refusal / API 429 in the contract.
- Query bound: `returns_same_query_count_when_catalogue_holds_3_or_30_clinicians` using `CaptureQueriesContext` on page and API; the number is asserted as a constant (value fixed after the first measure, stated in the test).
- `views/pages/test_booking_code_page.py`: `returns_missing_hold_page_when_another_browser_opens_the_code_page` (same status and body as a random hold id, no masked email); same for post code and resend; `returns_code_page_when_the_booking_browser_opens_it`; the hold cookie flags (HttpOnly, SameSite=Strict). Browser-form rules: `browser_client` with Origin and cross-site check.

Each test is shown failing for the stated reason before the fix (red proven), and the race tests are run 10 times (`parametrize`) as the link race is.

## Trust boundaries
- Email, password, JSON body, content type, `Content-Length`, search query, hold id in the path, hold cookie: all from the client. Email by one rule (6); content type refused before parse (4); search query already parsed by `parse_search_query`, now limited per network address from `REMOTE_ADDR` only (`network_address`); hold id plus cookie proof compared with `hmac.compare_digest`.
- Counters hold only keyed hashes (existing rule); no new sensitive log line; the lock key is an HMAC, never the address.

## Domain entities
Visitor, Patient, ApiClient, BookingHold, VerificationCode, SignInLink, SignInFailure, RateLimitHit, AuditLogEntry, User.

## Will not do
No new setting, no proxy handling (26 item 3), no Redis/cache, no CAPTCHA, no change of lockout numbers, no middleware for headers (`ApiView` is the one place), no deprecated-rule full RFC email validator, no limits on public detail pages, no refactor of `search.py`.

## Not in this run
- Items 1-3 (start-up checks, cookies flags, proxy trust), 8-12 of task 26: later runs (26b and on).
- Rate limit on public detail pages and `/fhir` search.

## Architect review

Verdict: approve, with one required adjustment (A1) and three notes.

Judged well: coherent slice (all of 26a), no new dependency, right layers (lock in use case, headers in `ApiView`, email rule in domain), first tests named as behaviours with spec numbers, race tests for every other counter kept as proof, red-proven step stated.

- **A1 (required, block 4):** gating on `Content-Length > 0` leaves a bypass: a chunked `text/plain` write has no `Content-Length` and passes unchecked, which defeats 3c ("refuse any content type but JSON on a write"). Refuse when a `Content-Type` is present and is not `application/json`, or when it is absent and the body is non-empty/length unknown. Only a write with no `Content-Type` and no body passes. Add a test: `text/plain` with no `Content-Length` (chunked) answers invalid_input; also `application/json; charset=utf-8` passes.
- N1 (block 10): one fixed cookie name `drlibre_hold` means a second hold in the same browser (another email, another tab) invalidates the first tab's code page. Accept and state it in the test, or name the cookie per hold id. Pick one; do not leave it implicit.
- N2 (block 3): the "once per window" rule rests on the newest failure row id. Add the edge test: failures aging out of the window and a new lock writes a second entry (already listed) and a lockout never fires while under the threshold.
- N3 (block 7): `search_for_visitor` rate limit keys on `REMOTE_ADDR`; in the containers every caller may share one address. State that in the test or plan as known and accepted (proxy trust is task 26 item 3), so the limit is not mistaken for per-user.
