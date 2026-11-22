# Review: task 26b, start-up, cookies, proxy, logs

Diff `main...HEAD`, 21 files. Commits after `verify_green` up to `prove` touch only `test_forwarded_address.py` and `test_cookie_flags.py`: no product line changed in proof. Gate: lint, test (4617), gate passed in `check`.

## Findings

1. **Blocker, missing test.** Item 9 is in the declared slice (plan "Slice: items 1, 2, 3, 8, 9", block 7 `scheduling/views/test_log_privacy.py`). The file does not exist in the diff or tree. Nothing reads the log lines of booking, sign-in by link, admin edit and FHIR read, so item 8's new `exc_info=True` trace (`scheduling/use_cases/background_mail.py:47`) and all other lines are unguarded. Fix: write the test as planned, with the planted values and the non-empty-lines assertion; prove it fails with a temporary leak.
2. **Later, plan and code differ.** `drlibre/settings.py:50` sets `CSRF_COOKIE_SAMESITE = "Strict"`; the plan table says Lax is kept. Strict is safe (a new token is issued on the next page) but undeclared. Fix: update the plan or revert the line.
3. **Later, unrequested edit of the Makefile.** `SAFE_ENV` (Makefile:7) replaces the planned `DEBUG=true` in `.env.example`; works, but the `.env.example` dev values now fail start-up with DEBUG off, so `docker compose`/`manage.py` users with DEBUG unset get a refusal. Intended, but say it in the README or ADR.
4. **Later, `TRUSTED_PROXY_COUNT` negative** (`settings.py:51-55`) is accepted and behaves as 0. Plan said non-negative; reject it.
5. **Later, start-up check** reads `DEMO_PASSWORD` from `os.environ` directly (`settings.py:15`) not via `drlibre/environment.py`; minor inconsistency.
6. **Later, `X-Forwarded-Proto`** trusted whole when count > 0 (declared limit).
7. **Later, `scripts/qa_stack.sh`** is a process file; the orchestrator owns it. Seed line duplicates the dev values inline.
8. Measured: `make test` 203 s in the shared sandbox; not a blocker.

Confirmed at a glance: `startup_refusal`, `caller_address` (pure, rightmost-n, falls back on malformed), `cookie_secure` and its five users. Traced: the order of refusals and the `HTTPS_ONLY or not DEBUG` logic. No type escape hatch added except named `noqa` codes; no swallowed error (`_send` logs with trace); no dependency added; no write path touched.

## Re-review after address

Commit `ade8f6c` adds only `scheduling/views/test_log_privacy.py` (155 lines) and the review note. Product code unchanged. Test plugs a `JsonFormatter` handler on root, asserts non-empty lines and at least four request lines, checks planted values and email, phone, birth date patterns across four flows. Finding 1 closed. Small gaps (Later): no planted password in the list; unused `settings` parameter in the test signature (`test_log_privacy.py:128`).

## Blocking

None. Item 9 test now present.

## Later

- Findings 2 to 8.

## Left for the orchestrator

- Item 3a limits (new `RateLimitScope`, migration, detail pages, `/api/v1` twins, `/api/v1/slots`, anonymous `/fhir` search): task 26b2.
- Item 10 access table over every route: task 26b3.
- Slice item not finished: item 9 test (blocking above).
