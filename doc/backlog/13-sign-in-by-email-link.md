Task 13: sign-in by email link.

`drlibre-specs.md` section 7.3, the two link endpoints of section 14 and the pages that
go with them, for the Patient role only. A link signs someone in without a password, so
every rule of 7.3 is a security rule.

1. Ask. `POST /api/v1/auth/link` with an email address. When it belongs to an active
   Patient, a link is sent to it. In every other case (no account, an Admin, a
   Clinician, an inactive user) nothing is sent and nothing is created. The answer is the
   same either way, in body, status and time: say in the plan how sending an email does
   not make one answer slower than the other, and test it as far as a test can.
2. The link is valid for 15 minutes and works once. Asking for a new link cancels the
   earlier ones. At most 3 links an hour per email address, limited per network address
   as well, through the rate limiter of task 12.
3. Only a hash of the token is stored. The token is random, at least 128 bits, and never
   appears in a log line, an audit entry or an error page: prove it with a planted token
   through the page and the API, at the level of what the process writes.
4. Use. Opening the link shows a page with a "Continue" button and uses nothing. Only
   pressing the button uses the link, so a mail scanner that opens it cannot spend it.
   `POST /api/v1/auth/link/verify` exchanges the token for a session. After it the
   patient is sent to an address that no longer contains the token.
5. The session lasts 24 hours and is never extended (section 12.2), through the session
   use case of task 05 with the email link kind, whether or not the patient also has a
   password.
6. An expired, used, cancelled or unknown link answers one same message and offers to
   ask for a new one.
7. Pages: the sign-in page offers "Email me a sign-in link" beside the password form, a
   "Check your email" page, and the page with the button. Layout and components of task
   05a; no inline script or style; they work without JavaScript.
8. Email (7.6): the sign-in link email is the only email of the product that signs its
   reader in. It says how long the link works and that it works once.
9. Audit (7.7): link requested, link used, link refused, with the email domain only and an
   empty actor until the link is used.
10. Add what the model needs with a migration and regenerate `doc/data-model.md`.

Carried from the review and the host check of task 12, to fix here because this task
works on the same code:

- Lock order. `booking_verification._patient_of` locks the user row before placing locks
  the clinicians, while placing documents the order clinicians, patient, rooms. A
  verification racing a normal booking of the same patient can deadlock and answer 500.
  One lock order everywhere, with a test that races the two paths.
- Mail server down. A hold or a resend then answers the generic 500. It must answer a
  failure of its own that tells the visitor to try again in a few minutes, with nothing
  held and no account touched. The link request of this task must not fail that way at
  all: its answer is the same whether or not an email could be sent.

After signing in the patient lands on the patient home; their appointments arrive with
task 14.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone. The orchestrator follows a link from the smtp4dev inbox in Chrome.
