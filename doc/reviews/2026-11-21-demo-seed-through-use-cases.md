# Review: task 17d, demo seed through the use cases

Diff `main...HEAD`: 9 files, all under `scheduling/demo_seed/` plus the plan. No page, route, model,
migration, use case or dependency touched. Proof stage (`verify_green`..`prove`, 181ff33) changed
no file: no mutation left behind. `make test` 2309 passed in 17s here (baseline 20s with failing
tests), lint/gate clean in the `check` stage. I did not re-run `make mutate`.

One-sentence plans: `booking.py` calls use cases as demo users under a per-call clock; `marker.py`
records one `demo_seed.mark` audit entry per row and retires marked rows; `writer.py` upserts the
catalogue, then rebuilds the world once per local day. All confirmed at a glance; I traced
`world_is_current`, the `email_pending` silencing and `retire_world` ordering.

## Findings

1. **Medium** `writer.py:62-65`: silencing mail is `update(email_pending=False)` on every pending
   row not in the pre-run snapshot. Under READ COMMITTED a real notification committed by another
   request during the seed would be seen as "new" and silently never mailed. Fix: select the
   rows by `appointment`/`waitlist_entry` in the seeded set instead of by snapshot difference.
2. **Medium** `marker.py:56-69`: `retire_world` raises `ProtectedError` if a person attached a row
   to a seeded appointment (e.g. a reschedule, a hold, a note they made). Seed would then fail
   with a stack trace instead of leaving that world alone. Fix: catch per appointment and keep it,
   or cover with a test that documents the intent.
3. **Low** `marker.py:42-50`: `world_is_current` needs the same local date in all three zones, so
   the world is rebuilt up to three times a UTC day (each rebuild adds audit entries). Not a
   defect against the task (same instant, same run is a no-op); note only.
4. **Low** `booking.py:77-110`: `row_unless_slot_taken` also swallows `CONFLICT`/`NO_*` for
   `change_status` and `mark_read` follow-ups, and for bookings. A seed that silently drops (for
   example a seed landing in time off) shows only as a missing row. `test_writer.py` status set
   catches most losses, but there is no assertion that every `APPOINTMENTS` entry exists.
   Fix: test that the placed count equals `len(scenarios.APPOINTMENTS)` on an empty database.
5. **Low** `writer.py:134-143`: stale time off is found by clinician and reason, not by marker, so a
   person's own "Annual leave" for a demo clinician is deleted on rebuild. Task item 7 asks for a
   marker for seeded records. Fix: mark time off like the others, or document it.
6. **Low** plan vs code: the plan lists `send_reminders` and a seeded "Appointment reminder"; the
   code never calls it. Task item 9 needs only unread notifications, and they exist (booking,
   offer), but no test asserts an unread one exists. Fix: add that assertion, or update the plan.
7. **Low** `test_writer.py:26,90`: `CONFIRMED` dropped from the status set and the finished check
   relaxed to `day <= today`. Matches the new scenarios (today's completed/no-show), but weakens
   the old guard; the new today-status test covers it.
8. **Nit** `test_seed_world.py:79`: `# type: ignore[operator]` names its code, gate passes; a typed
   fixture would be cleaner.

Checks with no finding: authorization from the actor user, never payload; no `Any`/`cast`/bare
ignores; `SeedBrokeRuleError` raises inside the atomic block so it rolls back; marker entries are
entity `DemoSeed`, read only through `appointment_history` filtered to `Appointment`, so no API
or page shows them; `DEBUG` and `DEMO_PASSWORD` checks untouched; clock rebinding confined to
`at_clock`, restored by the context manager; no dependency added; task item 10 test present.

## Blocking

None.

## Later

- Findings 1 to 6 above (1 and 2 first).
