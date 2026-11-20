Stage: GREEN (§10). Make the failing test pass with the simplest code that works.

- Smallest sufficient change in the right place (§1). No refactoring in this stage.
- Expected errors are values in the published contract; raise only on a broken
  invariant (§9). Never swallow an error.
- Validate at every trust boundary with a schema and derive the type from it (§7).
  No `Any`, no `cast`, no bare `# type: ignore` or `# noqa`.
- Names state roles (§3.1). No `temp`, `data2`, or single letters outside a two-line
  scope.
- Comment only the why, never the what, under 255 characters per block (§4). The
  write gate will reject longer blocks.
- Run `make test` until green. Never weaken or delete a test to pass.
- If the gate sent you back, read the failure output and fix the root cause.

Reply with the files changed and the one-sentence plan of each changed block.
