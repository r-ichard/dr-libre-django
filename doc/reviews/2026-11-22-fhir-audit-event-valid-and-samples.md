# Review: task 24a, valid AuditEvent, samples, leftovers of task 24

Diff base `0ef2823`. Commit order checked: the commit between `verify_green` and `prove`
(`20de887`) touches `scheduling/views/fhir/test_samples.py` only. No product line changed in proof.
Run by me: `make fhir-validate` exit 0; `make mutate` exit 0 (no unlisted survivor).

## What I confirmed at a glance
- `scheduling/domain/fhir_audit_action.py`: one table plus suffix rule, default `E`; pure. Test ties it to `audit_labels`.
- `fhir_audit_event.py:36-60`: `action` is the code, `type.code` keeps product name, `_details` allow-lists by `METADATA_KEYS`.
- `fhir_communication.py:32-38`: display words from a domain map; mutant tests added.
- `samples_staff.py`: samples for the four types, guard tests in `test_samples.py`.

## Findings

1. **Important** `doc/adr/` has no `0007-fhir-appointment-and-the-rest.md` (task point 6); the plan listed it as block 11 and cut nothing. Also the ADR line "a FHIR search sorts by database collation" (point 7) is absent. Fix: write the ADR.
2. **Important** Point 7 untouched: `scripts/fhir_validate.sh:12` trap removes only `$SAMPLES`, no `dropdb`; `scheduling/views/fhir/views.py:98` still `assert` (with `noqa: S101`); busy intervals still in `fhir_slot_reads.py` (290 lines, no `fhir_busy_slots.py`); `update_appointment` and typing of `test_fhir_appointment_race.py` not in the diff. Fix: do each item.
3. **Important (promised)** Point 1 asks that "say in the ADR which element `action` search reads"; no ADR, so undocumented. Covered by finding 1.
4. **Medium** `scheduling/use_cases/fhir_response_reads.py:55-58`: authorization is a new `forbidden` check placed before the actor comparison, good. But an absent entry (`patient_id is None`) goes straight to `accept_offer`, while another patient's entry answers 403. Whether `accept_offer` answers 403 for absent entries too is not tested, so an existence leak is possible. The plan promised an identical refusal for absent and present. Fix: test absent entry id as a patient equals 403.
5. **Low** `fhir_audit_action.py:25-26`: `audit_action_code` default `E` for unknown actions; deliberate and documented. `user.activate`, `housekeeping.purge` mapping is judgement, belongs in the ADR.
6. **Low** `samples_staff.py:51-53`: `refusal-staff` for AuditEvent is a patient read of the Bundle; passes only if the route answers 403 OperationOutcome. A test covers refusal outcome codes, accepted.
7. **Low** `samples_staff.py` runs 107+ lines, `Appointment-create-staff` is a hand-filtered copy of a read; it validates, accepted.
8. **Low** `test_api_tokens.py:101`: an existing test altered (clock moved a second) to fix ordering; justified, scope-adjacent.
9. **Low** `NOTIFICATION_KIND_WORDS` is a new map; pages hold no per-kind words (grep found none), so no second source exists. Accepted.

## Gates
Plan said size/time: not measured here. Fhir-validate and mutate pass; lint/test/gate passed in stage `check`.

## Blocking
- ADR 0007 missing (task point 6 and the collation sentence of point 7).
- Point 7 small items not done (dropdb in `fhir_validate.sh`, `_allowed_methods` assert, busy-interval module, single lookup in `update_appointment`, typed race test).

## Outcomes of the blocking findings (address stage)
- ADR 0007 missing: **fixed**. `doc/adr/0007-fhir-appointment-and-the-rest.md` written (collation sentence,
  `action` search reads `type.code`, mapping, `entity.detail`). A document, no test.
- `fhir_validate.sh` dropdb: **fixed**. `scripts/drop_database.py` runs in the exit trap; checked by
  counting `drlibre_validate_*` databases across a `make fhir-validate` run (unchanged).
- `_allowed_methods` assert: **fixed**, returns `()` for an undeclared type; existing route tests cover it.
- Busy intervals module: **fixed**, `scheduling/use_cases/fhir_busy_slots.py`; slot read tests unchanged and green.
- `update_appointment` single lookup: **fixed**, one `Q` query; existing update tests green.
- Typed `test_fhir_appointment_race.py`: **fixed**, `Clinic` and `User`, no `type: ignore`; `make lint` green.
- No new failing test written for the refactor items: behaviour is unchanged, existing tests are the guard.

## Later
- Finding 4: test absent-entry refusal equals other-patient refusal.
- Record the E bucket and `user.*` mapping choices in the ADR.
- Measure `make test` (45 s here, shared machine) on a quiet machine.

## Left for the orchestrator
Plan declared: "None cut". Unfinished items of the slice: those under Blocking above.
