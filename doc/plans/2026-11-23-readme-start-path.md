# Task 27c item 1: README a person can start from

Slice: item 1 only (README). Item 2 (`make smoke`) is not in this run.

## Focal point

`README.md` (today: title, one line, `make audit` note, FHIR section, DEBUG-off section). It must
open with what DrLibre is, then start, accounts, first walk, stop, checks, FHIR, DEBUG off.

## Blocks

Each block is one edit to `README.md`. No other file changes.

1. **Title and purpose.** Replace the one-line intro with the first two sentences of
   `drlibre-specs.md` section 1, verbatim: "DrLibre is an appointment scheduling product for
   hospitals." and "Anyone can search hospitals, clinicians and specialties, see the next free
   appointment times, and book one without signing in or choosing a password." (sentences start at
   line 13 of `drlibre-specs.md`; check with `sed -n '13,14p'` before copying). Drop "Setup and the
   working rules are in CLAUDE.md" from here; it moves to Checks.
2. **Start it.** `## Start it`, first the clone (needs git): `git clone https://github.com/r-ichard/dr-libre-django.git drlibre-try && cd drlibre-try`
   (source: `doc/handover.md` line 72; `git remote` confirms the URL). Then `docker compose up --wait`
   (migrates, returns when `/api/v1/health` answers; Compose reads `.env.example` directly, so no `cp`), `docker compose exec web python manage.py seed_demo`, product at
   `http://127.0.0.1:8000`, mail inbox at `http://127.0.0.1:8025`. Marked "needs Docker". Source:
   `doc/handover.md` "Run it" lines 73-76, `compose.yaml`.
3. **Demo accounts.** `admin@example.test`, `clinician@example.test`, `patient@example.test`.
   Password is the value of `DEMO_PASSWORD` in `.env.example`; the README names the file and key,
   does not repeat the value. Source: `scheduling/demo_seed/seed_support.py`, `.env.example`.
   A visitor needs no account (one sentence, from handover line 81-82).
4. **First walk.** `## First walk`: numbered steps from `doc/handover.md` lines 84-92 (admin:
   hospital with time zone, specialty, department, room, appointment type with colour and
   "Bookable online", user with role Clinician and temporary password, Clinicians: attach profile;
   clinician: Availability rule per weekday; visitor: start page, pick a time, email, code from
   inbox, confirm; clinician calendar shows it). Sign-in page is `/sign-in`. Marked "needs Docker"
   and "not walked by this run" (the walk was done on `6d98501`, handover line 84).
   `open` (macOS) becomes the plain address.
5. **Stop and forget.** `docker compose down -v`; say `-v` deletes the database volume and the
   demo data. Marked "needs Docker".
6. **Checks.** `## Checks`. Commands with where each runs and what it needs:
   - `make test`, `make lint`, `make gate`, `make mutate`: host after `make setup` (uv,
     local PostgreSQL). `docker compose exec web make test` runs the suite in the container
     (Dockerfile installs `make`). Marked "needs Docker" for the container form.
   - `make fhir-validate`: needs network and Java; installs `default-jre-headless` with `apt-get`
     when Java is absent, so needs root. Fetches the pinned HL7 validator.
   - `make audit`: queries a vulnerability service over the network; run before a hand-over and
     after any change to `uv.lock`; not part of `make test` (moved from line 3 of the old README).
   - One line: working rules are in `CLAUDE.md`.
7. **FHIR API.** Unchanged, byte for byte, lines from `## FHIR API` to the end of "Validate".
8. **Running with DEBUG off.** Unchanged. Four refusals, the `.env.example` note, `seed_demo`
   refusal.

Order in the file: 1, 2, 3, 4, 5, 6, 7, 8.

## Files to touch, in order

1. `README.md` only.
2. `doc/plans/2026-11-23-readme-start-path.md` (this file), `scratch/plan.path`.

## Files deliberately not touched

- `drlibre-specs.md` (owner text, never edited by a run).
- `doc/handover.md` (orchestrator's; the walk is copied, not moved).
- `doc/backlog/27c-readme-smoke-test.md` (orchestrator updates status).
- `Makefile`, `compose.yaml`, `.env.example`, `scripts/*`, all code, all tests (no behaviour).
- Any new file beside the README (task rule).
- No smoke test, no `make smoke` target, no mention of `make smoke` in the README (item 2).

## Commands the README will show, and how this run verifies them

- `make test`, `make lint`, `make gate`, `make mutate`, `make fhir-validate`: run in the sandbox
  after `make setup`. Must pass before the README claims them.
- `make audit`: run in the sandbox if it has network; if not, the README note says it needs
  network and the run reports that it did not run.
- `docker compose ...` and `curl` lines: sandbox has no Docker assumed; marked "needs Docker".
  Run `docker compose version` first; if Docker exists, the run may execute `up --wait` and
  `seed_demo`, otherwise the lines stay marked and reported as not executed.
- DEBUG-off section: each of the four refusals checked by reading `drlibre/settings.py`
  (named variables present). If one does not match the code, the section is corrected to the
  code and the mismatch is reported; no product change.

## Invariants that must not break

- No secret in the README: no real token, no password value; `DEMO_PASSWORD` is named, not printed.
- FHIR section and DEBUG-off section unchanged in text.
- Every command in the README is either run in the sandbox or marked "needs Docker" /
  "needs network" / "needs root".
- No claim that the first walk was re-run.

Blast radius: documentation only. No runtime, data, auth or audit path changes.

## Failing tests first

None. Item 1 changes no behaviour (CLAUDE.md "A task that changes no behaviour"). Route this
run to `fabro run tests-and-docs`: plan, write, prove, review, last gates, no red gate. The
red-gate workflow cannot pass for it (27a3). The "prove" step is the command checks above.

## Trust boundaries and validation

None crossed by the change. The FHIR curl examples contain only placeholders (`$TOKEN`,
`<service id>`); the existing text is kept as is.

## Domain entities used (CLAUDE.md §3 vocabulary)

Visitor, Patient, Clinician, Admin, Hospital, Specialty, Department, Room, AppointmentType,
AvailabilityRule, Appointment, BookingHold, VerificationCode. Public word "provider" is used in
the walk only where the start page shows it; the admin step says "a user with the role
Clinician".

## What I will not do

- No new file, no docs site, no `CONTRIBUTING`, no badges.
- No rewrite of the FHIR section or the DEBUG-off section.
- No reordering of FHIR or DEBUG-off sections beyond what the order list requires.
- No script that checks README commands against the Makefile (not asked; a later item decides).
- No change to `doc/handover.md` or the backlog file.

## Risks

- The first walk and the Docker commands cannot be run in the sandbox unless Docker exists; they
  are marked and the orchestrator verifies them on the host.
- `make fhir-validate` needs root for `apt-get`; the README says so rather than hiding it.

## Architect review

Reviewer: second reader, read-only on source. Verdict: **revise**.

1. **Missing first step (material).** Block 2 starts at `docker compose up --wait`. The task says the
   README must serve a person who has Docker and nothing else, so it must first say how to get the
   code. `doc/handover.md` line 72 has `git clone https://github.com/r-ichard/dr-libre-django.git
   drlibre-try && cd drlibre-try`; `git remote` confirms that URL. Add it as the first command of
   `## Start it`, before `docker compose up --wait`. Compose reads `.env.example` directly
   (`env_file:`), so no `cp` step is needed; the plan is right to omit it.
2. **Wrong source range (fix the pointer).** Block 1 cites `drlibre-specs.md` lines 11-16. Section 1
   heading is at line 11 of `drlibre-specs.md`; the sentences are at lines 13-17. Cite the
   sentences by text, or by the correct lines, and check them with `sed -n` before copying.
3. **Ladder: fine.** One file, documentation only, no new file, no dependency, no refactor. Slice
   (item 1 of 27c) is coherent and leaves the product whole; item 2 is correctly excluded.
4. **Test-first: accepted as stated.** No behaviour changes, so no red test. Routing to
   `tests-and-docs` is what CLAUDE.md prescribes. The "prove" step is the command checks, which the
   plan already lists; keep them.
5. **Security: fine.** No secret value printed. `DEMO_PASSWORD` named, value not repeated. FHIR
   examples use placeholders. Four DEBUG-off refusals match `drlibre/settings.py` (lines 16-19, 56):
   the run must still check each by reading, as the plan says.
6. **Vocabulary and layer: fine.** Entities match CLAUDE.md §3. "Provider" used only where the start
   page shows it, as CLAUDE.md's public-word rule requires.
7. **Commands: fine.** `Dockerfile` installs `make` (container `make test` is valid). `fhir_validate.sh`
   runs `apt-get` when Java is absent, so "needs root" is correct. `compose.yaml` sets `DEBUG: "true"`,
   so `seed_demo` works under compose.

Revision asked: add the clone step (item 1 above), fix the spec line pointer (item 2), then
re-read and proceed.

## Revision (after architect review)

- Item 1 addressed: `## Start it` opens with the `git clone ... && cd drlibre-try` line, from
  `doc/handover.md` line 72. Git is named as a requirement next to Docker ("Docker and git").
- Item 2 addressed: sentences cited by text, with their start at `drlibre-specs.md` line 13
  (verified), not 11-16.
- Items 3 to 7: accepted as written, unchanged. Checked again: `/sign-in` is the route
  (`drlibre/urls.py` line 127); `DEBUG: "true"` is set for `web` in `compose.yaml` line 2;
  `DEMO_PASSWORD` is set in `.env.example` line 14 and the README names the key, not the value.
- Walk step "open" on macOS becomes the plain address; the walk is copied, not re-run.

## Architect re-review (after revision)

Verdict: **approve**. Both material reasons from the first review are resolved in the plan body:

- Clone step is the first command of `## Start it`; `doc/handover.md` line 72 is that line and matches `git remote` origin.
- Spec sentences start at `drlibre-specs.md` line 13 (checked: "## 1. Purpose" at line 11, sentences at 13-14).

Re-checked, no new issues: `make fhir-validate` and `make audit` exist in the Makefile; `make smoke` is absent (item 2 excluded, correctly); the Dockerfile installs `make`; `DEMO_PASSWORD` is named, not printed; the four DEBUG-off refusals are in `drlibre/startup_checks.py`. Not re-checked: that `web` inherits `DEBUG: "true"` from the compose anchor. The run must confirm it when it reads the DEBUG-off section.
