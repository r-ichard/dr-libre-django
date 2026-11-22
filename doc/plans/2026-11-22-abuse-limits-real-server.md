# Task 26a2: abuse limits, as the real server and a real visitor meet them

Slice: items 1 to 7, all. Each is small; they share two files (`rate_limit_rules.py`, `hold_cookie.py`). If the run runs long, cut in this order and say so: item 5 first, then item 2. Items 1, 3, 4, 6 are the product defects and stay.

Branch: `task/26a-security-abuse-limits` (held). Changes only what 26a added.

## Focal point

`refuse_non_json_write` (item 1) and `take_hit` (item 4, feeds items 3 and 4 alike).

## Blocks, one sentence each

1. `views/input_limits.py::refuse_non_json_write`: a write with no body passes whatever its type says; a write with a body (Content-Length not empty/0, or Transfer-Encoding) must be `application/json`, else `UnsupportedMediaType` before the body is read. Drop the "empty media type" branch. DRF `_parse` returns `{}` for a zero-length stream before it looks at the media type, so a route that needs fields then names them (to be confirmed by the new test; if DRF still refuses, set empty data in `ApiView.initial` for bodyless writes, nothing more).
2. `views/test_api_live_server.py` (new): two tests over a real socket (`http.client` against pytest-django `live_server`, whose class is Django's `WSGIServer`, the class `runserver` uses): bodyless `POST /api/v1/auth/logout` without `Content-Type` is not 400; a `text/plain` body to `/api/v1/auth/login` is 400 `invalid_input` naming the body.
3. `views/test_api_bodyless_writes.py` (new): enumerate `/api/v1` write routes from the URL configuration (walk `get_resolver().url_patterns`, take view classes of `ApiView` with a `post/put/patch/delete` handler, skip the catch-all `NotFoundView`; the uuid converter gets a made-up uuid), send each with no body and `CONTENT_TYPE=text/plain`, assert the answer is not 400 with message "The request body is not readable." A route that needs fields answers 400 naming fields, one that needs none does its work (or answers 401/403/404 for lack of a session; never the unreadable-body message).
4. `domain/rate_limit_rules.py`: add pure `retry_after_seconds(hit_times, limit, now)` (full window: the hit whose departure leaves `limit - 1` hits is the `len - limit + 1`-th oldest; seconds = ceil(that hit + WINDOW - now), at least 1) and `wait_sentence(seconds)` ("Try again in 12 minutes." / "in 1 minute" / "in 40 seconds"; rounds up). Tests in `test_rate_limit_rules.py`: exact boundary values (limit reached with one hit, with many, hit leaving this second, hits older than window are ignored by the caller); mutants killed by exact numbers.
5. `use_cases/rate_limits.py::take_hit`: returns `Failure | None` (None = taken). When a counter is full, it reads that counter's hit times (one query, ordered) and the answer is the maximum of `retry_after_seconds` over full counters, carried as `Failure.rate_limited(retry_after_seconds)` (details `{"retry_after_seconds": n}`, `domain/failure.py`). Five callers change from `if not take_hit(...): return Failure.rate_limited()` to returning the failure: `booking_holds.create_hold`, `resend_code`, `sign_in_link.ask_for_link`, `api_tokens.resolve_token`, `search_limited.search_for_visitor`. Clock stays `current_request_context().now`.
6. `views/retry_after.py` (new, 8 lines): `with_retry_after(response, failure)` sets `Retry-After` from the failure's details when the code is RATE_LIMITED. Applied at every 429 renderer: `failure_response.failure_response` (API), `fhir/responses.failure_response` (FHIR token 429), `booking_refusal.refused_page`, `booking_details._hold_refused` path (notice page, status 429), `sign_in_link._refused` (page), `search_page`.
7. `domain/booking_refusals.py::refusal_for`: the rate-limit message uses `wait_sentence(seconds)` from the failure's details; the sign-in page text `TOO_MANY_LINKS` and `errors/429.html` sentence do the same, so page and header agree. `429.html` is deleted (nothing else uses it; check with grep).
8. `views/pages/search_page.py` + `templates/search/index.html` + `search_context.py`: a limited search answers `search/index.html` with status 429: same header, form, footer; where results go, a notice with the wait sentence; no result list, no list switch, no widen link (those link to searches that answer 429 for this visitor). Context built with an empty page; a `limited` flag in the context (no new view).
9. `views/hold_cookie.py`: one cookie `drlibre_hold` holding up to 5 entries `<expiry epoch>.<proof>`, proof = HMAC of the hold id truncated to 32 hex; `set_hold_cookie(request, response, hold_id, expires_at)` reads the browser's current cookie, drops entries expired at the request-context clock, appends the new one, keeps the newest 5 (a visitor makes at most 5 holds an hour per email, a hold lives 10 minutes), cookie expiry = latest entry. `made_this_hold` checks the hold's proof against every entry with `compare_digest`. Size bound: 5 × ~50 bytes, under 400 bytes. Still `HttpOnly`, `SameSite=Strict`, `secure` from settings. Callers: `booking_details._create_hold` passes the request.
10. `views/pages/booking_code.py::ResendPage.post`: `made_this_hold` first, then `hold_summary`, as `CodePage` does. (Summary is only needed for the way back after a rate limit.)
11. `use_cases/race_support.py` (new, moved from `test_sign_in_race.py::_run_together`, second caller) and `use_cases/test_hold_race.py` (new): ten threads `create_hold` for one email: exactly 5 not rate limited; ten threads `resend_code` for one hold: exactly 3 not rate limited. Run 5× each as the sign-in tests do. Prove they can fail: temporarily remove `lock_keys` and see both fail.

## Order (red first, each proven failing for the right reason)

1. Tests of 3, 2 (red under current code: 400 for bodyless text/plain), then block 1.
2. Domain tests of 4, then block 4; then 5, 6, 7 with tests per renderer.
3. Search page test (item 3 invariant: log in as limited address by taking 120 hits, GET `/` and `/?q=x`, status 429, contains header sign-in link, form, footer; parse every `href` and form `action` on it except the search form's own action, request each as the limited visitor, assert status < 400), then block 8.
4. Cookie tests (two tabs both complete; another browser gets the missing-hold page for both; cookie HttpOnly, length bound after 8 holds in one browser; expired entries dropped), then block 9. Then 10 with a test: a foreign-browser resend answers the missing-hold page without reading the hold (patch `hold_summary` to fail), then 11.

Files deliberately not touched: start-up checks, cookie flags beyond what exists, trusted proxy, public detail pages and anonymous FHIR searches (26b), models, migrations, `static/` CSS (the notice component exists).

## Failing tests to write first (`returns_X_when_Y`)

- `returns_no_unreadable_body_refusal_when_any_api_write_route_gets_no_body_and_text_plain` (every route from the URL configuration).
- `returns_logout_answer_when_post_has_no_body_and_no_type_over_a_socket`; `returns_invalid_input_naming_body_when_text_plain_body_is_posted_over_a_socket`.
- `returns_retry_after_seconds_until_oldest_hit_leaves_when_limit_is_full` and siblings (domain; e.g. 5 hits, limit 5, oldest 10 minutes old → 3000 s; limit 3 with 5 hits → third oldest decides).
- `returns_retry_after_header_in_seconds_when_hold, code, link, token, search or api is limited` (one per path: page, `/api/v1`, `/fhir`); header equals the sentence's minutes.
- `returns_search_page_with_429_and_form_when_address_is_limited` (with and without `q`); `returns_below_400_for_every_link_on_the_limited_page`.
- `returns_both_code_pages_when_two_holds_are_made_in_one_browser`; `returns_missing_hold_page_when_another_browser_opens_either_code_page`; `returns_short_cookie_when_eight_holds_are_made`.
- `returns_five_holds_at_most_when_ten_threads_hold_for_one_email`; `returns_three_resends_at_most_when_ten_threads_resend_one_hold`.
- `returns_missing_hold_page_before_reading_hold_when_resend_has_no_cookie`.

## Invariants and blast radius

Never break: no double booking (hold flow untouched apart from the cookie and the limit's return type); authorization from session and the hold cookie, server-side; audit rows still in the same transaction (`take_hit` still inside `atomic`, lock order unchanged: counter lock before hold row lock); every counter stays serialised. A hold cookie proves a browser only, the mailed code is still needed. Blast radius: every rate-limited route (return type of `take_hit`), every `/api/v1` write (content type rule), the hold cookie of the booking flow.

## Trust boundaries

- Request body and `Content-Type`: client claims; the rule goes by whether a body exists (headers `Content-Length`, `Transfer-Encoding`), body requires JSON before reading; oversize check unchanged.
- `drlibre_hold` cookie: client controlled; parsed defensively (split, ignore malformed, never raise), only compared by HMAC; expiry in it only prunes and never grants.
- `Retry-After`: computed from stored hit times, no client input; hashes in the table unchanged.

## Vocabulary

Visitor, Patient, ApiClient, BookingHold, VerificationCode, SignInLink, Appointment, AuditLogEntry (unchanged). `RateLimitHit` is the counter row.

## Will not do

No new dependency, no limit changes, no change to the 120/5/3/10/20 values, no new template for 429s, no cookie per hold, no generic response-header middleware, no rewrite of the test client setup. Same-email second hold still replaces the first (spec 7.5); the two-tab test uses two addresses.

## Gate

`make setup && make lint && make test && make gate && make mutate && make fhir-validate`. `rate_limit_rules.py` stays under mutation; new survivors fixed with tests, not listed. Cookie parsing lives in `views/`, so outside `make mutate`; its tests carry the proof.

## Risks

Whether DRF names fields on an empty `text/plain` write (block 1 confirms; fallback stated). `live_server` needs `transaction=True` DB; test uses `django_db(transaction=True)`. Removing `429.html` if any other template includes it (grep first, keep otherwise).

## Architect review

Verdict: approve.

- Ladder: smallest fit. No dependency, no new abstraction beyond `retry_after.py` (five-plus callers) and `race_support.py` (second caller, as §8 allows).
- Scope: items 1 to 7 all mapped to blocks, each with a first failing test. Cut order for overrun is stated.
- Block 4 formula is right: the (len - limit + 1)-th oldest hit leaving leaves limit - 1 hits. Max across full counters is right, since all must clear.
- Security: cookie parsed defensively, HMAC compared with `compare_digest`, expiry only prunes. Size bound holds at 5 entries.
- Watch in green: (a) block 1 relies on DRF returning `{}` for an empty stream, so confirm with the test and use the stated fallback if not. (b) Item 4 requires the `/fhir` and `/api/v1` 429s to carry the header: keep one test per renderer, as planned. (c) Page sentence and header must come from the same seconds value. (d) The limited-page link test must include the header sign-in link and footer links.
