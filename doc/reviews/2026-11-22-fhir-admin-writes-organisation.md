# Review: task 24b slice, FHIR admin writes for Organization, Location, HealthcareService

Diff `main...HEAD`, 23 files. Commit order checked: after `verify_green` (99b7e60) up to `prove`
(a9edbcc) only `test_fhir_code_identifier.py` and `test_fhir_organisation_writes.py` changed. No
product or migration line moved there.

## Plan in one sentence per block (§2.5)
- `use_cases/fhir_record_writes.py`: turn a checked FHIR body into `admin_records` values, call the console use case, rebuild the answer. Confirmed at a glance.
- `domain/fhir_record_write.py`: pure shapes and body-to-values per kind. Traced `derived_difference` and the `physicalType` split (si vs ro); sound.
- `admin_records.py`: `RecordEdit.version` may be None (skip check, still lock and audit); `delete_record` takes `expected_version` under the lock. Console callers unchanged.
- `views/fhir/writes.py`: 403 before the body, 405 `Allow: GET` for PUT/DELETE of a hospital Organization.

## Findings
1. **Info**, `use_cases/admin_records.py:61,90`: authorization from `caller.role` and `caller.user` (token), never the body; use cases re-check admin. Version check under the row lock. Audit stays inside the use cases' transaction. No finding.
2. **Low**, `scheduling/domain/fhir_record_write.py` (324 lines): over the 300 soft limit of §5.1, under the 500 cap. Fix: split values builders from helpers.
3. **Low**, `use_cases/fhir_resources.py:117-122`: two pass-through wrappers (`is_read_only_here`, `refusal_before_body`) only rename `fhir_record_writes` functions. Fix: import them directly in `writes.py`.
4. **Low**, `domain/fhir_outcome.py:49`: `_with_dependents` appends dependents text to the correlation-id argument, so `diagnostics` carries it. Works, but the parameter name no longer states its role. Fix: rename the parameter to `diagnostics`.
5. **Info**: `make mutate` and `make fhir-validate` were not run in any stage log shown (check ran lint, test, gate). The orchestrator runs both on host.
6. **Info**: no dependency, migration or model change.

## Blocking
None.

## Later
- Findings 2, 3, 4.
- Measure `make test` time (about 35 s here) on a quiet machine.
- Run `make mutate` (new domain module `fhir_record_write.py`) and `make fhir-validate` on host.

## Left for the orchestrator
Plan `## Not in this run`:
- `CodeSystem` / `ValueSet` writes (task items 2 specialty half, 3, and their parts of 4 to 7), with the ADR 0008 sections for the specialty list.
- Full pass of `make mutate` and `make fhir-validate` after both runs.
