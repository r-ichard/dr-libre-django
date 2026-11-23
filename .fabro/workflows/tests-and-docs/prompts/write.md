Stage: WRITE. Read CLAUDE.md, then the approved plan (newest file in `doc/plans/`). This
task changes no behaviour of the product: it adds tests the code already passes, a
document, a gate, or a rewording of docstrings and comments.

- A test states what the product promises, from the specification in the plan, never
  from running the code. One behaviour per test, named `returns_X_when_Y`.
- A test that passes at once can still be vacuous: the next stage breaks the code on
  purpose and the test must fail. Write it so that it would.
- If a test fails because the product is wrong, stop: do not change product code. Write
  the failure under `## Left for the orchestrator` in `doc/plans/` and leave the test
  marked with `pytest.mark.xfail(strict=True, reason=...)` naming it.
- Product code may change only where the task names it (a docstring, a module moved
  out of the product package). No behaviour changes.
- `drlibre-specs.md` is the owner's text: never edit it.

Run `make lint && make test && make gate` until clean. Every command in the foreground
with a timeout; no background process.

Reply with the files changed and, for each test, the behaviour it holds.
