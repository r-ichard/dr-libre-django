# Task 26b: start-up checks, cookie flags, trusted proxy, logs without personal data

Slice: items 1, 2, 3, 8, 9. Settings and logs, small blocks, no new table of data. One coherent product afterwards: nothing is half-wired.

## Not in this run

- Item 3a (limit on public detail pages, their `/api/v1` twins, `/api/v1/slots`, anonymous `/fhir` search): needs a new `RateLimitScope` and a migration (`RateLimitHit.scope` has choices) plus six renderers. Task 26b2. The `drlibre_hold` cookie flags of 3a ARE in this run (item 2 list).
- Item 10 (access table over every route): about 250 rows split over four data files (300-line cap) and the real answers of each surface to be read first. Task 26b3, after 26b2 so the new routes' limits are in the table.

## Focal point

`drlibre/settings.py` end: one `check_startup(...)` call, and one `COOKIES_SECURE` value every cookie reads.

## Decisions

- Test environment: `.env.example` is what `make test` loads and it has no `DEBUG`, the development key and the published demo password, so the new check would refuse every test run. Add `DEBUG=true` to `.env.example` (compose already sets it; dev values only). pytest-django forces `settings.DEBUG=False` during tests anyway; tests that read `DEBUG` set it themselves (grep showed they do). Side effect: `/style` is now in the URL configuration at import; `test_pages.py` is the only user, run it.
- Items 2, literal reading: "DEBUG off => Secure". `COOKIES_SECURE = HTTPS_ONLY or not DEBUG` in settings, used for `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` and every `secure=` argument (replaces `settings.HTTPS_ONLY` in `session_cookie.py` and `hold_cookie.py`). `HTTPS_ONLY` keeps its other meaning (redirect, HSTS).
- Proxy: env `TRUSTED_PROXY_COUNT` (non-negative integer, default 0, invalid value is `ImproperlyConfigured` naming it). With 0: `SECURE_PROXY_SSL_HEADER = None`, address = `REMOTE_ADDR`. With n > 0: `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` and address = the n-th entry from the right of `X-Forwarded-For` (each trusted proxy appends the peer it saw, so the entries left of that are caller-written); fewer than n entries (request did not pass every proxy) or an unparsable entry => `REMOTE_ADDR`. Limit of this design, stated in the module: `X-Forwarded-Proto` is trusted whole when n > 0, so the outermost proxy must overwrite it.
- No new dependency.

## Cookies and flags (item 2, with 3a's hold cookie)

| cookie | set in | HttpOnly | SameSite | Secure (DEBUG off) | note |
|---|---|---|---|---|---|
| `drlibre_session` | `views/session_cookie.py` | yes | Strict | yes (was `HTTPS_ONLY`) | no script needs it |
| `csrftoken` | Django, `CSRF_COOKIE_*` in settings | yes (already) | Lax (Django default, kept: the token is not a login) | yes (was `HTTPS_ONLY`) | forms put the token in the page; no script reads `document.cookie` (grep: none) |
| `drlibre_hold` | `views/hold_cookie.py` | yes | Strict | yes (was `HTTPS_ONLY`) | |
| `drlibre_notice` | `pages/portal_forms.py::redirect_with_notice` | yes | Strict | **no today, fix** | |
| `drlibre_admin_notice` | `pages/admin_notices.py::admin_redirect` | yes | Strict | **no today, fix** | |

Deleting cookies (`delete_cookie`) carry an empty value and `max-age=0`; the test skips empty values and says why.

## Blocks, one sentence each

1. `drlibre/startup_checks.py` (new): pure `startup_refusal(debug, secret_key, allowed_hosts, demo_password) -> str | None` returns one message naming the variable (`SECRET_KEY`, `ALLOWED_HOSTS`, `DEMO_PASSWORD`) when DEBUG is off and the value is the published one (`.env.example` value constant), empty, or set; `settings.py` calls it last and raises `ImproperlyConfigured` with it. Published values live as two named constants here, one test reads `.env.example` to prove they match.
2. `drlibre/settings.py`: `COOKIES_SECURE`, `TRUSTED_PROXY_COUNT`, `SECURE_PROXY_SSL_HEADER` derived from it, `CSRF_COOKIE_SAMESITE` stated.
3. `scheduling/views/session_cookie.py`, `hold_cookie.py`, `pages/portal_forms.py`, `pages/admin_notices.py`: `secure=settings.COOKIES_SECURE`, notice cookies gain it.
4. `scheduling/domain/forwarded_address.py` (new, pure, under mutation): `caller_address(remote_address, forwarded_for, trusted_proxies) -> str`; `views/network_address.py` calls it with `settings.TRUSTED_PROXY_COUNT` and the header.
5. `scheduling/use_cases/background_mail.py::_send`: `logger.error("background mail not sent", exc_info=True)`. `JsonFormatter` already drops the exception message and keeps type and frames (no values), so the address in an exception text cannot leave; correlation id comes from the copied context.
6. `scripts/qa_stack.sh` (process file, orchestrator-owned, one line): the server runs with DEBUG off, so give it `SECRET_KEY` not equal to the development key and no `DEMO_PASSWORD` (the seed line keeps `DEBUG=true`). Also `drlibre/test_deployment_checks.py` helper: production environment sets `DEBUG=false` and `DEMO_PASSWORD=""` (it copies `.env.example`).
7. `scheduling/views/test_log_privacy.py` (new, item 9): see tests.

Files deliberately not touched: models, migrations, rate-limit rules and scopes, detail pages, FHIR, `urls.py`, templates, `Dockerfile`, `compose.yaml` (already `DEBUG: "true"`).

## Failing tests first (`returns_X_when_Y`)

`drlibre/test_startup_checks.py` (pure function, plus one subprocess test per variable that `import django; django.setup()` fails with the name in the message):
- `returns_secret_key_message_when_debug_off_and_development_key` (and `returns_none_when_debug_on_with_development_values`).
- `returns_allowed_hosts_message_when_debug_off_and_hosts_empty`.
- `returns_demo_password_message_when_debug_off_and_password_set`; `returns_none_when_debug_off_and_demo_password_empty_and_key_changed_and_hosts_listed`.
- `returns_constants_equal_to_env_example_values` (constants match the file).

`scheduling/views/test_cookie_flags.py` (one test, parametrised over a signed-out and a signed-in request; `DEBUG` off): a booking hold submission over the cross-site-checked client (Origin header set) sets the hold cookie; sign-in sets the session cookie; a page with a form sets `csrftoken`; an admin action sets the admin notice; a patient action sets the notice.
- `returns_secure_httponly_samesite_on_every_cookie_when_debug_is_off` (every non-empty cookie of every response in the flow: `secure` true, `httponly` true, `samesite` in Strict/Lax; the cookie names seen must equal the five in the table, so a sixth fails the test).
- `returns_secure_cookies_when_https_only_is_off_and_debug_is_off` (the literal case: `HTTPS_ONLY=false`).

`scheduling/domain/test_forwarded_address.py` (exact values):
- `returns_remote_address_when_no_proxy_is_trusted_and_header_is_set`.
- `returns_rightmost_entry_when_one_proxy_is_trusted` (`"1.1.1.1, 2.2.2.2"`, n=1 => `2.2.2.2`); `returns_second_from_right_when_two_proxies_are_trusted` (`"9.9.9.9, 1.1.1.1, 2.2.2.2"`, n=2 => `1.1.1.1`).
- `returns_remote_address_when_header_has_fewer_entries_than_trusted_proxies`; `returns_remote_address_when_entry_is_not_an_address`; `returns_remote_address_when_header_is_empty`.

`scheduling/views/test_trusted_proxy.py` (through the client, `override_settings` for the count and the header):
- `returns_http_scheme_when_forwarded_proto_comes_from_untrusted_caller` (count 0, `X-Forwarded-Proto: https`, `request.is_secure()` false and, with `HTTPS_ONLY` on, still the redirect).
- `returns_remote_address_for_rate_limit_when_forwarded_for_comes_from_untrusted_caller` (count 0: 120 search requests with differing `X-Forwarded-For` still hit the same counter and the 121st is 429).
- `returns_forwarded_address_counter_when_one_proxy_is_trusted` (two forwarded addresses count apart behind the same `REMOTE_ADDR`).
- `drlibre/test_settings.py`: `returns_proxy_ssl_header_none_when_trusted_proxy_count_is_unset`; `returns_proxy_ssl_header_when_count_is_one`; `raises_improperly_configured_naming_trusted_proxy_count_when_not_a_number` (subprocess, as `test_deployment_checks.py`).

`scheduling/use_cases/test_background_mail.py`:
- `returns_error_type_trace_and_correlation_id_in_log_when_send_fails` (a send raising `SMTPException` whose text holds a planted address `planted.person@example.test`; the formatted line holds `SMTPException`, a frame, the correlation id, and neither the planted address nor the body).

`scheduling/views/test_log_privacy.py` (item 9): handler with `JsonFormatter` on the root logger collects every line of: one booking (hold, code, verify, appointment), one sign-in by link, one admin user edit (name, email, phone, birth date changed), one FHIR patient read with a bearer token. The flows plant known values (email, phone number, full name, birth date, the bearer token, the mailed code, the link token, a password) which the test also reads from the outbox and the setup.
- `returns_no_personal_value_in_any_log_line_when_the_four_flows_run` (planted strings absent; regexes for an email, a phone number of 7 or more digits, an ISO date of birth; the lines list is asserted non-empty and to contain the four request lines, so an unplugged handler cannot pass).
- Proof it can fail: a temporary `logger.info(f"sent to {email}")` makes it red; recorded in the red stage.

## Red proof

Each of items 1, 2, 3, 8 fails today for the stated reason: no check exists (settings load), `drlibre_notice` has no `Secure`, `X-Forwarded-For` is ignored (so only the trusted cases fail; the untrusted ones pass today and are regression guards, named so in the test), the mail line has no exception. Item 9 may pass today; it is then a guard, proven by the temporary leak.

## Invariants and blast radius

- Never break: session cookie stays HttpOnly and Strict; CSRF check and Origin check unchanged; rate limit counters unchanged (only the address string given to them changes, and only when `TRUSTED_PROXY_COUNT` > 0); audit log untouched; double booking untouched.
- Blast radius: every process start (new refusal), every cookie, the address of every rate-limited route, the QA stack script, `.env.example` (all tests).

## Trust boundaries

- Environment: validated at start-up, refused with the variable's name; never logged.
- `X-Forwarded-For` and `X-Forwarded-Proto`: caller-written unless a trusted proxy count says otherwise; parsed with `ipaddress`, never raises, falls back to `REMOTE_ADDR`.
- Logs: allowlist formatter stays; the test is the proof no new line carries a value.

## Vocabulary

Visitor, Patient, Clinician, Admin, ApiClient, BookingHold, VerificationCode, SignInLink, AuditLogEntry (read only), Session.

## Will not do

No config class, no settings framework, no middleware for forwarded headers (Django's own `SECURE_PROXY_SSL_HEADER` plus one pure function), no `django-ipware`, no cookie-prefix scheme (`__Host-`), no change to limits or scopes, no `Dockerfile` or server change (that is item 17, task 26d).

## Gate

`make setup && make lint && make test && make gate && make mutate && make fhir-validate` (fhir script exports `DEBUG=true` already). `forwarded_address.py` stays under mutation, boundary values above kill the index mutants. `startup_checks.py` lives outside `scheduling/domain`, so its tests carry the proof.

## Risks

- `.env.example` gains `DEBUG=true`: if a test relied on DEBUG unset at import (urls `/style`), it shows in the full run; fix the test, not the file.
- Secure cookies with DEBUG off over plain `http://127.0.0.1` (QA stack): Chromium and Firefox accept them on loopback; a client that does not (curl cookie jar honours `secure`) stops sending them. Check `qa_stack.sh` users after the change.
- `X-Forwarded-Proto` trusted whole when n > 0 (stated in code).

## Architect review

Verdict: approve.

- Slice (items 1, 2, 3, 8, 9; 3a hold cookie included) is coherent and leaves the product whole. Deferring 3a limits (new scope plus migration) and item 10 (about 250 rows) to 26b2 and 26b3 is reasonable for one green stage. Orchestrator must create those two backlog files and keep "Done when" for 26b open until they merge.
- Ladder: no new dependency, no middleware, one pure function under mutation, one startup function. Right layers (domain pure, view adapter, settings).
- Tests are named as behaviours with exact values; the untrusted-header cases are labelled regression guards. Item 9 has a proof-it-can-fail step.
- Security: `JsonFormatter` verified to drop exception messages and keep type and frames, so item 8 holds. `X-Forwarded-Proto` trusted whole at n > 0 is a stated limit.
- Watch in implementation: (a) `.env.example` gaining `DEBUG=true` makes `/style` import-time routes; run the full suite. (b) Cookie test must also cover the `HTTPS_ONLY=false` case, as planned. (c) Frames carry source line text; keep the item 9 test scanning them.
