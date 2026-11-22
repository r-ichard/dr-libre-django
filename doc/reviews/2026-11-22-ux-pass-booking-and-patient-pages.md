# Review: task 25b, UX pass for booking and the patient's pages

Diff `main...HEAD`, 29 files. Commits between `verify_green` (5d12d9a) and `prove` (e19905c): tests only
(`test_date_parts.py`, `test_date_and_legal_pages.py`). No product line changed during proof.

## Findings

1. **Nit** `scheduling/views/pages/test_no_iso_dates_in_messages.py:28`: the notification test covers the three
   text builders, not each notification kind through its use case. "Waitlist slot offered" and
   "Appointment reminder" reuse `booked_notification_text` (`scheduling/use_cases/notifications.py:41,58`), so the
   builder test covers them only by shared code. A new builder would escape it. Fix: add one test that creates
   each kind through its use case and scans stored bodies.
2. **Nit** same file, line 36: `text_of: object` plus `# type: ignore[operator]`. Named code, passes the gate, but
   `Callable[[datetime, ZoneInfo], str]` removes the suppression.
3. **Nit** `scheduling/domain/date_parts.py:21-22`: a single empty part names the first missing one only
   ("Enter a day" when day and month are empty). Spec allows one error per group; fine.
4. **Nit** `scheduling/templates/booking/details.html:16`: the terms links use `target="_blank"`. That is how
   typed values survive without script, and the text says so. The link text names the new tab. Acceptable.
5. **Nit** `scheduling/views/pages/patient_profile.py:30-34`: `_summary` rewrites the target after `summary_items`.
   Small, but a second place knows the group's first id (`booking_forms.py:_target` does too). Later: one helper.
6. **Nit** the date group does not set `max` or the year's `autocomplete` per spec section 16 beyond
   `bday-day/month/year`; matches the request.

## Checked, no defect

- Trust boundaries: the use cases still receive an ISO string (booking) or `date | None` (profile); the
  `DetailsSchema` still validates. The profile view takes the user from the session. Terms and privacy pages are
  GET-only, no data, open to all.
- `read_birth_date` rejects non-ASCII digits, a year without four digits, the future and today, and ages over the
  limit. Errors are values, nothing swallowed.
- `written_moment` is pure, zone always named; used by pages (via placement rules), notifications and emails.
  No remaining `%Y-%m-%d` in user-facing text; remaining ones are FHIR, audit export or URLs.
- No dependency added, no model, migration or write path changed, so no audit or double-booking impact.
- No `Any`, `cast`, bare `noqa` or bare `type: ignore`.

## Unverified here

`make mutate` was not run in this stage; the orchestrator runs it. `written_moment.py` and `date_parts.py` sit in
`scheduling/domain`, so both fall under the gate. Test count 4001, `make test` about 50 s here (budget is not a
blocker). Browser behaviour at 375 px: not checkable in the sandbox.

## Blocking

None.

## Later

- Findings 1, 2, 5.
