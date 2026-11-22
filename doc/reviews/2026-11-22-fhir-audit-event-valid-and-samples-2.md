# Review 2: task 24a after the address stage

Diff base `0ef2823` (no local `main` in this sandbox). Proof commit `20de887` touched `scheduling/views/fhir/test_samples.py` only. Nothing was re-run by me; I read the diff. `check` passed in the pipeline (lint, 4017 tests, gate).

## Confirmed at a glance
- ADR 0007 now exists and covers the collation sentence, the `action` search reading `type.code`, the action mapping and the `entity.detail` allow-list (`doc/adr/0007-fhir-appointment-and-the-rest.md`).
- `fhir_busy_slots.py` holds the busy intervals; `fhir_slot_reads.py` only imports it.
- `views.py:98` returns `()` instead of asserting.
- `scripts/drop_database.py` uses `sql.Identifier`, no string-built SQL.
- `fhir_audit_event.py:59-63` allows metadata keys by name via `METADATA_KEYS`.
- The test of the 50 000-entry log and the demo-seed privacy test exist (`test_fhir_audit_event.py:23,173,210`).

## Findings
1. **Low** `scripts/fhir_validate.sh` cleanup: `|| true` on the drop hides a failed cleanup. It must not hide the validator's exit status, so this is accepted; print a line on failure.
2. **Low** `fhir_appointment_writes.py:57-60`: `update_appointment` still calls `read_appointment` and then looks the row up again, with one `Q` OR query instead of two. Point 7 asked for a single lookup; the `OR` with `.first()` has no ordering, though a pk and a waitlist-entry id cannot collide in practice.
3. **Low** `fhir_response_reads.py:55-58`: an absent entry skips the forbidden check and goes to `accept_offer`. No test shows the refusal for an absent entry equals the one for another patient's entry (existence leak). `_may_accept` runs under `guard_record`, which probably answers alike; unproven.
4. **Low** `NOTIFICATION_KIND_WORDS` (`fhir_communication.py:32`) is a second place for words; the task said "from the place the pages take them" (the stored `title`). Accepted: the title carries per-notification text, not a kind label.
5. **Low** The mapping of `user.*` and `housekeeping.*` actions is judgement; recorded in the ADR.
6. Measured: `make test` 4017 tests in 41.7 s on a shared machine; the orchestrator measures on a quiet one.

## Blocking
None.

## Later
- Test an absent waitlist entry id answers the same as another patient's (finding 3).
- Make `update_appointment` reuse the row that `read_appointment` resolved (finding 2).
- Print a warning when the throwaway database cannot be dropped.
- Orchestrator: run `make fhir-validate` and `make mutate` from a fresh clone (Done when); I did not run them here.

## Left for the orchestrator
Plan declared: "None cut". Nothing unfinished in the slice.
