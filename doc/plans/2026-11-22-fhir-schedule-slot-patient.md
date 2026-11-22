# Plan: task 23, FHIR `Schedule`, `Slot`, `Patient` and the first FHIR writes

Plan in one sentence: three new resource types on the existing declaration, each a pure domain
mapper plus a thin use-case adapter; writes call the use cases the screens call
(`availability.py`, `profile.py`, `admin_users.update_user`) after one generic body check, and one
domain table maps every `Failure` to status and `OperationOutcome` code.

Read: `drlibre-specs.md` 4, 12.3, 15.1 to 15.6; ADR 0003, 0005; `fhir_declaration.py`,
`fhir_search.py`, `fhir_capability.py`, `fhir_outcome.py`, `fhir_reads.py`, `views/fhir/*`,
`availability.py`, `profile.py`, `admin_users.py`, `free_slots_query.py`, `schedule_loading.py`.

## Focal point

`fhir_entry` in `scheduling/views/fhir/views.py`: today GET-only, caller reduced to
`Viewer.PUBLIC|STAFF`. It becomes: resolve a `Caller` (viewer plus the token's `User`, or none),
route by declaration, read body for writes, call one use-case adapter, format. Everything else
hangs off the declaration.

## Blocks (one sentence each)

Domain, pure, under mutation gate (each with `test_*.py` beside it):
1. `fhir_declaration.py`: add `interactions` per type (Schedule: read, search-type, create,
   update, delete; Slot: read, search-type; Patient: read, search-type, update), `ParameterKind.DATE`
   (Schedule `date`, Slot `start`, Patient `birthdate`), a `maximum_repeats` on a parameter
   (`start` twice, for `ge` and `lt`), `required` parameters (Slot `start`, `service-type`),
   `includes=("Slot:schedule",)`; Schedule/Slot/Patient entries with the 15.5 parameters.
2. `fhir_search.py`: parse DATE with `eq|ge|gt|le|lt` prefix into a range; allow the declared
   repeats; refuse a missing required parameter by name; `Slot:schedule` include.
3. `fhir_capability.py`: interactions and description from the declaration (no more "read-only").
4. `fhir_schedule.py`: rule to `Schedule` (actors practitioner and room, planningHorizon,
   extension `schedule-weekday`, `schedule-start-time`, `schedule-end-time`,
   `schedule-slot-step-minutes`, added to `fhir_common.py`) and body to `RuleCommand` fields.
5. `fhir_body.py`: generic check, `exact_elements(body, allowed, path)` names the first unknown
   or mistyped element (`Schedule.planningHorizon.foo`); resourceType and id must match the URL
   (id absent on POST); deep or non-object JSON is 400.
6. `fhir_patient.py`: user to `Patient` (name, birthDate, telecom email and phone, active) and
   `refused_changes(stored, body, allowed)`: every top-level element that differs from the stored
   resource and is not allowed for this caller is named (`meta` is server-owned and ignored).
   Patient may change `telecom[phone]` and `birthDate`; an admin also name, email, active.
7. `fhir_slot.py` and `fhir_slot_id.py`: slot resource (status, schedule, serviceType coding with
   the type id, start, end; never patient or appointment); id format below; `schedule_of(rules,
   start)` picks the rule whose weekday, local times and validity cover the start (rules of a
   clinician cannot overlap, so it is unique).
8. `slot_status.py`: for the clinician's grid (`free_slots` run with no obstacles) minus the free
   starts, classify each start: time off overlap `busy-unavailable`, active appointment (buffer
   applied) `busy`, live hold `busy-tentative`; first match in that order.
9. `fhir_write_failures.py`: the one table, `FailureCode` to `(http status, issue code)` for every
   code, plus `STALE_VERSION` (412). The product code travels as `issue.details.coding`
   (`<base>/CodeSystem/failure`). Replaces `ISSUE_CODE_BY_FAILURE` in `fhir_outcome.py` and the
   status lookup in `views/fhir/responses.py`, so reads and writes share it. Test is exhaustive over
   `FailureCode`.

Use cases (adapters, no new rules):
10. `fhir_schedule_reads.py`: `Part` for rules (visible = rules of `listable_profiles`, staff all;
    filters `actor` (practitioner or room id), `date` (horizon contains), `active` = clinician user
    active); registered in `PARTS` (fhir_reads.py is at 292 lines, one line added only).
11. `fhir_schedule_writes.py`: create, update, delete call `create_rule`, `update_rule`,
    `delete_rule` with the token's user; planningHorizon must equal what the use case sets (create)
    or the stored one (update), else 400 naming it; actor naming another practitioner is 403.
    `update_rule` and `delete_rule` get an optional `expected_version` checked under the existing
    lock (default none, the pages unchanged).
12. `fhir_slot_reads.py`: search calls `find_free_slots` (same type, clinician, range) and
    `online_only_for(user)`; one `Slot` per (clinician schedule, start); busy statuses only for
    clinician and admin callers, public asking gets zero slots (no error tells busy exists); read by
    id parses, finds the rule, asks `find_free_slots` for exactly that slot, else 404.
13. `fhir_patient_reads.py` and `fhir_patient_writes.py`: readable set built from the caller first
    (patient: own row; clinician: users in own appointments, as `clinician_patients.py`; admin all),
    filters only narrow it, total counts only that set. Write: patient calls `update_profile`
    (optional `expected_version`), admin calls `update_user` (`RecordEdit`, version from
    `If-Match`).
14. `views/fhir/views.py` (split a `writes.py` beside it to stay under 300 lines): `Caller`,
    methods per declaration (405 `Allow` computed), body read (JSON, size limit already there),
    `If-Match` to version (stale 412), 201 with `Location` and `ETag`, 200 with new `ETag` on
    update, 200 `OperationOutcome` (information) on delete (every answer stays FHIR JSON), Patient
    answers always `Cache-Control: no-store` including failures.
15. `scheduling/management/commands/fhir_samples.py` and `views/fhir/samples.py`: per-type
    queries (Slot needs a range and a type), staff slots with busy statuses, `_include=Slot:schedule`,
    Patient as staff and as the patient, request bodies of every write (POST/PUT Schedule, PUT
    Patient) and the success and failure `OperationOutcome`s; `make fhir-validate` validates them.
16. `doc/adr/0006-fhir-schedule-slot-patient-writes.md`, plus one line each in ADR 0005 where
    this task changes it (birth date served to those who may read the patient; `start` may repeat
    twice; no longer read-only).

## Decisions the ADR records

- **Slot id** `<rule>.<type>.<minutes>`: the rule id and the type id as 26-character base32
  (RFC 4648, lower-case, no padding) of the UUID bytes, minutes since the Unix epoch of the start
  in decimal. At most 62 characters, inside FHIR's 64 and its id alphabet; tells nothing beyond
  the three parts. Anything that does not parse, a start off the rule's grid, or a slot not
  offered (past, booked, time off, held, type not bookable for this caller) is 404.
- **`Slot` without `service-type`** is 400 naming `service-type` (the shared use case needs the type).
  Read by id answers free slots only.
- **No `If-Match`**: the write applies to the current version (FHIR default), the use case still
  compares versions under its lock. A stale `If-Match` is 412.
- **Patient visibility**: no token 401, any role on a record it may not read 403 (so a patient or
  a clinician cannot tell an absent id from another's); admin gets 404 for an absent id. Search
  returns only readable rows, `total` counts only those.
- **Schedule `active`** is the clinician's `is_active`.
- **Failure lists** (conflict resources, rule names) are not carried in the outcome; the product
  code is. Delete answers 200 with an `OperationOutcome`, not 204.

## Files to touch, in order

`fhir_common.py`, `fhir_declaration.py`, `fhir_search.py`, `fhir_capability.py`,
`fhir_write_failures.py`, `fhir_outcome.py`, `fhir_body.py`, `fhir_schedule.py`, `fhir_patient.py`,
`fhir_slot_id.py`, `fhir_slot.py`, `slot_status.py` (all `scheduling/domain/`, tests beside);
`use_cases/availability.py`, `profile.py` (optional `expected_version`),
`fhir_schedule_reads.py`, `fhir_schedule_writes.py`, `fhir_slot_reads.py`,
`fhir_patient_reads.py`, `fhir_patient_writes.py`, `fhir_reads.py` (register);
`views/fhir/views.py`, `responses.py`, `writes.py`; `views/test_hostile_input.py` (FHIR write
bodies); `samples.py`, `fhir_samples.py`; ADR 0006, ADR 0005 edits, `doc/backlog.md` row.

Deliberately not touched: `views/pages/`, `templates/`, `use_cases/admin_*` (imported, not
edited), `PractitionerRole` mapper (`availableTime` is already built from the rules; task adds
tests only), Appointment and booking (23a), the application API, models and migrations (no new
column: version, horizon and ids exist).

## Invariants and blast radius

- No double booking: slots come from `find_free_slots`, the same code `GET /api/v1/slots` runs;
  no new write path touches appointments.
- Authorization on the server from the token's user, never the body: Schedule writes only through
  `locked_profile` and `_own_rule`; Patient readable set built before filters.
- Every write audited inside the use case's transaction; audit metadata keeps ids and changed
  field names only (`AuditMetadata` types forbid more). No new write skips a use case.
- Blast radius: `fhir_entry` (all FHIR routes), `fhir_outcome`/`responses` (every failure answer,
  now via one table), `update_rule`/`delete_rule`/`update_profile` signatures (default param, pages
  unaffected). Reads of tasks 22/22a must answer byte-identical: existing FHIR tests stay green.

## Failing tests first (`returns_X_when_Y`)

Domain:
- `returns_one_status_and_issue_code_for_every_failure_code`: 400, 403, 404, 409 (`conflict`,
  `has_dependents`), 422, and `STALE_VERSION` 412; a missing code fails the test.
- `returns_schedule_with_both_actors_and_horizon_when_rule_has_room`; weekday, start, end, step
  as the extension; no end of horizon when `valid_to` is empty.
- `returns_element_name_when_body_has_unknown_element`, `..._wrong_type`, `..._other_id`,
  `..._id_on_post`.
- `returns_name_of_changed_element_when_patient_body_changes_email`; phone and birthDate pass.
- `returns_same_slot_id_for_same_schedule_type_and_start`; `returns_none_when_id_has_bad_base32`,
  `..._extra_part`, `..._minutes_not_digits`; round trip over many starts.
- `returns_busy_unavailable_when_time_off_covers_start` (and `busy`, `busy-tentative`, order of
  precedence).
- Search: `returns_range_when_start_has_ge_and_lt`, `refuses_third_start`, `names_service_type_when_missing`.

API (FHIR client: bearer token, no cookie, no `Origin`, cross-site check enforced):
- `returns_201_with_location_and_etag_when_clinician_creates_schedule`, then Schedule search,
  `PractitionerRole.availableTime` and `GET /api/v1/slots` agree; same after update and delete.
- `returns_403_when_admin_or_other_clinician_writes_schedule`; `returns_422_or_400_when_rule_overlaps`
  as the page answers; `returns_412_when_if_match_is_stale`; `returns_401_without_token`.
- `returns_hidden_schedule_to_public_when_clinician_not_listable`; staff sees it.
- `returns_same_starts_as_api_slots_for_a_week_of_the_demo_seed` (and same clinicians).
- `returns_400_naming_start_when_range_missing` and `..._over_31_days`; `returns_404_when_slot_id_
  unparseable_or_not_offered`; `returns_slot_when_read_back_by_its_id`.
- `returns_free_only_when_public_or_patient_asks_for_busy`; clinician and admin get the three busy
  statuses; the body of a busy slot names no patient and no appointment id.
- Patient: own record for patient; clinician only patients with an appointment with them; admin
  all; another patient's id 403 for patient and clinician (same body as an absent id); search
  `total` counts readable rows only; 401 without token.
- `returns_400_naming_element_when_patient_put_changes_name`; admin changes name like the console;
  stale `If-Match` 412; no `If-Match` applies.
- `answers_no_store_on_every_patient_response`; `keeps_planted_phone_and_birth_date_out_of_logs`
  (plant values, run read, search, update and a failed update, scan captured log records and
  audit metadata for the planted values).
- Hostile-input test gains Schedule, Slot, Patient paths with each write method and hostile bodies
  (nested 100 000 deep, wrong types, huge strings): no 500.
- `test_samples` walks the new samples for empty values.

Mutation: every new domain module gets tests that kill its mutants; survivors that are equivalent
go in `mutation-equivalents.txt` with a reason. Speed: builders and one shared clinic fixture, no
per-test seed; the 45 second cap is checked with `make test`.

## Trust boundaries

| Boundary | Validation and authorization |
| --- | --- |
| Bearer token | `resolve_token` (task 22); a write needs a token, none is 401 |
| Request body | size limit (ADR 0004), JSON object only, `fhir_body` names unknown or mistyped elements, id and type match the URL, then the use case validates again |
| Query string | declaration parser: unknown, repeated, unreadable or missing required is 400 |
| Path ids | `parse_id`; slot id parser returns none on any irregularity, 404 |
| `If-Match` | parsed to an integer, bad value 400, stale 412 |
| Output | `without_empty`, no secrets; Patient `no-store`; logs hold no record values |

## Domain vocabulary used

AvailabilityRule (Schedule), Clinician and ClinicianProfile, Room, AppointmentType (Slot service
type), Appointment and TimeOff and BookingHold (slot status only, read), Patient and User, Admin,
ApiClient (token), AuditLogEntry (via use cases).

## What I will not do

No new dependency, model, migration or column. No generic FHIR framework beyond `fhir_body` and the
failure table (second caller: 23a and 24). No Appointment, booking, `Communication`, `AuditEvent`.
No change to pages or admin use cases. No stored slots. No 428 requirement for `If-Match`. No
refactor of `fhir_reads.py` beyond one registration line.

## Architect review

Verdict: approve. The plan covers all 13 task points, keeps rules in pure mappers, sends writes
through the existing use cases, and lists the first failing tests with expected values.

Recommendations to apply during the work (none blocks):
- Patient search by `email`, `phone` and `birthdate` puts personal data in the query string.
  Make the planted-value log test also search by the planted email and phone in the URL. Check
  that no request or access log keeps query strings for `/fhir/Patient`.
- Slot search: say in the ADR what `schedule.actor` does for a room actor, and whether a
  clinician's `busy*` search covers other clinicians (time off and holds are private-ish). Test
  the chosen scope.
- Add a test that a patient's 403 on another id has the same body and headers as the 403 for an
  absent id. The plan states this but the test list only names status.
- `expected_version` on `update_rule`, `delete_rule` and `update_profile`: add a test that the
  pages' calls without it behave unchanged.
- Keep the failure-table swap (`fhir_outcome.py`, `responses.py`) covered by the existing
  task 22 tests staying green, as the plan says.
