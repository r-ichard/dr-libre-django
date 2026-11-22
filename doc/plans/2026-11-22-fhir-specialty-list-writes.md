# Plan: task 24b2, FHIR specialty list writes (CodeSystem, ValueSet)

Slice: items 1 to 6, whole task. Small enough: one pure module, one use case, six wiring edits. No
migration, no new rule.

## Focal point

New use case `scheduling/use_cases/fhir_specialty_writes.py`: `update_specialty_list(body, caller,
expected_version)`. In one transaction it locks the revision row, compares `If-Match`, diffs the
stored specialties against the body's concepts, applies each change through the console's
`create_record`, `update_record`, `delete_record` (kind `specialty`), and answers the rebuilt
CodeSystem. Any refused step rolls the whole request back.

## Design judged (goes into ADR 0008, new section "The specialty list")

The sketch in the 24b plan holds, with three corrections.

- **Client writes `PUT /fhir/CodeSystem/specialty` with the whole list.** FHIR has no concept-level
  interaction, `PATCH` is not in spec 15.4, and `DELETE CodeSystem/specialty` would mean "delete
  the list", so a removal can only be an absence. Body: `content` `complete`, `status` `active`,
  `concept[]` with `code`, `display`, optional `property`. `count`, `url`, `name` round-trip and
  must equal what the server builds, else 400 naming the element (the derived-element rule of
  0008). No `POST` (single id), no `DELETE`, a `PUT` to any other id is 404.
- **Match by `code`**, case-insensitively (the CodeSystem says `caseSensitive: false`, the table's
  unique index is `lower(code)`). Stored but absent = remove; present, stored missing = add;
  `display` differs = rename (`name`); `inactive` differs = (de)activate (`is_active`). A changed
  code is a remove plus an add by this rule, so it is 409 when clinicians use the old one. Two
  concepts with the same code ignoring case: 400 naming `CodeSystem.concept[i].code`.
- **Inactive in R4:** the CodeSystem declares `property` `{code: inactive, uri:
  http://hl7.org/fhir/concept-properties#inactive, type: boolean}`; a concept says
  `property: [{code: "inactive", valueBoolean: true}]`; an active concept sends none or `false`.
- **Correction 1, reads for an admin list inactive concepts.** Public reads keep "active only"
  (spec 15.4). Without this a client that GETs then PUTs the list would delete every deactivated
  specialty. So `specialty_list` takes the viewer; an admin sees all concepts, inactive flagged,
  `count` counts them. Same `versionId`; the body differs by viewer, like staff reads of
  Practitioner. A stale or partial body without `If-Match` still removes what it omits (ADR 0006
  has no 428); the removal is audited and blocked while clinicians use it. Said in the ADR.
- **Correction 2, ValueSet is the read-only view of the same list, not a PUT-equal mirror.** Its
  interactions stay read and search; `PUT`, `POST`, `DELETE` answer 405 with `Allow: GET` straight
  from the declaration, as `Slot` does. Simpler than "equal body is 200, other 400", same
  precedent as the hospital Organization in 0008. The ValueSet's `versionId` moves with the list.
- **Correction 3, concurrency by locking the revision row.** `SELECT ... FOR UPDATE` on
  `scheduling_specialty_revision` first, then everything else. A second admin waits, then sees the
  committed version: with `If-Match` it is 412; without, its whole-list diff runs on the fresh
  rows and the list ends as exactly what it sent, never a mix. (The row trigger in 0004 takes the
  same lock on any specialty write, so console writes serialize too.) `If-Match` is the revision
  row, checked under that lock.
- **Version:** the trigger fires once per statement, so a request with n changed rows moves the
  version by n, and a request with no change runs no statement and leaves it. No-op PUT answers
  200 with the current document and writes no audit entry.
- **Failures:** non-admin 403 (before the body is read), no token 401, stale `If-Match` 412
  (`stale_version()`), removal with clinicians 409 `has_dependents` with the console's counts text
  from `delete_record`, code or name invalid 400 with the element `CodeSystem.concept[i].code` or
  `.display`. One failure is returned; `transaction.set_rollback(True)` undoes earlier steps and
  their audit rows.
- **Order of steps inside the transaction:** removals, renames and (de)activations, then adds, so a
  code freed by a removal can be taken again by an add in the same body.
- **Audit:** the use cases write `specialty.create|update|delete` per changed row, as the console
  does; this task writes none itself.

## Files, in order

1. `scheduling/domain/fhir_specialty_write.py` (pure, new): `CODESYSTEM_SHAPE`; `desired_concepts(body)`
   returns concepts or the name of the bad element (derived elements, duplicate codes, bad
   property); `plan_changes(stored, desired)` returns removals, renames, activation changes, adds
   in apply order. Domain test file beside it, mutated by `make mutate`.
2. `scheduling/domain/fhir_specialty.py`: `SpecialtyList` carries the inactive flag per concept;
   `specialty_code_system` declares the `inactive` property and emits it for inactive concepts,
   `count` over what is shown. ValueSet unchanged.
3. `scheduling/use_cases/fhir_loading.py` and `fhir_reads.py`: `specialty_list(viewer)`, and
   `SINGLE_BUILDERS` take the viewer (admin: all rows; others: active).
4. `scheduling/use_cases/fhir_specialty_writes.py` (new, focal block).
5. `scheduling/use_cases/fhir_resources.py`: route `update("CodeSystem", ...)` and the 403/401 check
   in `refusal_before_body` (extend `write_refusal` or add one line beside it). `update` takes a
   `UUID`; the specialty id is the string `specialty`, so the CodeSystem route is dispatched
   before `UUID(identifier)` in `writes.py`: one small branch passing the id string.
6. `scheduling/domain/fhir_declaration.py`: CodeSystem `interactions=(*READ_ONLY, "update")`;
   `fhir_write_shapes.py`: add the shape. Routes, `Allow` and the CapabilityStatement follow.
   `parse_id` rejects the word `specialty`: `writes.py` accepts it for CodeSystem only.
7. `scheduling/views/fhir/samples_records.py` (or a new `samples_specialty.py` if it passes 300 lines):
   body of an add, a rename, a deactivation, a removal; the answer to a write; the `has_dependents`
   refusal; the 412 outcome; all into `make fhir-validate` through `fhir_samples`.
8. `scheduling/views/test_hostile_input.py`: add `PUT /fhir/CodeSystem/specialty` bodies.
9. `doc/adr/0008-...md`: new section with the decisions above; fix the status line.

Not touched: models, migrations, console pages, `admin_records.py` (`version=None` and
`expected_version=None` already exist), `admin_record_specs.py`, the 405 mechanism, `backlog.md`.

## Invariants and blast radius

- Authorization from the token's user, never the body; `create_record` etc. refuse non-admin again.
- One transaction per request, audit rows inside, rolled back with it. Audit stays append-only.
- Blast radius: the admin read of CodeSystem now lists inactive concepts (public read unchanged);
  `specialty_list` signature; `SINGLE_BUILDERS` signature; sample documents of CodeSystem gain the
  `property` declaration; tests comparing whole CodeSystem bodies. Search and booking read the same
  rows and need no change.
- Risk: the lock order. Revision row first, then specialty rows (`_locked` in the use cases), and
  the trigger's own update of the revision row is already held: no cycle.

## Trust boundaries

JSON body from the network: `request_limits`, then `exact_elements` against the shape, then the
pure `desired_concepts`, then the console's `check_name` and `check_code` inside the use cases.
Admin from the bearer token. `If-Match` parsed by `if_match_version`.

## Failing tests first (`returns_X_when_Y`, views with `fhir_client(token)`: bearer, no cookie, no `Origin`)

- `returns_200_with_new_etag_when_admin_adds_a_concept` (row exists, `specialty.create` audit by the
  admin, version rose by 1, public read lists it).
- `returns_200_when_admin_renames_a_concept_by_code` (match ignores case; audit `specialty.update`
  names `name` only).
- `returns_200_and_hides_it_from_public_reads_when_admin_marks_a_concept_inactive` (admin read still
  shows it with `inactive` true; public CodeSystem and search no longer offer it; reactivating by
  dropping the property brings it back).
- `returns_200_when_admin_omits_an_unused_concept` (row gone, `specialty.delete` audit).
- `returns_409_has_dependents_with_counts_when_the_omitted_concept_has_clinicians`
  ("1 clinician"; the other changes of the same body not applied, no audit rows).
- `returns_200_and_applies_both_when_one_body_adds_one_and_renames_another`; one audit entry per
  changed specialty; and `applies_neither_when_the_second_change_is_refused` (add + invalid name).
- `returns_200_and_keeps_version_when_the_body_changes_nothing` (no audit row).
- `returns_412_when_if_match_is_stale`; rows and audit untouched.
- Race: two threads, same `If-Match`, different bodies (pattern of `test_fhir_appointment_race.py`):
  one 200, the other 412; list equals the winner's body. Same without `If-Match`: both 200, list
  equals exactly the later body.
- `returns_403_when_a_clinician_or_patient_writes` and `returns_401_when_no_token_writes`; no row,
  no audit entry.
- `returns_400_naming_the_element_when_the_body_has_a_duplicate_code_a_blank_display_or_a_wrong_
  count` (parametrised), `returns_404_when_putting_another_id`.
- `returns_405_with_allow_get_when_valueset_is_written` and `...codesystem_is_posted_or_deleted`.
- Search follows at once: a new specialty appears in `search_catalog` with the fallback icon, a
  renamed one under its new name, a deactivated one is gone.
- Parity: the console and FHIR write the same name and code and leave the same row and the same
  audit metadata.
- CapabilityStatement: CodeSystem lists `read`, `search-type`, `update`; ValueSet read and search
  only.
- Domain tests: `desired_concepts` (each bad element), `plan_changes` (each kind, apply order, no-op).
- `test_samples.py`: every new sample exists and `make fhir-validate` passes.
- Hostile-input test passes with the new route.

## Domain entities

Specialty, Admin, ApiClient (token), AuditLogEntry, ClinicianProfile (dependents only).

## Not doing

No `PATCH`, no `fragment` content, no one-concept body, no `428` without `If-Match`, no
update-as-create, no new rule or console change, no icon field (the fallback icon is the search's
existing behaviour), no new dependency.

## Not in this run

Nothing of the task. Task 24c (Practitioner writes) and 24d stay as in the backlog.

## Architect review

Verdict: approve.

- Ladder: one pure module, one use case reusing the console's `create_record`, `update_record`, `delete_record`; no migration, no dependency, no new rule. Whole task in one slice is coherent.
- Design judgement holds: whole-list `PUT` on `CodeSystem/specialty` (no concept-level interaction in R4), match by case-insensitive `code`, `inactive` as a concept property, ValueSet read-only with 405. The admin-sees-inactive read is needed so GET then PUT does not delete deactivated specialties; the plan names it and its blast radius.
- Security: 403 before body read, 401 without token, authorization from token, schema then pure validation then console checks, audit inside the transaction. Hostile-input test is planned.
- Concurrency: revision-row `FOR UPDATE` first, then specialty rows; no lock cycle, since the trigger updates the same row. Race tests for both the `If-Match` and no-`If-Match` cases are listed.
- Tests: first failing tests are behaviours with expected values and cover error paths (409 with nothing applied, atomic rollback, 412, 400 per element).
- Watch in implementation (not blocking): the inner `atomic` blocks of the console use cases return a refused `Result` without raising, so the outer transaction must be marked for rollback on the first refusal (the plan says `set_rollback`); the test `applies_neither_when_the_second_change_is_refused` must prove it. The admin and public GET share one ETag with different bodies; say so in the ADR.
