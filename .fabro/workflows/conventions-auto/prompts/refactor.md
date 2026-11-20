Stage: REFACTOR SIMPLER (§1 cycle, §2, §5). Behaviour is frozen; tests stay green.

- Cut extraneous load only: opaque names, delocalised logic, a bespoke construct where
  a known pattern fits, needless indirection. Never drop an edge case to look clean (§2.2).
- One recognisable pattern per unit; every non-trivial block has a beacon (§2.3).
- Callers above callees, variables near use, guard clauses, functions under 50 lines,
  files under 300 (§5).
- Strip generated narration comments. Keep only why-comments under 255 characters (§4).
- An abstraction needs a second caller (§8). Deletion over addition.
- Deterministic import order; no unused imports, variables or dead branches (§6).
  Never reformat unrelated code.
- If the ship gate sent you review findings, address every one and say how.

Run `make test` and `make lint` before you finish.

Reply with what you removed, what you renamed, and what you deliberately left alone.
