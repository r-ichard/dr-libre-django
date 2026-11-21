# Backlog

One task per fabro run of `conventions-auto`. Each task is one reviewed PR-sized change.
Run: `fabro run conventions-auto --goal-file doc/backlog/NN-slug.md -d`.
Status is kept here by the orchestrator: todo, running, merged, failed.

A task file is written just before its run, from the specification sections named here
and from what the previous runs taught. The orchestrator writes tasks and process files
and never product code: a defect found on the host becomes a task. Milestones are mirrored
as GitHub issues; the issue number is in the heading.

## Owner decisions (2026-11-21)

- Latest stable Django and Django REST Framework. PostgreSQL, tests included.
- Front end: server-rendered Django templates and hand-written CSS. No CSS framework, no
  Node build. Specialty icons from healthicons.org, vendored as SVG files.
- Everything runs locally in containers: application, database, and `rnwood/smtp4dev` to
  receive email. Nothing leaves the machine.
- The owner checks the data model after task 02 merges.

## Tasks

| # | Task | Specification | Status |
|---|---|---|---|
| | **M1 Foundation (#1)** | | |
| 01 | Scaffold and stack binding | 14, 16 | merged `eaf7ef2` |
| 01a | Scaffold hardening: host defects and reviewer "Later" list of 01 | 16 | merged `b972eac` |
| 02 | Domain model and migrations | 3 | green, run `01M7YR6HE159` failed after it; continued in 02a |
| 02a | Finish the model, FHIR readiness: versions, one Appointment resource, mapping check | 3, 15 | running `For more inf` on `task/02-domain-model` |
| 03 | Repeatable demo seed | 16 | todo |
| 04 | Platform baseline: result codes, correlation id, structured logs, audit writer, security headers | 4, 12.3, 16 | todo |
| | **M2 Sign-in and access (#2)** | | |
| 05 | Design foundation, password sign-in, sessions, access rules | 12, 16 | todo |
| | **M3 Scheduling and booking (#3)** | | |
| 06 | Scheduling engine: free slots, conflicts, status changes, booking rules; bind `make mutate` | 5.1 to 5.3, 5.6 | todo |
| 07 | Booking use cases and API: placing, who books for whom, round robin, slots | 5.2, 5.4, 5.5, 14 | todo |
| 08 | Appointment changes: cancel, reschedule, status actions, notifications, email | 5.6, 7.6, 11, 14 | todo |
| 09 | Waitlist, reminders, expiry, scheduled jobs | 5.7, 5.8, 14 | todo |
| | **M4 Public search and passwordless booking (#4)** | | |
| 10 | Public search | 6.1 to 6.5, 14 | todo |
| 11 | Public detail pages | 6.6 | todo |
| 12 | Booking without signing in: hold, code, patient account | 7.1, 7.2, 7.5 to 7.7 | todo |
| 13 | Sign-in by email link | 7.3, 7.4, 12.2 | todo |
| | **M5 Patient portal (#5)** | | |
| 14 | Home, appointments, booking wizard, reschedule, cancel, calendar file | 8 | todo |
| 15 | Waitlist, notifications, profile | 8 | todo |
| | **M6 Clinician workspace (#6)** | | |
| 16 | Today, calendar, appointment, clinical notes | 9 | todo |
| 17 | Availability, time off, patients, rooms | 9 | todo |
| | **M7 Admin console and reporting (#7)** | | |
| 18 | Hospitals, specialties, departments, rooms, appointment types | 10 | todo |
| 19 | Users and clinicians | 10 | todo |
| 20 | Appointments, waitlist, audit log, settings | 10 | todo |
| 21 | Dashboard, reporting, CSV export | 13 | todo |
| | **M8 FHIR API (#8)** | | |
| 22 | Tokens, metadata, public read resources, search bundles | 15.1 to 15.5 | todo |
| 23 | Schedule, Slot, Patient, Appointment, booking through FHIR | 15.3 to 15.6 | todo |
| 24 | AppointmentResponse, Communication, AuditEvent, versions | 15 | todo |
| | **M9 Hardening and hand-over (#9)** | | |
| 25 | Accessibility and UX pass (impeccable) | 16 | todo |
| 26 | Security review, smoke test, README, hand-over | all | todo |

## Carried items

Small findings waiting for the next task that touches the same file.

- `compose.yaml`: `web` has no health check, so `docker compose up --wait` returns before
  the server listens. Add one with the next compose change (task 09, worker container).
- `scripts/ensure_database.py`: a non-numeric `DB_PORT` raises a bare `ValueError`.
- Start-up should refuse the development `SECRET_KEY` when `DEBUG` is off (task 26).
