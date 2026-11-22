# Backlog

One task per fabro run of `conventions-auto`. Each task is one reviewed PR-sized change.
Run: `fabro run conventions-auto --goal-file doc/backlog/NN-slug.md -d`.
Status is kept here by the orchestrator: todo, running, merged, failed.

Order inside M4: 10, 12, 13, 12a, 10a, 11, so that a slot link always has somewhere to go.
A task file is written just before its run, from the specification sections named here
and from what the previous runs taught. The orchestrator writes tasks and process files
and never product code: a defect found on the host becomes a task. Milestones are mirrored
as GitHub issues; the issue number is in the heading.

## QA gate

QA runs (`fabro run qa`, one per area in `.fabro/workflows/qa/areas/`) test the product as
it is on `main` and file GitHub issues labelled `qa` and `P0`, `P1` or `P2`. Before a new
backlog task starts: `gh issue list --label P0 --state open`. An open P0 that the
orchestrator has reproduced becomes the next task. P1 and P2 are batched into hardening
tasks.

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
| 05b | Screens hardening: sliding session cookie on pages, layout edges, favicon | 12.2, 16 | merged `0fa71b5` |
| | **M3 Scheduling and booking (#3)** | | |
| 06 | Scheduling engine: free slots, status changes, booking rules, first available; `make mutate` bound | 5.1 to 5.3, 5.5, 5.6 | merged `5d18572` |
| 06a | Domain hardening: domain owns its enumerations, identifier type, property tests, mutation survivors | 5, 4 | merged `59cda46` |
| 07 | Booking use cases and API: placing, who books for whom, round robin, slots | 5.2, 5.4, 5.5, 14 | merged `4466b27` |
| 08 | Appointment changes: cancel, reschedule, status actions, notifications, email | 5.6, 7.6, 11, 14 | merged `032461d` |
| 08a | Booking hardening: reason for the visit, errors after commit, size gate, range checks | 3.1, 8, 14 | merged `47d6ed1` |
| 09 | Waitlist, reminders, expiry, scheduled jobs | 5.7, 5.8, 14 | merged `5370249` |
| | **M4 Public search and passwordless booking (#4)** | | |
| 10 | Public search, use case and API | 6.1 to 6.5, 14 | merged `2344ec0` |
| 10a | Public search pages | 6.1 to 6.5, 16 | merged `ca68ee5` |
| 11 | Public detail pages | 6.6 | merged `62d00f2` |
| 12 | Booking without signing in, use cases and API: hold, code, patient account, rate limits | 7.1, 7.2, 7.5 to 7.7, 14 | merged `bc85ddf` |
| 12a | Booking pages: details, code, confirmation, calendar file | 7.1, 16 | merged `1b00054` |
| 13 | Sign-in by email link | 7.3, 7.4, 12.2 | merged `b3192e7` |
| 13a | Fix: the link's Continue button answers 403 in a browser; browser-like form tests | 7.3, 12.3 | merged `84412f9` |
| | **M5 Patient portal (#5)** | | |
| 14 | Patient portal: home, appointments, booking wizard, reschedule, cancel | 8, 7.4 | merged `abb50a6` |
| 15 | Patient portal: waitlist, notifications, profile, password | 8 | merged `9d36ae6` |
| | **M6 Clinician workspace (#6)** | | |
| 16 | Clinician workspace: today, calendar, appointment, clinical notes | 9 | merged `f72c635` |
| 17 | Clinician workspace: availability, time off, patients, rooms; calendar grid fixes | 9 | merged `a6609fc` |
| 17a | QA round 1: no input answers 500 (#10, #12, #13, #14, #18) and a hostile-input test over every route | 4 | merged `e412ecb` |
| 17b | QA round 1: ten smaller findings (#11, #15 to #17, #19 to #24) and what task 17a left open | 4, 5, 6, 8, 12.3, 16 | merged `58caea4` |
| 17c | QA round 2, clinician: time grid alignment, multi-day time off, four smaller (#25 to #29, #31) | 9, 16 | merged `64d18a7` |
| 17f | Time grid: blocks stay in their column and show whole lines (#30) | 9, 16 | merged `f3340e6` |
| 17d | Demo seed books through the use cases (#32) | 16 | merged with 17e `3df1aa8` |
| 17e | Demo seed survives a person using the demo | 16 | merged `3df1aa8` |
| | **M7 Admin console and reporting (#7)** | | |
| 18 | Hospitals, specialties, departments, rooms, appointment types | 10 | merged `42600a0` |
| 19 | Users and clinicians; carried: list paging, demo specialty icons, two time grid faults | 10 | running `01M80E7BVMNV` |
| 20 | Appointments, waitlist, audit log, settings | 10 | todo |
| 21 | Dashboard, reporting, CSV export | 13 | todo |
| | **M8 FHIR API (#8)** | | |
| 22 | Conventions, tokens, metadata, the seven public resources: read and search | 15.1, 15.2, 15.4, 15.5 | merged `ef6e229` |
| 22a | FHIR hardening: valid R4 proven by the HL7 validator, writes answer FHIR JSON, repeated `_include`, cache headers | 15.1 | running |
| 23 | Schedule, Slot, Patient, Appointment, booking through FHIR | 15.3 to 15.6 | todo |
| 24 | AppointmentResponse, Communication, AuditEvent, versions | 15 | todo |
| | **M9 Hardening and hand-over (#9)** | | |
| 25 | Accessibility and UX pass (impeccable) | 16 | todo |
| 26 | Security review, smoke test, README, hand-over | all | todo |

## Carried items

Small findings waiting for the next task that touches the same file.

- Start-up should refuse the development `SECRET_KEY` when `DEBUG` is off (task 26).
- `If-Match` goes through a filtered `update` and its row count, not `save` (review of
  02a). Tasks 22 to 24.
- Rules the model plan left to use cases: `doc/plans/2026-11-21-domain-model.md`, "Waits
  for its use case". Each feature task reads that table.
- Encryption at rest for clinical notes and visitor details in a hold: open point for the
  security review. Task 26.
- Test-only probe views live in `scheduling/views/` (`probe_views.py`, `probe_urls.py`).
  Move them out of the product package when a test support location exists.
- Start-up lines of `migrate` and the development server are plain text, not JSON. Settle
  with the production server choice. Task 26.
- `SECURE_PROXY_SSL_HEADER` is not set; needed before any deployment behind a proxy that
  ends TLS (review of 04b). Task 26.
- A locked address writes one `auth.lockout` audit entry per attempt: an attacker can
  flood the append-only log. Audit the crossing of the threshold, or once per window
  (review of 05). Task 26, sooner if a task touches sign-in.
- Static files are served by Django's development file server, also with `DEBUG` off.
  Settle with the production server choice. Task 26.
- The sign-in page sits at the left edge of a wide screen with empty space beside it.
  Layout polish for single-form pages. Task 25.
- Review of 05b, small: lockout minutes in the message derived from `LOCKOUT_WINDOW`; a
  test for cookie renewal on a redirect response; favicon colour is not the primary token.
  Task 25.
- Review of 06a, small: the domain import guard does not look into subpackages; a stale
  line in `mutation-equivalents.txt` is printed but does not fail. With the next task that
  touches them.
- Section 5.2 step 2 names no code for a named room that is inactive or of another
  department; the code answers `not_found`. Owner to confirm.
- The email of a change is sent inside the request after commit and can hold the answer
  for up to the 10 second mail timeout when the server hangs (review of 08). Revisit when
  the worker of task 09 sends pending emails.
- Review of 09, small: a stale offer is detected by clinician overlap only; the manual
  offer loads every future cancelled slot of the type. With the admin waitlist screen,
  task 20.
- Public search loads the whole catalogue and 90 days of schedules per request and has no
  rate limit (review of 10). Task 26, with the rate limits of task 12 as the mechanism.
- The network address for rate limits is `REMOTE_ADDR`: behind a proxy every visitor
  shares it (review of 12). Settle with `SECURE_PROXY_SSL_HEADER`. Task 26.
- The sign-in page shows the password form first; most patients have no password. And
  the "link not valid" page does not show the signed-in user in its header. Task 25.
- `background_mail._send` logs a failure without its trace. Task 26.
- The terms and the privacy notice a visitor accepts have no page to read. And the date of
  birth is a date picker, awkward for a birth date. Task 25.
- The code page is addressed by the hold id and shows a masked email to whoever has the
  address (review of 12a): consider binding it to the browser that made the hold. Task 26.
- Patient portal, from the browser check of task 15: accepting a waitlist offer lands on
  the appointments without a notice; the notifications page goes from an h1 to h3
  headings; the profile form does not move focus to its first invalid field; notification
  times are shown in UTC while the rest of the portal uses the hospital's zone. Task 25.
- `ClinicalNote` declares itself not exposed through FHIR, but section 15.3 maps clinical
  notes to `Appointment.comment`, returned only to the appointment's clinician. Task 23.
- Section 5.6 puts no time on a status change: a clinician can mark an appointment two
  days ahead as completed or as a no-show (seen in the demo seed of task 17d). Owner to
  confirm whether check in, complete and no-show wait for the day or the start time.
- Module docstrings name task numbers ("Task 10a: ...", "Task 17a: ..."), which says
  nothing to a reader of the code. Sweep with task 26.
- Review of 17e, small: any `invalid_input` from `create_time_off` counts as "skipped";
  the reminder test accepts any unread notification; `test_survives_use.py` is 346
  lines; the seed's tests take 16 seconds alone. With the next task that touches the seed.
- "Appointment booked", "Waitlist slot offered" and the emails still write dates as
  "2026-11-23 at 13:00"; pages and the cancelled notification write "Monday 23 November
  2026, 13:00" (rest of #23). Task 25.
- Review of 17b, small: the notice cookie is not marked secure when `DEBUG` is off; ADR
  0004 gives the portal page limit as "6 digits" beside the API's 1,000,000; the
  middleware imports the 400 page from `views.pages`. Task 26.
- The patient's waitlist form offers a type that is not bookable online ("Skin check")
  and names its clinician, whom the public search hides. Section 5.8 only asks for an
  active type, and an admin can accept the offer for the patient, but the patient
  cannot. Owner to confirm whether a patient may join for such a type.
- Admin lists at 375 px: the table scrolls sideways inside its frame and shows the name
  and half of the code; the other columns are found only by scrolling. A list of cards
  under 40rem would read better. Task 25.
- Review of 18, small: the stale-save page offers "saving again replaces theirs" and
  shows no difference between the two versions. Task 25.
