# Review: task 26b2, limits on public reads

Diff `main...HEAD`, 26 files. Gates (lint, test, gate) passed in the `check` stage. Specification untouched. The `prove` commit changed only `test_read_limits.py`: clean.

## Findings

1. **Blocker, item 6 missing.** `README.md` is not in the diff, and `grep` finds no "Running with DEBUG off" or `TRUSTED_PROXY_COUNT` in it. The plan (block 9, "README content") promised it. Smallest fix: add the section as the plan words it.
   **Outcome: fixed.** Section "Running with DEBUG off" added to `README.md`; read against `settings.py`, `startup_checks.py`, `environment.py`.
2. **Blocker, item 3 missing.** `scheduling/views/test_public_route_limits.py` does not exist. The plan names it, and the task requires one test that walks the URL configuration and fails on an unlimited route without a reason entry. Existing `get_resolver` walkers (`test_api_bodyless_writes.py:41`, `test_hostile_input.py`) show the pattern. Smallest fix: write the walker with `COSTS_NOTHING` and `OWN_LIMIT` lists that carry reasons and a stale-entry check, and prove it can fail by dropping one limit.
   **Outcome: fixed.** `returns_a_limit_or_a_reason_for_every_route_that_answers_without_a_session_or_token` and `returns_no_stale_entry_when_every_listed_route_is_in_the_url_configuration`. Red proof: removing `api_read_refusal` from `ProviderDetailView.get` made the first name `api/v1/providers/<uuid:provider_id>`.
3. **Important, hook coverage is by hand.** `PageView.read_scope` (`page_view.py:57`, `:80`) and `api_read_refusal` calls (`public_details.py:28`, `slots.py:30`) must each be remembered per view. Finding 2 is the guard for that; without it a new public route ships unlimited.
4. **Later, `api_read_refusal` runs before parameter validation** (`slots.py:30`), so a malformed query costs a hit. This is safe, because it errs toward limiting.
5. **Later, `RateLimitHit` growth.** Each read writes one row, up to 1200 an hour per key. The plan declares no cleanup. Check the table's growth.
6. **Confirmed at a glance.** `counter_key` (`read_limits.py:11`) takes the user from the session or token, never from a payload. The FHIR hook sits after the `metadata` early return, so metadata stays free (`fhir/views.py:91`). The negative count is refused in `environment.py:34`, naming the variable. `DEMO_PASSWORD` now goes through `optional_env`. The log privacy test plants a password and signs in by it (`test_log_privacy.py`).
7. **Later, `/fhir` limit for token holders.** A valid token is counted per user at 600 an hour on the fhir scope. This is the open question for the owner below.

## Blocking

None. Findings 1 and 2 were re-read at HEAD: `README.md:69` section matches `settings.py` and `environment.py:26`; `test_public_route_limits.py` exists, each `COSTS_NOTHING` and `OWN_LIMIT` entry carries a reason, and a stale-entry test guards the lists. Commits after `verify_green` up to `prove` touched `test_read_limits.py` only.

## Later

- Plan blocks 4 to 6 named a DRF throttle and a `before_get` mixin; the code uses `api_read_refusal` and `PageView.read_scope` instead. Simpler, same behaviour; the plan text is stale.
- Finding 3 (becomes a lesser risk once the walker exists), finding 4, finding 5.
- Time measured: `make test` took 137 to 151 s in this sandbox, which shares its machine. Not a blocker; measure it on a quiet machine.

## For the owner

- Signed-in callers are limited per user id (1200 schedule, 600 fhir, 120 search) rather than not at all. Say if staff integrations need more.

## Left for the orchestrator

- Plan "Not in this run": the behavioural proof of `OWN_LIMIT` entries (relies on their own tests), and cleanup of old `RateLimitHit` rows.
- Items of the slice the run did not finish: none.
