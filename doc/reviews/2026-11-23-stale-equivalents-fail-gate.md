# Review: a stale mutation-equivalents entry fails the gate (task 26c item 19)

Reviewer: second reader, stage review. Reviewed `git diff main...HEAD` (12 commits, 4 files, +108 / -2). Plan: `doc/plans/2026-11-23-stale-equivalents-fail-gate.md`.

## Changed blocks, one-sentence plans

- `scripts/mutation_survivors.py:27` `main()` return: exits 1 when there is an unlisted survivor or a stale entry. Confirmed at a glance; one expression, the other branches are unchanged.
- `scripts/test_mutation_survivors.py:45-61` `returns_exit_one_when_a_listed_mutant_no_longer_survives`: feeds a results file and an equivalents file from `tmp_path`, asserts exit 1 and the stale line on stdout. Confirmed at a glance; the monkeypatch targets are the module globals `main()` reads at call time, so the patch takes effect.
- `scripts/test_mutation_survivors.py:64-73` `returns_exit_one_when_a_survivor_has_no_listed_reason`: an unlisted survivor with an empty equivalents file exits 1. Read at a glance; it does what it says, but the name does not (see Later).
- `mutation-equivalents.txt`: deletes the single line for `scheduling.domain.waitlist_window.x_window_words__mutmut_11`. Confirmed at a glance: the diff is one `-` line, nothing else in the file.
- `doc/plans/2026-11-23-stale-equivalents-fail-gate.md`: plan artifact, no code.

Nothing needed tracing beyond `check_survivors` (`scripts/mutation_survivors.py:39-47`), which I read to confirm that "stale" means "listed but not reported as `: survived`".

## Findings

### 1. Stale is "not reported as survived", not "killed" (Later)
- `scripts/mutation_survivors.py:46` `stale=[name for name in equivalents if name not in survivors]`.
- Risk: a listed mutant whose mutmut status is `timeout`, `no tests` or `suspicious` is now stale and fails `make mutate`. Before this change it passed silently. This is fail-closed and matches the plan's intent for killed mutants, but the other statuses were not decided by anyone.
- Smallest fix: none in this run. Decide the semantics in a later task if `make mutate` shows a false failure.

### 2. `make mutate` was not run by any stage (Later; orchestrator gate)
- The plan's verification says "Mutate: `make mutate` exits 0 and prints no stale or unlisted line" and the plan requires the green stage to confirm `x_window_words__mutmut_11` is not `survived`. No `mutants/` directory exists in the sandbox and no stage output shows `make mutate`.
- The removal of the equivalents line is therefore unverified against the real mutation run. The unit test proves the gate logic only.
- Smallest fix: the orchestrator runs `make mutate` on the verify clone before the squash (CLAUDE.md: last scripted gate). If it prints a stale line for another entry, that is a new finding, not part of this run (per plan).

### 3. Misnamed test (Later, nit)
- `scripts/test_mutation_survivors.py:64` `returns_exit_one_when_a_survivor_has_no_listed_reason`: the body has an unlisted survivor (mutmut_3 has no equivalents line). It does not test a listed entry with no reason; that case is already covered by `raises_system_exit_when_an_equivalent_entry_has_no_reason`.
- Smallest fix: rename to `returns_exit_one_when_a_survivor_has_no_equivalent_entry`.

### 4. Second new test is outside the plan (Later)
- The plan promises one new test. The diff adds two: `scripts/test_mutation_survivors.py:64-73`. The second one covers the unlisted-survivor exit path, which is existing behaviour and is correct to test, but it is not what the task asked for.
- Smallest fix: keep it (it guards the unchanged branch of the same expression) or drop it to match the one-test plan. Orchestrator's call.

### 5. Plan line references are off by one (Later, nit)
- `doc/plans/2026-11-23-stale-equivalents-fail-gate.md` (Blocks section) says the return is line 26; it is line 27. The architect's correction note in the same plan already says so. Artifact only.

## Checks

1. Plan per block: stated above.
2. Correctness and errors: the new branch only ORs an existing list with another. No exception is swallowed; `parse_equivalents` still raises `SystemExit` on a missing reason, unchanged. Edge: an empty equivalents file with no results survivors exits 0 (unchanged, covered by existing tests).
3. Authorization, boundaries, sensitive data: no request, user input, auth, or audit path. Local files only. Nothing logged beyond the existing stdout lines.
4. Double booking: not applicable.
5. Tests: the red test asserts the exit code and the message text, derived from the required behaviour (stale fails the gate), not from the implementation. Red was proven: `verify_red` shows `assert 0 == 1`. The assertion on printed output would catch a change of message; that is acceptable.
6. Names and comments: `main`, `check_survivors`, `stale`, `unlisted` are the existing roles. No comments added. Test-name issue in Finding 3.
7. Proof left no trace: commits `a20f3e4` (red) and `3f2d1a1` (prove) touch only `scripts/test_mutation_survivors.py`. `b45bb08` (verify_green) has no file changes. `f901012` (refactor) and `1364732` (check) have no file changes. `git diff 3f2d1a1 HEAD --stat` is empty. `1786a08` (green) carries the product line and the equivalents deletion, which is its allowed stage. The prove commit only added the `capsys` assertion; that is a test change. No product or migration line changed after verify_green. The branch is clean on this rule.
8. Scope and dependencies: no dependency, no lock change, no spec change (`drlibre-specs.md` untouched), no `scheduling/` product code, no Makefile change, no contract across layers. The only unrequested item is the second test (Finding 4).

Hard rules: no `Any`, `cast`, bare `# type: ignore` or `# noqa` in the diff (the new `pytest.CaptureFixture[str]` annotation is typed). No function over 100 lines, no file over 500. No swallowed error. No write path, so no audit requirement.

Measured in the sandbox (not a budget for this task; recorded for the orchestrator): `verify_red` suite 215.57 s, `verify_green` 350.51 s, `check` 426.54 s, all with 5244-5245 tests. The machine is shared, so these are not meaningful timings.

Gate status from the run: `make test` (verify_green) passed with 5244 tests; `check` passed `make lint && make test && make gate` with 5245 tests. The `red` failure before green was the expected one.

## Blocking

(none)

## Later

1. `scripts/mutation_survivors.py:46`: stale semantics treat `timeout`, `no tests`, `suspicious` as stale. Decide in a later task if it produces a false failure. (Finding 1)
2. `make mutate` not run in any stage; orchestrator runs it on the verify clone before squash. (Finding 2)
3. `scripts/test_mutation_survivors.py:64`: rename `returns_exit_one_when_a_survivor_has_no_listed_reason` to match what it tests. (Finding 3)
4. `scripts/test_mutation_survivors.py:64-73`: second new test is beyond the one-test plan; keep or drop. (Finding 4)
5. `doc/plans/2026-11-23-stale-equivalents-fail-gate.md`: return line is 27, plan says 26. (Finding 5)
6. Squash message: the run commits carry "Generated with Fabro" and `Fabro-Run` trailers; the squash to `main` needs a hand-written message that discloses tooling (CLAUDE.md hand-applied gap 1).

## Left for the orchestrator

Not in this run (plan, "Not in this run"):
- Other stale entries if `make mutate` shows any (report, do not fix).
- `make fhir-validate` and `make audit` (other items of 26c).

Not finished in this run: none of item 19's planned checks is missing from the diff. The mutate verification (Later 2) is the one step the orchestrator must run.
