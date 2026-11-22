Task 24d: FHIR API, section 15 closed.

After tasks 22 to 24c every resource of `drlibre-specs.md` section 15 is served. This
task proves it and writes it down. It adds no resource and no rule.

1. A test holds the tables of sections 15.2, 15.4 and 15.5 as data (resource,
   interactions and who may use them, search parameters, `_include`) and asserts,
   against the CapabilityStatement and against the running routes, that each one named
   there is served and that nothing else is. Where the product chose differently from
   the letter of the specification (ADR 0005 to 0007), the table says so with the ADR
   as its reason; a difference without a reason fails.
2. Section 15.3: one test walks every appointment status and every waitlist status
   through FHIR and asserts the mapped `Appointment.status`.
3. Section 15.6, as one journey through FHIR only, with a patient's token: find a slot,
   book it, reschedule, cancel; join the waitlist, receive the offer when a clinician
   cancels, accept it with an `AppointmentResponse`, read the `Communication`, mark it
   received. Then, with an admin's token, read the `AuditEvent` of each step. One test.
4. ADR 0005, 0006 and 0007: every open point is closed, or stated as a question for the
   owner with the choice the product makes today. Collect those questions in one list
   at the end of ADR 0007.
5. The README gains a section "FHIR API": how to issue a token, one read, one search,
   one booking and one refusal, with `curl`, each command run against the demo seed
   and its answer shortened, and `make fhir-validate`.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
