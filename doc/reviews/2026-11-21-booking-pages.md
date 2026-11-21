# Review: task 12a booking pages

Diff `main...HEAD`, 36 files. Commit order checked: after `verify_green` (386ed28) the `prove` commit (a646918) touched tests and `mutation-equivalents.txt` only; no product or migration line. Earlier `verify_green (failure)` was fixed in `green` before the final verify.

## Read at a glance
- `booking_times.py`, `booking_summary.py`, `booking_links.py`: format only, plan clear.
- `booking_refusal.py:36`: refusal kind picks the way forward; one sentence.
- `booking_confirmation.py:21-30`: ownership via `appointment_for_patient(..., patient=user)`, 404 otherwise, patient role only, never-cache headers on the .ics (`:79`). Summary has no reason or notes.
- `booking_page_data.py:114`: `_week_shown` clamps typed weeks, no overflow.

## Traced
- `booking_details.py:60-80`: the visitor POST goes through `create_hold` and the signed-in POST through `place_appointment`. Both are use cases that own transaction, conflict check and audit, so the views add no write path. Staff get 403 before any use case.
- `booking_code.py:42`: wrong code re-reads the hold for fresh attempts left; an expired hold gives the "start again" page.

## Findings
- Low, `booking_code.py:50-57`: `verify_hold` can return a failure that is neither `INVALID_INPUT` nor a mapped refusal; it falls to `refusal_for`. The plan's `returns_a_refusal_when_any_failure_code_can_come_from_booking` test covers every code, so there is no unhandled path. No fix.
- Low, `booking_confirmation.py:21`: a signed-in staff user opening a confirmation gets the role gate's answer, not a 404; harmless.
- Low, `booking_code.py:35`: the code page is a capability address (hold UUID) and shows the masked email to whoever holds it. The UUID is unguessable and the mask is minimal; acceptable.
- Info: `make mutate` and the browser/accessibility pass were not run in this review; the orchestrator owns them. Two new equivalents in `mutation-equivalents.txt` carry reasons.

## Checks against hard rules
No `Any`, `cast`, bare `type: ignore`; the only `noqa` in `booking_pages_support.py:44` names its code and gives a reason. No file over 500 lines, no function over 100. No swallowed errors seen. Authorization comes from the session, never the payload. No personal detail in a URL (details by POST; hold and appointment ids only; `provider` and `starts_at` are not personal). Never-cache set in `page_view.py:44`. No dependency added. Every form test uses the browser helper.

## Blocking
None.

## Later
- Hold-address capability: consider binding the code page to the browser that created the hold (cookie) in a hardening task.
- Add a test that a staff user gets 403 on the confirmation and calendar routes, if absent.
