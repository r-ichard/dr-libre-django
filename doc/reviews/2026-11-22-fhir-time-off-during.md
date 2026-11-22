# Review: task 24c2, `notAvailable.during` (run 01M81HWAZKBK0PJES5DT04XBZ7)

Base: `f6d7288`. Slice declared: items 1, 2, 3 and the item 5 duties of the existing writes. Item 4 is not in this run.

## Plan in one sentence per block
- Rename `period` to `during` on the read side (`scheduling/domain/fhir_practitioner_role.py:90`), the shape and reader (`scheduling/domain/fhir_role_write.py:32`, `:141`), samples (`scheduling/views/fhir/samples_records.py:23`) and the test helper (`scheduling/views/fhir_role_support.py:43`). Confirmed at a glance. `period` is gone from `ROLE_SHAPE`, so it is refused as an unknown element.
- Survivor tests: `scheduling/domain/test_fhir_coding_code.py`, beside `fhir_record_write._coding_code` (`:325`) and `first_coding_code` (`:331`). Traced the two paths: first coding wins, a missing or malformed part reads as `""`. The tests assert on `first_coding_code` and `location_kind` directly. Whether they kill mutmut_9 and mutmut_11 was not run here (`make mutate` is a final gate).
- Journey test: `scheduling/views/test_fhir_time_off_journey.py`. The clinician's own token, add, read back with `id`, API slots and `/fhir/Slot` agree, remove. Refusals are one test each.

## Findings

### 1. Important: ADR 0009 not updated
Outcome: fixed. ADR 0009 now says `during` and lists the R4 names checked (documentation only, no test applies).

`doc/adr/0009*.md:18-24` still says `period` and has no "checked against R4" list. The goal (item 1) and plan block 6 both require it. The diff touches nothing under `doc/adr`. The contract text now contradicts the code. Fix: change `period` to `during` at lines 19 and 24, and add the checked-elements line from plan block 6. Also state the admin answer for `notAvailable` (400 naming `PractitionerRole.notAvailable`) if the ADR does not already say it.

### 2. Minor: the time-off journey does not repeat "changed in place" or "patient/no token"
"Changed in place" is covered in `test_fhir_role_time_off.py`. The plan's block 7 matrix audit left no visible trace in the diff, and no new matrix cells were added. For existing writes this belongs to Later. Check that `scheduling/views/test_fhir_role_writes.py` has every cell of {admin, own clinician, other clinician, patient, none}.

### 3. Minor: the identical-period-twice assertions are loose
`test_fhir_time_off_journey.py` asserts only the status 400 and the row count for "added to a stored one", not the element name. Add `element_names(...) == ["PractitionerRole.notAvailable"]`.

### 4. Nit: `# type: ignore[misc]` and `[attr-defined]` in the journey test
Each names its code, so the gate allows them. `_api_starts(clinic: object)` could take the typed clinic fixture instead.

## Checks
- Authorization, audit and transaction code is unchanged. Only the wire name changed. No new dependency.
- Proof stages: after `verify_green` (a8e3152) the `prove` commit is empty. Later `refactor` commits touch only the local variable name in `_period_of` and tests. No mutation left behind.
- Hard rules: no `Any`, `cast`, bare ignore or bare noqa. No swallowed error: `_period_of` returns `None`, and the caller reports it as a 400 naming the entry.
- Not run here: `make fhir-validate`, `make mutate` (final gates).

## Blocking
- ADR 0009 still names `period` and lacks the R4 element check list (goal item 1, plan block 6).

## Later
- Matrix audit of {admin, own clinician, other clinician, patient, none} x {POST, PUT, DELETE} for `PractitionerRole` (finding 2).
- Element name assertion in the identical-period test (finding 3).
- Type the journey helpers (finding 4).

## Left for the orchestrator
- `PUT /fhir/Practitioner/{id}` for an admin token through `update_user`, `deactivate_user`, `update_profile`. A differing phone is 400. Own-account and last-admin refusals come from those use cases.
- `DELETE /fhir/Practitioner/{id}` through `delete_user` (409 with a profile, appointments or audit entries).
- No `POST /fhir/Practitioner`, with the reason in ADR 0009.
- `Practitioner.versionId` moves when the profile title changes (trigger migration, ADR 0003). The old `If-Match` is 412.
- Write matrix, samples, hostile paths and CapabilityStatement `update`/`delete` for `Practitioner`.
