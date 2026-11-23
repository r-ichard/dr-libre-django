# ADR 0012: page access readings encoded by the access table

Status: proposed, 2026-11-23, for the owner to accept or change the specification.

## Context

The page access table (`scheduling/views/pages/test_page_access_rows*.py`) gives, for every page
route, the answer each caller gets: visitor, patient, clinician, admin. The table follows
`drlibre-specs.md` sections 12.3, 14 and 16. Where the specification is silent or two of its
statements disagree, the table states the reading it takes. This ADR lists those readings so the
owner can accept them or change the specification. This ADR makes no code change and edits no
specification text.

## Decision

Until the owner decides otherwise, the table encodes the readings below. Changing a reading means
changing the specification or this ADR, then the matching rows.

## Readings for the owner

1. **Record existence (conflict).** Section 12.3 says a record that belongs to someone else gives
   `forbidden` and a missing record gives `not_found`. Those two answers reveal whether the record
   exists, which the access goal rules out. The table follows 12.3. The divergence is already in the
   code: `scheduling/views/pages/booking_code.py` (`_expired`) answers `not_found` for a hold made
   by another visitor. The owner picks one answer for both cases; `not_found` for both removes the
   leak and changes 12.3.
2. **Signed-in staff on no-session pages.** Section 12.3 says search, public pages, the booking steps
   and the sign-in link "need no session". The table reads that as OK for every caller, including a
   signed-in clinician or admin, not `forbidden`.
3. **Appointment confirmation and calendar file.** The specification names no area for them. The
   table reads them as patient-only: a clinician and an admin get `forbidden`.
4. **Password for signed-in staff.** `account/password` gives a patient `forbidden` and staff OK.
   This matches the `allowed_roles` of the code; the specification does not name the page.
5. **Sign-out.** Section 14 lists logout as "Anyone". The table gives every caller, a visitor
   included, a redirect to sign-in with the session cookie cleared.
6. **Favicon.** `favicon.ico` redirects to a static file with no session check; OK for every caller.
7. **Style page.** `style` exists only when `DEBUG` is on. The specification is silent; the table
   lists it as debug-only.
8. **Static files.** `/static/` is not a page and has no row.
9. **Methods the view refuses.** A method the view does not accept answers 405. The specification
   does not name 405; the table says nothing about it.
10. **Hold routes and the hold cookie.** On `book/holds/<id>/code` and `resend` the hold cookie,
    not the session, identifies the caller. A visitor's own hold gives OK; another visitor's hold
    gives `forbidden`, subject to reading 1. Section 12.3 gives no rule for the cookie.

## Consequences

- A route that answers differently from the table fails the access walk once that walk exists.
  The table is written as the specification and these readings say, so such a route is a finding
  for the owner, not a reason to change the table.
- The security review's "For the owner" section repeats these readings when it gains its access
  section.
