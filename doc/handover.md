# Hand-over: how to carry this project on

Written 2026-11-22 for whoever orchestrates next: a person, or an agent in any harness
on any model. It says where things stand, what is in flight, and the exact recipes used
so far. Keep it current: change it in the same commit that changes the state it
describes.

## What to read first

| File | What it is |
|---|---|
| `drlibre-specs.md` | The product. The owner's text: nobody edits it but the owner. |
| `CLAUDE.md` | The agent card: rules, vocabulary, how work flows. Read whole. Any agent follows it, whatever its name. |
| `doc/engineering-conventions.md` | The rules behind the card, by section. |
| `doc/backlog.md` | Every task with its status, then "Carried items": open points and questions for the owner. |
| `doc/backlog/NN-slug.md` | One task each. Self-contained: a task file is the whole brief of a run. |
| `doc/retro.md` | What happened in every run and what the process learned. Newest last. |
| `doc/adr/` | Decisions. 0010 is "proposed" and waits for the owner. |
| `doc/qa/` | The findings of each QA round, issue by issue. |
| `doc/data-model.md` | The data model, generated from the code. |

## Where it stands

- `main` holds a product that runs: every milestone M1 to M9 of the specification is
  merged (search, booking with a verified email, patient portal, clinician workspace,
  admin console, waitlist, reminders, audit, the FHIR R4 API, and the hardening of M9).
  GitHub issue #9 lists what M9 holds, commit by commit.
- From a fresh clone of `main`: `make lint`, `make test` (about 5500 tests, two to five
  minutes; a test phase over 60 s fails it), `make gate`, `make mutate`,
  `make fhir-validate` (115 samples) and `make audit` (locked dependencies, no known
  vulnerabilities) pass. Against a running, seeded stack, `make smoke` walks a booking
  from search to cancellation.
- Security: `doc/security-review.md` says, rule by rule, where each security rule of the
  specification is enforced and which test holds it; its access section is generated
  from three access tables by `make access-table`, and a test fails when the two differ.
  ADR 0011 (encryption at rest, the development server) and ADR 0012 (readings of the
  access rules) are proposed, for the owner.
- Three QA rounds ran; round 3 filed 20 issues, no P0, all closed. No further round
  unless the owner asks for one.
- Try it: see "Run it" below.

## How work is done now

Since 2026-11-23 (owner's decision) new work goes to Claude Code sub-agents on Haiku, one
finding or item each, in a git worktree of their own; see "The pipeline". A sub-agent on
the host has no PostgreSQL: it stops after `make lint` and `make gate`, and the
orchestrator runs `make test` and the other gates in a container from a fresh clone.

## What is left, after M9

Proposed in issue #9, none of them a known defect:

1. The access walk for the 13 personal FHIR writes (Patient, Appointment, Schedule,
   PractitionerRole and others): `scheduling/views/test_fhir_access_write_cases.py`
   lists them in `NOT_WALKED_YET`.
2. `27d3-fhir-refusal-messages.md`: a message of its own on every FHIR 400.
3. `26c-gates-that-hold.md` item 11a: about 1165 mutants of `scheduling/domain` that no
   test reaches; items 17, 18 and 20: tests over every form.
4. The writer of a stray audit row one test used to see (`doc/backlog.md`).
5. The owner's questions, below, each with the choice the product makes today.

## Run it

From a clone of its own, not from the working tree an orchestrator switches branches
in: the compose file mounts the source into the container, so a checkout changes the
code under a running server.

```sh
git clone https://github.com/r-ichard/dr-libre-django.git drlibre-try && cd drlibre-try
docker compose up --wait                                   # app, database, mail inbox
docker compose exec web python manage.py seed_demo         # demo data, repeatable
open http://127.0.0.1:8000                                 # the product
open http://127.0.0.1:8025                                 # every email it sends
docker compose down -v                                     # stop and forget
```

Demo accounts, all with the password in `.env.example` (`DEMO_PASSWORD`):
`admin@example.test`, `clinician@example.test`, `patient@example.test`. A visitor needs
no account: search, pick a time, type an email address, read the code in the inbox.

From an empty hospital to a booking, walked on `6d98501` (2026-11-22), every step
answered as expected. As the admin, in the admin console, in this order: a hospital
(with its time zone), a specialty, a department of the hospital, a room of the
department, an appointment type of the department (the colour is typed, like `#2f6f6a`;
tick "Bookable online"), a user with the role Clinician and a temporary password, then
"Clinicians": attach a profile to that user (department, specialty, room). Sign out,
sign in as the clinician, "Availability": one rule per weekday. Sign out: the start
page finds the clinician, the hospital and the specialty; pick a time, fill in the
details, take the code from the inbox, confirm. The clinician's calendar shows it.

## The pipeline

Since 2026-11-23 (owner's decision) new work goes to Claude Code sub-agents on Haiku, each
in its own git worktree (`Agent` tool, `model: haiku`, `isolation: worktree`), one finding
or item each, with the task's rules in the prompt: test first, this card, no background
process, no edit of `drlibre-specs.md`. The sub-agent leaves its change committed on its
worktree branch; the orchestrator reads it, runs the gates below and lands it. Fabro, as
described next, stays usable by anyone who prefers it.


`fabro` (0.408, `~/.fabro/bin/fabro`) runs one workflow per task in its own sandbox,
cloned from GitHub: `.fabro/workflows/conventions-auto/workflow.fabro`. Stages: plan,
plan review, failing tests, proof they fail, code, proof they pass, proof the tests
guard, refactor, lint + tests + gate, review by a second reader, then `make mutate` and
`make fhir-validate` as a scripted last gate. Each stage's brief is a file in
`.fabro/workflows/conventions-auto/prompts/`.

```sh
fabro run conventions-auto --goal-file doc/backlog/<task>.md -d      # prints the run id
fabro run conventions-auto --target r-ichard/dr-libre-django@task/<branch> --goal-file doc/backlog/<task>.md -d
caffeinate -i -s fabro wait <id>                                      # blocks until it ends
fabro attach <id>                                                     # stage lines, only after wait returned
fabro run qa --goal-file .fabro/workflows/qa/areas/<area>.md -d       # a QA run: tests, then files issues
fabro run repair --target r-ichard/dr-libre-django@task/<branch> --goal-file doc/backlog/<task>.md -d   # approved branch, a last gate fails: tests only, no red stage
fabro run tests-and-docs --goal "..." -d                            # no behaviour change: tests, documents, gates
```

Since 2026-11-22 every agent stage runs on Haiku (`ANTHROPIC_MODEL` in each
`workflow.toml`; `fabro run probe` shows the model in its events) and a run gets one
finding or one item: `--goal "Item N only of doc/backlog/<file>.md (#issue)"`. The
orchestrator reviews each diff itself. Three small runs side by side work when their
files do not overlap. Push before launching: the
sandbox clones from GitHub.

### Another harness, another model

- The agent stages are bound to one agent in one line of each `workflow.fabro`:
  `acp.command="npx -y @agentclientprotocol/claude-agent-acp@0.109.0"`. Any agent that
  speaks the Agent Client Protocol can stand there; credentials are a fabro secret
  (`fabro secret`). Run `fabro run probe` after such a change: it proves in 20 seconds
  that the agent has its tools, reads `CLAUDE.md` and meets the write gate.
- Without fabro the same work is done by hand, one task at a time: branch
  `task/<nn>-<slug>` from `main`, then follow the stage prompts in their order (they are
  plain instructions, nothing in them needs fabro), run the gates below, and have a
  second reader that did not write the code review the diff with `prompts/review.md`.
- `CLAUDE.md` is the card for every agent; `AGENTS.md` points to it. The hooks of
  `.claude/settings.json` (a comment cap, no background processes in the sandbox) only
  fire in Claude Code: elsewhere `make gate` is what catches a long comment.

## Verifying a run (never skip)

Before anything else the orchestrator reads every changed line of product code in the
run's diff (`git diff main...origin/fabro/run/<id> -- . ':!doc' ':!*test_*'`) and the
names of its tests. The pipeline's own reviewer is one of the cheap agents that wrote
the code; it does not replace this reading. Two merges that skipped it (`ac99dd7`,
`4078bbd`) each held a defect that reading found afterwards: a limit that `HEAD`
walks around, and a refusal that quotes part of a password.

Gates and review pass and a run is still wrong about one time in three: every hold in
`doc/retro.md` was found by using the product, not by reading the diff.

```sh
git fetch origin
git switch -C verify/<task> main            # -C: a stale branch of that name is replaced, never reused
git merge --squash origin/fabro/run/<run id>
[ "$(git branch --show-current)" = "verify/<task>" ] && git commit -m "wip: <task>, verification only"
git switch main && git status -sb | head -1  # must read "## main...origin/main", nothing ahead

# 1. the five gates, from a fresh clone, in a container
docker run --rm -v "$PWD":/src:ro node:22-bookworm bash -c "git config --global --add safe.directory '*' \
  && git clone -q -b verify/<task> /src /workspace && cd /workspace && make setup >/dev/null 2>&1; \
  make lint; echo lint=\$?; make test; echo test=\$?; make gate; echo gate=\$?; \
  make fhir-validate; echo fhir=\$?; make mutate; echo mutate=\$?"

# 2. the product itself, from the same branch, on ports of its own (8100, mail 8125)
git clone -q -b verify/<task> . /tmp/drlibre-fresh && cd /tmp/drlibre-fresh
cat > /tmp/verify-ports.yaml <<'YAML'
services:
  web:
    ports: !override ["127.0.0.1:8100:8000"]
  mail:
    ports: !override ["127.0.0.1:8125:80"]
YAML
alias stack='docker compose -p drlibre-verify -f compose.yaml -f /tmp/verify-ports.yaml'
stack up -d --build --wait
stack exec -T web python manage.py seed_demo
#    ... do what the task's last paragraph says "the orchestrator" does ...
stack down -v --rmi local --remove-orphans
```

The ports differ from a try-out stack's (8000, 8025) so both can be up at once.

What to do by hand, learned the hard way:

- Send requests as the real client sends them: a browser's form post with `Origin` and
  the cross-site token, `curl -X POST` with nothing else, a FHIR client with a bearer
  token and no cookie. Three defects hid behind a test client that sends something else.
- Compare with the database, not with the answer: read the rows with `psql` in the `db`
  container and ask the product for the same thing.
- Try the neighbours of the fix: the other forms that use the same rule, the other
  roles, hospitals on both sides of UTC, 375 px and 1440 px for anything visible.
- A token for `/fhir`: `docker compose exec web python manage.py api_tokens issue --name x <email>`.
  Keep it in a file, never in a log or an issue.

### Landing a run

```sh
git checkout verify/<task>
git commit --amend            # Conventional Commit, hand-written body, tooling disclosed, no AI co-author
git checkout main && git merge --ff-only verify/<task> && git push origin main
git branch -D verify/<task>; git push origin --delete fabro/run/<run id>
```

Then: a comment on each issue it closes saying what was checked; the row in
`doc/backlog.md`; an entry in `doc/retro.md`; a task file for what the run left.
`Closes #N` only in the commit that lands the fix: the word closes the issue from any
commit on `main`.

### When a run is right but broke something

Do not merge and do not fix it by hand. Push its branch as `task/<nn>-<slug>`, write a
follow-up task (`<nn>2-...md`) that names the defect with the request that shows it, run
it with `--target ...@task/<nn>-<slug>`, verify the new run's branch, land both as one
squash.

### When a squash conflicts

In `doc/backlog.md`, `doc/retro.md`, `doc/backlog/**`, `doc/qa/**`, `CLAUDE.md`,
`.fabro/**`: take `main`'s side. In product code: never by hand. Push the run branch as
`task/<nn>-<slug>` and, from `main`:
`fabro run sync --target r-ichard/dr-libre-django@task/<nn>-<slug> --goal "<task>" -d`.
Verify the sync run's branch like any other.

## Questions that wait for the owner

One list, with the choice the product makes today and the cost of changing it, at the end
of `doc/security-review.md` ("For the owner"); `doc/backlog.md` "Carried items" holds the
rest. The ones that change behaviour:

- ADR 0010 (FHIR sorting, 415, search values), ADR 0011 (encryption at rest, the
  development server), ADR 0012 (readings of the access rules): all "proposed".
- An admin acts on every user's record (specification "Decisions" item 2), where section
  12.3 says "forbidden" for another user's record: which rule wins for an admin.
- "Forbidden" for another user's record and "not found" for a missing one tell a caller
  whether a record exists (ADR 0012, reading 1).
- A clinician's or admin's FHIR search of notifications, and a clinician's search of
  offer answers, answer an empty set, not 403.
- A hospital's FHIR `Organization` cannot be updated or deleted (405): ADR 0008 writes a
  hospital through `Location`.
- A signed-in clinician or admin gets 403 on the public booking details page.
- A day without a time in a FHIR search is a UTC day; a wrong method on `/api/v1` answers
  404; check-in and no-show are possible before the day; a patient may join the waitlist
  for a type they cannot book online; patients are not told when a hospital's time zone
  changes (#36).

## Things nobody should do

- Edit `drlibre-specs.md`, or let a run do it.
- Commit a work-in-progress squash to `main`: verification lives on `verify/<task>`.
  It happened twice: once pushed (`e9a419c`, reverted), once caught before the push,
  when `git checkout -b` met a stale `verify/` branch, failed, and the script went on
  and committed on `main`. Check the branch name before every wip commit.
- Force-push `main`, or rewrite its history: the repository is public.
- Put a token, a password other than the published demo one, or a real person's data
  in an issue, a log or a commit.
- Add `Co-Authored-By` or a tool byline to a commit.
