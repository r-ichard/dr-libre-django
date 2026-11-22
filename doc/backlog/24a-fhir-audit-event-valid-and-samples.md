Task 24a: FHIR API, a valid AuditEvent, samples for every type, and what task 24 left.

Task 24 (`doc/backlog/24-fhir-responses-communication-audit-admin-writes.md`) delivered
the read side of `AppointmentResponse`, `Communication` and `AuditEvent`, the acceptance
of a waitlist offer and "mark as read". Its review is in `doc/reviews/`. This task closes
what the orchestrator found on the running stack and what that run did not reach for
those three resources. The admin writes are tasks 24b and 24c; the closing of section 15
is task 24d. Reproduce each finding with a failing test before the fix.

1. Every `AuditEvent` is invalid FHIR R4. `AuditEvent.action` carries the product's
   action name (`appointment.book`, `time_off.create`), and R4 requires a code of the
   value set AuditEventAction there: `C`, `R`, `U`, `D` or `E`. The HL7 validator
   (`validator_cli.jar -version 4.0.1 -tx n/a`) reports two errors for each of the 80
   events of the demo seed. The product's action name already travels in `type`. Map
   each product action to one of the five codes with a pure function in the domain
   layer, under the mutation gate; a test fails when an action the product can write
   (the list `scheduling/domain/audit_labels.py` holds) has no mapping. Search by
   `action` keeps finding events by the product's action name: say in the ADR which
   element that parameter reads.
2. `make fhir-validate` samples nothing for `Appointment`, `AppointmentResponse`,
   `Communication` and `AuditEvent` (`scheduling/views/fhir/samples.py`), which is why
   point 1 passed every gate. Add for each: every status or kind the product can
   serve, a search Bundle with every `_include` the type has, the body of each write,
   and one refusal (for `Appointment` one that names a violated rule). A test fails when
   a resource type of the declaration has no sample, and when an interaction of a type
   has none.
3. `Communication.category` shows the product's raw code as its display
   (`SCHEDULE_CHANGED`). The display is words, from the place the pages take them.
4. From task 24's own list: a search of `AuditEvent` costs a bounded number of queries
   and stays fast on 50 000 entries, asserted; no `AuditEvent` of the demo seed carries
   a name, an email address beyond its domain, a phone number, a birth date, a reason
   or a note, asserted over every event.
5. Review of task 24: `create_response` compares the actor before it authorizes
   (`scheduling/use_cases/fhir_response_reads.py`); authorize first. The metadata of an
   audit entry is copied into `AuditEvent.entity.detail` key by key: allow the keys of
   `AuditMetadata` by name, so a key added later is not served by accident.
6. Decisions without a record: `doc/adr/0007-fhir-appointment-and-the-rest.md` for
   `Appointment` (status and source extensions, the `violated-rule` and
   `conflicting-resource` extensions, how a hold and a waitlist entry appear, what a
   body may change), `AppointmentResponse` (only `accepted`; declining is not in the
   specification), `Communication` (what the recipient may change) and `AuditEvent`
   (the mapping of point 1, what `entity.detail` holds).
7. Small, from the reviews of tasks 22a, 23 and 23a: `scripts/fhir_validate.sh` drops
   its throwaway database when it ends; the ADR says a FHIR search sorts by the
   database collation; the busy intervals leave `fhir_slot_reads.py` for a module of
   their own; the `assert` in `_allowed_methods` becomes a return; `update_appointment`
   looks the appointment up once; `test_fhir_appointment_race.py` is typed.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
