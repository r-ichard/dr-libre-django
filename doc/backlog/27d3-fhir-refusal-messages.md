Task 27d3: the FHIR API, a message of its own on every refusal.

Item 3 of task 27d2 (`doc/backlog/27d2-fhir-writes-refusals-sort.md`), which its run left
whole. Finding of QA round 3, FHIR area (`doc/qa/2026-11-22-round-3.md`, not filed):
every 400 under `/fhir` says "The request is not valid." and names an element, so a
client cannot tell what to fix. Tasks 27d and 27d2 began it: `_with_messages` in
`scheduling/domain/fhir_outcome.py` for search values, and the message for
`Appointment.end`. Conventions of tasks 22 to 24d and ADR 0005 to 0010.

1. Each issue of a 400 under `/fhir` carries, in `diagnostics` after the correlation
   id, the message `/api/v1` gives for the same refusal (section 4: `invalid_input` has
   a message for each field): one issue per element, the element as a FHIR path. One
   table from the product's field to the FHIR element and one place that writes the
   issue, in the domain layer under the mutation gate; the sentence lives with the rule
   that refuses, not in a use case of the FHIR layer.
2. A refusal of the FHIR layer itself (an unknown element, a wrong type, an id that
   differs from the address, a `resourceType` that differs, an extension the
   declaration does not have, a value of another type than the declaration gives it)
   says which of these it is.
3. One test takes every write of the declaration and every refusal the hostile-input
   test already provokes, and fails on a 400 whose issues all say only "The request is
   not valid." A second takes every search parameter with a value it must refuse.
4. No message echoes what the client sent: a refused value may be personal data, and
   the answer is logged by clients. Prove it with a planted value.
5. Every changed answer keeps passing `make fhir-validate`; add a sample of a refusal
   with two issues.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
