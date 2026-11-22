# Review: task 26a2, abuse limits against the real server

Base: `0f70f5b` (26a head). Head: `5dc1e94`. 30 files, 755 insertions; 21 product files.

## Stage proof
- `verify_green` (4deb07b) to `prove` (ff4d482): only four `test_*.py` files changed. No product or migration line moved. Clean.
- `refactor` touched `scheduling/views/pages/sign_in_link.py` only after `prove`. Allowed.

## Plan in one sentence, per block
- `views/input_limits.py:33-46`: a write passes if it has no body, otherwise it must say `application/json`. Confirmed at a glance. The body is never read before the check.
- `domain/rate_limit_rules.py:48-62`: `retry_after_seconds` finds the hit whose leaving brings the count under the limit, rounded up, at least 1. Traced: `hits[len-limit]` is right for `hits >= limit`.
- `use_cases/rate_limits.py:28-53`: `take_hit` returns None or the seconds to wait (the larger of the two counters), under the same advisory lock. Check and insert are still one step.
- `domain/failure.py:35`: `retry_after_seconds` rides on `Failure` with `compare=False`. It is a field on a domain type for a view concern. Acceptable.
- `views/hold_cookie.py`: one cookie holds up to 8 `hold-proof` entries, each an HMAC of the hold id. Still `HttpOnly`, bounded. Traced the dedupe and the trim.
- `views/pages/search_page.py:_limited`: the search page is rendered with status 429, an empty result set, and the brand link replaced by a span. Result links and list switch are left out.
- `views/pages/booking_code.py:104`: cookie check now comes before `hold_summary`. Item 7 done.

## Findings
- **Later**, `scheduling/views/test_api_bodyless_writes.py:55`: the test only asserts that "not readable" is absent. A route that crashes (500) or answers 404 for the made-up id passes. Fix: also assert `status_code != 500`.
- **Later**, tests: `Retry-After` is tested for the page search, the API search and the bearer token (`scheduling/views/pages/test_search_limited_page.py:90-123`). The hold page, resend, sign-in link page (`views/pages/sign_in_link.py:41-43`), and `/fhir` (`views/fhir/responses.py:39`) set the header with no test. Task item 4 names all of them. Risk: a later edit drops one header unseen. Fix: one parametrised test per route that drives a limited caller and reads the header and sentence.
- **Later**, `scheduling/views/hold_cookie.py:21`: the comment says eight entries are 534 characters. 8 × 65 + 7 separators is 527. Fix: correct the number.
- **Later**, `scheduling/views/hold_cookie.py:42`: the cookie expiry follows the newest hold. An older entry never outlives its own hold, so this is safe. The cookie also keeps expired holds' entries until trimmed. Harmless, because the proof is useless once the hold is gone.
- **Later**, `scheduling/views/pages/search_page.py:27`: `load_filter_options()` now runs before the limit check's result is used, so a limited visitor still costs the filter-option query. Small cost. Fix: load the options only in the branches that use them.
- **Later**, `scheduling/domain/failure.py:35`: the `retry_after_seconds` field is on `Failure`. If a second field of this kind appears, move to a wrapper type.
- **Later**: I did not run `make mutate` or `make fhir-validate`. The stages passed `make test` (4591), lint and gate. The orchestrator runs mutate on `rate_limit_rules.py`.

## Checked, no finding
- Authorisation: the hold cookie is a browser proof only, never an identity. Comparison is `hmac.compare_digest`. No sensitive data in logs or URLs. No new dependency. No `Any`, `cast`, or bare suppressions in the diff.
- Double booking: not touched.
- Audit: no new write. `auth.link_refused` audit stays inside the transaction.
- Items 5 and 6 have tests: `scheduling/use_cases/test_hold_race.py` and `scheduling/views/pages/test_booking_hold_cookie.py`. Items 1 and 2 have `test_api_bodyless_writes.py` and `test_api_live_server.py`. Item 3 has `test_search_limited_page.py`.
- Time budget: `make test` took 127 s and 140 s in the sandbox. Not a blocker. The orchestrator measures it on a quiet machine.

## Blocking
None.

## Later
The seven items above.

## Left for the orchestrator
The plan declares no `## Not in this run` list. Start-up checks, cookie flags, the trusted proxy and the public detail page limits are 26b by the task text. Run `make mutate` and `make fhir-validate` from a fresh clone, and the curl and two-tab checks against the container stack.
