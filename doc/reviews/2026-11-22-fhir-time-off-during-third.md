# Review: task 24c2, second reader, third pass (run 01M81HWAZKBK0PJES5DT04XBZ7)

Base `f6d7288`. Slice declared by the plan: items 1, 2, 3 and the item 5 duties of the existing writes (PractitionerRole, time off). Item 4 is not in this run.

## Plan in one sentence per block
- `period` becomes `during` on read, shape and reader, samples (`scheduling/domain/fhir_practitioner_role.py`, `scheduling/domain/fhir_role_write.py:141`, `scheduling/views/fhir/samples_records.py`). Confirmed at a glance.
- Domain tests kill the survivors (`scheduling/domain/test_fhir_coding_code.py`, `scheduling/domain/test_fhir_practitioner_role.py`). Confirmed by running `make mutate`.
- Journey test `scheduling/views/test_fhir_time_off_journey.py`: own token, add, read, slots, remove, refusals.
- ADR 0009 lists the R4 names checked (`doc/adr/0009-...md:29-31`).

## Findings
### 1. The previous blocker is fixed
Last pass: 8 unlisted survivors. Now I ran `make mutate`: `scripts/mutation_survivors.py` exits 0, no listed line added. 5 timeouts, all in `free_slots` and `search_availability`, which this task did not touch. They are accepted by the script.
I ran `make fhir-validate`: exit 0, 112 samples, each "0 errors".

### 2. Later: identical-period journey test asserts status and row count
Add `element_names(...) == ["PractitionerRole.notAvailable"]` (`scheduling/views/test_fhir_time_off_journey.py`).

### 3. Later: write matrix
Check `scheduling/views/test_fhir_role_writes.py` covers {admin, own clinician, other clinician, patient, none} x {POST, PUT, DELETE}.

### 4. Nit: `# type: ignore[misc]` and `[attr-defined]` in the journey test
They name their codes, so the gate allows them. Type the clinic fixture instead.

## Checks
- Authorization, transaction and audit code unchanged; only the wire name moved. No new dependency, no `Any`, `cast`, bare ignore or bare noqa, no swallowed error.
- Proof stages: no `scheduling` line changed between `verify_green` and `prove`. The later local rename in `_period_of` is a refactor.
- Not re-run here: `make lint`, `make test`, `make gate`. The `check` stage passed them.

## Blocking
None.

## Later
- Findings 2, 3, 4.
- `make mutate` ran at 119 mutations/s on a shared machine; the orchestrator measures on a quiet one.

## Left for the orchestrator
- `PUT /fhir/Practitioner/{id}` for an admin token through `update_user`, `deactivate_user`, `update_profile`; a differing phone is 400; own-account and last-admin refusals come from those use cases.
- `DELETE /fhir/Practitioner/{id}` through `delete_user` (409 with a profile, appointments or audit entries).
- No `POST /fhir/Practitioner`, reason in ADR 0009.
- `Practitioner.versionId` moves when the profile title changes (trigger migration, ADR 0003); old `If-Match` is 412.
- Write matrix, samples, hostile paths and CapabilityStatement `update`/`delete` for `Practitioner`.
