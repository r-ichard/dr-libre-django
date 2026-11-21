# Review: task 06, scheduling engine (pure)

Diff: `git diff main...HEAD`, 12 files, all under `scheduling/domain/` plus the plan. Proof commits (`verify_green`..`prove`) touch tests only: clean. No product line changed after `green` except the `refactor` stage. Gate, lint, tests pass (856).

## Findings

1. **Blocker.** `Makefile:28-29`, `pyproject.toml`: `make mutate` still prints `not configured` and exits 1. No mutation tool is added or pinned (item 6, §11), no score is recorded, no runtime stated. "Done when ... `make mutate` runs and reports" is unmet, as is the 80 percent target. Fix: add a pinned dev dependency (e.g. mutmut), scope it to `scheduling/domain/`, bind the target, run it, record the score in the plan.
2. Important, later. `free_slots.py:62-77`: the 31-day cap lives only in `slot_search.py`; `free_slots` itself accepts any window. Fine as the single-clinician query is the use case's concern; task 07 must apply the cap there too.
3. Later. `booking_rules.py:57-61`: `raise ValueError` for missing `new_start`/`current_start` is an invariant break, acceptable under §9, but a typed attempt per action would make the state unrepresentable.
4. Later. `free_slots.py:105-111`: skipped local time is dropped, repeated time uses fold=0 (first occurrence only). Confirm the plan states this; tests exist in `test_free_slots_daylight_saving.py`.
5. Later. `free_slots.py:37-41`: `BusyInterval` and `TimeRange` are structurally identical; merge when a third caller shows.
6. Later. `first_available.py:20-29`: tie handling for equal idle products depends on float math; use integer seconds times weight if timestamps can have microseconds.
7. Later. Domain modules import `scheduling.models.*` enums (`free_slots.py:9`, `booking_rules.py:9-10`, `appointment_status.py:3-4`). Enums only, no ORM use, but it ties the pure layer to Django model imports; consider moving enums to the domain.
8. Later. Property-based tests (item 7) not present; welcome, not required.

No security or authorization surface in this diff (no views, models, migrations). No `Any`, `cast` or bare suppressions seen; gate clean. No double-booking write path yet (task 07); half-open intervals are correct at `free_slots.py:67`, buffer uses the booked type's buffer at `:60`.

## Blocking

- `make mutate` not bound to a pinned mutation tool, no score, no runtime (item 6, done-when).
  **Outcome: fixed.** `mutmut==3.8.1` pinned in `pyproject.toml` and `uv.lock`, `[tool.mutmut]` scoped to
  `scheduling/domain/`, `make mutate` runs `mutmut run` then `mutmut results`, foreground, about 17 s.
  Score on task modules (free_slots, booking_rules, slot_search, first_available,
  appointment_status): 207 of 215 mutants killed, 96 percent. No new test: the finding is tooling, the
  proof is that `make mutate` runs and reports.

## Later

- Findings 2 to 8.

## Re-review after address

Re-ran `make mutate` on the host: foreground, 16.7 s, reports survivors. Task modules: 8 survivors and
1 timeout (`free_slots._rule_starts_22`) among 215, consistent with the recorded 96 percent. `Makefile:28-30`,
`pyproject.toml` (`mutmut==3.8.1` pinned, `[tool.mutmut]` scoped to `scheduling/domain/`) confirmed. The address
and prove commits change tests, config and docs only; no product line moved after `refactor`.

Later (new):

- `make mutate` also mutates earlier domain modules (`failure`, `audit_metadata`, `request_context`) whose
  survivors are not in this task's scope; give them a hardening task or narrow `source_paths`.
- Survivors left in task modules: `first_available._rank_key` 3 and 6, `booking_rules.violated_rules` 6 and 12,
  `free_slots._local_days` 10, `_to_utc_if_it_exists` 5 and 8. Triage as equivalent or add a test.

Verdict: approve.
