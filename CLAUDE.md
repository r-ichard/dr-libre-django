# DrLibre: agent instructions

Card. Read whole. Body: `doc/engineering-conventions.md`, by section (§N). Product truth:
`drlibre-specs.md`, by section number.

## Modes, always on

- **Ponytail** (skill `ponytail`, §1): smallest change that fully solves task. Ladder,
  stop at first rung that holds. Never cut validation, error handling, security,
  accessibility, requested behaviour. End reply: one line what skipped or unchecked, one
  line risks.
- **Impeccable** (skill `impeccable`) for any UI or UX change: Operate mode,
  `drlibre-specs.md` section 16 is product truth until `PRODUCT.md` exists; read its
  `reference/craft-floor.md` before a UI edit.
- **Caveman** (skill `caveman`) for replies and stage outputs: answer first, no filler,
  no hedging, no tool narration, technical terms and error strings exact. Artifacts stay
  normal prose: code, comments, commits, plans, reviews, ADRs, README.

Skills live in `.claude/skills/`, vendored and read-only (§13.1).

## Project bindings

- **Purpose:** appointment scheduling for several hospitals. Visitors search hospitals,
  clinicians and specialties and book without an account; a verified email makes them a
  passwordless patient. Clinicians and admins manage schedules, availability, time off,
  waitlists. Every write audited. Every concept also served through a FHIR R4 API.
- **Branch:** `main`. Solo repo, direct commits allowed (§12) until second contributor
  or branch protection. Runs work on `fabro/run/<id>`, reach `main` squash-merged after
  review.
- **Risk classes (§13.1):** `doc/plans/**`, `doc/reviews/**`, `scratch/**` throwaway.
  Rest product code. Unclassified = product.
- **Owner decisions, fixed:** latest stable Django + Django REST Framework; PostgreSQL,
  tests too. Front end: server-rendered Django templates, hand-written CSS, no CSS
  framework, no Node build; specialty icons from healthicons.org vendored as SVG. Local
  only, in containers: application, database, `rnwood/smtp4dev` for email.
- **Stack:** Python 3.13, Django 6.1.3, djangorestframework 3.18.3, psycopg 3.3.9,
  PostgreSQL 15, uv 0.12.13; dev: pytest 9.2.0, pytest-django 4.14.0, ruff 0.17.6, mypy
  2.4.1 strict + django-stubs 6.1.2 + djangorestframework-stubs 3.18.2. Project package
  `drlibre`, domain app `scheduling`. Settings read the environment (`.env.example` holds
  dev values; real environment wins). `Makefile`: `make setup` (uv, locked sync, local
  PostgreSQL in the sandbox), `make test` (starts local PostgreSQL if none answers, then
  pytest), `make lint` (ruff, mypy), `make gate` (comment cap, escape hatches, size cap of 500 lines a file and 100 a function);
  `make mutate` (mutmut on `scheduling/domain`, fails on a survivor not explained in
  `mutation-equivalents.txt`). Decisions: `doc/adr/0001-stack.md`.
- **Fresh checkout order:** sandbox: `make setup`, then `make lint`, `make test`,
  `make gate`. Containers: `docker compose up --wait` (migrates, returns when
  `/api/v1/health` answers), then `docker compose exec web python manage.py seed_demo`
  (repeatable demo data, needs `DEBUG` on and `DEMO_PASSWORD` from `.env.example`), then
  `curl 127.0.0.1:8000/api/v1/health`; inbox at `http://127.0.0.1:8025`; tests:
  `docker compose exec web make test`.
- **Pages:** `scheduling/views/pages/` (server-rendered), templates in `scheduling/templates/`,
  CSS/JS in `static/`; `/style` lists every component, only with `DEBUG` on. Error pages: `DEBUG` off
  shows ours (403, 404, 500, with correlation id); `DEBUG` on shows Django's technical 404 and 500
  pages, ours only for 403.
- **Docs:** tasks `doc/backlog/NN-slug.md`, plans `doc/plans/YYYY-MM-DD-slug.md`, reviews
  `doc/reviews/YYYY-MM-DD-slug.md`, decisions `doc/adr/NNNN-slug.md`, run log
  `doc/retro.md`.
- **Comment gate (§4.1):** `scripts/comment_cap.py` as Claude Code `PreToolUse` hook
  (`.claude/settings.json`), as `make gate`, as git pre-commit after
  `git config core.hooksPath .githooks`.

## Domain vocabulary (§3), exact names everywhere

Visitor (not signed in, searches, starts a booking), Patient (receives care, books; a
passwordless patient has no password), Clinician (delivers care; public word "provider",
domain name stays Clinician), Admin (manages every hospital), ApiClient (token, one
user's rights), Hospital (owns departments, has a time zone), Department (owns
clinicians, rooms, types), Specialty (managed list), User, ClinicianProfile, Room,
AppointmentType (duration, buffer, room need), AvailabilityRule (weekly clinician
availability), TimeOff, Appointment (patient + clinician + type + room, scheduled),
WaitlistEntry (wants a freed slot), Notification, AuditLogEntry (append-only), Session,
BookingHold (slot reserved while an email is verified), VerificationCode, SignInLink.

## The card

**Think**
1. Understand first, then ladder: smallest sufficient change, right place. Best code =
   none written.
2. Comprehension is the constraint, not typing. Write for next reader's working memory.
3. Plan before generating. Block plan not stateable in one sentence? Reject.
4. Missing knowledge: look up. Missing information: fetch code. Missing capacity: write
   state down.

**Write**
5. Name the role. Leave a beacon. One recognisable pattern per unit.
6. Comment why, never what. 255 chars per block, hook-enforced.
7. Test first; prove test can fail; mutate pure modules.
8. Expected errors = values in contract. Throw only on broken invariant.

**Ship**
9. Never trust client, never log sensitive, pin everything, authorize server-side.
10. Rebase not merge; small PRs; draft by default; ask before commit, push, merge.
11. No AI authorship in git history. Disclose tooling in PR or tracker.
12. Review diff, not chat. Nothing merges unread where it matters.

## Rules while writing

- **Naming (§3):** English, 3+ chars, no acronyms or shortened words, named constants.
  Names state roles (`best_match`, `pending_jobs`), not types. `temp`, `data2`, single
  letters beyond two lines: rename. Tests: `returns_X_when_Y`.
- **Test placement (§10):** tests beside the code they cover, `test_*.py`. Layers (§8):
  domain `scheduling/domain/`, use cases `scheduling/use_cases/`, views and API endpoints
  `scheduling/views/`; each created when first used.
- **Page forms:** test them as a browser sends them: cross-site request check enforced
  and the `Origin` header set. The test client sends neither by default, so a form can
  pass every test and answer 403 in a browser (task 13a).
- **API routes:** same rule. The test client enforces the cross-site check and sends what
  the route's real client sends: a browser `Origin` and the cookie, a FHIR client a
  bearer token and neither (task 22: every write under `/fhir` answered Django's 403 page).
- **Layout:** state the invariant and its measurement for the page, the block and the
  line (`scrollWidth`, `scrollHeight`, edges against the column). The sandbox has no
  browser; what the plan cannot derive from numbers, nobody sees (tasks 16 to 17f).
- **Comments (§4):** obvious in code first; else why; else delete. Changes with code?
  Narration, delete. Docstrings count toward the cap.
- **Size (§5):** functions < 50 lines, files < 300, callers above callees, variables
  near use, ~3 args max. Generated migrations exempt; hand-written ones are not.
- **Types (§7):** fully typed, strictest checker setting, schema-derived boundary types.
  Gate rejects `Any`, `cast`, bare `# type: ignore`, bare `# noqa`; a suppression names
  its code.
- **Architecture (§8):** domain logic pure (no I/O, no clock, no ORM); use cases own the
  transaction and authorization; views and API endpoints thin, format only. Mappers
  between wire and storage. One transaction per logical change, audit entry inside it.
  Clock from request context. Abstraction needs second caller. Model unfinished without
  full CRUDL + tests.
- **Errors (§9):** expected = values in the contract; raise only on invariant break;
  never swallow; never leak internals; structured logs with correlation id.
- **Security (§11):** authorization from session, never payload; ORM or parameterized
  queries only; no sensitive data in logs, URLs, model context; pin and verify deps; UTC
  explicit; audit log append-only.
- **Generation (§13):** session state not evidence; re-read, re-run. No `Co-Authored-By`,
  no tool byline.

## How work flows

Process = `conventions-auto`; task = goal, one run per `doc/backlog/` file: toolchain,
plan, architect gate, red, red proven, green, green proven, prove tests guard, refactor,
lint + tests + gate, reviewer gate, address findings. Orchestrator writes tasks and
process files, never product code; host defect = new task. Orchestrator verifies on host,
squash-merges with Conventional Commit, updates `doc/backlog.md`, logs `doc/retro.md`,
fixes process on repeat patterns.

**QA runs:** `fabro run qa --goal-file .fabro/workflows/qa/areas/<area>.md -d`, one run per
area (access, booking, public, journeys), in parallel with the task run. Each has its own
sandbox, database, mail sink (`scratch/qa/mail.log`) and headless browser. One agent
tests, a second reproduces before filing a GitHub issue labelled `qa` + `P0`/`P1`/`P2`.
Open `P0` issue = next task, before backlog moves on. Orchestrator verifies a P0 first.

**Sync runs:** two task runs may go side by side; the second to finish meets a moved
`main`. A squash that conflicts in product code is never resolved by hand: push the run
branch as `task/<nn>-<slug>`, then from `main` (the branch has no `sync` workflow yet)
`fabro run sync --target r-ichard/dr-libre-django@task/<nn>-<slug> --goal "<task>" -d`.
One agent merges `main` keeping both sides, then lint, tests and gate. The orchestrator
verifies the sync run's branch like a task run and squash-merges it.

**Hand-applied gaps:** (1) fabro checkpoints carry "Generated with Fabro" and
`Co-Authored-By: Fabro`; never merge run branch as-is, squash with hand-written message,
disclose tooling in body. (2) "Red for right reason" judged by agent and reviewer; gate
only proves suite fails. (3) `make mutate` covers `scheduling/domain` only; use cases and views rely on tests and
review. (4) A reviewer
"Later" list on a foundation layer becomes its own hardening task before the next layer.

## Fabro gotchas (§13.6)

- Agent stages = Claude Code over ACP on the Claude subscription. Fabro model, provider
  and hook settings do not reach them; Claude Code reads this file, `.claude/skills/` and
  `.claude/settings.json`.
- Sandbox clones from GitHub. Unpushed files do not exist in a run; push process changes
  before launch. Prompts and graph travel with the run.
- `run` tables in `.fabro/project.toml` are ignored; image and token live in each
  `workflow.toml`.
- Final status reads `SUCCEEDED` even when a stage failed. Read the stage lines.
- Command node scripts shell-quote templated values as one word. Literal commands.
- Graph = process, not backlog. Features in `doc/backlog/`.
- Generators write long comments the write-gate never sees; `make gate` catches.
- Stage = one agent turn. Background process outlives it, mutates files and runs tests
  under later stages. `scripts/no_background.sh` hook blocks it in the sandbox
  (`DRLIBRE_PIPELINE=1`). Foreground only; start, use and stop a server in one command.
- Run ids from `fabro run -d` output; mistyped id makes `fabro wait` return at once.
- No `fabro server restart` during a run; kills it. `fabro resume <id>`.
- Laptop sleep kills sandboxes mid-run. Keep `caffeinate -i -s` running during runs.
- Goal paths may be stale; `ls` them before launch.
- `fabro run probe` (20 seconds) proves tools, skills, this file and the write-gate in the
  sandbox. Run it after any process change, before a real task.

## Done

§14 before hand-off; say plainly what could not run and why.
