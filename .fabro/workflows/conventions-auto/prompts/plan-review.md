Stage: ARCHITECT REVIEWS THE PLAN (§13.3 "no plan, no generation"). You are a second,
independent reader. Read CLAUDE.md, then the plan at the path in `scratch/plan.path`
(fall back to the newest file in `doc/plans/`). Do not edit source code.

Judge the plan against the task and the conventions:
1. Ladder (§1): is this the smallest sufficient change in the right place? Any
   speculative abstraction, new dependency or refactor nobody asked for?
2. Plan knowledge (§2.5): can you state each block's purpose in one sentence from the plan
   alone? Entities use the CLAUDE.md vocabulary?
3. Test-first (§10): are the first failing tests named as behaviours with expected values
   from the specification, covering edge and error paths, not just the happy path?
4. Security (§11): every trust boundary validated with a schema, authorization server-side
   from the session, no sensitive data in logs or URLs, audit log append-only, secrets only
   via environment. Is the threat the task introduces named and handled?
5. Architecture (§8): thin boundary, wire schema separate from storage, one transaction per
   logical change, expected errors as values (§9).
6. Scope: does the plan deliver the whole task, including callers, tests and docs it
   breaks? Anything silently dropped? A plan may declare a slice ("Slice: items 1 to 6")
   with the rest under `## Not in this run`: judge whether the slice is coherent, leaves
   the product whole and is what one green stage can finish. A plan for the whole of a
   task too large for one run is a reason to revise: ask for a slice.

Then write two things:
- Append a section `## Architect review` to the plan file with your findings.
- Write `scratch/plan.verdict`: first line exactly `approve` or `revise`, then one line per
  reason. Use `revise` only for material problems: a missing invariant, missing first test,
  scope creep, a security hole, or the wrong layer. Style preferences are not reasons.

Reply with the verdict and the reasons.
