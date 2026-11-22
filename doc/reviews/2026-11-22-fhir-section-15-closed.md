# Review: task 24d, FHIR section 15 closed

Diff: `main...HEAD`, 10 files. No product, migration or dependency line changed. Commits between
`verify_green` and `prove` touch only `test_fhir_documentation.py` and `test_fhir_surface.py` (tests).

## Findings

1. **Later** `README.md:14-60`: the claim "ran against the demo seed" cannot be re-checked from the diff
   (no transcript). Risk: stale or invented answers. Fix: orchestrator re-runs the commands on the
   container stack once.
2. **Later** `scheduling/views/test_fhir_status_mapping.py:12`: imports private `_cancelled_slot` and
   `_offered_entry` from `test_waitlist_support`. Risk: coupling to underscore names. Fix: rename them
   public in a later task.
3. **Later** `scheduling/views/test_fhir_booking_journey.py:127`: agent check is
   `endswith(<id>)` on the reference, weaker than an equality on the full reference. Fix: compare whole reference.
4. **Later** `scheduling/views/test_fhir_surface.py:44-50`: the surface test accepts 400 as a refusal
   for body-decided resources; an empty body hides whether the role check runs. Fix: send a minimal valid body per role.
5. **Later** `scheduling/views/test_fhir_booking_journey.py:100`: the journey test is about 70 lines, under the cap, but mixes act and assert; split into steps if it grows.
6. Nothing at a glance needed tracing except the surface test's refusal-code logic (finding 4).
   Difference table entries each name ADR number and quote; the test checks the quote in the ADR text.
7. ADR 0005 to 0007: every open point is replaced by a pointer to the list at the end of 0007, five questions, each with "Today the product". Matches item 4.
8. Type suppressions carry codes; no `Any`, `cast`, bare `noqa`.

Measured: `make test` 44 to 47 s here, shared machine; orchestrator measures on a quiet one.

## Blocking

None.

## Later

Findings 1 to 5.

## Left for the orchestrator

Plan declared the full slice (items 1 to 5), no "Not in this run" list. Still to do: `make mutate` and `make fhir-validate`
(not run in this stage), re-run README commands, `doc/backlog.md` status, retro line (ADR 0008/0009 open points unchecked).
