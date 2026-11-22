Area: the admin console.

Specification: `drlibre-specs.md` sections 4, 5.2 to 5.8, 10, 12.3 and 13. Demo admin:
`admin@example.test` with `DEMO_PASSWORD`. Create a second admin through the console when
a check needs two. Use the browser for the pages and `curl` for direct requests.

Try at least:
- Reach: every route under `/admin-console/` as a visitor, a patient and a clinician, by
  GET and by a forged POST with a valid cross-site token of that user. None may show or
  change anything.
- The five organisation records (hospitals, specialties, departments, rooms, appointment
  types): create, edit, delete; every field at its limits and beyond; a code that
  differs only in letter case; two tabs saving the same record; each refusal of the
  delete table of section 10, and a delete the address bar asks for without the
  confirmation page.
- What follows in public: a deactivated hospital, specialty, room and type in the public
  search, the booking pages and `GET /api/v1/slots`, at once; a changed time zone and
  what the pages then say about existing appointments.
- Users: a temporary password in any page, answer, log line, email or audit row after
  the form is sent; the admin's own account (deactivate, change role, delete), the last
  active admin from two sessions at once; a changed email and what then still signs in
  (old session, old sign-in link, old password); a role change that contradicts the
  user's records; that a deactivated user's open session stops at the next request.
- Clinicians: a profile with a room of another department, an inactive room, an inactive
  specialty, a weight of 0; moving a clinician who has appointments; the read-only week
  calendar: no action, no clinical note, in the page source too.
- Appointments: the filters with odd and hostile values; book for a patient (every
  active type offered, no "first available", conflicts and availability still apply,
  lead time and open-booking limits do not); every status action twice and out of
  order; cancel without a reason; reschedule onto a taken time. Clinical notes must
  never reach an admin: plant one as the clinician, then look everywhere as the admin.
- Waitlist: add a patient with an impossible window; a manual offer when no cancelled
  time fits, when another entry holds the offer, when the time was taken since; accept
  an offer for the patient twice and from two tabs.
- Audit log: that every write you made is there with the right actor; that no row holds
  a name, an email address beyond its domain, a phone number, a birth date, a reason or
  a note; that nothing under `/admin-console/audit` changes an entry.
- Dashboard and export, when `doc/backlog.md` marks task 21 merged: each figure of
  section 13 against the database by hand for one range; a range with no appointment;
  the CSV: columns, UTC instants, ids only, a cell that starts with `=`, `+`, `-` or
  `@`, the audit entry with the row count, and that a link from another site cannot
  trigger it.
- Every list and form at 375 px and 1440 px, with the keyboard only, and console errors
  on every page of the console.
