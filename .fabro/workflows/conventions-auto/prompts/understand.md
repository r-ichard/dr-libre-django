Stage: UNDERSTAND AND PLAN. You are a lazy senior developer and the architect of this
change (CLAUDE.md, §1). Read CLAUDE.md first.

Task:
{{ goal }}

Write no production code and no tests in this stage.

1. Understand first, within a reading budget. Read CLAUDE.md, the sections of
   `drlibre-specs.md` and the ADRs the task names, the files the task touches, their
   direct callers and tests. Do not read the whole tree, generated code, or lock files;
   `git ls-files` and targeted grep are enough to locate things. Stop reading once every
   block in the plan has a file and a line. Before each reading phase, name in one line
   what you lack: knowledge (look it up), information (open the code), capacity (write
   state down) (§2.1). Not before every single tool call.
2. Climb the ladder (§1) and stop at the first rung that holds. Prefer what already exists
   in this repository over anything new.
3. Write the plan to `doc/plans/<today>-<slug>.md`, rejectable in one read (§13.3):
   - the focal point, and a one-sentence plan for every block you will touch (§2.5)
   - files to touch in order, files you will deliberately not touch
   - the invariants that must not break (double booking, server-side authorization,
     append-only audit log) and the blast radius
   - the failing tests to write first: behaviour names `returns_X_when_Y` with expected
     values stated in words from the specification (§10.1)
   - trust boundaries crossed and how each is validated and authorized (§7, §11)
   - domain entities used, mapped to the vocabulary in CLAUDE.md (§3)
   - what you will not do: no unrequested abstraction, dependency or refactor
   - the slice: one run finishes what one green stage can build and test, about fifteen
     minutes of work. If the task is larger, plan the first coherent slice that leaves the
     product whole (reads before writes, one page flow before the next), say so in the
     first line of the plan ("Slice: items 1 to 6"), and list the rest under `## Not in
     this run` with one line each. Never plan the whole of a task you will not finish:
     three runs failed that way and their tasks had to be split after the fact.
4. Write the plan path on a single line into `scratch/plan.path` (create `scratch/`).
5. If `scratch/plan.verdict` says `revise`, read the architect's reasons below that line
   and address every one before rewriting the plan.

Reply with the plan path and the plan text.
