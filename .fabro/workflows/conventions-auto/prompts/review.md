Stage: SECOND READER REVIEWS THE DIFF (§12, §13.3). Review the diff, not the chat.
Do not edit any source file. You write only the review document and the verdict file.

Run `git diff main...HEAD --stat` (the sandbox has the base as local `main`, no
`origin/main`), then read the changed files. Trust boundaries
first: views, API endpoints, middleware, forms and serializers, models and migrations;
then the domain logic; then templates and other UI. CLAUDE.md names the paths. Read at
chunk and plan level, then line by line where it matters.

Check in this order and cite `file:line` for every finding:
1. For each changed block, can you state its plan in one sentence without re-reading
   (§2.5)? What did you confirm at a glance, what forced you to trace (§2.3)?
2. Correctness, edge cases, error handling. Any swallowed error is a defect (§9).
3. Authorization from the session on every use case and route; ownership checks; a schema
   at every boundary with the type derived; nothing sensitive logged or placed in a URL
   (§7, §11).
4. Double booking: conflicts checked inside the transaction, half-open intervals, room and
   patient conflicts, not only clinician (§8, `drlibre-specs.md` section 5.2).
5. Tests: derived from specification or implementation? Assertions that pass forever?
   Missing edge cases the plan promised? (§10.1)
6. Names state roles (§3). Comments pass the litmus test and the 255 cap (§4).
7. Proof left no trace: `git log --oneline` names the stage of each commit. The commits
   after `verify_green` up to `prove` may change tests and test helpers only. A product
   or migration line changed there is a mutation left behind: blocker.
8. Scope: anything unrequested bundled in? Any dependency added, is it the package meant
   and pinned (§11)? Contract sync across layers (§8)?

Write `doc/reviews/<today>-<slug>.md` with findings as severity, `file:line`, risk, and
the smallest fix, then a `## Blocking` list and a `## Later` list.
Write `scratch/review.verdict`: first line exactly `approve` or `revise`, then the blocking
items one per line. `revise` is only for blockers: security, correctness, data loss, a
promised test missing, a failing gate, or a hard rule broken. Hard rules are blockers even
when the code works: any type escape hatch (`Any`, `cast`, bare `# type: ignore` or
`# noqa`, §7), a function over 100 lines or a file over 500 (§5), a swallowed error (§9),
a write without an audit entry in the same transaction (`drlibre-specs.md` section 4),
authorization read from a payload (§11). Everything else goes to Later and is approved.
When the plan declared a slice, hold the run to the slice, not to the whole task: an
item under `## Not in this run` is never a blocker. Copy that list into the review under
`## Left for the orchestrator`, and add any item of the slice the run did not finish.
A time, speed or size budget in the task (how long `make test` takes, for example) is
never a blocker: the sandbox shares its machine with other runs, so a number measured
here proves nothing. Write the number you measured under Later; the orchestrator
measures it on a quiet machine. Changing tests, test data or the Makefile to meet such a
budget is out of scope unless the task is about the budget.

Reply with the verdict and both lists.
