Stage: REPAIR WHAT THE GATES NAME. Read CLAUDE.md, then the task in the goal. The branch
you are on was reviewed and approved; a scripted gate refused it. The gate's output is in
the context above: `sh scripts/final_gates.sh` (`make mutate`, then `make fhir-validate`),
or `make lint && make test && make gate`.

Work from what the gate prints now, not from a list in the task.

- A surviving mutant: a test that kills it, in the test file of the module it lives in,
  named `returns_X_when_Y` after what the function promises. A line in
  `mutation-equivalents.txt` only when the mutant cannot change behaviour, with the
  reason in that line. A stale entry of that file is removed, or moved when the same
  mutant got a new number: check that it is the same mutant.
- A validation error of `make fhir-validate`: the resource is wrong, never the sample
  or the validator's options.
- A failing test, lint or comment gate: the cause, not the symptom.

Change tests and `mutation-equivalents.txt` only, unless the task says otherwise. Product
code that looks wrong or unneeded is a finding: write it under `## Later` in a new file
`doc/reviews/YYYY-MM-DD-<task>-repair.md`, with the file and line, and leave it.

Run the gate that failed yourself until it passes, then `make lint && make test && make
gate`. Every command in the foreground, with a timeout; no background process.

Reply with one line per survivor or error: what it was, and the test or the reason.
