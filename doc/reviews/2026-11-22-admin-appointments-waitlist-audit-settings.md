# Review: task 20, admin appointments, waitlist, audit log, settings

Diff `main...HEAD`, 55 files. Proof stage (`verify_green`..`prove`) touched tests only (checked with `git diff --stat 92c7f29 1bde7d3`): no mutation left behind. Gates reported green in `check`.

## Confirmed at a glance
- Every new page view sets `allowed_roles = {ADMIN}`; the audit and settings pages accept GET only, the reminder route POST only (`admin_audit.py:30`, `admin_settings.py:20,36`).
- Filters are parsed by `admin_filters.py` and fall back to "no filter"; the actor is never read from a payload.
- Status changes, cancel and reminder run through existing use cases, which audit inside their transaction (`reminders.py:35`).
- Audit page cut from a key walk, fetched whole (`admin_audit.py` use case), with three new indexes (migration 0015).
- `delete_user` now deletes dependents inside the nested atomic, so a refused final delete rolls them back (`admin_users.py:173-180`).
- Seed clean-up touches only `demo-<code>` of the five seed codes and moves clinicians first (`writer.py:166-175`).
- Waitlist offer checks clinician, patient and room via `find_conflicts`, and walks candidates soonest first with a cap (`waitlist.py:190-215`).

## Findings
- **Low**, `scheduling/views/pages/admin_audit.py:21-25`: the entity-type filter is a hand-kept list; `SignInLink` (`sign_in_link.py:29`) is audited but missing, so its entries cannot be filtered. Fix: add it, or derive the list from a shared constant plus a test that every `AuditEvent` entity type is listed.
- **Low**, `scheduling/use_cases/waitlist.py:186-215`: `MAX_SLOTS_CHECKED = 100` means a type with 100 or more unusable earlier cancelled slots hides a later usable one and the admin sees a conflict refusal. Fix: raise the cap or filter busy slots in SQL; note the limit in the refusal.
- **Low**, `scheduling/views/pages/admin_audit.py:79`: `csrf_exempt` on the audit route is deliberate and safe because the view only reads; keep the 405 test as its guard.
- **Nit**, `scheduling/use_cases/admin_clinicians.py:172`: `reference_messages` opens a transaction with `select_for_update` for a read-only validation; a lock is held for the length of the form check. Fix: drop the lock for this path.

## Blocking
None.

## Later
- Add `SignInLink` to the audit entity filter, with a test that ties the list to the audited types.
- Revisit `MAX_SLOTS_CHECKED` for the manual offer.
- Drop the row lock in `reference_messages`.
- Not run by this reviewer: the suite, `make mutate`, browser layout (no browser in the sandbox).
