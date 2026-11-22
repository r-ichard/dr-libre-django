# Review: task 18, admin console records

Diff `main...HEAD`, 34 files. Commits after `verify_green` up to `prove` touch only
`test_record_fields.py` and `test_admin_records_pages.py`: no mutation left behind.

## Plan in one sentence per block
- `use_cases/admin_records.py`: one lock, version check, validate, save, audit per write; delete counts dependents (pure `delete_refusal`) and re-checks on `ProtectedError`. Confirmed at a glance. Traced: delete race path, room-move check.
- `views/pages/admin_records.py`: one page class per step, kind from the route, thin formatting. Confirmed.
- Migration 0013 and `Lower("code")` constraints: case-insensitive code uniqueness. Confirmed.
- `free_slots_query._lacks_room`: no active room means no offer for a room-needing type. Confirmed.

## Findings
- **Low**, `use_cases/admin_record_reads.py:53`: `list_records` loads every row, then slices in Python. Risk: slow on large lists. Fix: count and slice in the database.
- **Low**, `use_cases/admin_records.py:68-83`: delete locks the record but not its dependents; the race is covered by the `ProtectedError`/`IntegrityError` re-check, and the bare `raise` there re-raises only when no dependent is found, so nothing is swallowed. Fine; a test of the race would pin it.
- **Low**, `views/pages/admin_records.py:34`: the stale-save text says "Saving again replaces theirs", and the 409 form carries the fresh version. This meets "not silently". No diff of the two versions is shown.
- **Low**, `use_cases/admin_records.py:150`: `_room_move_messages` is read before the row is mutated, so it sees the old department. Correct, but it relies on call order; a comment would help.
- **Info**, timing: `make test` took 38 s here (2778 tests) and 41 s in the `check` stage. `main` alone (2482 tests) took 43 s in the same sandbox, so the goal's 30 s is not met, and it was not met before this branch either. Machine noise is large. Not attributable to this diff.
- Authorization: the admin comes from the session (`allowed_roles`, `_is_admin` in every use case). Nothing is read from the payload. No type escape hatches seen. Audit is inside the transaction in create, update and delete. An edit that changes nothing writes nothing.
- Not run by me beyond `make test`: `make mutate`, and a browser check.

## Blocking
None.

## Later
- Paginate in the database (`admin_record_reads.py:53`).
- Test the delete race, with a dependent inserted between the count and the delete.
- Bring `make test` under 30 s (parallelism or fixtures); it is a pre-existing miss.
