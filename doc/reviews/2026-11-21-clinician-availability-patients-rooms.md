# Review: task 17, clinician availability, time off, patients, rooms

Scope: `git diff main...HEAD`, 56 files. Gates (lint, test, gate) pass per `check` stage; I did not re-run them.

## Proof left no trace
Commits `verify_green`..`prove` touch only `test_availability.py`, `test_clinician_schedule_pages.py`, `test_time_grid.py`. No product or migration line changed. Clean.

## Findings

1. **Info** `scheduling/models/availability.py:27`: weekday constants renamed from Monday=0 to Sunday=0. `free_slots.py:85` already read Sunday=0, so this fixes a misleading name; no data migration needed. Confirmed at a glance.
2. **Low** `scheduling/views/pages/clinician_patients.py:28`: the patient-name search travels as `?q=` in the URL (history, server logs). Spec asks for a search in pages; a name is personal data. Fix: POST-less alternative is not simple; at least keep `q` out of access logs, or accept and document.
3. **Low** `scheduling/use_cases/clinician_patients.py:25`: loads every appointment of the clinician to build the list. Fine now; grows with history. Fix: aggregate in the database when volume matters.
4. **Low** `scheduling/use_cases/clinician_rooms.py:16`: `appointment_id: object | None` is loose; use `UUID | None`.
5. **Low** `scheduling/use_cases/availability.py:112`: room row locked with `select_for_update` but a room deactivated later leaves existing rules in place; edit then rejects an unchanged room. Acceptable per spec ("active room"), but the user sees an error on unrelated edits.

## Checks
- Authorization: every write goes through `locked_profile` (role and profile from session) and `guard_record` on ids; payload carries no actor. Good.
- Concurrency: profile row locked before overlap check; database exclusion constraint (half-open `[)`, btree_gist exists from migration 0001) and unique constraint back it; `IntegrityError` becomes a value inside a savepoint. Good.
- Audit: create, update, delete for rules and time off write the entry in the same transaction; time-off audit holds ids only. Good.
- Patients and rooms: set built from the clinician's own appointments first; other rooms' cells carry no patient (`clinician_rooms.py:44`). Good.
- Cache: `render_page` adds never-cache headers. Good.
- No new dependency; no escape hatches found.

## Blocking
None.

## Later
- Finding 2 (patient search in URL).
- Finding 3 (patient list aggregation).
- Finding 4 (`UUID` type on `RoomCell`).
- Finding 5 (edit of a rule whose room went inactive).
