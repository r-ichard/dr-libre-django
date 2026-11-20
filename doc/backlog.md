# Backlog

One task per fabro run of `conventions-auto`. Each task is one reviewed PR-sized change.
Run: `fabro run conventions-auto --goal-file doc/backlog/NN-slug.md -d`.
Status is kept here by the orchestrator: todo, running, merged, failed.

A task file is written just before its run, from the specification sections named here
and from what the previous runs taught. Only task 01 has a file so far. The slicing below
is a draft; reorder or split it freely.

| # | Task | Specification | Status |
|---|---|---|---|
| 01 | Scaffold and stack binding | 16 | todo |
| 02 | Architecture decision records and security baseline | 4, 12.3, 16 | todo |
| 03 | Domain model, migrations, repeatable seed | 3, 16 | todo |
| 04 | Sign-in with a password, sessions, access rules | 12 | todo |
| 05 | Scheduling engine: free slots, placing, conflicts, status | 5.1, 5.2, 5.6 | todo |
| 06 | Scheduling engine: booking rules, round robin, reminders, waitlist | 5.3 to 5.5, 5.7, 5.8 | todo |
| 07 | Booking use cases, transactions, application API, notifications | 11, 14 | todo |
| 08 | Public search and public detail pages | 6 | todo |
| 09 | Passwordless patients: hold, code, sign-in link, email | 7 | todo |
| 10 | Patient portal | 8 | todo |
| 11 | Clinician workspace | 9 | todo |
| 12 | Admin console | 10 | todo |
| 13 | Reporting, dashboard, audit log views | 13 | todo |
| 14 | FHIR API | 15 | todo |
| 15 | UX polish and accessibility pass (impeccable) | 16 | todo |
| 16 | Smoke test, README, hand-over | all | todo |
