Stage: RED (§10). Write the failing test from the approved plan. Do not touch
implementation code.

- One behaviour per test, named as behaviour, Arrange-Act-Assert with Act on one line.
- Assert what it does, not which helper it called. No assertion that passes forever:
  non-null, mock-was-called, shape-without-value.
- Expected values come from the specification in the plan, never from running the code.
- If `make test` reports "not configured", the stack is not bound yet. Bind it now in
  the Makefile exactly as the plan says, with the smallest runner that works, and
  record the choice in CLAUDE.md under Stack binding.
- Run `make test`. Red must fail for the right reason: an assertion
  failure or the expected error. A compile or import error is a setup failure. Fix the
  setup, never the assertion.
- If the gate sent you back because the suite did not fail, your test is vacuous or
  mirrors existing behaviour. Restate the expected behaviour in words, then assert that.

Reply with the test file paths, the failing assertion text, and why it fails for the
right reason.
