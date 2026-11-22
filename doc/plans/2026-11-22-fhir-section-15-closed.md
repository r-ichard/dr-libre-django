# Plan: Task 24d, FHIR section 15 closed

Slice: items 1 to 5, all of them. Nothing but tests and prose; no production code, no resource, no rule.
If a test finds that the product contradicts section 15 without an ADR reason, the run stops and files
a new task ("host defect = new task"); it does not fix product code here.

## Focal point

`scheduling/domain/fhir_declaration.py` is the one declaration routes, parser and CapabilityStatement read.
The new test holds section 15 as a second, independent copy (the spec as data) and compares both ways.

## Blocks

1. **Spec tables as data** `scheduling/views/fhir_spec_tables.py` (support module, no tests, under 300
   lines): one tuple per table of 15.2/15.4/15.5: resource, interactions, who may use them
   (public, patient, clinician, admin), search parameters, `_include`s, and `Difference(adr, reason)`
   entries where the product departs from the letter.
2. **Surface test** `scheduling/views/test_fhir_surface.py`: CapabilityStatement against the table; routes
   against the table with real calls (method + role -> status not 405/404 for each named interaction;
   405/404 for each unnamed one, for every type and method); search parameters (named one accepted,
   an unnamed one refused 400), `_include` likewise. A difference without an ADR reference fails
   (a test of the table itself).
3. **Status test** `scheduling/views/test_fhir_status_mapping.py`: parametrized over the 15.3 tables
   (BOOKED, CONFIRMED, CHECKED_IN, COMPLETED, CANCELLED, NO_SHOW; WAITING, OFFERED, BOOKED, EXPIRED),
   built with the existing builders, read through `/fhir/Appointment/<id>`, assert mapped `status`
   (and the `appointment-status` extension for booked/confirmed, `cancelationReason` for cancelled,
   offered start/end/practitioner for proposed). One test function, parametrized from the table,
   plus one assertion that the parametrization covers every `AppointmentStatus` and `WaitlistStatus`.
4. **Journey test** `scheduling/views/test_fhir_booking_journey.py`: ONE test, FHIR only, bearer
   tokens, no cookie, no Origin (client_for): patient token searches Slot, creates Appointment
   `proposed` (-> booked), updates start, updates status cancelled with cancelationReason; joins waitlist
   (`waitlist` + requestedPeriod); a clinician token cancels the booked slot through FHIR; patient
   searches Communication (category offer), sees the offer as `proposed`, POSTs AppointmentResponse
   `accepted`, reads the Communication, PUTs `received`. Admin token searches AuditEvent for each step
   (booking create, reschedule, cancel, waitlist join, offer, accept) and asserts action/entity/agent.
   Reuse `fhir_test_support`, `test_waitlist_support` helpers; frozen clock `NOW`.
5. **ADRs 0005, 0006, 0007**: each "Open points for the owner" entry gets a verdict: closed (with the test
   or rule that closes it) or kept as a question. Collect every kept question in one numbered list
   "Questions for the owner" at the end of ADR 0007, each with "Today the product: ...". 0005/0006 point
   to that list. Spec section 17 and ADR 0008/0009 not touched (not named by the task); if they hold open
   points, note it in the retro line only.
6. **README.md** (does not exist: create, short): section "FHIR API": issue a token
   (`python manage.py api_tokens issue <email> --name ...`, shown once), one read, one search, one
   booking, one refusal (`curl`), `make fhir-validate`. Each command is run against the demo seed
   (`seed_demo` with `.env.example`, `runserver` started and stopped in one foreground command per
   `scripts/no_background.sh`) and the answer pasted shortened. Under 300 lines of file, 255-char
   comment rule not applicable (prose).

## Files in order

`fhir_spec_tables.py`, `test_fhir_surface.py`, `test_fhir_status_mapping.py`,
`test_fhir_booking_journey.py` (all under `scheduling/views/`), ADR 0005/0006/0007, `README.md`,
`doc/backlog.md` status line is the orchestrator's.

## Deliberately not touched

All of `scheduling/domain`, `use_cases`, `views/fhir/*`, models, migrations, `scripts/fhir_validate.sh`,
Makefile, `mutation-equivalents.txt`, ADR 0001 to 0004, 0008, 0009, the spec.

## Invariants and blast radius

No product code changes, so double booking, server-side authorization and append-only audit cannot
regress; the tests prove them through the door. Blast radius: `make test` time (journey and surface
tests are the heaviest; keep surface calls to one token per role, one client per role).
Test files stay under 300 lines and functions under 50 lines (split tables and helpers).
`make mutate` covers `scheduling/domain` only: untouched, expected unchanged.

## Failing tests first (behaviour names)

- `returns_every_resource_interaction_and_parameter_of_the_spec_in_the_capability_statement`
  (expected: each spec resource, interaction, search param, include present; nothing extra).
- `returns_405_or_404_for_every_interaction_the_spec_does_not_name` (any type x method not in table).
- `returns_access_of_section_15_4_for_every_role_on_every_named_interaction` (public 401/403/read-only,
  patient, clinician, admin as 15.4 states).
- `returns_400_naming_the_parameter_when_a_search_parameter_is_not_in_the_spec`.
- `fails_when_a_difference_from_the_spec_names_no_adr` (table self-check).
- `returns_the_mapped_appointment_status_for_every_appointment_and_waitlist_status`.
- `returns_the_whole_section_15_6_journey_and_one_audit_event_per_step_through_fhir_only`.
Red proof: each test fails when the declaration drops an interaction/parameter, the mapping table
changes one value, or a journey step is skipped (prove by temporary local edit, reverted, in the red
stage log). Since the product exists, "red" for items 1 to 3 means a mutated expectation, not
missing code; the reviewer judges it.

## Trust boundaries

Only the FHIR door: bearer token per request, authorization from the token's user, never payload.
Tests send what a FHIR client sends (no Origin, no cookie, cross-site check enforced) per CLAUDE.md.
README commands use demo tokens issued for the demo seed only; no real secret printed or committed
(the sample token shown is replaced by `<token>`).

## Domain entities

Hospital, Department, Clinician, ClinicianProfile, Patient, Admin, ApiClient, AppointmentType,
AvailabilityRule, Appointment, WaitlistEntry, Notification, AuditLogEntry.

## Will not do

No new resource, rule, abstraction, dependency or refactor; no change to the declaration to make a test
pass (that is a new task); no edit of the spec.

## Risks

- The spec/declaration differences (e.g. Practitioner delete, `Slot` busy statuses, Schedule create by
  admin, public-clinician strictness) must each find an ADR reason; one lacking a reason means an ADR
  text addition here (allowed) or a new task (if it is a real defect).
- Journey needs a slot, a waitlist and a cancelling clinician in one frozen clock: reuse builders;
  if more than ~50 lines, split into named helper functions in a support module.

## Architect review

Verdict: approve.

- Ladder: tests and prose only, no product code, no dependency. Spec tables as an independent copy is the point of item 1, not speculation.
- Scope: items 1 to 5 all covered, stop rule for product defects ("host defect = new task") is right. Item 5 README is correctly noted as new (no README exists).
- Tests first: seven named behaviours with expected values; red proof by mutated expectation is acknowledged as the only possible red here.
- Security: FHIR door only, bearer token, no Origin or cookie; README shows `<token>`, never a real one.
- Watch in implementation: the surface test must call routes with each role's own token (not the payload), keep files under 300 lines, and the journey must stay one test with helpers in a support module. Differences without an ADR reason: add ADR text only if the product behaviour is intended, otherwise stop and file a task.
