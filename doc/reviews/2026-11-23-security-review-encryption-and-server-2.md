# Review: task 26d items 16 and 17, second reader (encryption at rest, the development server)

Diff `main...HEAD`: 3 files, all prose. `doc/adr/0011-security-review.md` (+99),
`doc/plans/2026-11-23-security-review-encryption-and-server.md` (+83) and
`doc/reviews/2026-11-23-security-review-encryption-and-server.md` (+125, the earlier review
stage's document). No code, test, migration, dependency, `compose.yaml`, `Dockerfile`, settings
or `drlibre-specs.md` change (`git diff main...HEAD -- drlibre-specs.md` is empty).

Commits: `98751f8` (write) adds the ADR; `414b40a` (address) changes two lines of it. `3f6db3e`,
`e426b0f`, `9f461cd`, `44f9113` and `c489e05` change no file, so the proof left no trace (check 7).
The earlier review's F1 (false DEBUG mechanism) is fixed in the tree: `doc/adr/0011-security-review.md:67-68`
now names `environment:` as the override and says `.env.example` sets no `DEBUG`. Verified.

The earlier review document is kept; this one is a separate file so its findings stay on record.

## Method

1. Plan per block, one sentence each, without re-reading: the ADR states what protects notes and
   holds today, what a deployment adds, the owner's three options; then what the container runs,
   what the development server is safe for, what a deployment replaces. Confirmed at a glance:
   structure, scope, status line, no secret quoted. Forced to trace: every `file:line`, the
   extension claim, the keyed-hash claim, the spec items for the hold lifetime.
2. Citations checked against the tree: `compose.yaml:2,12,16-18,60`; `.env.example:13` (the only
   `DEBUG` mention, a comment); `Dockerfile:22,26`; `drlibre/settings.py:48-57`;
   `drlibre/urls.py:191-192`; `drlibre/startup_checks.py:13-18`;
   `scheduling/models/booking.py:110-116`; `scheduling/models/access.py:109-113, 117-124`;
   `scheduling/use_cases/booking_holds.py:54`; `scheduling/use_cases/hold_expiry.py:14-33`;
   `scheduling/use_cases/clinical_notes.py:20-52, 55-64`;
   `scheduling/use_cases/fhir_appointment_loading.py:27-33`; `scheduling/domain/audit_metadata.py:1-3`;
   `doc/adr/0002-identifiers-and-schema-guards.md:18-28`; `doc/handover.md:218-225`;
   `drlibre-specs.md:373` (section 7.1 step 3), `:835-836` (section 17 item 14, "proposed values").
   Grep: no `encrypt`, `pgcrypto`, `staticfiles`, `whitenoise`, `gunicorn` in product code.
   Accurate except the points in the findings.
3. Authorization, double booking, schema, logging: no code in the diff. Checked as claims only:
   notes are readable and writable only by the appointment's clinician (`_is_its_clinician`,
   `clinical_notes.py:63-64`); the audit metadata type carries no free text. No sensitive value
   or published development value is written into the ADR (grep).
4. Scope: exactly the two items of the plan's slice. Items 18 and 19 and `doc/security-review.md`
   are absent, as the plan says. No dependency. No spec edit.

## Findings

### F1 (blocking): the ADR says no extension is used; one is

- `doc/adr/0011-security-review.md:34`: "PostgreSQL 15 keeps its data ... No `pgcrypto` or other
  extension is used."
- `scheduling/migrations/0001_initial.py:10,23` installs `BtreeGistExtension()`. The ADR is the
  record the owner decides from, and its "what protects the data today" list is wrong on this point.
- Risk: the owner reads that the database has no extensions and reasons about option (c)
  (`pgcrypto`, "needs the extension") from a false baseline. The `btree_gist` extension is the
  one ADR 0002 names as trusted.
- Smallest fix: replace the sentence with "No `pgcrypto` is used; the only extension is
  `btree_gist` (`scheduling/migrations/0001_initial.py:23`), for the booking overlap constraint."
- Outcome: fixed. `doc/adr/0011-security-review.md:34` now names `btree_gist` and says no `pgcrypto`.
  No test: the change is prose, and no test can fail on it. Checked by grep: `BtreeGistExtension` at
  `scheduling/migrations/0001_initial.py:10,23` is the only extension install; the constraint it serves
  is the `ExclusionConstraint` at line 1256.

### F2 (later): the handover citation starts at the heading

- `doc/adr/0011-security-review.md:9`: "`doc/handover.md:218` lists them". Line 218 is the heading;
  the encryption item is at `doc/handover.md:225`.
- Smallest fix: cite `doc/handover.md:218-225`.

### F3 (later): the clinical notes range is wider than the code

- `doc/adr/0011-security-review.md:21`: "`clinical_notes.py:1-4, 20-52`". Lines 1-3 are the module
  docstring and line 4 is blank. The access check is `_own_appointment` at 55-60 and
  `_is_its_clinician` at 63-64.
- Smallest fix: cite `clinical_notes.py:20-52, 55-64`.

### F4 (later): "keyed hash, the pattern of ADR 0002" cites an unkeyed convention

- `doc/adr/0011-security-review.md:43-44` (and option (b), line 52): "a keyed hash column for
  lookups, the pattern of ADR 0002".
- `doc/adr/0002-identifiers-and-schema-guards.md:22` defines only `*_hash` columns for secrets,
  64 characters. It names no key.
- Risk: an unkeyed hash of an email address can be matched against a list of known addresses. An
  implementer who reads "the pattern of ADR 0002" may build exactly that.
- Smallest fix: say "a keyed hash (HMAC, key from the environment, rotated under Decision 16); ADR
  0002:22 gives the column naming convention only."

### F5 (later): the hold lifetime cites the item marked as proposed

- `doc/adr/0011-security-review.md:29`: "A hold lasts 10 minutes (`drlibre-specs.md`, section 17,
  item 14)." Section 17 item 14 ends with "These are proposed values." (`drlibre-specs.md:836`).
- The firm statement is section 7.1 step 3 (`drlibre-specs.md:373`).
- Smallest fix: cite section 7.1 step 3 for the ten minutes; keep section 17 item 14 as the
  proposed-values note.

### F6 (later): the Dockerfile line is the image default, not what the stack runs

- `doc/adr/0011-security-review.md:63`: "`Dockerfile:26` sets the command to `runserver`."
  `compose.yaml:12` overrides it for `web`, and `compose.yaml:37` overrides it for `worker`.
- The conclusion holds. The wording should say which command the stack runs.
- Smallest fix: "`Dockerfile:26` is the image default; `compose.yaml:12` is the command the `web`
  service runs."

## Blocking

- F1: `doc/adr/0011-security-review.md:34` states no extension is used; `btree_gist` is installed at
  `scheduling/migrations/0001_initial.py:23`. Fix: name `btree_gist` and say no `pgcrypto`. Outcome: fixed (see F1 above; no test, prose only).

## Later

- F2: `doc/adr/0011-security-review.md:9` cites handover line 218 (the heading); cite 218-225.
- F3: `doc/adr/0011-security-review.md:21` cites `clinical_notes.py:1-4`; cite 20-52 and 55-64.
- F4: `doc/adr/0011-security-review.md:43-44` calls the lookup hash "keyed" by reference to ADR 0002, which describes an unkeyed convention. Fix the text before anyone builds it.
- F5: `doc/adr/0011-security-review.md:29` cites the spec item marked "proposed values"; cite section 7.1 step 3.
- F6: `doc/adr/0011-security-review.md:63` cites the Dockerfile as the command the stack runs; compose overrides it.
- Gates: the check stage ran `make lint`, `make test` and `make gate` on this content (5263 passed).
  Not re-run here: prose only, nothing a gate reads. No timing or size budget applies; none measured.
- `make mutate` and `make fhir-validate` (named in the task's Done-when list): not run by this
  stage. Docs-only change, not affected; the orchestrator runs them on a fresh clone.

## Left for the orchestrator

From the plan's "Not in this run":

- Items 18 and 19 of task 26d: `doc/security-review.md`, the rule-by-rule table, the owner question
  list, the limits of ADR 0004, what was not reviewed.
- Edits to `doc/backlog/26d-security-review-written.md`, `doc/backlog.md` and `doc/handover.md`
  (the "Questions that wait for the owner" entries for encryption and the server, once the owner
  decides).
- Any change to `compose.yaml`, the `Dockerfile` or the server: waits for the owner's decision on
  the deployment target and on encryption.

## For the owner

1. Decision 16: choose (a) volume and backup encryption only, (b) application column encryption, or
   (c) `pgcrypto`, and say when clinical notes must be protected. The ADR's lean is (a) for holds
   now and (b) or (c) for notes before real notes are kept; the product makes no choice. Cost of (b):
   a key from the environment, a new pinned library (approval needed), a keyed hash column for
   `visitor_email`, a migration and key rotation.
2. Decision 17: accept that the container runs Django's development server and file server with
   `DEBUG` on (`compose.yaml:2`), and name the deployment target. The replacements are listed in the
   ADR under "What a deployment replaces"; each new dependency needs approval.
