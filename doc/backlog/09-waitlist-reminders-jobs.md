Task 09: waitlist, reminders and scheduled jobs.

`drlibre-specs.md` sections 5.7 and 5.8 and the three endpoints of section 14 that go
with them, on top of tasks 07 and 08, plus the worker that runs the jobs on a schedule.
Screens come later.

1. Join (5.8). A patient for themself, an admin for a patient, never a clinician. The
   type must be active and a preferred clinician, if named, active.
2. Automatic offer. Cancelling an appointment (task 08) runs the matching in the same
   transaction: the `WAITING` entries for the same type whose preferred clinician is
   empty or is the freed clinician and whose window contains the freed slot; the oldest
   wins, ties to the lowest id. It becomes `OFFERED`, linked to the freed appointment,
   and the patient is notified.
3. Manual offer. An admin offers a `WAITING` entry the first future cancelled slot of the
   same type inside its window, provided that clinician is still free then and no other
   entry holds that offer.
4. Accept. The patient for their own entry, or an admin. The appointment is placed
   through the placing use case of task 07 for the offered clinician, type and start, so
   conflicts and booking rules apply and a slot someone else took answers `conflict`.
   The entry becomes `BOOKED`, the appointment is linked to it and takes its
   `inherited_version` from the locked entry (ADR 0003), and the patient is notified.
5. Expiry. A `WAITING` entry whose latest time has passed becomes `EXPIRED`. State in the
   plan what happens to an `OFFERED` entry whose offered slot has passed or was taken;
   the specification is silent.
6. Reminders (5.7). One reminder notification for each appointment that starts within
   the next 24 hours, is `BOOKED` or `CONFIRMED` and has none yet. Running it twice
   reminds nobody twice, also when two runs overlap. One audit entry with the count when
   it created any.
7. API (section 14): `POST /api/v1/waitlist`, `POST /api/v1/waitlist/{id}/accept`,
   `POST /api/v1/jobs/reminders` (admin), and `POST /api/v1/waitlist/{id}/offer` (admin)
   for the manual offer, which the admin console will call.
8. Scheduled jobs. One worker process, a service of its own in `compose.yaml` on the
   application image, runs on a schedule: reminders, waitlist expiry, sending the emails
   still pending (task 08), and purging expired sessions and sign-in failure rows older
   than the lockout window. Each job runs in its own transaction with its own correlation
   id and instant, logs one JSON line with its counts, and a failing job neither stops
   the worker nor the other jobs. Each job is also a management command, so it can be
   run and tested alone. Say in the plan how often each runs.
9. Every write is audited through the audit writer, and every notification goes through
   the notification path of task 08, email included.
10. Matching, ranking and expiry decisions are pure functions in the domain layer, under
    the mutation gate.

Carried from the review of task 08a: the appointment body now carries the visit reason,
safe only because every caller limits its readers to the patient, the appointment's
clinician and an admin. No waitlist answer may include another patient's appointment
reason: an offer shows the time, the provider and the hospital only. And the test helper
`scheduling/views/appointment_action_support.py` gets a name the lint rules for test files
already cover, so its per-file exception can go.

The sandbox cannot run Docker: the orchestrator starts the worker on the host and
watches a reminder email arrive.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
