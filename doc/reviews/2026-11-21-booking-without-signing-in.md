# Review: task 12, booking without signing in

Scope: `git diff main...HEAD` (51 files). Gates reported green (lint, 1624 tests, gate). Proof commit
`f0150ee` touches two test files only; no product or migration line changed between `verify_green`
and `prove`. Refactor stage changed product code after proof, gates re-ran in `check`.

## Plan in one sentence per block (§2.5)

- `views/booking.py`, `hold_schemas.py`: strict schema, thin view, `REMOTE_ADDR` only. Confirmed at a glance.
- `booking_holds.py`: rate-limit, probe placement for an anonymous patient, replace earlier hold, create hold, mail code, audit. Traced lock order (advisory keys, then hold row, then clinicians).
- `booking_verification.py`: lock hold, check code, nested savepoint books, rolls back on failure and keeps hold. Traced.
- `rate_limits.py`: keyed-hash counters under advisory locks. Traced.
- `placement.py` / `placement_checks.py` / `placement_choice.py`: held slot is a clinician conflict; probe skips patient checks so the answer cannot reveal an account. Traced.

## Findings

1. **Medium (Later)**, `booking_verification.py:93` (`_patient_of`) then `place_appointment`: the User row is locked before the clinician rows, while `placement.py` documents lock order clinicians, patient, rooms. A verify for an existing patient racing a normal booking of the same patient on the same clinician can deadlock; Postgres aborts one, the caller gets a 500. Smallest fix: lock the user after the clinician pool, or lock without `select_for_update` and rely on the patient lock inside placing.
2. **Low (Later)**, `booking_codes.py:50`, `views/booking.py`: mail-server failure raises out of the use case (not swallowed, good, tested at use case level at `test_booking_holds.py:318,333`) but the API answer is the generic 500. The visitor gets no hint to retry. Smallest fix: map the send error to an own failure code (503) with "try again in a few minutes", and add an API-level test.
3. **Low (Later)**, `booking_holds.py:63`: a failed mail send rolls back the rate-limit hit too, so requests that fail by mail error are uncounted. Harmless while the server is down; note it.
4. **Low (Later)**, `0008_booking_holds_and_rate_limits.py:19`: `RunSQL DELETE` of holds and codes is irreversible. Acceptable only because nothing created these rows before; state it in the ADR or retro.
5. **Low (Later)**, `placement.py:_first_refusal`: a hold blocks the clinician only, not the room. A hold of a room-needing type can pass at verify with a `conflict` on room if another booking took the room meanwhile. Visitor sees `conflict`, hold stays; acceptable, but a retry message helps.
6. **Nit**, `booking_verification.py:93` forbidden after a verified code for staff addresses: body is generic (confirmed), status 403 differs from 201, only after the visitor proves mailbox control. Matches 7.2.

## Checks passed

- No-leak: hold creation and resend never read `User`; tests in `test_booking_no_leak.py` compare body, status and work.
- Hash only: code and counters stored as HMAC with `SECRET_KEY`; `compare_digest` used; compare done even for unusable code.
- Attempts: failure audit and counter commit (return, no raise); success path deletes code and hold in the same transaction as booking, account and session.
- Authorization from session / none needed (public); patient identity comes from the verified hold email, not the payload.
- Audit: created, expired, replaced, verification failed, patient created, booking made, all inside the transaction, email domain only.
- Titles and single waitlist email fixed (`announce=False`), tests updated.
- No escape hatches, no dependency added, size caps respected per gate.

## Blocking

None.

## Later

Findings 1 to 5 above.
