# Review: task 26d items 16 and 17, second reader, third pass (encryption at rest, the development server)

Diff `main...HEAD`: 4 files, all prose. `doc/adr/0011-security-review.md` (+99),
`doc/plans/2026-11-23-security-review-encryption-and-server.md` (+83), and two review documents from
earlier passes (`doc/reviews/2026-11-23-security-review-encryption-and-server.md` and `-2.md`). No code,
test, migration, dependency, `compose.yaml`, `Dockerfile`, settings or `drlibre-specs.md` change.

The previous verdict (`scratch/review.verdict`, `revise`) had one blocker: the ADR said no PostgreSQL
extension is used. That is fixed: `doc/adr/0011-security-review.md:34` names `btree_gist` and the only
install, `scheduling/migrations/0001_initial.py:10,23` (`BtreeGistExtension()`), is the only extension
in the tree. Verified this pass by grep.

## Method

1. Plan per block, one sentence each: the ADR states what protects notes and holds today, what a
   deployment adds, the owner's three options; then what the container runs, what the development
   server is safe for, and what a deployment replaces. Confirmed at a glance: structure, scope, status
   `proposed`, no secret value quoted. Traced: every citation, the `btree_gist` claim, the worker call
   of `expire_booking_holds` (`scheduling/jobs/worker.py:10,41`), the spec hold lifetime
   (`drlibre-specs.md:373`, `:835`, section 17 item 14).
2. Citations checked against the tree and all hold except the points under Later: `compose.yaml:2,12,18,35,37,60`;
   `Dockerfile:22,26`; `drlibre/settings.py:48-57`; `drlibre/urls.py:191-192`; `drlibre/startup_checks.py:13-18`;
   `scheduling/models/booking.py:110-116`; `scheduling/models/access.py:109-113, 117-123`;
   `scheduling/use_cases/booking_holds.py:54`; `scheduling/use_cases/hold_expiry.py:14-33`;
   `scheduling/use_cases/clinical_notes.py`; `scheduling/use_cases/fhir_appointment_loading.py:27-33`;
   `scheduling/domain/audit_metadata.py:1-3`; `.env.example:13` (the only `DEBUG` mention, a comment).
3. Grep for `encrypt`, `pgcrypto`, `staticfiles`, `whitenoise`, `gunicorn` in product code: no hit.
4. Authorization, double booking, schema and logging: no code in the diff. Checked as claims only. Notes
   are readable and writable by the appointment's clinician alone (`clinical_notes.py:55-64`).
5. Scope: exactly the two items of the plan's slice. Items 18 and 19 and `doc/security-review.md` are
   absent, as the plan says. No dependency. No spec edit.

## Findings

### F1 (later): the handover citation points at the heading

- `doc/adr/0011-security-review.md:9`: "`doc/handover.md:218` lists them". Line 218 is the heading
  "Questions that wait for the owner"; the encryption item is at `doc/handover.md:225`.
- Risk: none to the decision; the reader lands one heading early.
- Smallest fix: cite `doc/handover.md:218-225`.

### F2 (later): the clinical notes range is wider than the code

- `doc/adr/0011-security-review.md:22`: "`clinical_notes.py:1-4, 20-52`". Lines 1-3 are the module
  docstring and line 4 is an import. The access check is `_own_appointment` at 55-60 and
  `_is_its_clinician` at 63-64.
- Smallest fix: cite `clinical_notes.py:20-52, 55-64`.

### F3 (later): "a keyed hash, the pattern of ADR 0002" names an unkeyed convention

- `doc/adr/0011-security-review.md:44`: "needs a keyed hash column for lookups, the pattern of ADR 0002".
- `doc/adr/0002-identifiers-and-schema-guards.md:22` defines `*_hash` columns for secrets, 64 characters,
  with no key. An unkeyed hash of an email address can be matched against a list of known addresses.
  An implementer who reads "the pattern of ADR 0002" may build exactly that.
- Risk: a wrong design lead in the option the owner would pick. Not a defect in code (none exists).
- Smallest fix: replace "the pattern of ADR 0002" with "an HMAC keyed from the environment, rotated under
  Decision 16; ADR 0002's `*_hash` columns are unkeyed and are not the model".

### F4 (later): one verification pass only, no test for prose

- The ADR's claims are checked by reading and grep. No test can fail on it. Recorded so the owner knows
  nothing mechanical guards the citations; a later drift will not be caught.

## Blocking

None.

## Later

- F1 to F4 above.
- Commits: `3f6db3e`, `e426b0f`, `9f461cd`, `44f9113`, `c489e05` change no file, so the proof left no
  trace (check 7).

## Left for the orchestrator

- Items 18 and 19 of `doc/backlog/26d-security-review-written.md`: the review document, the rule-by-rule
  table, the owner question list (`doc/security-review.md`). Not in this run.
- Edits to `doc/backlog/26d-security-review-written.md`, `doc/backlog.md` and `doc/handover.md`
  (orchestrator, after the review).
- Any change to compose, the Dockerfile or the server: waits for the owner's decision on target and
  encryption.

## For the owner

1. The encryption choice in ADR 0011 Decision 16: (a) volume and backup encryption only, (b) application
   column encryption, or (c) `pgcrypto`, and by when clinical notes must be protected.
2. Accept that the container runs Django's development server (`Dockerfile:26`, `compose.yaml:12`), that
   it is for one user on `127.0.0.1` only, and that the deployment target is open.
3. Whether `doc/handover.md` drops the two items from "Questions that wait for the owner" once decided.
   Orchestrator's edit.

## Verdict

approve. No blocker. The only remaining issues are the citation and wording points in Later.
