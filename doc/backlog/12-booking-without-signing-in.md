Task 12: booking without signing in, use cases and API.

`drlibre-specs.md` sections 7.1, 7.2, 7.5, 7.6 and 7.7 and the three hold endpoints of
section 14. The booking pages are task 12a and sign-in by email link is task 13. These
endpoints are public and create accounts: they are the widest door of the product.

1. Hold (7.1 step 3). `POST /api/v1/booking/holds` takes the appointment type, a named
   clinician or none for first available, the slot start, and the visitor's details: full
   name, date of birth, email, optional phone, optional reason, and acceptance of the
   terms and privacy notice, which is required and recorded with its time. It runs the
   checks placing would run for a patient on that slot, so no hold is created for a slot
   that could not be booked, then holds the slot for 10 minutes. For first available the
   clinician is chosen now, by the ranking of section 5.5, and held.
2. A held slot is not offered to anyone else and counts as a conflict: placing on it
   answers `conflict`, not `rule_violation` as today. An expired hold frees the slot.
   One open hold per email address at a time: say in the plan what a second request does.
3. Code (step 4). A 6 digit code is sent by email, valid 10 minutes, 5 attempts. Only a
   keyed hash of it is stored. `POST /api/v1/booking/holds/{id}/resend` sends a new code,
   at most 3 times an hour per email address, and the earlier code stops working.
4. Verify (steps 5 and 6). `POST /api/v1/booking/holds/{id}/verify` with the correct code
   places the appointment through the placing use case for the patient that email
   identifies (7.2), with source `ONLINE` or `ROUND_ROBIN`, leaving the visitor's own hold
   out of the conflict check, removes the hold, and opens a 24 hour session of kind
   booking code. All in one transaction: a failed placing books nothing, creates no
   account and keeps the hold.
5. The account (7.2). No user with that email: a Patient is created with the typed name,
   birth date and phone, no password, the email marked verified. An active Patient with
   that email: the booking is theirs and their profile is not changed. An Admin, a
   Clinician or an inactive user: refused with a generic message that does not say why.
6. Nothing leaks (7.5). No answer reveals whether an address has an account, and before
   the code is verified nothing about a patient or their appointments is returned. Test
   that the answers for a new address, an existing patient and a staff address are the
   same in body, status and, as far as a test can tell, work done.
7. Rate limits (7.5): holds and code requests are limited per email address and per
   network address. Say in the plan where the counters live, why they hold no readable
   address, and the limits you chose. A refused request gets a code of its own with
   status 429: add it to the failure contract and to ADR 0004.
8. Email (7.6): the code email carries the code and nothing that signs the reader in.
   The booking confirmation goes through the notification path. A code email must reach
   the visitor at once: say what the visitor can do when the mail server is down.
9. Audit (7.7): hold created, hold expired, code verification failed, patient account
   created and booking made, with the email domain only. The actor is empty before
   verification and the patient after it. Expired holds are removed by a job of the
   worker, which audits each.
10. Add what the model needs with migrations and regenerate `doc/data-model.md`.

Carried, to fix here because this task touches booking emails: the notification titles
must be those of section 11 ("Waitlist slot offered", "Waitlist slot booked"), and
accepting a waitlist offer must send one email, not two.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone. The orchestrator books as a visitor on the host and reads the code in the
smtp4dev inbox.
