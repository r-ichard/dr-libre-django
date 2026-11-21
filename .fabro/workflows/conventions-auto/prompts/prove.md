Stage: PROVE THE TESTS GUARD (§10.1, §10.2). A passing test is not evidence.

Every command runs in the foreground and has finished before you reply. Nothing you
start may outlive this stage: a process left behind keeps changing files and running
tests under the stages that follow. If the work is long, split it into foreground
commands that each end within their timeout, and run the narrowest tests that can catch
each break instead of the whole suite.

1. For every test touched in this run, deliberately break the implementation it covers
   (flip a condition, return a wrong value), run `make test`, and
   confirm it goes red for the right reason. Then restore the code exactly. A test that
   stayed green is vacuous: sharpen it until it catches the break. When there are more
   tests than the stage has time for, break at least one of each kind and one in each
   file, cover every rule that protects data, and say which tests you did not break.
2. Hunt tests derived from the implementation: green by construction, mirroring the
   code. Restate the expected behaviour in words, then assert that.
3. If `make mutate` is bound, run it scoped to the pure modules you
   touched. Each survivor is a real gap (sharpen the test) or an equivalent mutant
   (mark it ignored). Target 80 percent or more on pure modules. Never mutate glue:
   I/O, database, network, time, randomness.
4. Leave the implementation exactly as GREEN left it. Show it: `git status --short` and
   `git diff --stat` must list test files and test helpers only. Then run
   `make test` once more and confirm green.

Reply with a table: test, what you broke, observed result, action taken. Then the output
of the two git commands of step 4.
