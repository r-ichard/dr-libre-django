# Plan: task 26d items 16 and 17 (encryption at rest, the development server)

Slice: items 16 and 17 (the whole of this run's scope). Items 18 and 19 and `doc/security-review.md` are another run.

Focal point: one new decision record, `doc/adr/0011-security-review.md`, status proposed, for the owner. Prose only. No code, no tests, no change to `compose.yaml`, the `Dockerfile`, models, settings or `drlibre-specs.md`.

## Blocks

1. **`doc/adr/0011-security-review.md` (new), the only file written.** Header in the style of ADR 0010 (`Status: proposed, 2026-11-23, for the owner to accept. Task 26d, items 16 and 17.`), then:
   - **Context**: two paragraphs. Both gaps were already recorded as open points (`doc/adr/0002-identifiers-and-schema-guards.md:28`, `doc/backlog/02-domain-model.md:50`), and `doc/handover.md:225` lists them as waiting for the owner.
   - **Decision 16, what protects the data today**: one short list, each line citing its file and line. Clinical notes: plain `CharField` (`scheduling/models/booking.py:110-116`); reads and writes only by the appointment's clinician, server side (`scheduling/use_cases/clinical_notes.py:1-4, 20-52`); notes returned by FHIR only to the owning clinician (`scheduling/use_cases/fhir_appointment_loading.py:30-36`); audit names the field only and omits notes and reasons (`scheduling/domain/audit_metadata.py:3`). Visitor hold: plain `visitor_*` fields (`scheduling/models/access.py:109-113`); short life, and expired holds are deleted (`scheduling/use_cases/hold_expiry.py:20-35`; ten minutes per `drlibre-specs.md` section 17, item 14). Transport: `HTTPS_ONLY` and HSTS in `drlibre/settings.py`; compose serves plain HTTP on `127.0.0.1`. Database: named volume `database`, no port published, no `pgcrypto` (`compose.yaml`, `db` service). Nothing in the code encrypts a column.
   - **Decision 16, what a deployment must add**: encrypted storage under the database volume and its backups (host or volume level); TLS in front of the product; a documented key-management owner. Note the constraint: `visitor_email` has a unique constraint and an exact-match lookup (`scheduling/models/access.py:117-124`, `scheduling/use_cases/booking_holds.py:54`). Column encryption that randomises values breaks both, so it needs a keyed `*_hash` column, the pattern of ADR 0002.
   - **Decision 16, the choice left to the owner**: three options with cost, no pick made. (a) Volume and backup encryption only: no code, no dependency; does not protect against a database operator. (b) Application column encryption: key from the environment or a secret store, a pinned library (new dependency, needs approval), a keyed hash column for `visitor_email`, a migration, key rotation. (c) In-database encryption (`pgcrypto`): extension required, key handling in SQL, query-log exposure risk. The plan's lean, stated as a lean: (a) now, because holds are short-lived; the notes decision (b or c) before real patient notes are held. The owner decides.
   - **Decision 17, what the container runs**: `Dockerfile:26` CMD `runserver 0.0.0.0:8000`; `compose.yaml` `web` command runs `migrate` then `exec runserver` (line 12); `DEBUG: "true"` is set in the shared environment (compose line 2-3), so compose always runs with DEBUG on, whatever `.env.example` says; the published port is `127.0.0.1:8000` (compose ports); the source is bind-mounted (`.:/app`). Static files: no `staticfiles` app and no whitenoise; Django's `serve` view answers `/static/` (`drlibre/urls.py:191-192`, its comment says local-only and works with DEBUG off). The `worker` service uses the same image for `run_worker`.
   - **Decision 17, safe for**: one user on one machine, reached on `127.0.0.1`, data that is test or demo data. Caveat: inside the container `runserver` listens on all interfaces; only the host port mapping keeps it local. Any other network exposure (host networking, a changed port mapping) is outside what this allows.
   - **Decision 17, what a deployment replaces**: `runserver` with a production WSGI server (a new pinned dependency, needs approval); static files served by a reverse proxy or `collectstatic`-style step, not `serve`; TLS termination and `HTTPS_ONLY=true`, `HSTS_SECONDS`, `TRUSTED_PROXY_COUNT` set; `DEBUG` off in the deployment's own compose file (the file here hard-codes it on); no bind mount of source; migrations as a separate job, not in the web start command; a non-dev install (`uv sync --locked` installs the dev group by default, `Dockerfile:22`); a real `SECRET_KEY` (`drlibre/startup_checks.py` refuses the published one when DEBUG is off).
   - **For the owner**: (1) the encryption choice above; (2) accept the statement that the container is a development server and the deployment target is open; (3) whether `handover.md` should drop the two items from "waiting for the owner" once the owner decides (the orchestrator's call, not this run's).
2. **`scratch/plan.path`**: one line, the path of this plan. `scratch/` is gitignored.

## Files to touch, in order

1. `doc/adr/0011-security-review.md` (new).
2. `scratch/plan.path` (new, gitignored).
3. This plan file (already written).

## Files deliberately not touched

- `drlibre-specs.md` (never edited by a run).
- `doc/security-review.md`, items 18 and 19 (another run).
- `doc/backlog/26d-security-review-written.md`, `doc/backlog.md`, `doc/handover.md`: orchestrator edits. The handover's "waiting for the owner" line stays until the owner decides.
- `compose.yaml`, `Dockerfile`, `.env.example`, `drlibre/settings.py`, any model, migration, use case or test. The ADR describes; it does not change.

## Invariants and blast radius

- Documentation only. No behaviour, no schema, no audit entry, no dependency change. Nothing a gate could newly fail: `make gate` caps comments in Python files only, and no test reads ADR files (checked: no reference to `doc/adr` in tests or scripts).
- Facts in the ADR must match the files at the commit. The writer re-reads each cited line with `grep -n` before writing it.
- No secret, no real key, no real address in the ADR. The published development values are named only as "published development values", not quoted.
- Spec text is quoted only by section number and paraphrase; no edit.

## Failing tests first

None. Items 16 and 17 say "prose" and "no code", and §10 applies to code. The verify stage runs `make lint`, `make test` and `make gate` as the regression check, which a docs-only change must still pass.

## Trust boundaries crossed

None are changed. The ADR describes three existing ones: browser to `runserver` (over HTTP on `127.0.0.1` here), `web` to PostgreSQL (internal network, `db` publishes no port), and host to container (the published port). Authorization of clinical notes is cited as server-side in the use case, not re-verified in this run beyond the lines cited.

## Domain entities (CLAUDE.md §3 vocabulary)

ClinicalNote (on an Appointment, owned by a Clinician), BookingHold (holds a Visitor's details until verification), Appointment, Clinician, Admin, Patient.

## What I will not do

- No encryption library, no key store, no migration, no WSGI server, no compose or Dockerfile edit. These are the owner's choices, and a dependency needs approval and a pin.
- No recommendation dressed as a decision. The lean in Decision 16 is marked as a lean.
- No rewrite of the spec's open points or of ADR 0002 (its open point stays as written).

## Not in this run

- Items 18 and 19: the review document, the rule-by-rule table, the owner question list (`doc/security-review.md`).
- Edits to `doc/backlog/26d-security-review-written.md`, `doc/backlog.md` and `doc/handover.md` (orchestrator, after the review).
- Any change to compose, the Dockerfile or the server: that waits for the owner's decision on target and encryption.

## Architect review

Verdict: approve. Docs only, one new file, slice matches the task's items 16 and 17, and every
cited fact I re-checked against the tree at this commit holds.

Checked:
- Ladder: prose ADR, no code, no dependency, no compose or Dockerfile change. Smallest sufficient change, in the right place (`doc/adr/`).
- Facts: `compose.yaml` lines 2-3 (`DEBUG: "true"`), 12 (`runserver`), 18 (`127.0.0.1:8000`), 60 (`database` volume); `Dockerfile:22` and `:26`; `scheduling/models/booking.py:110-116`; `scheduling/models/access.py:109-113` and `:117-124`; `scheduling/use_cases/booking_holds.py:54`; `scheduling/use_cases/hold_expiry.py:14-33`; `drlibre/urls.py:191-192`; `drlibre/settings.py:48-57`; `drlibre/startup_checks.py`; `drlibre-specs.md` section 17 item 14 (10 minute hold). No `pgcrypto`, `whitenoise`, `staticfiles` or `gunicorn` in the tree. No encryption code exists.
- Clinical note access: `scheduling/use_cases/clinical_notes.py` and the FHIR loader confirm owner-only reads. The only other readers are demo seed and tests.
- Vocabulary: ClinicalNote, BookingHold, Appointment, Clinician, Admin, Patient, Visitor match CLAUDE.md §3.

Items to fix while writing (not reasons to revise):
- Block 1, Decision 16 citation: the FHIR owner filter is `scheduling/use_cases/fhir_appointment_loading.py:27-32`, not `30-36`. Cite `27-33`.
- Block 1, handover citation: the heading is `doc/handover.md:218` ("Questions that wait for the owner"); the list is at `:221-226`. The phrase "waiting for the owner" is the heading's, not a literal line at 225. Cite the heading.
- Verification: the task's Done-when list also names `make mutate` and `make fhir-validate`. This is a docs-only change and they cannot be affected, but the run should still report them as run or as skipped, not omit them.

Test-first: none. Justified by items 16 and 17 ("prose", "no code") and §10 scope (code only). Regression check named (`make lint`, `make test`, `make gate`).
Security: no trust boundary changes. Secrets: the ADR names the published development values but must not quote them (plan already says so).
Architecture, transactions, errors: not applicable to a docs change.
Scope: the plan delivers both items in full. Items 18 and 19 and `doc/security-review.md` are correctly excluded. `drlibre-specs.md` is not touched.
