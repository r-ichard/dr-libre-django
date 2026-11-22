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

## 2026-11-21 task 03a, run 01M7YZ43HXP3 (13 minutes, merged d7ad7aa)

- Clean pass. Suite: 100 seconds to 3 (5 in the container). The cause was one line: every
  test user was hashed with PBKDF2 at production cost. Measure before tuning.
- Host check: two `make test` at once both pass and leave no database behind; the
  collection guard still fails the run under xdist; a failing test still fails `make`.

## 2026-11-21 task 04, run 01M7YZZNRFAQ (14 minutes, merged 1d3643c)

- One review bounce (the promised ADR was missing), then approved. 496 tests in 3 seconds.
- Host check on the running stack found a leak the suite cannot see: a logger with no
  handler and no propagation falls through to Python's last-resort handler, which printed
  `Not Found: <raw path>` as plain text. The tests checked the formatter, not what the
  process writes. Lesson: test logging at the process boundary, and always run the leak
  check (`docker compose logs | grep` for a planted email and token) on the host.
- Split again: 04a fixes the log and error paths first, 04b carries the audit writer and
  the security headers.

## 2026-11-21 task 04a, run 01M7Z0WGGPWF (8 minutes, merged f8cb3d8)

- Clean pass. Host leak check repeated on the running stack: planted email, path segment
  and token appear in no line; every request line is JSON with the route pattern.
- What remains plain text is start-up output (`migrate`, development server banner).

## 2026-11-21 task 04b, run 01M7Z1DH5DCF (10 minutes, merged 45d9150)

- One plan bounce, then clean. 557 tests in 4 seconds.
- Host check: the security headers are on 200 and on API errors; Django's deployment
  check passes on production-like values and reports 4 warnings on the development ones;
  the seed's audit row holds counts only.
- A non-API 404 has no content security policy under `DEBUG`: Django leaves its debug
  pages out on purpose. With `DEBUG` off the header is there. Check headers both ways.
- Milestone M1 is complete: 9 runs, 8 merged, 1 failed and recovered.

## 2026-11-21 task 05, run 01M7Z3ZD8WKH (14 minutes, merged 796da1f)

- Clean pass, no bounce. 657 tests in 3 seconds.
- Host check against the running stack with the seeded accounts: cookie flags, hashed
  token in the database, 12 hour admin lifetime, unknown field refused, cross-origin
  login refused, equal time for a wrong password and an unknown address (0.21 s both),
  lockout after ten failures holding against the right password, sign-out deleting the
  session, audit rows with the email domain only, nothing readable in logs.

## 2026-11-21 task 05a, run 01M7Z4WKE7WY (13 minutes, merged b35274e)

- Clean pass, 717 tests. First run verified in Chrome DevTools: style page and sign-in at
  375, 768 and 1440 px, sign-in driven with the keyboard only (skip link, empty submit,
  wrong password, right password, return to the page asked for), forbidden page, product
  404 page.
- Lighthouse accessibility 100 on the style page (mobile) and the sign-in page (desktop).
  No horizontal scroll at 375 px, no inline style or script.
- Found in the browser: three different left edges at 1440 px, a favicon 404 in the
  console. Found by reading the code: a page request extends the session in the database
  but does not renew the cookie, so sliding sessions do not slide for pages. Task 05b.
- The compose stack always runs with `DEBUG` on, which hides the product's 404 and 500
  pages. To see them: `docker compose run -d -e DEBUG=false -p 127.0.0.1:8001:8001 web
  python manage.py runserver 0.0.0.0:8001`.
- The Lighthouse tool cannot write reports outside the workspace roots; omit the output
  directory.

## 2026-11-21 task 05b, run 01M7Z5V66AB7 (8 minutes, merged 0fa71b5)

- One plan bounce and one review bounce (two CSS items had been skipped), then approved.
- Chrome: header, main and footer share one left edge at 1440 px (176) and at 375 px
  (16); card spacing equal above and below; favicon served; cross-site cookie HttpOnly.
- My task asked for keyboard access to the scrolling table, which task 05a had already
  built. The reviewer noticed the test was never red. Check the code before writing a
  defect into a task.
- Milestone M2 is complete.

## 2026-11-21 task 06, run 01M7Z6E17G4R (1 minute, failed in toolchain)

- `apt-get install postgresql` could not resolve `deb.debian.org`: a network blip, nothing
  in the repository. Relaunched unchanged. First such failure in 16 runs; if it repeats,
  bake PostgreSQL and uv into the sandbox image instead of installing them per run.

## 2026-11-21 task 06, run 01M7Z6MJ3HR7 (13 minutes, merged 5d18572)

- Plan bounced once; the reviewer blocked on `make mutate` not being bound, and the
  address stage bound it. 856 tests. Mutation run: 17 seconds, 96 percent on the engine.
- Reading the engine against section 5 line by line found no rule error. It found three
  fit problems the review rated "Later": the domain imports its enumerations from the
  model layer, clinician ids are typed `int` while identifiers are UUIDs, and on a
  clock-change day the real end of a slot can pass the rule's wall-clock end.
- `make mutate` covers all of `scheduling/domain`: 21 of the 38 survivors are in
  `audit_metadata.py`, written before mutation testing existed. Task 06a.
- "Welcome" in a task means skipped. Property-based tests were welcome; none were written.
  Ask for what is wanted.

## 2026-11-21 task 06a, run 01M7Z7GTSNN6 (12 minutes, merged 59cda46)

- Clean pass. 884 tests in 4.5 seconds, `make mutate` in 26 seconds with 5 survivors, each
  explained in `mutation-equivalents.txt`.
- Host check: no migration from moving the enumerations; planting a Django import in a
  domain module fails the import guard.
- `make mutate` is now a gate: the proof stage can run it and trust its exit code.

## 2026-11-21 task 07, run 01M7ZA9QJG1D (79 minutes of which 50 asleep, merged 4466b27)

- Clean pass, no bounce. 1125 tests in 10 seconds, mutation gate clean.
- The laptop slept on battery with the lid closed from 16:19 to 17:09. `caffeinate -i -s`
  holds on AC power only. The sandbox and the agent survived and the run resumed by
  itself a few minutes after wake; the events stream simply stops while asleep. Before
  restarting a silent run, read `pmset -g log` and look at the sandbox with
  `docker exec <container> ps`.
- Host check on the running stack: slots in the hospital time zone, booking, the same
  slot twice (conflict naming clinician and patient), another patient's id (forbidden),
  an end time in the body (unknown field), a start that is no slot (outside
  availability), first available. Then the race: six patients for one slot in parallel,
  three rounds, one 201 and five 409 each time; one patient with two clinicians at the
  same time, three rounds, one 201 and one 409 each time. No overlap in the database, no
  500, nothing readable in the logs.

## 2026-11-21 task 08, run 01M7ZF0DSJDH (23 minutes, merged 032461d)

- Clean pass, no bounce. 1185 tests in 10 seconds.
- Host check: reschedule, check-in, complete, each refused transition with the current
  status, a foreign clinician refused, a patient refused inside 24 hours and the clinician
  allowed. Four emails read in smtp4dev: time with zone, hospital, provider, sign-in
  link. A planted reason appears in no email, log line or audit row.
- Mail server stopped: the booking still answers 201 in 26 ms and one email stays
  pending; server back, the retry sends 1, a second run sends 0.
- Found by trying: the booking API has no field for the patient's reason for the visit.
- The reviewer approved a 719 line test file although the review prompt names 500 as a
  hard rule. A rule a reader must remember gets missed; task 08a moves it into
  `make gate`.

## 2026-11-21 task 08a, run 01M7ZGGVDM2F (19 minutes, merged 47d6ed1)

- Clean pass. 1220 tests in 11 seconds.
- Host check: a planted reason is read by the patient and the appointment's clinician,
  not by another clinician, and appears in no notification, audit row, log line or
  email; 201 characters and a reversed or empty range answer 400; a 501 line file fails
  `make gate`.

## 2026-11-21 task 09, run 01M7ZHR8YB0N (22 minutes, merged 5370249)

- Clean pass, no bounce. 1399 tests in 10 seconds, mutation gate clean.
- Host check with the worker container running: a clinician cannot join; cancelling an
  appointment offered the slot to the oldest matching entry, which was a seeded one and
  not the entry I had just added, as section 5.8 says; another patient could not accept
  it; an admin accepted, the appointment is linked to the entry and carries its version;
  a second accept answers `invalid_transition`. The reminder job answers 1 then 0, and a
  patient calling it gets 403. Worker lines are all JSON.
- Seed data takes part in live checks. Read the database before deciding a result is
  wrong.
- Found by reading the inbox: two notification titles differ from section 11 and an
  accepted offer sends two emails. Carried.
- Milestone M3 is complete.

## 2026-11-21 task 10, run 01M7ZK5KBHH0 (18 minutes, merged 2344ec0)

- Clean pass, no bounce. 1528 tests in 11 seconds; mutation gate clean with 11 new
  equivalents, each explained.
- Host check: three lists with next availabilities in three time zones, text match,
  sort, a time-of-day filter that empties the list, junk parameters falling back, a page
  past the end. The first slot a result showed was booked with 201: the list and booking
  agree.
- A grep for private data matched "phone" in the type name "Cardiology phone follow-up".
  Search for values, not words.

## 2026-11-21 task 12, run 01M7ZMBW87BK (27 minutes, merged bc85ddf)

- Clean pass, no bounce. 1624 tests in 12 seconds, mutation gate clean.
- Host check as a visitor, code read from smtp4dev: terms required; a hold answers with
  the slot only; the held slot leaves the slot list and a patient booking it gets
  `conflict`; two wrong codes, then the right one books, creates a passwordless verified
  patient and opens a 24 hour session; the code cannot be replayed. A new address, an
  existing patient and a staff address get the same hold answer; the staff address is
  refused after the right code and nothing is booked; an existing patient keeps their
  profile; five wrong codes kill the code. Sixth hold in an hour and fourth resend
  answer 429. No visitor data in audit rows or logs, no code in logs, hashes only.
- My first pass used `birth_date` where the API says `date_of_birth`, and the strict
  schema said so. Then random slot picks collided and looked like a leak. Read the schema
  first and use distinct slots.
- With the mail server down a hold answers a bare 500. Carried to task 13 with the lock
  order finding of the review.

## 2026-11-21 task 13, run 01M7ZP6HTKGF (27 minutes, merged b3192e7)

- One review bounce (a purge without its audit entry), then approved. 1746 tests.
- API on the host: a patient, an unknown address and an admin all get 202 and an empty
  body; only the patient gets mail; a second request cancels the first link; the fourth
  request in an hour answers 429; token and address appear in no log line; the database
  holds the hash.
- Chrome found what 1746 tests did not: the Continue button answers 403. The page sends
  `Referrer-Policy: no-referrer`, the browser then posts with `Origin: null`, and the
  cross-site request check refuses. Django's test client sends no `Origin` header at
  all, so the form passed every test. A flow is verified when a browser has walked it.
- Rule added to `CLAUDE.md`: page forms are tested with the check enforced and the
  header set. Task 13a fixes the page and adds the helper.

## 2026-11-21 task 13a, run 01M7ZQXQPPY9 (8 minutes, merged 84412f9)

- Clean pass. 1765 tests.
- Chrome, with a link taken from smtp4dev: Continue signs the passwordless patient in and
  lands on `/patient/` with no token in the address; the same link again shows "Sign-in
  link not valid" with a way to ask for a new one; the link request form answers "Check
  your email" for an unknown address too. A POST with `Origin: null` gets the product's
  403 page. Lighthouse on the sign-in page: accessibility 100, best practices 100.

## 2026-11-21 task 12a, run 01M7ZRJ0D432 (20 minutes, merged 1b00054)

- One green bounce, then clean. 1838 tests.
- Chrome, as a visitor at 375 px: week of slots, each link named with its day; an empty
  details form answers with a summary of four errors, each tied to its field, focus on
  the first; a wrong code says "You have 4 tries left"; the code from smtp4dev books and
  signs in; the confirmation shows whom, when with zone, where with room. The calendar
  file is valid, in UTC, without the reason. As the signed-in patient: one review page,
  then confirmed; the same slot again answers "That time was just taken" with a link to
  the refreshed times. Lighthouse accessibility 100 on the times page at 1440 px.
- Compiling with warnings as errors found an invalid escape sequence in the calendar
  module that ruff's selected rules and the suite both let through. Carried to task 10a
  with a request to fail the suite on warnings.

## 2026-11-21 task 10a, run 01M7ZSYPETVJ (17 minutes, merged ca68ee5)

- Clean pass. 1885 tests; the suite now fails on warnings.
- Chrome at 1440 and 375 px: three lists, healthicons icons on the specialties, text
  search, every link keeps the rest of the address, junk parameters fall back, a slot
  link opens the details page with the right time and zone. Lighthouse on the search
  page: accessibility, best practices and SEO all 100.
- Lighthouse 100 is not the end of an accessibility check: the slot links hide their
  visible text from assistive technology and announce different words, which fails
  label in name. The reviewer had flagged it; the browser confirmed it.
- Found by using the page: the empty state's way out leads back to the same empty
  search, and on a phone the filters push the results a thousand pixels down. Carried
  into task 11 with four smaller items.

## 2026-11-21 task 11, run 01M7ZV3AMNKP (27 minutes, merged 62d00f2)

- One green bounce, then clean. 1957 tests.
- Chrome at 375 px: hospital page with first available per type, departments,
  specialties and providers; provider page with its week of slots; specialty page. An
  unbookable provider and an unknown id answer 404 on the page and in the API. Booked as
  a visitor from a hospital's "first available": the appointment has source
  `ROUND_ROBIN`, a clinician and the round robin stamp. Lighthouse 100 on all four
  categories on the provider page.
- The six items carried from the search page are fixed and checked in the browser.
- Milestone M4 is complete: a visitor can search, book without an account and come back
  through an emailed link.

## 2026-11-21 task 14, run 01M7ZWV0TF4K (16 minutes, merged abb50a6)

- One review bounce: the home page had been left as a greeting, and the reviewer blocked
  on it. 2010 tests in 21 seconds.
- Chrome as the demo patient at 375 px, keyboard for the forms: sign-in returns to the
  page asked for; service, provider, time and review book an appointment; the home shows
  it with its actions and the unread count; reschedule shows the old and the new time and
  confirms; cancel refuses an empty reason and then cancels. Another patient's
  appointment id answers 403 or 404 and shows nothing. The planted cancel reason is in no
  log line, audit row or email. Lighthouse 100 in all four categories.
- Measured, not eyeballed: the space between appointment cards is 0 px. Carried into
  task 15.

## 2026-11-21 task 15, run 01M7ZXYSSG2P (21 minutes, merged 9d36ae6)

- One green bounce and one review bounce. 2106 tests.
- Chrome as the demo patient at 375 px: accepted a seeded waitlist offer and found the
  appointment in the upcoming list; marked a notification as read; an invalid phone is
  refused on its field, a valid phone and birth date are saved with an audit entry that
  names the two fields and holds neither value. Password change, posted as a browser
  would: wrong current, too short and unchanged are refused; the right one ends the
  other session (Chrome was sent back to sign-in), the old password answers 401 and the
  new one 200. A passwordless patient gets 404 on the password page and no link to it.
- A grep for "password" on the passwordless profile matched the address
  passwordless@example.test. Second time a word search misled; search for the element.
- Milestone M5 is complete.

## 2026-11-21 QA workflow added

- The owner asked for QA agents that test through the API and Chrome DevTools, in
  parallel, on a database of their own, and file GitHub issues. Fabro fits: each run has
  its own sandbox, so one `qa` run per area is isolated from the task run and from the
  other areas. A fork node inside one workflow would share one checkout and one database.
- Probe run, 2 minutes, beside a running task: Claude Code over ACP in the sandbox gets
  the Chrome DevTools MCP tools from `~/.claude.json` with Debian's `chromium`
  (`--headless --no-sandbox`); `gh` works with the `GITHUB_TOKEN` secret passed as
  `GH_TOKEN`; five runs execute at once.
- The probe also found two harness bugs: the mail sink buffered its output when it wrote
  to a file (`python -u`), and the background hook let `(sleep 30 &)` through.
- Processes a QA run needs for its whole life (product, worker, mail sink) are started by
  a script node with `setsid nohup`: the property that broke task 02 is used on purpose.

## 2026-11-21 task 16, run 01M7ZZBVRQ7T (25 minutes, merged f72c635)

- Two review bounces, both right: no test proved the note stays out of the logs, and a
  failed note read was shown as an empty note. 2178 tests.
- Planted a clinical note in Chrome and looked for it: the appointment's clinician reads
  it; a clinician of the same department, an admin and a patient get 403 and nothing;
  it is in no API list, log line, audit row, notification or appointment row, only in
  its own table; another clinician cannot overwrite it. Check-in and the history work.
- The calendar week is the first page that passes every test and is not usable: no time
  axis, no rows, clipped blocks. Nothing in the sandbox can see that. Carried to task 17.
- First two QA issues arrived while this ran: #10 and #11, no P0.

## 2026-11-21 QA round 1 (runs 01M8001VW5XE, 01M8001WCA9V, 01M8001WY83F, 01M8001XEDGY)

- Four runs in parallel, 8 to 18 minutes each, beside the task run. 15 issues filed,
  #10 to #24: 5 P1, 10 P2, no P0. The issue bodies are good enough to hand to a task run:
  repeatable steps, observed, expected with the section number, a correlation id.
- No access-control hole, no leak of personal data and no double booking was found by
  the access, booking and public runs, which went looking for exactly those.
- Five of fifteen are one class: an input nobody expected answers 500. Hundreds of unit
  tests per task did not cover it; a hostile-input test over every route will. Task 17a.
- The journeys run found in the browser what I had found by hand and more: focus not
  moving to the first invalid field, a notice that can be forged through the address,
  cancelled notifications that read as if the appointment were on.
- Copies of the issue bodies are in `doc/qa/2026-11-21-round-1.md`, because a task run has
  no GitHub access.

## 2026-11-21 task 17, run 01M80115TVZ7 (24 minutes, merged a6609fc)

- Clean pass, no bounce. 2298 tests.
- As the demo clinician: a new Friday rule shows 4 slots in the public API at once, an
  overlapping rule is refused, a touching one accepted, deleting leaves the right 2;
  another clinician's rule answers 403. The patient list and its search show only the
  clinician's own two patients out of six. The rooms timeline names the clinician's own
  patient and nobody else.
- The time grid now has hours and rows, but measuring it showed the labels 49 px above
  the rows they name, and block text spilling out. A screenshot looked nearly right;
  the numbers did not. Carried into task 17b.
- Milestone M6 is complete, with that defect open.

## 2026-11-21 QA round 2, clinician area (run 01M802MMFCAQ, 11 minutes)

- 8 issues filed, #25 to #32: 2 P1, 6 P2, no P0. No access-control hole and no leak of
  another clinician's patients was found by a run that went looking for them.
- #25 is the grid misalignment I had measured by hand after task 17 (49 px); the run
  measured 48 px and gave the cause. #26 is new and worse: a time off of several days is
  drawn in no day, so the week looks free. Both in task 17c, before the P2 batch.
- #32 and the time off at 01:00 behind #26 are the demo seed, which still writes through
  the models. The re-seed was carried "after task 08" and never scheduled: a carried item
  with no task number does not get done. It is task 17d now, and it touches only
  `scheduling/demo_seed/`, so it runs beside task 17a.
- The two grid items I had put into task 17b moved to task 17c with the issues that
  describe them better.

## 2026-11-21 task 17a, run 01M802KYJ8DS (26 minutes, merged e412ecb)

- Plan bounced once, review bounced once. The reviewer's two blockers were the task's own
  words: the hostile test ran without a session, and the promised property test was
  missing. With sessions it found three real 500s at once (GET on pages that only accept
  POST).
- On the running stack the inputs of #10, #12, #13, #14 and #18 answer 400. In Chrome the
  sign-in page with `a@b` shows its message, keeps the address and puts focus on it.
- The reviewer rated "non-numeric Content-Length answers 500" low, because a production
  server refuses it first. The product runs on the development server, and there it is a
  500 on every API route without a session, which did not exist before this task. A
  reviewer's "low" on a task about 500s needs my own request before I accept it. Task 17b.
- The suite went from 15 to 75 seconds: the hostile test sends about 290 000 requests.
  The task said "every route" and set no time budget, so nobody was wrong. Tasks that add
  a broad test now state a budget. Fixed in task 17b, which therefore runs before 17c.
- The test fills path ids with random ones, so routes that name a record are only
  tested for "not found". Also task 17b.
- My gate command pipes each `make` into `tail`, which hides its exit code. I read the
  output for the error line instead; the command should use `set -o pipefail` or no pipe.

## 2026-11-21 task 17d, run 01M803CR8PEP (22 minutes, not merged)

- Ran beside task 17a without trouble: it touches only `scheduling/demo_seed/`, and the
  squash onto the moved `main` applied cleanly. Gates pass on the merged tree, 2344 tests.
- The seeded world is right: clinics open Monday to Friday, all 17 appointments inside
  their clinician's hours and outside time off, time off on whole local days, the
  product's own notification titles, no mail sent or pending, a second run adds nothing.
- Not merged. As the demo patient I accepted the seeded waitlist offer, then ran the
  seed with a clock two days later: `ProtectedError`, stack trace, no refresh ever again.
  The reviewer had this as finding 2, "medium, later". It is the first thing a person
  does with the demo. A review that lists a crash under "later" is a review I repeat by
  hand: second time today (task 17a, the Content-Length 500).
- On a Saturday the "today" scenarios land on Monday, finished ones included: visits
  completed in the future. The task said "today in every status" and did not say what a
  weekend is. The product allows it too; noted for the owner.
- Task 17e continues on the branch `task/17d-demo-seed` and merges both.
- To verify a run that finished behind a moved `main`: squash it locally, clone the local
  repository into the container (`-v "$PWD":/src:ro`, `git clone /src`), push only after.

## 2026-11-22 task 17b, run 01M804C63PMX stopped by the subscription limit

- Green failed after 8 minutes: "You've hit your 5-hour limit, resets 12:10am (UTC)".
  Not the task. Since the evening the subscription had carried four task runs and five
  QA runs, up to three at once.
- `fabro resume` does nothing for a failed run. `fabro rewind <id> verify_red` makes a
  new run from the checkpoint before the failed stage and starts it: 01M809JSVRXD. Plan
  and red tests kept, 8 minutes not paid twice.
- Runs beside each other are fast and each costs its share of one five-hour window. Two
  at a time from now on; QA rounds start when no more than one task run is going. If the
  limit hits again, the stage line reads "Error: ?" and the reason is in the last event
  of `fabro events <id> --json`.

## 2026-11-22 task 17e, run 01M809HZ6B4J (26 minutes, merged 3df1aa8 with 17d)

- Clean pass. Launched from a checkout of the branch that held task 17d, so the run
  built on it and the reviewer read both.
- On the stack, on a Sunday: finished visits on Friday, upcoming from Monday. As the demo
  patient I accepted the seeded offer, cancelled a seeded appointment and booked my own,
  then ran the seed with the clock 2, 4 and 6 days ahead: no error, "kept 2 appointments,
  1 entry", my rows untouched, no double booking, no mail pending.
- The squash onto `main` conflicted in `doc/backlog.md` and `doc/retro.md` only: the
  branch carried a cherry-picked process commit and `main` had moved. A run branch that
  needs a task file gets that file alone, not a commit that edits the backlog.
- The task set a budget of 10 seconds for the seed's tests; they take 16 alone. I merged
  anyway, because the number includes creating the test database. A budget needs to say
  how it is measured, or it is not a gate.
- My timing command called `uv` without the Makefile's PATH and failed after the gates
  had passed; ten minutes lost to a rerun.

## 2026-11-22 task 17b, run 01M809JSVRXD (30 minutes after the rewind, merged 58caea4)

- Clean pass, no bounce, fifteen items in one run. The rewound run kept the plan and the
  red tests of the run the subscription limit had stopped.
- Replayed on the stack: the ten issues with curl, focus and the one-time notice in
  Chrome at 375 px, the cancellation email in the inbox. `Content-Length: abc` answers
  400; a page with 1500 fields shows the product's 400 page with its reference.
- Suite: 75 seconds before, 37 on my machine and 22 in the sandbox, with 2482 tests. The
  budget said "under 30 seconds" and not where; the sandbox number is the one a run pays.
- The fix for #23 changed the two notifications the task named and left the others in
  the old date style. A task that names examples gets the examples fixed: name the rule.
- Looking at the waitlist page for the focus check showed a type that is not bookable
  online offered to a patient. Within the letter of section 5.8; noted for the owner.

## 2026-11-22 task 17c, run 01M80BGB54SD (17 minutes, merged 64d18a7, #30 left open)

- Clean pass. In Chrome at 1440 px: the 12:00 block starts 1 px under the 12:00 line
  (was 48), a time off from Wednesday to Saturday fills 07:00 to 19:00 on each day, the
  two forms of the time off page have their own ids, the repeated hour of October is
  accepted and the skipped hour of March refused with the reason, a reschedule into
  2020 says "That time has already passed".
- #30 is not fixed, and the fix made a new defect: overlapping blocks got a minimum
  width of 128 px in a 144 px column, so the second is drawn over the next day. And
  `overflow: hidden` cuts the patient's name through its letters in every 30 minute
  block. The reviewer rated the clipping "low" and could not see the rest: the proof was
  a test over the text of the style sheet.
- Merged without #30 rather than held: the two P1 fixes are worth having on `main`, and
  holding a branch cost a conflict last time. Task 17f takes the block layout.
- Third layout task on this grid (16, 17, 17c). Each said what was wrong and let the
  run choose the numbers; none could see the result. Task 17f asks for the numbers in
  the plan and names the three measurements I will take, so the plan can be checked
  against arithmetic before any code.

## 2026-11-22 task 18, run 01M80BHGNBMQ (35 minutes), first sync run

- Clean pass beside task 17c. The squash onto `main` conflicted in one product file,
  `scheduling/domain/audit_labels.py`: both tasks add entries to the same dictionary. I
  had told task 18 about the rule and it kept it; the text still collides.
- Keeping both sides is mechanical, and still product code. New workflow `sync`: setup,
  one agent that merges `main` into the branch keeping both sides, then lint, tests and
  gate. Launched with `--target owner/repo@branch` from `main`, because a branch cut
  before the workflow existed cannot name it.
- Two runs side by side pay for their speed here. A sync run is cheap if it stays at
  five minutes; if it does not, side by side is only for tasks that share no file.
- The reviewer measured `make test` at 38 to 43 seconds in the sandbox for a tree that
  takes 22 alone: two sandboxes share the machine. A time budget read under load is
  noise; I read it from my own fresh-clone run, one at a time.

## 2026-11-22 task 18 merged 42600a0, sync run 01M80DN7M194 (2 minutes)

- The sync run merged `main` into the branch, kept both sides of the one conflict, ran
  lint, tests and gate: 2 minutes 10. The diff against `main` had the size of task 18.
  A branch cut before a workflow existed cannot name it: launch with `--target`.
- As the demo admin in Chrome: create, edit, refuse, delete for the five records; every
  bad value I could think of answered on its field, none with 500; refused deletes name
  what blocks with counts; a second admin's save answers 409; the public search follows
  a deactivated hospital and a new type at once. Lighthouse accessibility 100 at 375 px.
- Looking at the specialty page showed "uses fallback.svg" for Cardiology. The demo
  codes are `demo-cardiology`, the icons answer to `cardiology`: since task 10a no demo
  specialty has shown its icon, and I checked that task in the browser. I saw an icon and
  did not ask which one. Carried into task 19.
- Suite: 2831 tests, 41 seconds on my machine with a sandbox running beside it.

## 2026-11-22 task 17f, run 01M80CQ06WM7 (23 minutes, merged f3340e6)

- Asking for the numbers in the plan worked. The plan derived column 144 px, row 68 px,
  line 18 px, three lines in 30 minutes, and chose time off as a band behind the
  appointments. My three measurements pass for every block at 1440 px and 1024 px: inside
  its column, no clipped height, lines of one height.
- Two faults I had not asked about, so nobody looked: the status icon is 20 px in an
  18 px line and pushes the time out of it; and the hidden text for screen readers is
  positioned out of flow, escapes the grid's scroll frame and makes the page scroll
  sideways by 65 px at 1024 px. Both found by measuring one level deeper (`scrollHeight`
  of a line, `scrollWidth` of the document). Carried into task 19, which reuses the grid.
- The rule for layout tasks, after four passes on this grid: state the invariant and the
  measurement, for the page, the block and the line. What is not measured is not built.
- Task 22 (FHIR) started on the second track while this was verified.

## 2026-11-22 task 22, run 01M80E2000SQ (29 minutes), sync 01M80FRVG5GR (2 minutes)

- Review bounced once: tokens, the ADR and the hostile-input case were missing at first
  read. Second sync run of the night, for one line in `mutation-equivalents.txt`.
- With curl and a token for each role: the hidden clinician is served to staff only,
  email and phone to staff only, paging runs to its end, every refusal I tried is an
  `OperationOutcome`. 3053 tests.
- The task asked for validity "proven with a tool, not by eye". The run skipped it and
  wrote "not part of this change" into the ADR; the reviewer did not notice. I ran the
  HL7 validator in a Java container: five errors, empty arrays and two invariants of the
  CapabilityStatement. A requirement that needs a new tool is the first one to be
  dropped. It is now a make target with a pinned validator and part of "done when".
- Every write under `/fhir` answers Django's 403 page for the cross-site check. The test
  client skips that check, the same hole as task 13a, one layer further. The page-form
  rule in the card now covers API routes.
- Merged with the faults named in the commit; task 22a fixes them before task 23.

## 2026-11-22 task 19, run 01M80E7BVMNV (35 minutes, merged bc0bbac)

- Review bounced once: its first pass had read a partial diff, before the pages existed.
  The squash onto a `main` that had gained the FHIR task merged without a conflict.
- In Chrome with two sessions: as admin I created a clinician user and attached a
  profile; she signed in in a second window with the temporary password; I deactivated
  her; her next request went to the sign-in page and her password was refused with the
  same message as a wrong one. My own account offers no role and no active field, and a
  forged post of both changed nothing. Moving a clinician with booked appointments to
  another department is refused with the count.
- Carried items: the public search shows the specialty icons at last; the page no longer
  scrolls sideways at 1024 px; the time line holds its icon. One remainder: beside the
  rail of a time off band the end time still ends in an ellipsis. Task 25.
- 3298 tests in 53 seconds on my machine while a sandbox ran. The "30 seconds" I wrote
  into four tasks was never checked by anything. A budget is a gate or it is a wish.

## 2026-11-22 task 22a, run 01M80G2TSWY5 (21 minutes, merged)

- Review bounced once, on the four things the task was about: the validate target, the
  sample walk, the page cut in the database, the ADR. The second reader holds a run to
  the task when the task says "done when `make fhir-validate` passes".
- From a fresh clone: `make fhir-validate` fetches Java and the pinned validator and
  validates 34 samples with 0 errors. With curl: writes answer 405 as FHIR JSON, two
  `_include` work, `Vary` and `no-store` are set, 25 bad tokens do not lock out the
  valid one.
- Every API test now goes through a client that enforces the cross-site check, 30 test
  files changed for it, and a guard test refuses the bare client. The hole of task 13a
  is closed for the third and, by construction, last time.
- The sync prompt tells its agent to take `scripts/**` from `main`; this run added a
  product script there. Narrowed the rule to the files the orchestrator wrote.

## 2026-11-22 task 20, run 01M80GDSH94F (34 minutes, merged)

- Clean pass, no bounce, and the squash onto a `main` two FHIR merges ahead applied
  without a conflict. 3511 tests.
- As the demo admin in Chrome: booked a cardiology consultation for a patient in four
  steps (every active service offered, no "first available"), cancelled it with a
  reason (without one: refused), and the freed time went at once to the oldest waiting
  entry; accepted that offer for its patient; added another patient to the waitlist; a
  manual offer with no cancelled time left that fits was refused with the reason. The
  audit log shows every step with who, what, the record and the correlation id; a POST
  to it answers 405. Four emails in the inbox, one per step.
- Not provoked by hand: a manual offer that succeeds. The only cancelled time in the
  window had just been taken by the automatic offer. The run's tests cover it.
- After "Accept for the patient" the list returns without a word. Carried into task 21.

## 2026-11-22 task 23, run 01M80HFKDRHQ (43 minutes, merged)

- Review bounced once, on a 500: `/fhir/Slot?service-type=not-a-uuid`, without a token.
  The reviewer wrote a throw-away test to prove it. The hostile-input test had not sent
  that value to that parameter.
- With a token per role: a clinician creates a Saturday rule through FHIR and both APIs
  offer 31 Saturday slots, then none after the delete; an admin's token cannot write
  another's schedule; a patient reads one Patient, a clinician two, an admin six;
  another patient's id and an absent one answer the same 403 body. 52 samples valid.
- Following `next` to the end, which I had done for one type in task 22, found that the
  links carry `_sort=name` for every type and three types refuse it. PractitionerRole
  has been unpageable since task 22. "Follow the links to the end" is a check for every
  type, so it is a test over the declaration now, not a thing I do by hand. Task 23a.
- My first Schedule body repeated `planningHorizon` from an older rule and was refused,
  correctly. I read the refusal as a defect for a minute. The outcome names the element;
  the message text says only "The request is not valid".
- 3640 tests, 69 seconds on my machine beside a sandbox and Chrome.

## 2026-11-22 task 21 failed on my time budget; the subscription limit, second time

- Task 21 did everything it was asked and its run failed: three reviews, each blocked
  only by "`make test` over 30 s". The reviewer was right to hold the task to its words
  and the words were mine. Two sandboxes shared the host; the same suite measured 22,
  32, 38 and 52 seconds that night. The run spent 27 of its 49 minutes shrinking test
  data and raising the worker count to chase a number that could not be met there.
- Rule, in the review prompt now: a time or size budget is reported, never blocking, and
  no run changes tests to meet one unless the task is about it. The budget left the task
  files. The suite's speed gets its own task with its own gate (task 26).
- For the run already going (23a) I used `fabro steer`: it reaches only the stage that
  is live, so a background loop offers the note to the review stage until it is taken.
- At 03:42 UTC both runs stopped with "You've hit your 5-hour limit, resets 5:10am":
  the window that opened at 00:10 had carried fourteen runs, two at a time. The
  session then sat idle until the owner came back at 08:36 UTC; the wakeup did not fire
  while the laptop slept. Lost: five hours of wall time, no work. `fabro rewind <id>
  <last good stage>` and a second sync launch resumed both.
- What two runs side by side cost tonight, counted: two sync runs for one-line clashes,
  one limit stop, one budget failure made of machine load. What they bought: milestones
  M7 and M8 nearly done in one night. Still worth it; the limit is the price.

## 2026-11-22 task 21 merged 8a161f8, milestone M7 complete

- Third sync run, 2 minutes 20, for `mutation-equivalents.txt` again: every task that
  touches the domain adds a line at the end of that file, so two tasks side by side
  always collide there. A file per module would not.
- In Chrome, against SQL I wrote by hand: the seven-day tiles (3 appointments, 0
  cancelled, no-show 33 %, online 0 %, waitlist 2, utilisation 60 of 12 000 minutes
  shown as 1 %), "n/a" for a day with nothing, the export by form only with ten columns
  of ids and UTC instants and its audit entry with the row count, notices shown once.
- 3747 tests, 44 seconds on my machine with one sandbox beside it.
- The admin console is whole. Left for it in task 25: lists and the dashboard table at
  375 px, the notice cookie, the stale-save page.
