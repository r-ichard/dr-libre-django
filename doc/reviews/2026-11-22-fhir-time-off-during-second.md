# Review: task 24c2, second reader (run 01M81HWAZKBK0PJES5DT04XBZ7)

Base `f6d7288`. Slice declared by the plan: items 1, 2, 3 and the item 5 duties of the existing writes (PractitionerRole, time off). Item 4 is not in this run.

## Plan in one sentence per block
- Rename `period` to `during` on read (`scheduling/domain/fhir_practitioner_role.py:90`), shape and reader (`scheduling/domain/fhir_role_write.py:32`, `:141`), samples (`scheduling/views/fhir/samples_records.py:23`), helper (`scheduling/views/fhir_role_support.py:43`). Confirmed at a glance; `period` is now refused as an unknown element.
- ADR 0009 now says `during` and lists the R4 names checked (`doc/adr/0009-...md:18-32`). The first review's blocker is fixed.
- Survivor tests `scheduling/domain/test_fhir_coding_code.py` for `_coding_code` (`fhir_record_write.py:325`). Needed a trace; `make mutate` now shows `x__coding_code__mutmut_9` and `_11` gone.
- Journey test `scheduling/views/test_fhir_time_off_journey.py`: own token, add, read with `id`, slots in API and `/fhir/Slot`, remove, plus refusals.

## Findings

### 1. Blocker: `make mutate` still fails, 8 unlisted survivors
**Outcome: fixed.** `scheduling/domain/test_fhir_practitioner_role.py` (`returns_not_available_with_id_description_and_during_when_time_off_exists`, `returns_the_default_description_when_the_reason_is_empty`, `returns_no_not_available_when_there_is_no_time_off`, `returns_one_entry_per_time_off_in_the_given_order`) and `scheduling/domain/test_fhir_coding_code.py` (`returns_no_value_when_an_extension_of_another_url_holds_the_key`, `returns_no_value_when_the_extension_of_the_url_lacks_the_key`, `returns_no_id_when_a_reference_is_not_a_prefixed_text`, `returns_the_id_when_a_reference_has_the_prefix`). `make mutate` passes; no line added to `mutation-equivalents.txt`.

I ran `make mutate` here (6599 mutants, 81 survivors, 8 not in `mutation-equivalents.txt`):
- `fhir_practitioner_role.x_practitioner_role__mutmut_98` to `_102`: `resource["notAvailable"] = None` instead of `[_not_available(item) ...]` survives. `scheduling/domain/fhir_practitioner_role.py:29-30` and `_not_available` (`:87-91`, the `during` key, `id`, default description) have no domain test; only view tests cover them, and mutmut runs the domain tests. The plan's first failing test (`returns_200_and_serves_during_...`) never reached the domain layer.
- `fhir_record_write.x__extension_values__mutmut_7` (`and` to `or` in the url/key test), `x_reference_id__mutmut_3` (`or True`) and `_8` (`or` to `and` in the type/prefix guard).
The goal's "Done when" requires `make mutate` to pass. Fix: a domain test for `practitioner_role` with time off (one entry: `id`, `during` start/end as instants, `description`, default "Time off" when the reason is empty, absent when no time off, and no `period` key); tests for `extension_values` with an extension of another url holding the same key, and `reference_id` with a non-dict, a non-string `reference`, and a string without the prefix. List a mutant in `mutation-equivalents.txt` only with a reason after `mutmut show`.

### 2. Later: identical-period test is loose (`test_fhir_time_off_journey.py`)
It asserts status and row count, not the element name. Add `element_names(...) == ["PractitionerRole.notAvailable"]`.

### 3. Later: write matrix audit
{admin, own clinician, other clinician, patient, none} x {POST, PUT, DELETE} for `PractitionerRole` left no trace in the diff. Check `test_fhir_role_writes.py` for every cell.

### 4. Nit: `# type: ignore[misc]` and `[attr-defined]` in the journey test
They name their codes, so the gate allows them. Type the clinic fixture instead.

## Checks
- Authorization, transaction and audit code unchanged; only the wire name moved. No new dependency, no `Any`, `cast`, bare ignore or bare noqa, no swallowed error (`_period_of` returns `None`, the caller answers 400 naming the entry).
- Proof stages: `prove` and later `refactor` commits touch no product line beyond the local-name change in `_period_of`. No mutation left behind.
- Not run here: `make fhir-validate`. `make lint`, `make test`, `make gate` passed in the `check` stage.

## Blocking
- `make mutate` fails: 8 unlisted survivors (finding 1).

## Later
- Element name assertion in the identical-period test (finding 2).
- Matrix audit (finding 3).
- Type the journey helpers (finding 4).
- `make mutate` took about 55 s of mutation run (121 mutations/s) on this shared machine; the orchestrator measures on a quiet one.

## Left for the orchestrator
- `PUT /fhir/Practitioner/{id}` for an admin token through `update_user`, `deactivate_user`, `update_profile`; a differing phone is 400; own-account and last-admin refusals come from those use cases.
- `DELETE /fhir/Practitioner/{id}` through `delete_user` (409 with a profile, appointments or audit entries).
- No `POST /fhir/Practitioner`, reason in ADR 0009.
- `Practitioner.versionId` moves when the profile title changes (trigger migration, ADR 0003); old `If-Match` is 412.
- Write matrix, samples, hostile paths and CapabilityStatement `update`/`delete` for `Practitioner`.
