# Review: smoke search window past the cancel window, and refusal detail in step failures

Reviewer: second reader, diff `42a9ea7..HEAD` (the run's base; this sandbox has no local `main` branch, so `git diff main...HEAD` fails; `6710745^` is `42a9ea7`, the last commit before the run's `start` commit). Run `01M849QWFC0XF277SZ9N3ZZP1C`. Plan: `doc/plans/2026-11-23-smoke-cancel-window-and-refusal-detail.md`.

Diff stat: `scripts/smoke.py` (+27/-4), `scripts/test_smoke_window_and_detail.py` (new, 97 lines), `doc/plans/2026-11-23-smoke-cancel-window-and-refusal-detail.md` (new). No server, migration, dependency, spec, or Makefile change.

I did not re-run the suite. The recorded `verify_red`, `verify_green` and `check` stages are the evidence for that. I did run one check myself (Stage 5).

## Stage 1: plan per changed block, in one sentence

- `scripts/smoke.py:22-23` constant `SEARCH_LEAD_HOURS = 25`, with a comment naming the 24 hour cancel window (drlibre-specs.md 5.3). Confirmed at a glance. Name differs from the plan (`SLOT_SEARCH_START_HOURS`); see Later.
- `scripts/smoke.py:164-170` `_first_free_start`: "the window starts at now plus 25 hours and spans `SEARCH_DAYS`." Confirmed at a glance. Traced the `_instant` format (`%Y-%m-%dT%H:%M:%SZ`, `smoke.py:160-161`) against `INSTANT_FORMAT` in the test: they match, and the value is UTC-aware.
- `scripts/smoke.py:94-111` `_refusal_detail`: "the code, then the string rule names, or nothing when the body is not a usable error." Traced: each level is type-checked before use, and only `code` and rule names are returned.
- `scripts/smoke.py:114-117` `_expect_status`: "on a status mismatch, append the refusal detail to the existing message." Confirmed at a glance.
- `scripts/test_smoke_window_and_detail.py:18-29` window test: "starts 25 hours from now, read around the call." Traced the tolerance: `before` is read before the call, `after` after it, and the instants are cut to whole seconds, so `before+25h-1s <= from <= after+25h` is a correct bound and not flaky.
- `scripts/test_smoke_window_and_detail.py:32-97`: refusal tests (code and rules, code without rules, mixed rule types, four unusable-body cases). Read, did not need to trace.

Traced, because it matters: the server side of the rules. `drlibre-specs.md:202` confirms `cancellation_window_closed` applies when the start is 24 hours or more away. `scheduling/domain/booking_rules.py:24` holds the rule name. `scheduling/views/failure_response.py:74` builds `{"error": {...}}`. The test body shape matches.

## Stage 2: correctness and error handling

- `scripts/smoke.py:97-98`: `json.loads` is caught on `JSONDecodeError` only. Good enough: `json.loads` on a `str` raises only that for bad input. A `RecursionError` on pathologically nested JSON would escape. Not reachable from a local stack's answer in practice; see Later.
- `scripts/smoke.py:100-102`: `isinstance` narrowing covers non-object top level, non-object `error`, and non-string `code`. Returns `""`, so the message falls back to the status-only text. No swallowed error: the status mismatch still raises `SmokeFailure` on the same line.
- `scripts/smoke.py:108`: non-string rule items are dropped, as the plan says. Empty strings are not dropped (see Later).
- `_refusal_detail` is called only inside the mismatch branch (`smoke.py:115-116`), so successful steps print exactly what they printed before.

No finding that blocks.

## Stage 3: authorization, boundaries, sensitive data

- Trust boundary: the refusal body is a stack answer. It is parsed as `object`, not `Any`, and checked level by level (`smoke.py:97-111`). No exception path from a malformed body (the four unusable-body tests cover it).
- Only `code` and rule names reach stderr via `run_steps` (`smoke.py:68`). These are the server's fixed vocabulary (`booking_rules.py:24`). No `message`, `correlation_id`, booking code, email or name is printed. The plan's sensitive-data claim holds.
- No authorization, route, serializer, or audit path touched. The smoke test reads and books through the public API as before.

No finding.

## Stage 4: double booking

Not touched. No write path or conflict check changed. The window change is client-side only: the server's lead time (120 minutes), horizon, and cancel window are unchanged. 25 hours clears all three.

## Stage 5: tests

- Red was recorded. `verify_red` (commit `0ff6217`) shows the window test and the two cancel-refusal tests failing for the stated reason. The guard tests pass on the old code, as the plan says.
- Guard proof, run by me on a copy in `/tmp` (no workspace file edited): with `_refusal_detail`'s `try/except` removed, `returns_status_only_message_when_refusal_body_has_no_usable_error[not_json]` fails with the raw `JSONDecodeError`. On the clean copy, all 8 tests pass. So the guard can fail, as the plan claimed. The plan asked that this be run in the red stage; it was not recorded there. Noted in Later, not a blocker: the proof now exists.
- **Dropped assertion.** The plan promised `to` is exactly 14 days after `from` inside the window test. The `refactor` commit (`9da3a4e`) removed `ends` and the `ends - starts == timedelta(days=SEARCH_DAYS)` line from `scripts/test_smoke_window_and_detail.py` (was after line 28). The span is still asserted by the existing `scripts/test_smoke.py:312-321` (`returns_utc_search_window_of_search_days_when_holding`), which is unchanged and green. So the behaviour is still guarded, and this is not a missing test. I am not treating it as a blocker. Restoring the two lines is cheap. See Later.
- The mixed-type rule test (`scripts/test_smoke_window_and_detail.py:62-79`) was added in `prove` (`b9472b2`), after `verify_green`. It was not red-proven. On the old code it would fail (no suffix at all), so it is a real test, not a pass-forever one. Accepted.
- Test names follow `returns_X_when_Y` / `raises_X_when_Y`. Assertions carry concrete values (`"cancel answered 422, wanted 200: rule_violation; violated rules: cancellation_window_closed"`), not `is not None`.
- Expected values come from the stated message format in the brief and plan, not from reading the implementation back. That is the right source for these.

## Stage 6: names and comments

- `scripts/smoke.py:22` comment is a why (the cancel window), under 255 characters. Good.
- `scripts/smoke.py:94-95` docstring: states what is returned and when it is empty. Good.
- Names state roles: `_refusal_detail`, `named_rules`, `wanted_status`. No `temp` or `data2`.
- `SEARCH_LEAD_HOURS` (`smoke.py:23`) reads as a lead time, which is what it is. The plan's name `SLOT_SEARCH_START_HOURS` is not used; the plan doc is out of step with the code.

No blocking finding.

## Stage 7: proof trace

`git show --stat` per commit, after `verify_green` (`98869dc`):

- `b9472b2` prove: `scripts/test_smoke_window_and_detail.py` only (+20). Tests only.
- `9da3a4e` refactor: `scripts/test_smoke_window_and_detail.py` only (-3, +1). Tests only.
- `58978cd` check: no file.

Before `verify_green`: `6ca8f3c` red (test file only), `3ffd816` green (`scripts/smoke.py` only), `0ff6217` verify_red and `98869dc` verify_green (no file). No product line changed after `verify_green`. No mutation left behind.

## Stage 8: scope and contract

- Scope matches the plan's slice. Two changes, nothing bundled. `scripts/test_smoke.py` is untouched and stays at 500 lines (`wc -l`), at the cap, so leaving it alone was required.
- No dependency added. Imports are stdlib (`json`, `datetime`) plus existing modules.
- Contract: the smoke script's `SmokeFailure` text changed for status mismatches only. Existing tests in `scripts/test_smoke.py` match by `re.search` on prefixes, so the suffix does not break them (verify_green shows them passing).
- `drlibre-specs.md` unchanged (`git diff` empty on the file). No decision it leaves open needs an ADR.
- `doc/backlog`, `README.md`, `doc/handover.md`: untouched, as the plan says.

## Blocking

None.

## Later

1. `scripts/test_smoke_window_and_detail.py:18-29`: the window test no longer asserts that `to` is 14 days after `from` (dropped in `9da3a4e`). The property is still asserted at `scripts/test_smoke.py:312-321`. Restore the two lines if you want the test to say what its name and plan promise. Risk: low, behaviour still guarded.
2. `scripts/smoke.py:23`: the constant is `SEARCH_LEAD_HOURS`; the plan says `SLOT_SEARCH_START_HOURS`, and the plan's line references (`smoke.py` 66-68, 91-101) are stale. Fix the plan text or accept the code name. Nit.
3. `scripts/smoke.py:108-110`: an empty-string rule name passes the filter and prints `violated rules: ` with nothing after it. The plan says string items are non-empty; the code does not filter them. Fix: `if isinstance(rule, str) and rule`. Nit.
4. `scripts/smoke.py:96-99`: `json.loads` raising `RecursionError` on deeply nested input is not caught. Not reachable from a local stack in practice. Leave, or catch `ValueError` (which covers `JSONDecodeError`) and note it. Nit.
5. Scope question for the orchestrator (the plan's open choice, unchanged): the brief says "when a step fails, its message names the status". The code adds the status only to status-answer failures (`_expect_status`). Content failures such as `health reports 'down'` and `no free slot in the next 14 days` (`smoke.py:148`, `175`) still do not name a status, because their status was 200. Read literally, the brief covers them. Decide whether to widen it; it is a separate small change and would move existing match strings.
6. Guard proof (plan's required red-stage record) was not recorded in `verify_red`. Reviewer re-ran it on a copy (see Stage 5); the guard fails as described. Record it in the run log if the process needs it.
7. Measured here: none. `make test` was not re-run in this stage; the recorded `verify_green` run took 264 seconds on a shared sandbox, which proves nothing about budget.
8. Squash: the run commits carry the Fabro byline and `Fabro-Run` trailers (known gap). The squash to `main` needs a hand-written message that discloses tooling and names the issue it addresses, with no `Co-Authored-By`.

## Left for the orchestrator

- The plan's `## Not in this run` section says "Nothing". No item of the slice was left unfinished: both changes are in `scripts/smoke.py`, and the red tests exist and pass.
- Orchestrator to measure on a quiet machine: `make smoke` against a fresh seeded stack (the plan's done check; this stage had no Docker). That run decides whether the window of 25 hours yields a slot in the seed, and whether the cancel now returns 200.
