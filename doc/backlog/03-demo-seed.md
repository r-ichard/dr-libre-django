Task 03: repeatable demo seed.

Give a developer a populated product after one command (`drlibre-specs.md` section 16,
"Demo data"), and make the container stack ready to use without manual steps. No view,
no use case: the seed writes rows through the models.

1. A management command seeds: several hospitals in at least two time zones (one with
   coordinates, one without), each with departments, rooms, appointment types (with and
   without a room need, bookable online and not), specialties, clinicians with weekly
   availability and some time off, patients, appointments in every status and every
   source, waitlist entries in every status, and notifications read and unread. Every row
   must satisfy the database constraints and the rules the model plan deferred to use
   cases (`doc/plans/2026-11-21-domain-model.md`, "Waits for its use case"): same
   department for clinician and type, roles, end equals start plus duration, rooms of the
   clinician's department.
2. Appointments are placed relative to the day of the run, so the product always shows
   past, today's and upcoming appointments. Running the command again, the same day or a
   later day, creates no duplicate and fails on nothing: say in the plan what identifies
   a seeded row and what a later run does to it.
3. One demo sign-in per role, plus one passwordless patient (verified email, no
   password). The demo password comes from the environment (`.env.example`), never from
   the code. The command refuses to run when `DEBUG` is off: accounts with a published
   password must not reach a real deployment.
4. The seed writes one audit log entry for the run, with counts per model and nothing
   else (section 4: no names, emails, phone numbers or dates of birth in audit metadata).
5. Fake people only: invented names, `example.test` addresses, phone numbers from a
   reserved range.
6. Container stack: `web` applies migrations before it serves; `web` gets a health check
   so `docker compose up --wait` returns only when `/api/v1/health` answers; seeding is
   one documented command. Update the Fresh checkout order in `CLAUDE.md`.
7. Tests, written first: the command twice leaves the same row counts; every appointment
   status, source and waitlist status is present; each demo account authenticates with
   the environment password and the passwordless patient has no usable password; the
   command refuses when `DEBUG` is off; the audit metadata holds only counts.

Done when `make setup && make lint && make test && make gate` pass from a fresh clone.
The sandbox cannot run Docker; the orchestrator verifies item 6 on the host.
