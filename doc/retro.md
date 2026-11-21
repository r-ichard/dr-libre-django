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
