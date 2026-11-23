# Task 26c item 19: a stale mutation-equivalents entry fails the gate

Slice: item 19 only. Gate change, its test, and removal of one stale line in `mutation-equivalents.txt`.

Focal point: `scripts/mutation_survivors.py` `main()` (line 19-27). It prints `stale entry in mutation-equivalents.txt: <name>` for every stale entry but returns `1 if report.unlisted else 0`, so a stale entry exits 0.

## Blocks

- `scripts/mutation_survivors.py:main`, return line (line 26): fail when `report.stale` or `report.unlisted` is non-empty. One expression, no new function.
- `scripts/test_mutation_survivors.py`: one new test, `returns_exit_one_when_a_listed_mutant_no_longer_survives`. It calls `main()` with `sys.argv` pointing at a results file in `tmp_path` and `EQUIVALENTS_FILE` monkeypatched to a file in `tmp_path` that lists a mutant the results do not show as surviving. Expected: return value 1. Today it returns 0, so the test is red first.
- `mutation-equivalents.txt`: delete the one line `scheduling.domain.waitlist_window.x_window_words__mutmut_11: ...`. Nothing else in the file changes.

## Files to touch, in order

1. `scripts/test_mutation_survivors.py` (red test first)
2. `scripts/mutation_survivors.py` (one line)
3. `mutation-equivalents.txt` (delete one line)

Not touched: `Makefile`, `scripts/final_gates.sh`, `pyproject.toml`, `drlibre-specs.md`, any `scheduling/` product code, the other entries of `mutation-equivalents.txt`, `doc/backlog/26c-gates-that-hold.md` (orchestrator updates the backlog).

## Invariants and blast radius

- The gate must not pass with a stale claim. Stale failing is the intended change; `make mutate` fails until the line is removed, which this change does.
- Unlisted-survivor behaviour is unchanged: still exit 1.
- Blast radius: `make mutate` and `scripts/final_gates.sh` (both call the script). No product path.
- Removing a line from the equivalents file is safe only if the mutant is killed. The green stage must confirm `x_window_words__mutmut_11` is not `survived` in `mutants/results.txt` after `make mutate`.
- If `make mutate` then reports another stale or unlisted entry, do not remove it here. Report it in the run's final message as a new finding.

## Trust boundaries, entities

- Trust boundaries: none. Developer tooling reads local files only. No request, user input, auth or audit.
- Domain entities: none. Mutation testing tooling.

## Failing test (write first)

- `returns_exit_one_when_a_listed_mutant_no_longer_survives`: given a listed equivalent that the results do not show as surviving, `main()` returns 1. Expected value stated in words: a stale entry fails the gate, so the exit code is one.

The existing `returns_stale_entries_when_a_listed_mutant_no_longer_survives` tests the report only and stays as is.

## What I will not do

- No refactor of `check_survivors` or `SurvivorReport`.
- No new CLI flag, no `--strict` option, no change to the message text.
- No removal of other entries, even if they look stale.
- No change to `mutmut` config or `make mutate` steps.

## Verification in the run

- Red: the new test fails with `assert 0 == 1`.
- Green: the test passes; `make lint`, `make test`, `make gate` pass.
- Mutate: `make mutate` exits 0 and prints no stale or unlisted line.

## Not in this run

- Other stale entries if `make mutate` shows any (report, do not fix).
- `make fhir-validate` and `make audit` (other items of 26c).

## Architect review

Verdict: approve.

1. Ladder: the change is one return expression in `main()`, one red test, and one deleted line. No abstraction, dependency or refactor. Right layer: developer tooling script, the file that already reports stale entries.
2. Plan knowledge: each block states its purpose in one sentence. Vocabulary is the tooling's own (stale, unlisted, survivor); no CLAUDE.md domain entity is involved, and the plan says so.
3. Test-first: the red test is named as a behaviour (`returns_exit_one_when_a_listed_mutant_no_longer_survives`) and states its expected value (1, with `assert 0 == 1` as the red output). It follows the `returns_X_when_Y` rule. Existing report-level test stays. Edge paths (unlisted survivors still exit 1, clean run exits 0) are not written as new tests. Acceptable for a one-line gate change, but the green stage should keep the existing exit-0 behaviour observable; see risk below.
4. Security: no trust boundary. Local files only. Stated in the plan.
5. Architecture: not applicable beyond the script's own separation (`check_survivors` pure, `main` formats and returns). The plan keeps it that way.
6. Scope: whole of item 19. Callers checked: `Makefile:36` and `scripts/final_gates.sh` both call the script; the plan names both in blast radius. Nothing dropped.

Corrections for the green stage (not reasons to revise):
- `main()` starts at line 17, not 19. The return is line 27, not 26. Fix the references when editing.
- Risk: `check_survivors` treats every equivalents entry that is not `: survived` in results as stale. That includes `killed`, `timeout`, `no tests` and `suspicious`. The plan's definition ("a test now kills the mutant") is narrower than the code. The change therefore fails the gate for timeout or no-tests statuses too. That is fail-closed, so acceptable for this item, but the orchestrator should know it. A separate task may refine the status check if it causes a false failure.
- Verification: removing the line is safe only if `x_window_words__mutmut_11` is absent from `mutants/results.txt` as `survived`. Green stage must check this after `make mutate`, as the plan already requires.
