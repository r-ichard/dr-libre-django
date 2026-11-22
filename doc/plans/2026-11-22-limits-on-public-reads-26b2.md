# Plan: task 26b2, limits on public reads

Slice: items 1 to 7 (all). Item 3 is the largest; if the run runs short, item 3's behavioural
half moves to "Not in this run" and the list stays (nothing else depends on it).

Focal point: one new hook that takes a hit of a counter before a public read computes anything,
keyed by user id when the caller is signed in and by network address otherwise.

## Decisions (the numbers and the sharing)

| Scope | Routes | Per hour | Why |
|---|---|---|---|
| `search` (exists) | `/`, `/api/v1/search/*` | 120 | unchanged |
| `schedule` (new) | `/providers/<id>`, `/hospitals/<id>`, `/specialties/<id>`, their `/api/v1` twins, `/api/v1/slots`, `/book`, `/book/<type>/provider`, `/book/<type>`, `/book/<type>/details` (GET) | 1200 | One counter: every one of them runs the same free-slot or first-available computation, so a caller who alternates page and API, or provider and times, cannot double the allowance. |
| `fhir` (new) | anonymous `GET /fhir/...` search and read, not `/fhir/metadata` | 600 | A program client pages with `_count`; kept apart so a script cannot use up what visitors behind the same address need, and the other way round. Metadata costs nothing and a client reads it first. |

Walk check (the "never meet it" rule): search (own counter) then per provider looked at: one
provider page, four weeks of times, one details page = 6 reads. Eight providers compared = 48.
1200 is 25 such walks an hour from one address (a hospital Wi-Fi), 10 times the search limit
because a walk makes about 6 reads per search. A test walks 1 provider page + 4 weeks + details
for 8 providers and expects every answer 200.

Item 2, signed-in callers. A session user or a valid-token user is counted per user id, same
scope, same number (`take_hit(scope, None, f"user:{user.pk}")`; the hash kind is "address" and
`user:` cannot collide with an address). Never against the address. Staff behind one address
each have their own 1200. Nothing-limits was rejected: a session costs only one verified mailbox,
so unlimited would let one cheap account compute schedules without bound. The same rule applies to
search (a signed-in search is counted per user). Invalid tokens keep the TOKEN counter.

## Blocks (one sentence each), in order

1. `scheduling/domain/rate_limit_rules.py`: add `RateLimitScope.SCHEDULE`, `FHIR` and their rows (1200, 600, `per_email=None`).
2. `scheduling/migrations/0017_...py` (generated, like 0016): widen the scope check constraint and choices.
3. `scheduling/use_cases/read_limits.py` (new): `counter_key(user, address) -> str` and `take_read_hit(scope, key) -> Failure | None` over `take_hit`; `search_limited.py` takes the key instead of the address.
4. `scheduling/views/network_address.py`: add `counter_key_of(request, user)` next to `network_address` (one place picks user or address).
5. API: `scheduling/views/read_throttle.py` (new): a DRF `BaseThrottle` reading `view.read_scope`; `failure_response.py`: map `exceptions.Throttled` to `Failure.rate_limited(wait)` (gives the error body and `Retry-After`). Set `throttle_classes` and `read_scope` on `ProviderDetailView`, `HospitalDetailView`, `SpecialtyDetailView`, `SlotsView`; `SearchView` uses the key too.
6. Pages: `PageView` gets a `before_get` hook returning `HttpResponse | None`, called after the role guard; `scheduling/views/pages/limited_page.py` (new) mixin `LimitedPage` implements it with `refused_page` (status 429, `Retry-After`, base layout so header and footer stay, "Try again" button back to the same URL). Apply to `ProviderPage`, `HospitalPage`, `SpecialtyPage`, `ServicePage`, `ProviderChoicePage`, `TimesPage`, `DetailsPage`; `SearchPage` passes the key.
7. FHIR: `scheduling/views/fhir/views.py` `_answer`: after method check, for GET other than `metadata`, take the `fhir` hit (key from `caller.user`, else address); on failure `failure_response` gives the OperationOutcome with code `throttled` (already mapped) and `Retry-After`.
8. `drlibre/environment.py`: `optional_env(name, default)` and `env_whole_count(name, default)` (non-negative, error names the variable); `settings.py` uses both, drops `import os`.
9. `README.md`: section "Running with DEBUG off".
10. `scheduling/views/test_log_privacy.py`: add the password sign-in flow; drop the unused `settings` argument.

Files not touched: `drlibre-specs.md`, `search` mechanism internals (`take_hit`, window), `startup_checks.py` (pure; negative count refused in `environment.py` because it is a parse error, not a policy), writes, FHIR use cases, templates (`booking/refused.html` reused).

## Failing tests first (names `returns_X_when_Y`)

- `scheduling/domain/test_rate_limit_rules.py`: `returns_1200_an_hour_for_schedule_and_600_for_fhir_per_address_and_no_email_limit`.
- `scheduling/views/test_read_limits.py` (new), frozen clock, limits as the table:
  - `returns_429_with_retry_after_when_one_address_reads_1201_provider_pages_in_an_hour`, same for the page and API twins; hospital, specialty, `/api/v1/slots`, `/book/<type>` each answer 429 on the 1201st shared read (one test across routes proves the shared counter: 600 provider-page reads + 601 slots calls).
  - `returns_200_for_every_read_when_a_person_walks_eight_providers_with_four_weeks_each`.
  - `returns_200_when_another_address_reads_after_the_first_is_limited`; `returns_200_again_when_an_hour_has_passed`.
  - `returns_the_limited_page_with_header_footer_and_a_try_again_link_when_a_page_is_limited` (status 429, `Retry-After`, `<header`, `<footer`, link to same URL).
  - `returns_operation_outcome_throttled_with_retry_after_when_anonymous_fhir_search_is_limited` (content type `application/fhir+json`, issue code `throttled`); `returns_200_for_fhir_metadata_when_the_fhir_counter_is_full`.
  - `returns_200_when_staff_with_sessions_behind_one_address_read_more_than_one_user_may` (two sessions, same address, the address counter full: both 200); `returns_429_when_one_signed_in_user_reads_1201_times` (per-user limit); same for a valid FHIR token.
  - Page forms and API routes tested as a browser or FHIR client sends them (`browser_api_client`, `fhir_client`): these are GETs, so Origin and bearer headers set as the real client does.
- Item 3, `scheduling/views/test_public_route_limits.py` (new): `returns_a_limit_or_a_reason_for_every_route_that_answers_without_a_session_or_token`. Walks `get_resolver()`, fills `<uuid:...>` with a random uuid, sends GET and POST with no cookie and no token. A route is public when an answer is not 301/302/303 to sign-in, 401, 403 or 405. For each public (route, method): it must be in `COSTS_NOTHING` (health, static, favicon, legal pages, sign-in form, `/api/v1/` catch-all 404, `/fhir/metadata`, `/style` only with DEBUG), in `OWN_LIMIT` (holds, resend, verify, link, sign-in by password with lockout, token failures; each names the mechanism and its test), or answer 429 on the second hit with every `RATE_LIMITS` row patched to one hit. Each entry carries a reason string; the test also fails on a stale entry (no such route). Proof it can fail: delete one `read_scope` and see it name the route. Limit: `OWN_LIMIT` entries are not re-proven here, their own tests do.
- Item 4: `drlibre/test_environment.py` `raises_improperly_configured_naming_variable_when_count_is_negative`; `drlibre/test_settings.py` `raises_improperly_configured_naming_trusted_proxy_count_when_negative`.
- Item 5: `drlibre/test_environment.py` `returns_default_when_optional_variable_is_unset` and `returns_value_when_optional_variable_is_set`; `test_settings.py` keeps its `DEMO_PASSWORD` refusal test green through the new reader (no separate failing test is possible for a source of the same value; said plainly).
- Item 7: in `test_log_privacy.py`, `_sign_in_by_password` with planted password `planted-password-...`; asserts 200 and that the password is in the planted list; red proof by a temporary `logger.info(password)` in sign-in, removed.
- Item 6: no test; checked by reading against `settings.py`, `startup_checks.py`, `forwarded_address.py`.

## README content (item 6)

With `DEBUG` off start-up refuses: `SECRET_KEY` equal to the published development key, empty `ALLOWED_HOSTS`, `DEMO_PASSWORD` equal to the published demo password, negative or non-numeric `TRUSTED_PROXY_COUNT`. To run that way locally set a private `SECRET_KEY`, `ALLOWED_HOSTS`, an empty `DEMO_PASSWORD`; `.env.example` values alone fail (as `make test` does with `SAFE_ENV`). Cookies are `Secure` when `DEBUG` is off, so a browser on plain http will not keep the session; use `HTTPS_ONLY=true` with `HSTS_SECONDS` behind TLS. `TRUSTED_PROXY_COUNT`: number of proxies in front that each append the address they saw to `X-Forwarded-For`; 0 ignores the header and uses the connection address; n takes the n-th entry from the right and trusts `X-Forwarded-Proto`.

## Invariants and blast radius

No write path, booking, audit log or authorization rule changes; limits sit before the read, after access checks (an unauthorised API call still gets 401/403 first). Each limited read now writes one `RateLimitHit` row in a short transaction with an advisory lock: more rows (up to 1200 an hour per key), constant query count per request. Existing tests that count queries or hit one route hundreds of times may need the limit patched, not removed.

## Trust boundaries

Address: `network_address` (rightmost trusted entry, never the raw header). Identity: the session or token resolved server-side, never the payload; the user key is never taken from a request field. Rows hold only a keyed hash (user id and address alike). Error bodies leak no counter data beyond `Retry-After`.

## Vocabulary

Visitor, Patient, Clinician, Admin, ApiClient, Session, Hospital, Specialty, Appointment type (slot reads), Clinician profile. Nothing new in the domain.

## What I will not do

No new limiter class, no middleware, no settings for the numbers (constants in the rules table, as the others), no limit on writes (they have theirs), no change to the search number, no edit of the specification. Open for the owner: a signed-in caller is limited per user (1200/600) rather than not at all; say if staff integrations need more.

## Not in this run

- Item 3 behavioural proof of `OWN_LIMIT` entries (relies on their own tests).
- Cleanup of old `RateLimitHit` rows (not asked; check the table's growth in the review).

## Architect review

Verdict: approve.

- Ladder: reuses `take_hit`, `Failure.rate_limited`, `refused.html`; no new limiter class, middleware or dependency. Per-user key is one function in one place.
- Numbers and sharing are stated with reasons; the walk arithmetic (6 reads per provider, 48 for eight) backs the "never meet it" rule and has its own test.
- Item 2 is answered (per user id, same scope; unlimited rejected with a reason). Signed-in search moving to a per-user key is a small extension beyond the task, but it keeps one rule; acceptable.
- Tests are named as behaviours, include the edge (1201st read, other address, hour passed, metadata exempt, two sessions behind one address) and the page/API/FHIR client rules from CLAUDE.md.
- Item 3: walker has stale-entry check and a stated proof that it can fail. `OWN_LIMIT` entries not re-proven is declared.
- Watch in green stage: (a) the Throttled mapping in `failure_response.py` must not change other DRF 429s; (b) the migration number must be checked against the real latest; (c) walker must also cover POST routes under `/book` and `/fhir` writes (answered 401/415 first, so list them with reasons); (d) the existing tests that hit routes many times may need the limit patched.
- Item 4 placed in `environment.py` as a parse error: coherent; the README claim about refusal must match.
