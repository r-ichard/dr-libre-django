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
| 02 | Domain model and migrations | 3 | merged `bc0c746` with 02a |
| 02a | Finish the model, FHIR readiness: versions, one Appointment resource, mapping check | 3, 15 | merged `bc0c746` |
| 03 | Repeatable demo seed | 16 | merged `8dd846f` |
| 03a | Fast test suite: measure, fast hasher in tests, parallel workers | 16 | merged `d7ad7aa` |
| 04 | Request plumbing: failure contract, correlation id, structured logs, clock, closed by default | 4 | merged `1d3643c` |
| 04a | Log and error path hardening: raw paths in logs, non-JSON lines, errors outside the API | 4, 16 | merged `f8cb3d8` |
| 04b | Audit writer, security headers, deployment checks | 4, 12.3, 16 | merged `45d9150` |
| | **M2 Sign-in and access (#2)** | | |
| 05 | Password sign-in, sessions, access rules (API and use cases) | 12, 14 | merged `796da1f` |
| 05a | Design foundation, sign-in screens, role homes, error pages | 12, 16 | merged `b35274e` |
| 05b | Screens hardening: sliding session cookie on pages, layout edges, favicon | 12.2, 16 | running `01M7Z5V66AB7` |
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

- Start-up should refuse the development `SECRET_KEY` when `DEBUG` is off (task 26).
- Acceptance of the terms and privacy notice (section 7.1) has no column. Task 12.
- Waitlist acceptance sets `Appointment.inherited_version` from the locked entry, with a
  test (review of 02a). Task 09.
- `If-Match` goes through a filtered `update` and its row count, not `save` (review of
  02a). Tasks 22 to 24.
- Rules the model plan left to use cases: `doc/plans/2026-11-21-domain-model.md`, "Waits
  for its use case". Each feature task reads that table.
- Encryption at rest for clinical notes and visitor details in a hold: open point for the
  security review. Task 26.
- Demo appointments are written straight through the models: some fall outside the
  clinician's availability (after 17:00, weekends) and outside the 07:00 to 19:00 calendar
  grid. Re-seed through the booking use cases on real free slots. After task 08.
- Seed review: identify seeded appointments by a marker, not by patient, clinician and
  type; notifications through the same upsert. With the re-seed above.
- The failure mapper answers 500 for exception types it does not list, `Throttled`
  included. Rate limiting needs its own answer (429). Task 12.
- Test-only probe views live in `scheduling/views/` (`probe_views.py`, `probe_urls.py`).
  Move them out of the product package when a test support location exists.
- Start-up lines of `migrate` and the development server are plain text, not JSON. Settle
  with the production server choice. Task 26.
- `SECURE_PROXY_SSL_HEADER` is not set; needed before any deployment behind a proxy that
  ends TLS (review of 04b). Task 26.
- A locked address writes one `auth.lockout` audit entry per attempt: an attacker can
  flood the append-only log. Audit the crossing of the threshold, or once per window
  (review of 05). Task 26, sooner if a task touches sign-in.
- Expired sessions and sign-in failure rows of addresses that never return are never
  purged. Task 09, with the scheduled jobs.
- Public pages need a meta description (Lighthouse SEO). Task 10.
- Static files are served by Django's development file server, also with `DEBUG` off.
  Settle with the production server choice. Task 26.
- The sign-in page sits at the left edge of a wide screen with empty space beside it.
  Layout polish for single-form pages. Task 25.
