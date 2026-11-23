# Review: `make audit` (task 26c, item 13)

Branch `fabro/run/01M82WQ6973K2GR0PSVZTHRD2G` against local `main`. Diff: 7 files, 546 insertions, 1 deletion
(the deletion is the `.PHONY` line in `Makefile`). Plan: `doc/plans/2026-11-23-make-audit.md`.

## Verdict

approve. No blocking items.

## What I checked

1. **Plan per block, one sentence each.** `Makefile:41-44`: runs `scripts/audit.sh`, not in `make test`.
   `scripts/audit.sh:1-8`: exports the locked, hashed requirements to a temp file, then runs `pip-audit` on
   them; exit status is the script's (`set -eu`, `trap` removes the work directory). `scripts/test_audit.py`:
   stubs `uv` on `PATH` and asserts exit codes and the logged calls. `pyproject.toml:22`: pin `pip-audit==2.10.1`
   in `dev`. `README.md:5`: when to run it. Confirmed at a glance except the `set -eu` and `trap` behaviour,
   which I traced: a failing `uv export` stops the script before `pip-audit` runs.
2. **Correctness and error handling.** No swallowed error. `scripts/audit.sh:7` writes the export to a file;
   a failed export aborts under `set -e`, so `pip-audit` never sees a partial file.
3. **Trust boundary.** Local tooling. No route, no session, no payload. The only outbound data is package names
   and versions sent to PyPI's service. Nothing sensitive is logged.
4. **Double booking.** Not applicable to this change.
5. **Tests.** Four tests in `returns_X_when_Y` form: `scripts/test_audit.py:47`, `:53`, `:59`, `:68`. They
   assert exact exit codes (1, 0, 3) and the logged `export` and `run pip-audit --require-hashes` calls. Exit
   3 (not 2) keeps a missing script from passing as an export failure; the comment at `:60` says so. The
   stub-based tests prove the script passes codes through. They do not prove that a real vulnerability makes
   `pip-audit` exit 1; that rests on the plan's scratch probe (`django==3.2.0`, four advisories, exit 1).
6. **Names and comments.** Names state roles (`_run_audit`, `stub_uv`, `audit_log`, `logged_lines`).
   Comments state why. The `# noqa: S603` at `scripts/test_audit.py:35` names its code, as the escape-hatch
   gate requires. `make gate` and `make lint` passed in the `check` stage.
7. **Proof left no trace.** Commits after `verify_green` (`3b1369a`) up to `prove`: `5d316e2` changed only
   `scripts/test_audit.py` (the `run pip-audit` assertion tightened to include `--disable-pip -r`). No product
   or migration line. `3aa7a0b` (`refactor`) came after `prove` and changed one comment line in `scripts/audit.sh:2`.
   `3b1369a` and `d46ad29` are empty commits.
8. **Scope and dependencies.** One new dev pin, exact (`pyproject.toml:22`). `uv.lock` has no removed lines;
   the added packages are pip-audit's own dependency set (`boolean-py`, `cachecontrol`, `cyclonedx-python-lib`,
   `pip-api`, `pip-audit`, `pip-requirements-parser`, `requests`, `urllib3`, etc.). `[project] dependencies`
   is unchanged. `drlibre-specs.md` is not in the diff. `doc/handover.md` is not in the diff (the plan made
   that block droppable). Contract sync across layers: not applicable.

## Host checks run by the reviewer

- `make audit` on the branch: exit 0, output `No known vulnerabilities found`, `Resolved 64 packages`.
- `HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 make audit`: exit non-zero (make reports `Error 1`), with a
  `ProxyError` traceback. It does not print `No known vulnerabilities found`. This was the plan's main risk
  (an unreachable service read as clean). It does not pass silently.
- `uv export --locked --no-emit-project --format requirements-txt`: 357 `--hash` entries.

## Findings

### Later

- **Later / nit.** `doc/handover.md:28-29` (fresh-clone list) has no `make audit` line. The plan's block 6
  made that edit droppable. CLAUDE.md asks that recipes in `doc/handover.md` be kept current in the commit that
  changes them. Smallest fix: one line in the fresh-clone list, or the orchestrator decides it is not needed.
- **Later / plan drift.** `doc/plans/2026-11-23-make-audit.md` (test 3) says the stub export exits 2. The test
  uses 3, with a comment at `scripts/test_audit.py:60`. The plan should be corrected to match.
- **Later / plan accuracy.** The plan says "product runtime does not change" and "the dev image gets the tool
  too". The Dockerfile runs `uv sync --locked` (`Dockerfile:22`), which installs the dev group, so the image
  does change. The plan should say so.
- **Later / plan accuracy.** The plan's "40 packages" count is from the probe, not re-measured here. The plan's
  claim that `pypi` checks hash validity (not just presence) rests on the tool's warning text, not on a run.
- **Later / coverage.** No in-repo test shows a real vulnerability making `make audit` exit 1. The stub tests
  cover the pass-through; the proof is the scratch probe only. Acceptable for this slice; a fixture pinning a
  known-vulnerable package would make it permanent, at the cost of a network call in an opt-in target.
- **Later / process.** `3aa7a0b` (`refactor`) ran after `prove` and touched `scripts/audit.sh`. It changed only a
  comment, so no test was affected. Noted, not a defect.

## Blocking

None.

## Left for the orchestrator

- Item 13 of task 26c is the slice. Items 1 to 12 and 14 onward are not in this run (plan, `## Not in this run`).
- Before the squash: the host check of the unreachable service is done (above). Re-run `make audit` on the
  `verify/` branch after squash, as the plan requires.
- The squash message must disclose tooling and must not carry the fabro checkpoint lines
  (`Generated with Fabro`, `Co-Authored-By: Fabro`), per CLAUDE.md hand-applied gap 1.

## For the owner

- None. The tool choice (pip-audit 2.10.1) is recorded in the plan. If it should be an ADR, that is a follow-up
  for the owner, as the plan says.
