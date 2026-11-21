Task 17e: the demo seed survives a person using the demo.

This branch holds the work of task 17d (`doc/backlog/17d-demo-seed-through-use-cases.md`,
its plan and its review in `doc/plans/` and `doc/reviews/`): the seed now builds its
world through the use cases and rebuilds it once a day. It is not merged, because the
rebuild breaks on ordinary use. This task changes `scheduling/demo_seed/` and nothing
else of the product. Reproduce each finding with a failing test before the fix.

Found by the orchestrator on the running stack:

1. Seed, sign in as `patient@example.test`, accept the seeded waitlist offer
   (`POST /api/v1/waitlist/<id>/accept`), then run the seed with a clock two days later:
   `ProtectedError: Cannot delete some instances of model 'WaitlistEntry' because they
   are referenced through protected foreign keys: 'Appointment.waitlist_entry'`. The
   command dies with a stack trace and the demo can never be refreshed again. Accepting
   that offer is the first thing a person does with the demo patient.
2. On a Saturday or a Sunday the scenarios of "today" all move to next Monday, the
   finished ones too: the demo shows visits completed, missed and checked in two days in
   the future. A finished visit sits on the last working day up to today; an upcoming
   one on the next working day from today.

The rule to build, and to state in the plan before the code:

3. The seed never fails and never loses a person's work because of what a person did
   with the demo world. A seeded row that an unseeded row depends on, or that a person
   changed after the seed made it (a reschedule, a cancellation, a status change, a
   clinical note, an accepted offer, a read notification), stays as it is. Every other
   seeded row is replaced. A row no seed made is never deleted or changed. Say in the
   plan how the seed tells "changed by a person" from its own work, and test each of the
   cases named here by doing it through the use case between two runs.
4. The command prints what it did: rows built, rows kept because a person used them,
   scenarios skipped because their slot was taken. On an empty database no scenario is
   skipped: a test asserts that every entry of `scenarios.APPOINTMENTS` and
   `scenarios.WAITLIST_ENTRIES` exists after the first run.

From the review of task 17d (`doc/reviews/2026-11-21-demo-seed-through-use-cases.md`):

5. Finding 1: mail is silenced by "pending now and not pending before", which would also
   silence a real notification committed during the run. Silence the seeded rows only.
6. Finding 5: stale time off is found by clinician and reason, so a person's own "Annual
   leave" is deleted. Recognise seeded time off by the marker, like the other rows.
7. Finding 3: the world is rebuilt up to three times in one UTC day, once per hospital
   time zone, and each rebuild adds about seventy audit entries. At most one rebuild a
   day; say which day in the plan.
8. Finding 6: a test asserts that each demo patient who has an upcoming appointment has
   an unread notification, or the plan stops promising a reminder.

Still true from task 17d: no page, API route, model or use case changes; the seed sends
no email; a second run at the same moment changes no row and adds no audit entry; it
refuses to run with `DEBUG` off. If a use case cannot do what the seed needs, stop and
say so in the reply instead of changing it.

Write the commit so that merging it closes the issue: the reply of the last stage lists
"Closes #32".

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone, and the tests of `scheduling/demo_seed/` take less than 10 seconds together.
