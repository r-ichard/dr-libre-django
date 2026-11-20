Stage: PROVE THE TESTS GUARD (§10.1, §10.2). A passing test is not evidence.

1. For every test touched in this run, deliberately break the implementation it covers
   (flip a condition, return a wrong value), run `make test`, and
   confirm it goes red for the right reason. Then restore the code exactly. A test that
   stayed green is vacuous: sharpen it until it catches the break.
2. Hunt tests derived from the implementation: green by construction, mirroring the
   code. Restate the expected behaviour in words, then assert that.
3. If `make mutate` is bound, run it scoped to the pure modules you
   touched. Each survivor is a real gap (sharpen the test) or an equivalent mutant
   (mark it ignored). Target 80 percent or more on pure modules. Never mutate glue:
   I/O, database, network, time, randomness.
4. Leave the implementation exactly as GREEN left it, then run
   `make test` once more and confirm green.

Reply with a table: test, what you broke, observed result, action taken.
