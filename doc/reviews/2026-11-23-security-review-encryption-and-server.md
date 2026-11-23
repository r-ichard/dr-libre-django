# Review: task 26d items 16 and 17 (encryption at rest, the development server)

Diff `main...HEAD`, 2 files, both prose: `doc/adr/0011-security-review.md` (99 lines) and
`doc/plans/2026-11-23-security-review-encryption-and-server.md` (83 lines). No code, test,
migration, dependency, `compose.yaml`, `Dockerfile`, settings or `drlibre-specs.md` change.
Commits `98751f8` (write) changes the ADR; `3f6db3e` (check) and `e426b0f` (prove) change no
file, so the proof left no trace (check 7). The check stage ran `make lint`, `make test` and
`make gate` on this content; this review did not re-run them.

## Method

1. Plan per block, one sentence each, without re-reading: the ADR states what the code does
   for notes and holds, what a deployment adds, the owner's options; then what the container
   runs, what the dev server is safe for, what a deployment replaces. Confirmed at a glance:
   the structure, the scope, the status line. Forced to trace: every `file:line` citation,
   the DEBUG mechanism in `compose.yaml`, the hash pattern cited from ADR 0002, the spec item
   cited for the hold lifetime.
2. Citations checked against the code: `scheduling/models/booking.py:110-116`,
   `scheduling/models/access.py:109-113` and `:117-124` (the constraint is at 119-123, the
   range cited is wide but holds), `scheduling/use_cases/booking_holds.py:54`,
   `scheduling/use_cases/clinical_notes.py:55-60` (`_own_appointment`),
   `scheduling/use_cases/fhir_appointment_loading.py:27-33`,
   `scheduling/domain/audit_metadata.py:1-3`, `drlibre/settings.py:48-57`,
   `scheduling/use_cases/hold_expiry.py:14-33`, `scheduling/jobs/worker.py:41`,
   `drlibre/urls.py:191-192`, `drlibre/startup_checks.py:13-18`, `compose.yaml:2,12,18,60`,
   `Dockerfile:22,26`. All hold except the points in the findings below.
3. Authorization, double booking, schema, logging: not in scope (no code in the diff).
   Checked as claims only: the clinician-only rule for notes is real (`_is_its_clinician`,
   `clinical_notes.py:63-64`), and the audit metadata type cannot carry free text (its
   docstring). No sensitive value is written into the ADR.
4. Scope: the diff is the two files the plan named. Items 18 and 19 are not present, as the
   plan says. No dependency added. No spec edit.

## Findings

### F1 (blocking): the ADR states a false DEBUG mechanism

- `doc/adr/0011-security-review.md:67-68`: "`compose.yaml:2` sets `DEBUG: "true"` in the shared
  environment, so compose runs with DEBUG on whatever `.env.example` says."
- Risk: `.env.example` sets no `DEBUG` value at all (its only `DEBUG` mention is a comment,
  line 13). The `environment:` block at `compose.yaml:2` takes precedence over `env_file:`, so
  DEBUG is on whatever any env file says. A reader who edits `.env.example` expects a change
  that does nothing. This is the exact question of decision 17 (run with DEBUG off or on).
- Smallest fix: replace the clause with "so compose runs with DEBUG on: `environment:` overrides
  `env_file:`, and `.env.example` sets no `DEBUG`."

### F2 (later): the Dockerfile command is overridden by compose

- `doc/adr/0011-security-review.md:63-64`: "`Dockerfile:26` sets the command to `runserver`."
- Risk: the stack does not run that command. `compose.yaml:12` overrides it for `web`, and
  `compose.yaml:37` sets `run_worker` for `worker`. `Dockerfile:26` applies only to a bare
  `docker run` of the image. The ADR's conclusion holds, but the cited file is the wrong one
  for "what the container runs".
- Smallest fix: name `compose.yaml:12` as the command the stack runs, and `Dockerfile:26` as the
  image default that compose overrides.

### F3 (later): "keyed hash column, the pattern of ADR 0002" cites a pattern that is not keyed

- `doc/adr/0011-security-review.md:43-44` (and line 53, option b): a keyed hash column "the
  pattern of ADR 0002".
- `doc/adr/0002-identifiers-and-schema-guards.md:22` describes only `*_hash` columns for
  secrets, exactly 64 characters. It names no key.
- Risk: an unkeyed hash of an email address can be checked against a list of known addresses.
  A later implementer who reads "the pattern of ADR 0002" might build exactly that.
- Smallest fix: say "a keyed hash (HMAC, key from the environment, rotated under decision 16);
  ADR 0002:22 gives the column convention only."

### F4 (later): the handover citation starts at the heading

- `doc/adr/0011-security-review.md:9`: "`doc/handover.md:218` lists them". Line 218 is the
  heading "Questions that wait for the owner"; the encryption item is at line 225.
- Smallest fix: cite `doc/handover.md:218-225`.

### F5 (later): the hold lifetime cites the item marked as proposed

- `doc/adr/0011-security-review.md:29`: "A hold lasts 10 minutes (`drlibre-specs.md`, section 17,
  item 14)." Section 17 item 14 ends "These are proposed values."
- The firm statement is section 7, item 3 (`drlibre-specs.md:373-375`): "creates a booking hold
  on the slot for 10 minutes."
- Smallest fix: cite section 7, item 3, and keep section 17 item 14 as the proposed-values note.

### F6 (nit): a citation range is wider than the code

- `doc/adr/0011-security-review.md:21`: "`clinical_notes.py:1-4, 20-52`". Lines 1-3 are the
  docstring and line 4 is blank; the check is at lines 55-64.
- Smallest fix: cite `clinical_notes.py:20-52, 55-64`.

## Blocking

- F1: `doc/adr/0011-security-review.md:67-68` states a false DEBUG mechanism in the decision-17
  record. Fix: name `environment:` as the override and drop the `.env.example` claim.

## Later

- F2: `doc/adr/0011-security-review.md:63-64` cites the Dockerfile as the command the stack runs; compose overrides it.
- F3: `doc/adr/0011-security-review.md:43-44` calls the lookup hash "keyed" by reference to ADR 0002, which describes an unkeyed convention. Fix the text before anyone builds it.
- F4: `doc/adr/0011-security-review.md:9` cites handover line 218; the item is at 225.
- F5: `doc/adr/0011-security-review.md:29` cites the spec item that says "proposed values"; cite section 7, item 3.
- F6: `doc/adr/0011-security-review.md:21` citation range is wider than the code.
- Gates: the check stage ran lint, test and gate on this content; not re-run here. No timing or size budget applies to a prose diff; none measured.

## Left for the orchestrator

From the plan's "Not in this run":

- Items 18 and 19 of task 26d: the review document `doc/security-review.md`, the rule-by-rule
  table, the owner question list, the limits of ADR 0004, what was not reviewed.
- Edits to `doc/backlog/26d-security-review-written.md`, `doc/backlog.md` and `doc/handover.md`
  (the handover "Questions that wait for the owner" entries for encryption and the server, once
  the owner decides).
- Any change to `compose.yaml`, the `Dockerfile` or the server: waits for the owner's decision
  on the deployment target and on encryption.
- The last scripted gates of task 26d (`make mutate`, `make fhir-validate`) on a fresh clone,
  as the task's "Done when" states; not part of this stage.

## For the owner

1. Decision 16: choose (a) volume and backup encryption only, (b) application column encryption,
   or (c) `pgcrypto`, and say when clinical notes must be protected. The ADR's lean is (a) for
   holds now and (b) or (c) for notes before real notes are kept; the product makes no choice.
   Cost of changing: (b) needs a key from the environment, a new pinned library (approval
   needed), a keyed hash column for `visitor_email`, a migration and key rotation.
2. Decision 17: accept that the container runs Django's development server and file server with
   `DEBUG` on (`compose.yaml:2`), and name the deployment target. The replacements are listed in
   the ADR under "What a deployment replaces"; each new dependency needs approval.
