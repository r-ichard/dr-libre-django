# Review: task 22, FHIR API, tokens and public resources (2026-11-22), second pass

Scope: `git diff main...HEAD`, 48 files, after the address stage. Commits after `verify_green` up to
`prove` change tests and `mutation-equivalents.txt` only: no product or migration line moved in proof.
Re-run on this checkout: `make lint` clean, `make gate` clean, token tests (38) pass. Full `make test`
and `make mutate` not re-run here; the check stage reports 3018 passed in 45.5 s.

## What the diff does (one sentence per block)
- Declaration + pure mappers (`domain/fhir_*.py`): one table routes, parses, and describes seven resources.
- `use_cases/fhir_reads.py`: reads through `bookable_types` and `listable_profiles`, the same rules as the
  application API (`search_catalog.py:36-49`); `Viewer.PUBLIC` or `STAFF`.
- `use_cases/api_tokens.py` and the `api_tokens` command: issue, list and revoke a hashed token, audited with ids only.
- `views/fhir/views.py`: size limits, Accept, bearer resolution, route; any exception becomes an `OperationOutcome` 500.
Confirmed at a glance: the shared visibility extraction, hash-only storage (`models/access.py`), middleware 500
mapping, the `fhir_not_exposed` marker. Forced a trace: `_viewer` header handling (`views.py:97`) and `is_full`/`record_hits`.

## Findings
1. Resolved from the first pass: tokens, ADR 0005, data-model entry, model tests, audit labels, hostile-input
   case all exist now (`use_cases/api_tokens.py`, `doc/adr/0005-fhir-conventions.md`, `audit_labels.py:13`).
2. **Later.** `scheduling/use_cases/rate_limits.py` `is_full` runs before the token lookup, so an attacker who burns
   20 failures from a shared address locks valid bearer clients on that address for the window (same trade-off as
   sign-in). Smallest fix: skip the per-address check when the token resolves. Record in ADR 0005.
3. **Later.** `is_full` then `record_hits` is not under the advisory lock `rate_limits.py:60` uses for the other
   scopes, so concurrent failures may overshoot the limit by a few. Fix: take `_lock_keys` in `resolve_token` failure path.
4. **Later.** Method not allowed answers 404 (`views.py:70`). Documented in the plan and follows ADR 0004; revisit if FHIR clients need 405 + `Allow`.
5. **Later.** `fhir_reads.py` is 275 lines, near the 300 target; `_included` ignores the `viewer` for
   `PractitionerRole:organization`, fine today (departments are public), recheck when task 23 adds private resources.
6. **Later.** `_candidates` loads every matching id then slices in Python; bounded queries, but memory grows with rows. Acceptable at hospital scale.
7. Tests: derived from the spec table and the plan; both directions of the capability check, query bound
   (`test_fhir_public_resources.py:144`), planted token, cookie and address never authenticate, 401/429 present.
   No assertion that passes forever found.
8. Scope and dependencies: no dependency added by this diff beyond what was planned; nothing unrequested in admin files.

## Blocking
None.

## Later
- Per-address lockout also blocks valid tokens (finding 2).
- Failure counter not under the advisory lock (finding 3).
- 404 rather than 405 for non-read methods (finding 4).
- Watch `fhir_reads.py` size and `_included` visibility when task 23 lands (finding 5).
- Confirm `make mutate` passes with the 14 new lines of `mutation-equivalents.txt`, each with a real reason.
