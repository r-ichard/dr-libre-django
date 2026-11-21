# Review: task 06a, domain hardening

Diff `main...HEAD`, 41 files. Re-ran on host: `makemigrations --check` (no changes, no migration file in diff), `make mutate` (5 survivors, all listed, exit 0).

## Process trace
- `prove` (defefd3) changed tests and `mutation-equivalents.txt` only. `refactor` changed nothing. No product line changed after `verify_green`.

## Findings
1. Info, `scheduling/models/base.py:85`: `choices_of` rebuilds TextChoices labels by hand. Risk: a label rule drift would create a migration; guarded by the existing migrations test. Fix: none.
2. Low, `scheduling/domain/test_domain_imports.py:24`: globs only top-level `*.py`; a future domain subpackage escapes the guard. Fix: `rglob`.
3. Low, `scripts/mutation_survivors.py:28`: stale equivalents entries are printed but do not fail. Risk: list rots. Fix: decide whether stale should exit non-zero.
4. Low, `scheduling/domain/free_slots.py:99`: repeated local times on fall-back use first occurrence; real end can fall short of the rule end (stated in plan item 5, tested). Fix: none.
5. Info, `pyproject.toml:21`: `hypothesis==6.170.17` pinned exactly, `uv.lock` updated. Correct package.

Confirmed at a glance: vocabulary move, UUID typing, integer-microsecond ranking. Traced: the real-end check in `_rule_starts`.

## Blocking
None.

## Later
- Guard recursion into subpackages (finding 2).
- Decide on failing stale mutation-equivalents entries (finding 3).
