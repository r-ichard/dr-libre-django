# ADR 0010: what a FHIR write declares, `_sort`, and search values

Status: proposed, 2026-11-22, for the owner to accept. Builds on ADR 0005. Task 27d2.

## Decisions

- **One rule for "has a body, says JSON".** `scheduling/domain/write_body.py`: a write carries a body
  when it has `Transfer-Encoding` or a `Content-Length` above zero (RFC 9112, section 6.3); an empty
  `CONTENT_LENGTH` (the `wsgiref` base environment) is no body. A write with a body must say
  `application/fhir+json` or `application/json`, else 415 before the body is read; under `/fhir` the
  answer is an `OperationOutcome` with code `not-supported`. `/api/v1` and `/fhir` share the rule.
- **`_sort` on every date parameter.** Section 15.1 was narrowed by ADR 0005 to `name`,
  `address-city` and `active`. It now also takes every date parameter of the declaration, ascending
  and with a `-` prefix descending. Each type's CapabilityStatement entry lists its sort values in
  `documentation` (R4 has no structured field for them). Without `_sort`, the newest-first default
  stays.
- **Appointment reschedule.** A `PUT` that changes `start` and repeats `end` is accepted when `end`
  equals the stored end or the end the new start gives (start plus duration); any other `end` is 400
  naming `Appointment.end`. The end is never taken from the client (5.2).
- **Search values.** A comma splits a value into alternatives in every type of parameter; `\,` and
  `\\` escape it (FHIR). A date prefix is `eq`, `ge`, `gt`, `le` or `lt`; `ne`, `sa`, `eb`, `ap` and a
  comma between dates are 400. A date of day precision is that whole UTC day; an instant is one
  second. A parameter with a closed list of codes (`status`, `action`) answers 400 listing the codes.
  A NUL byte in any parameter is 400 naming it. These first came with task 27d as a paragraph in
  `drlibre-specs.md`; the specification is the owner's text and stays as it was, so they live here.
- **Additions to section 15.** What the decision records add beyond the tables is the list
  `ADR_ADDITIONS` in `scheduling/views/fhir_spec_tables.py`, each entry naming its ADR; the test over
  the tables fails on anything served that neither the tables nor that list name.
  `AuditEvent?type=<action>` is the one entry so far (ADR 0009).

## For the owner

Accept or amend: `_sort` widened beyond 15.1 as above; the 415 code; the search-value rules that the
first run had put in the specification.
