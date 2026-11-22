# Review: task 19, admin console users and clinicians

Diff `main...HEAD`: 53 files. Supersedes the first pass, which read a partial diff (no pages yet). Commits `verify_green` to `prove` (`a6b26b8..6333964`) touch four test files only: no mutation left behind. `make gate` clean (comment cap, size cap, escape hatches); stage `check` reports lint and 3111 tests green. No type escape hatch found in the changed code.

## Plans in one sentence
- `admin_users.py`: lock actor, target and active admins in primary key order, check version, rules, save, audit in the same transaction. Confirmed at a glance.
- `admin_clinicians.py`: same for profiles; referenced department, specialty and room are locked while checked. Traced `_reference_messages` and `_move_messages`: correct for a department move with or without a room change.
- `admin_user_support.py`: lock order and clean values; `end_access` cancels links before ending sessions. Traced, sound.
- `admin_user_pages.py`, `admin_records.py`: thin pages over `WRITERS`; `sensitive_post_parameters("password")`; password never re-rendered (`kept_text`). Admin role gate on `RecordPage.allowed_roles`.
- `list_records`: count and slice in the database, page clamped, query count asserted.

## Findings
- **low**, `scheduling/use_cases/admin_users.py:157-162`: if the final `locked.target.delete()` is refused in the race branch, the function returns a `Failure` inside the outer `atomic`, which commits; the earlier deletes of sessions, sign-in links and notifications persist. Only reachable when a dependent appears after the first check; FK key-share locks against the row lock make that nearly impossible. Smallest fix: `transaction.set_rollback(True)` before returning, or run the three deletes after a successful target delete.
- **low**, `scheduling/demo_seed/writer.py:_drop_unused_legacy_specialties`: deletes any `demo-` specialty with no clinician, including one an admin made by hand, with no audit. Fix: restrict to the five legacy codes.
- **low**, `scheduling/demo_seed/writer.py:_adopt_legacy_specialty`: when `demo-x` and `x` both exist and the legacy row has clinicians, two sets stay. Fix: move the profiles to the new row before the drop.
- **low**, `scheduling/domain/user_rules.py:12`: `EMAIL_PATTERN` accepts `a@b`. Acceptable; tighten later.
- **low**, `scheduling/use_cases/admin_clinicians.py:update_profile`: does not lock the profile's user; a concurrent deactivation of that user is not blocked. Harmless: deactivation does not touch the profile.
- **ok**, audit metadata carries ids and changed field names only (`changed_field_names`); password is hashed in the use case; planted-password tests exist for audit, pages and log lines.
- **ok**, own-account and last-active-admin rules run under the lock; race test present (`test_admin_last_admin_race.py`); delete race test present (`test_admin_delete_race.py`).
- **ok**, changed email clears `email_verified_at`, ends sessions and cancels unused links; a passwordless patient is refused.
- **ok**, pixel items 21 and 22 are asserted only in the style sheet and template tests; the orchestrator measures in Chrome.

## Blocking
None.

## Later
- Roll back refused-delete side effects in `delete_user` (race branch).
- Tighten legacy seed cleanup to the five legacy codes and move profiles before the drop.
- Stricter email pattern.
