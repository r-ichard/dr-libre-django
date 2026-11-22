# Review: task 27d slice 1 (items 1 to 3), FHIR date, NUL and comma searches

Diff read: `main...HEAD`. Proof stages (`verify_green`..`prove`) changed tests and `mutation-equivalents.txt` only; the refactor commit touched `fhir_search.py` (allowed).

## Confirmed at a glance
- `use_cases/fhir_appointment_reads.py:162`: `starts_within` now filters `[low, high)` from `combined_bounds`, the cause the plan names. Plan states why tests and mutation gate missed it.
- `domain/fhir_search.py:49`: one NUL rule over name and every value (covers `_sort`, `_include`).
- `domain/fhir_search.py:116`: comma = either, closed list gives 400 naming the parameter and listing codes; dates refuse a comma via the date pattern.
- `use_cases/fhir_reads.py:322` `_either`: union applied inside the viewer-narrowed rows, so authorization is not widened.
- `domain/fhir_bundle.py:41` paging links rebuild alternatives with commas.
- `use_cases/fhir_audit_reads.py:57` `_action` uses the pure inverse `product_actions_of`.
- Read-only paths: no write, audit, or double-booking code touched.

## Findings
- **Later, `fhir_search.py:116`**: a comma now splits TEXT and REFERENCE values too, and `\,` escaping (R4) is not handled. `name=Smith, John` now means "Smith" or " John". Fix: honour `\,` and `\\` in the splitter, one test.
- **Later, `use_cases/fhir_audit_reads.py:108`, `fhir_declaration.py`**: `AuditEvent?type=` is a new search parameter. The plan said "NOT added" (smallest: no new parameter); the diff adds it and ADR 0009 documents it. Harmless and consistent across declaration, spec table and ADR, but it departs from the plan. Orchestrator to accept or drop.
- **Later, `domain/fhir_outcome.py:56`**: `_with_messages` is item 5 work (per-field messages in 400) which the plan put under "Not in this run". It is tested, small, and safe (fixed vocabulary). Finish item 5 in the next run; do not count it as done.
- **Later, `fhir_search.py:70`**: `problem` is set False then the loop returns early, leaving a dead assignment path for the trailing `if problem`; readable but could be simplified.
- **Later, measured**: `make test` took 157 s in the sandbox (4790 passed). Not a blocker; measure on a quiet machine.

## Blocking
None.

## Later
- Escaped comma (`\,`) in TEXT/REFERENCE values.
- Decide on `AuditEvent?type=` (plan said not added).
- Item 5 partially present (`_with_messages`); finish with the rest of item 5.
- Simplify `problem` flag in `parse_search`.
- `make test` 157 s measured in a shared sandbox.

## Left for the orchestrator
- Item 4 (#52): one `request_has_body` / media-type rule for `/api/v1` and `/fhir`; 415 + OperationOutcome before the body is read; empty `CONTENT_LENGTH` is no body; raw-socket live-server test.
- Item 5: per-field 400 messages naming an element on every `/fhir` 400, and `end` equal to stored or derived accepted on reschedule (`fhir_appointment_write._moved_element`).
- Item 6: `_sort` on every date parameter, both directions, CapabilityStatement says which values.
- 414/431 pages: task 26d.
- `make fhir-validate` not run in this stage; run it as the last scripted gate.

## Second pass (after `final_gates` failed)
- `final_gates` failed on `make mutate`; the `address` commit renumbered `parse_search` mutant 103 to 98 and dropped the unreachable `_read_value` entries in `mutation-equivalents.txt` (test-side file only, no product line).
- Re-ran `make mutate` here: `scripts/mutation_survivors.py` exits 0 (5 timeouts, none in this slice's modules besides pre-existing). The gate now holds.
- `domain/fhir_dates.py` unchanged: `PREFIXES` already limits to `eq ge gt le lt`, so `ne sa eb ap` fail `normalised_date` and a comma fails the date pattern; ADR 0005 states it.
- `make fhir-validate` not run here.
