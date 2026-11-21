Area: sign-in, sessions and access control.

Specification: `drlibre-specs.md` sections 4, 7.3, 12 and the access column of section 14.
Demo accounts: `admin@example.test`, `clinician@example.test` and the other clinicians,
`patient@example.test` (password), `passwordless@example.test` and the other patients
(no password).

Try at least:
- Password sign-in: same answer and same time for a wrong address and a wrong password;
  the lockout after 10 failures, its end, and whether it can be bypassed (case, spaces,
  another route); an inactive user; a passwordless patient.
- Sign-in by email link: every rule of 7.3 (15 minutes, once, a new link cancels the old,
  3 an hour, patients only, same answer for every address, the Continue step, the token
  gone from the address afterwards, the token in no log line).
- Session cookie: flags, lifetime per role and kind, sign-out, a deactivated user, an
  old cookie after a password change, a forged or truncated cookie.
- Every API route and every page with each role and with no session: a patient on
  clinician and admin routes, a clinician on admin routes, staff on patient routes.
  Every route that takes an id with another user's id (appointment, waitlist entry,
  notification, hold, calendar file). A missing record must answer not found and
  someone else's forbidden, never the record.
- State-changing requests from another origin, with `Origin: null`, without the
  cross-site token, with the wrong method or content type.
- Identity in the body: `patient_id`, `user_id`, `role`, `actor` and the like where the
  session should decide.
- Response headers on pages, API answers and errors; what an error page shows.
- Audit: sign-in success, failure, lockout, link requested, used and refused are there,
  with the email domain only.
