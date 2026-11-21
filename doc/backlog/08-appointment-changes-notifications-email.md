Task 08: appointment changes, notifications and email.

Cancel, reschedule and the status actions (`drlibre-specs.md` section 5.6), the
notification table of section 11 and the emails of section 7.6, as use cases and API on
top of task 07. The waitlist matching that follows a cancellation is task 09; screens
come later.

1. Cancel. The patient for their own appointment under the 24 hour rule, the
   appointment's clinician, or an admin. A reason is required. Records the cancellation
   time and reason and notifies the patient.
2. Reschedule. Only `BOOKED` or `CONFIRMED`; same clinician and type, new start. Runs the
   conflict check and the booking rules with the appointment itself ignored, reassigns
   the room preferring the current one, and notifies the patient. It goes through the
   placing logic of task 07, not a copy of it.
3. Check in, complete, mark no-show: staff only, a clinician on own appointments, an
   admin on any, no notification. A change the table forbids answers `invalid_transition`
   with the current status.
4. Every change follows the record rule (missing is `not_found`, someone else's is
   `forbidden`), locks the appointment so two changes cannot interleave, raises its
   version, and writes its audit entry in the same transaction (section 4). Audit
   metadata never holds the reason.
5. API (section 14): `POST /api/v1/appointments/{id}/cancel`, `/reschedule`, `/check-in`,
   `/complete`, `/no-show`, with strict schemas, the failure contract and declared access.
6. Notifications (section 11): one row per event of the table, created in the event's
   transaction, with the kind and title of the table. The in-app text carries the time
   only: no name, reason or email address. "Appointment booked" of task 07 uses the same
   path.
7. Email (section 7.6): each patient notification is also sent by email. The email
   carries the time in the hospital's time zone with the zone named, the hospital and the
   provider's name, never the reason for the visit or clinical notes, and links to the
   sign-in page, never to a link that signs the reader in.
8. Delivery must not be lost and must not block or undo the change. An email is sent
   only after its transaction commits; a notification whose email is not yet sent stays
   marked so a job can retry it (the scheduler is task 09: provide the function that
   sends what is pending and a management command that calls it). Add what the model
   needs with a migration and regenerate `doc/data-model.md`. Say in the plan what
   happens when the mail server is down. The sender address comes from the environment.
9. Tests: who may do what for each action, each refused transition, the 24 hour boundary
   with the request clock, reschedule into a taken slot, the content rules of the email
   (a planted reason and a planted note appear in no email), no email when the
   transaction rolls back, a retry after a failed send sends once.

The orchestrator reads the emails in the smtp4dev inbox on the host.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
