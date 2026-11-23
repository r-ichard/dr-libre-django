# Review: task 27c item 1, README start path

Reviewer: second reader, read-only on source. Diff: `git diff main...HEAD` (two files:
`README.md` and `doc/plans/2026-11-23-readme-start-path.md`). Scope: item 1 only.

## Verdict

Approve. No blocker found. The change is documentation only; no product code, migration,
test, Makefile, compose file or specification line changed.

## Plan check (§2.5)

- One block per README section, in the order the plan gives: title and purpose, start,
  demo accounts, first walk, stop and forget, checks, FHIR (unchanged), DEBUG off
  (unchanged). I could state each block's plan in one sentence without re-reading.
- The diff has a single hunk, old lines 1-8. Everything from `## FHIR API` (README.md:67)
  to the end is byte-identical to `main`. Confirmed by the hunk header, not by a line diff.
- Confirmed at a glance: the two purpose sentences match `drlibre-specs.md` lines 13-14
  verbatim (README.md:3); the clone URL matches `git remote` origin and `doc/handover.md`
  "Run it" (README.md:10); `DEMO_PASSWORD` is named, not printed (README.md:28;
  `.env.example:14` is the only value, and it is not repeated in the README); `/sign-in`
  is a route (`drlibre/urls.py:127`); `6d98501` exists in the repository.
- Traced: `make setup` and `make audit` descriptions against `Makefile:12-15` and `:43-44`;
  `fhir-validate` apt-get fallback against `scripts/fhir_validate.sh:21`; the `-v` volume
  claim against `compose.yaml` (`volumes:` at line 72, named volume).

## Findings

1. **Nit, Later.** `Makefile:32-36` `make mutate` is documented at README.md:60 as "slow"
   with no "needs ..." mark, and no mutate run appears in the completed stages. Plan
   invariant (plan line 84) says every README command is either run in the sandbox or
   marked. Risk: a reader cannot tell whether it was ever run. Smallest fix: the
   orchestrator runs `make mutate` on the host, and the README line says where it was run
   or adds a mark. Not a blocker: the README does not claim it passes.
2. **Nit, Later.** `make fhir-validate` (README.md:62) and `make mutate` are in the task's
   done-when list, but the stage list shows only `make lint`, `make test`, `make gate`.
   Risk: none to this diff; the gate is unverified. Smallest fix: orchestrator runs both
   on a clean clone, as the task requires.
3. **Nit, Later.** README.md:14 "starting a local one where it can" describes
   `scripts/ensure_database.py` (`Makefile:15`). I did not trace that script's start
   behaviour; the claim is not checked by this review. Smallest fix: read the script and
   reword to what it does, or leave it.
4. **Nit, Later.** The first walk (README.md:33-50) and the Docker lines are unverified
   here. The README says so ("not re-run for this README"; "Needs Docker"). The orchestrator
   runs `make smoke` for item 2 on a fresh stack; that is the real proof, not this review.
5. **Nit, Later (process).** `doc/plans/2026-11-23-readme-start-path.md` is a new file.
   Task 27c says "No new file beside the README". CLAUDE.md requires plan files in
   `doc/plans/`, so I read it as the process artifact, not a product file. Orchestrator
   decides whether it is squashed into `main` or left out.
6. **Nit, Later (process).** Eleven commits on the run branch carry
   `⚒️ Generated with [Fabro](https://fabro.sh)` (`git log main..HEAD`). CLAUDE.md
   hand-applied gap 1: squash with a hand-written message and no tool byline in the body
   or trailers.
7. **Nit, Later.** The DEBUG-off section (README.md:131-145) is unchanged from `main`. The
   plan asked the run to check the four refusals against `drlibre/startup_checks.py` and
   `drlibre/settings.py`. Not checked here. Not in this diff's change set, so not a
   blocker.

## Proof left no trace (§7 of the review checklist)

Commits after `write` are `check` (220e924) and `prove` (639c27b). `git show --stat` shows
no file for `220e924`. `639c27b` changes only `README.md` (62 insertions, 2 deletions, the same
stat as `9a50bd3` against `9ddc6d8`), so no product code, migration or test changed after
`write`. Nothing left behind.

## Double booking, authorization, schema, logging (checklist 3-4)

Not applicable: no code path changed. The README names no secret value.

## Scope and dependencies (checklist 8)

No dependency added. No `drlibre-specs.md` change in the diff. No `make smoke` target or
mention (item 2 excluded, plan line 65). FHIR section unchanged.

## Blocking

(none)

## Later

- `make mutate` mark or run record (finding 1).
- Run `make mutate` and `make fhir-validate` on a clean clone before merge (finding 2).
- Verify or reword the `ensure_database.py` claim (finding 3).
- Item 2 smoke run covers the walk and Docker lines (finding 4).
- Decide whether the plan file lands on `main` (finding 5).
- Squash the eleven Fabro-tagged commits with a hand-written message (finding 6).
- Trace the DEBUG-off refusals against code (finding 7).

## Left for the orchestrator

From the backlog slice (`doc/backlog/27c-readme-smoke-test.md`, item 2):

- `make smoke`: Makefile target, `scripts/` smoke script, README paragraph saying when to
  run it.
- Run `make smoke` against a fresh `docker compose up --wait` plus `seed_demo` stack.

Not run in this run (plan "Not in this run"): item 2 in full.

## For the owner

None. No decision the specification leaves open was touched.
