# Retrospective log

One entry per fabro run or orchestration mistake. A pattern that repeats becomes a
process fix (workflow, prompt, script) or a line in CLAUDE.md, in the same change.

## 2026-11-20 process ported from apt-clinic

- Taken: the `conventions-auto` graph and prompts, the verdict, red, comment-cap and
  escape-hatch gates, the engineering conventions, the backlog and this log, the
  `ponytail`, `caveman` and `impeccable` skills.
- Changed: agent stages run as Claude Code over ACP on the Claude subscription instead of
  fabro's API agents. Skills moved to `.claude/skills/`, the comment-cap write gate became
  a Claude Code `PreToolUse` hook, the escape-hatch gate was rewritten for Python, and a
  `make setup` stage installs the toolchain before the first agent runs.
- Left behind: per-stage model routing, provider fallbacks, the Anthropic relay and the
  spend script. They configure fabro's API agents and do not reach an ACP agent.
- Patterns carried over: the goal is the task and the workflow is the method; verify
  that configuration took effect instead of trusting that a file validates; a gate that
  fails on correct code gets bypassed, so fix the gate; close a reviewer "Later" list on a
  foundation layer before building on it; an agent without a browser cannot judge
  visuals.

## 2026-11-20 setup runs (hello, hello-claude, probe)

- `[run.model]` in `.fabro/project.toml` was ignored and the run used the server default,
  which was over its monthly limit. The stage failed and the run still reported
  `SUCCEEDED`. Run settings belong in `workflow.toml`; read the stage lines, not the
  final status.
- The first two runs pushed `fabro/run/<id>` branches to GitHub. Smoke workflows now set
  `[run.run_branch] push = false`.
- Probe run inside the sandbox: Claude Code over ACP ran shell and file tools as root in
  `/workspace`, loaded `CLAUDE.md`, used a skill from `.claude/skills/`, and a
  `.claude/settings.json` hook blocked a forbidden write. Default model: Sonnet 5.5.
- `node [backend="acp", ...]` inside a subgraph applies to every agent node in it, so the
  ACP command is written once per graph.

## 2026-11-21 orchestration starts

- Owner decisions recorded in `CLAUDE.md` and `doc/backlog.md`: latest Django and Django
  REST Framework, PostgreSQL, Django templates with hand-written CSS, containers with
  `rnwood/smtp4dev`. Backlog re-sliced into 26 tasks under 9 milestones.
- Sandbox facts, measured with a script-only run: no Docker daemon, 18 processors,
  16 GB, `apt-get install postgresql` gives PostgreSQL 15 in 9 seconds. Tests therefore
  run on PostgreSQL in the sandbox; the container stack is verified on the host.
- A script-only workflow needs no commit and no subscription call: the graph travels with
  the run and `fabro events <id> --json` carries the script output.

## 2026-11-21 task 01, run 01M7YQ6BV2GV (8 minutes, merged eaf7ef2)

- First full run of the pipeline. Three gates bounced the work once each and it passed
  on the second visit: the architect rejected the first plan, the lint gate rejected the
  first refactor, the reviewer found five missing task items (container files, `CLAUDE.md`
  binding, ADR, environment settings, email wiring). The gates earn their place.
- Host verification found what the sandbox cannot: `docker compose exec web make test`
  fails because a settings test asserts development values, and the inbox port 5000 is
  AirPlay on macOS. Both go to task 01a with the reviewer's "Later" list.
- pytest collects only `returns_*` and `raises_*`. A test named with another verb would
  never run and nothing would say so. Task 01a adds a guard.
- The review prompt diffed against `origin/main`, which does not exist in the sandbox;
  the reviewer fell back to `main` on its own. Prompt fixed.
- Host verification recipe: gates in `docker run node:22-bookworm` on a fresh clone of the
  run branch over https; stack with `docker compose -p drlibre-verify up -d --build --wait`
  in a second fresh clone, then `down -v --rmi local`.

## 2026-11-21 task 01a, run 01M7YQVQ7M60 (4 minutes, merged b972eac)

- Clean pass, no gate bounced. Host check confirmed all three host-only items: the suite
  passes inside the web container, the inbox answers on 8025 under both `localhost` and
  `127.0.0.1`, the database takes its credentials from `.env.example`.
- The collection guard works: a probe function named `checks_nothing` in a test file
  aborts `make test` with its name.
- `docker compose up --wait` returns before the development server listens, because
  `web` has no health check; a curl straight after gets no answer. Verify with retries.
  Carried in `doc/backlog.md`.

## 2026-11-21 task 02, run 01M7YR6HE159 (42 minutes, failed in check)

- Plan, red and green passed first time: 17 models, 291 tests green at `verify_green`.
- The prove stage wrote a script that removes one constraint at a time from the migration
  and reruns pytest, and started it with the Bash tool's `run_in_background`. The agent
  replied, the stage ended, the script ran on. Under refactor and check it kept rewriting
  `0001_initial.py` and running a second pytest: `database "test_drlibre" already exists`
  on all 291 tests, three failed checks, run failed. Every late checkpoint holds a
  different mutation; the tip lacks a constraint.
- Reading the timeline gave it away: a script stage (`check`) with a file change.
  `fabro timeline <id>` first, when a gate fails for no visible reason.
- Fix: `scripts/no_background.sh` as a `PreToolUse` hook on Bash, active when
  `DRLIBRE_PIPELINE=1`; prove prompt requires foreground work and a clean diff; reviewer
  checks that only tests changed between `verify_green` and `prove`; probe covers it.
- The probe's own check matched itself (`pgrep -f 31337` sees the shell running it).
  Anchor process patterns.
- Recovery without redoing 40 minutes: branch `task/02-domain-model` holds the squashed
  `verify_green` checkpoint; task 02a runs on it with `--target-branch` and reviews the
  whole diff.

## 2026-11-21 task 02a, run 01M7YV57N924 (29 minutes, merged bc0c746)

- Ran on `task/02-domain-model` (the green checkpoint of task 02) and passed with one plan
  bounce. `--target-branch` needs `--target-repo`; checking the branch out locally and
  running from there is the simple way to run on a branch.
- The background hook held: the prove stage ran in the foreground in 6 minutes and changed
  two test files only; no script stage shows a file change in `fabro timeline`.
- Host check beyond the suite (385 tests): migrations apply to an empty database, no
  drift; as table owner and as superuser the audit table refuses update, delete and
  truncate; a version cannot be skipped or kept; a hospital with a department cannot be
  deleted; the three exclusion constraints use half-open ranges and ignore cancelled and
  no-show appointments.
- The owner asked mid-run whether the model should follow FHIR naming. Answer recorded in
  ADR 0003 and the task: domain names stay, the schema carries what FHIR needs (versions,
  one Appointment resource for a waitlist entry and its booking, a declared mapping).

## 2026-11-21 task 03, run 01M7YX1M5WPW (30 minutes, merged 8dd846f)

- Passed with one lint bounce. Prove ran 10 minutes in the foreground and changed one
  test file; the background hook holds.
- Host check: `docker compose up --wait` now answers health straight away, the seed runs
  twice with identical counts, refuses with `DEBUG` off, and its audit entry holds counts
  only. Every appointment status and three time zones are present.
- The suite went from 46 to 100 seconds (175 in the container) with 29 more tests: the
  seed tests hash passwords at production cost and seed again per test. The pipeline runs
  the suite six times or more per task, so task 03a makes it fast before task 04.
- The seed writes rows the booking rules would refuse (outside availability). Fine for a
  schema demo, wrong for a product demo: carried, to redo through the use cases.
