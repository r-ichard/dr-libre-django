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
