# Review: task 23, FHIR Schedule, Slot, Patient

Scope: `git diff main...HEAD` (46 files). Trust boundaries first (`views/fhir`, use cases), then domain, then tests.
Proof commits (`verify_green`..`prove`, 8176691..da7f2a3) touch tests and `mutation-equivalents.txt` only: no product line left behind.
Gates reported green in the pipeline (3461 tests, 34 s; lint, gate clean). I did not re-run `make mutate` or `make fhir-validate`.

## Findings

### 1. Blocker, correctness: `GET /fhir/Slot?service-type=<not a UUID>` answers 500
`scheduling/use_cases/fhir_slot_reads.py:108` does `UUID(values["service-type"][0])`. The declaration (`scheduling/domain/fhir_declaration.py:123`) types `service-type` as a plain `CODE`, so the parser (`fhir_search.py:115`) lets any string through.
Reproduced with a throw-away test (removed): `/fhir/Slot?service-type=not-a-uuid&start=ge2026-12-01&start=lt2026-12-03` gives 500 `OperationOutcome` code `exception`, logged as `ValueError: badly formed hexadecimal UUID string`.
Any anonymous caller can hit it. An expected input error becomes an invariant break (§9), and the hostile-input test (`test_hostile_input.py`, task point 13) did not cover it.
Fix: parse the value with `parse_id` in the search layer (or return `Failure.invalid_input([FieldMessage("service-type", ...)])` here), and add `service-type=not-a-uuid` to the hostile cases.

### 2. Later, correctness: admin Patient update labels any conflict as 412 when `If-Match` is given
`scheduling/use_cases/fhir_patient_writes.py:78-82` maps every `FailureCode.CONFLICT` to stale version when `expected_version` is set. Today `update_user` returns CONFLICT only for a moved version (`admin_users.py:62,145`), so it holds; a future second conflict kind would be reported as 412.
Fix: have `update_user` and `update_profile` take the expected version and return `stale_version()` themselves, as `availability.py` does.

### 3. Later, correctness: `expected_version or ...` treats `If-Match: 0` as absent
`fhir_patient_writes.py:49`. A stored version is never 0, so a stale `W/"0"` is silently ignored for admin. Use `if expected_version is None`.

### 4. Later, test: `Patient` and `Schedule` hostile-input coverage for write bodies
`test_hostile_input.py` is extended, but I saw no case for a Patient body with an `id` that differs from the URL or a wrong `resourceType`. `identity_problem` is mutation-tested in the domain, so risk is low.

### 5. Later, structure: `fhir_slot_reads.py` is 279 lines
Under the 500 cap, over the 300 guideline of §5. `search_slots` is about 30 lines. Split the busy-interval code into its own module when next touched.

### 6. Later, style: `assert ... # noqa: S101` in `views.py` (`_allowed_methods`)
Named code and reason, so the gate passes; the stripped-assert path would turn into an `AttributeError`. Return `()` for an undeclared type instead.

## Confirmed at a glance
- Patient reads: readable set built from the caller first (self, own appointments, admin all). A foreign or missing id gives the same 403 for patient and clinician (`fhir_patient_reads.py:36-41`); no count or link leak.
- Patient writes go through `update_profile` and `update_user` (transaction, version, audit with field names); refused elements are named (`fhir_patient_writes.py:44-47`). `Cache-Control: no-store` is set on every `/fhir/Patient*` answer (`views.py:63-65`), including failures.
- Schedule writes: the practitioner in the body must equal the token's user (`fhir_schedule_writes.py:73`), and ownership is re-checked under lock in `update_rule` and `delete_rule`. Admin or another clinician gets 403. Overlap maps to 422. Authorization comes from the token, not the payload.
- Slot: free slots come from `find_free_slots`, the same use case as `/api/v1/slots`. Busy slots are limited to the own clinician, or all for an admin, and carry no patient data. The id is a strict, round-trip checked format (`fhir_slot_id.py`).
- Write door: bearer token only, `csrf_exempt`, body size limits and `If-Match` parsing before any use case.

## Blocking
- `fhir_slot_reads.py:108`: non-UUID `service-type` gives a 500 on an anonymous Slot search; validate as 400 and add the hostile case.
  **fixed**: `returns_outcome_and_no_500_when_fhir_gets_hostile_authorization` (`SLOT_BAD_TYPE_QUERY`); `search_slots` now answers 400 `invalid_input` naming `service-type`.

## Later
- Move stale-version mapping into `update_user` and `update_profile` (finding 2).
- `If-Match` of 0 handled as absent (finding 3).
- Patient write-body identity cases in the hostile-input test (finding 4).
- Split `fhir_slot_reads.py` (finding 5).
- Replace the `assert` in `_allowed_methods` (finding 6).
