Task 08a: booking hardening.

Gaps the orchestrator found on the running stack and in the reviews of tasks 07 and 08,
to close before the waitlist builds on this code. No new feature except item 1.

1. A patient cannot give a reason for the visit. `POST /api/v1/appointments` refuses a
   `reason` field, yet the appointment has one (`drlibre-specs.md` sections 3.1 and 8).
   Accept an optional reason, bounded in length, stored on the appointment, and never
   copied to the audit metadata, a notification, an email or a log line. It is returned
   only to the patient, the appointment's clinician and an admin: say where in the plan.
2. A committed change can answer 500. The email is sent from an `on_commit` callback that
   catches mail server errors only; any other error there escapes after the commit, so the
   client is told the change failed when it happened. Nothing raised while sending may
   change the answer of a change that committed: log it with its trace and leave the
   notification pending.
3. The email path raises for a notification without an appointment. Waitlist
   notifications (task 09) have none. Make the content builder total over the notification
   kinds of section 11, or keep kinds it cannot mail out of the pending set, and say
   which in the plan.
4. The size rule of §5 is not enforced: `scheduling/views/test_appointment_actions.py`
   has 719 lines, `scheduling/use_cases/test_placement.py` 426 and
   `scheduling/models/test_version.py` 409, and the review approved them. Make
   `make gate` fail on a Python file over 500 lines or a function over 100, generated
   migrations excepted, and split the files that fail it along what they test.
5. `GET /api/v1/slots` and `GET /api/v1/appointments` accept a range whose end is not
   after its start. Refuse it with `invalid_input`.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
