# Review: task 26a, abuse limits and what an answer may be

Diff `main...HEAD`, 35 files. Plan: `doc/plans/2026-11-22-security-hardening-26a.md`. Gate stages (lint, tests 4531, gate) passed.

## Glance versus trace
- Confirmed at a glance: `advisory_lock.py` (moved helper), `visitor_rules.py:24` (one email rule), `search_limited.py`, `hold_cookie.py` (HMAC, `compare_digest`, HttpOnly, SameSite, secure from settings), migration 0016, data-model doc.
- Traced: `sign_in.py` lock then count, hasher, write in one transaction (`sign_in.py:40`); `_audit_lockout_once` keyed on the newest failure row (`sign_in.py:61`); `input_limits.py:30` chunked and no-length bodies; `api_view.py:33` handler check before media check.

## Findings
- **Info** `scheduling/use_cases/sign_in.py:61`: once-per-window rests on the newest failure row id. Failures are not written while locked, so the id is stable; correct. Tests cover one entry and a second window.
- **Info** `scheduling/views/api_view.py:43-45`: `Vary` carries `Authorization` as well as `Cookie`, and `no-store` also applies to bearer callers. Wider than the plan, safe, correct.
- **Low** `scheduling/use_cases/test_sign_in_race.py`: the plan promised race tests for five holds per email and three code resends per hour. Not present. `take_hit` already locks per key, so the counters hold, but they are not shown. Smallest fix: two tests in the same file style.
- **Low** `scheduling/views/hold_cookie.py:15`: one fixed cookie name, so a second hold in the same browser invalidates the first tab's code page (plan note N1). A test stating the choice is worth adding.
- **Low** `scheduling/domain/rate_limit_rules.py:32`: search limit keys on `REMOTE_ADDR`; behind one proxy all callers share it. Comment says so (task 26 item 3).
- **Low** `scheduling/views/pages/booking_code.py:105`: `hold_summary` is queried before the cookie check on resend; harmless, move the check first.
- **Info** Proof trace: commits after `verify_green` touch only `mutation-equivalents.txt` (prove) and `auth_schemas.py`, `hold_schemas.py`, `booking_forms.py` (refactor, after prove: constant move). No mutation left behind.
- No new dependency. No `Any`, `cast`, bare ignore. No swallowed error. Authorization still from session; hold cookie is proof only, the mailed code is still required.

## Blocking
None.

## Later
- Race tests for holds (5 per email per hour) and resends (3 per hour).
- Test or comment for the single `drlibre_hold` cookie name across tabs.
- Move the cookie check ahead of `hold_summary` in `ResendPage.post`.
- Measured `make test`: 4531 passed in 43.6s on the shared sandbox; the orchestrator times it on a quiet machine.

## Left for the orchestrator
- Items 1-3 (start-up checks, cookie flags, proxy trust) and 8-12 of task 26: later runs (26b and on).
- Rate limit on public detail pages and `/fhir` search.
- `make mutate` and `make fhir-validate` as the last scripted gate, from a fresh clone.
