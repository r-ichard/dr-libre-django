# ADR 0006: FHIR Schedule, Slot, Patient and the first writes

Status: accepted, 2026-11-22. Builds on ADR 0003 (ids, versions), ADR 0004 (failures) and ADR 0005
(conventions). Changes to ADR 0005: `/fhir` is no longer read-only; `start` may be given twice;
`Patient.birthDate` is served to whoever may read that patient (ADR 0005 said never served).

## Decisions

- **Interactions per type** live in the declaration: Schedule read, search, create, update, delete;
  Slot read, search; Patient read, search, update. Routes, the `Allow` header and the
  CapabilityStatement read it. A method the type does not declare is 405 with `Allow`.
- **Writes.** `POST /fhir/<Type>` creates (201, `Location`, `ETag`), `PUT /fhir/<Type>/<id>` replaces
  (200, new `ETag`), `DELETE` deletes (200 with an information `OperationOutcome`; every answer
  stays FHIR JSON). A write needs a token (none: 401). The body is parsed as JSON and checked against
  the declared shape of the type before any use case runs (`fhir_body.py`): an unknown element, a
  wrong type, another `resourceType` or id (an id on `POST`) is 400, the element named in
  `issue.expression`. Every write calls the use case the screens call; no FHIR write bypasses one.
- **One failure table** (`fhir_write_failures.py`): `invalid_input` 400, `unauthenticated` 401,
  `forbidden` 403, `not_found` 404, `conflict` and `has_dependents` 409, `rule_violation` 422, stale
  version 412 (and the other codes of ADR 0004). The product code travels in
  `issue.extension` (`failure-code`, `valueCode`), so a client tells two 409s apart. A rule
  overlap, which the screens show as a field message, is `rule_violation` 422 here.
- **`If-Match`.** `W/"3"` or `"3"` is the version the client read; a stale one is 412 (checked
  under the use case's lock). Without `If-Match` the write applies to the current version (the FHIR
  default); no 428. An `If-Match` that is not a version is 400.
- **Schedule** is one availability rule. Actors: the practitioner (the user id) and the room.
  `planningHorizon` is `valid_from` to `valid_to`; weekday (0 Sunday), start, end and slot step are
  extensions `schedule-weekday`, `schedule-start-time`, `schedule-end-time`,
  `schedule-slot-step-minutes`. `active` is the clinician's `is_active`. Visible to the public as the
  clinician is (`listable_profiles`); staff see all. Only the clinician named as practitioner and
  holding the token may write: any other token (an admin's too) is 403. `planningHorizon` and
  `active` are the server's: a body may only repeat them, else 400 naming them. `PractitionerRole.
  availableTime` is built from the same rows, so it follows every write.
- **Slot** is computed. `start` is required with `ge` and `lt` (at most 31 days), and
  `service-type` is required: the shared use case needs the type. Without them, 400 naming the
  parameter. `find_free_slots` runs with the same type, range and `online_only` rule as
  `GET /api/v1/slots`; a slot is one start of one schedule (the rule covering that start). The
  range is the window of the use case (a slot must end inside it), as in the application API.
  `schedule.actor` matches the rule's practitioner or room. No `status` means `free` only.
  `busy`, `busy-tentative` (booking hold) and `busy-unavailable` (time off) are returned to a
  clinician for their own schedules and to an admin for all; for anyone else the answer is an empty
  search, never an error. A slot never names a patient or an appointment.
- **Slot id** is `<schedule>.<type>.<minutes>`: the rule id and the appointment type id, each as the
  26 characters of lower-case base32 (RFC 4648, no padding) of the UUID bytes, and the start as
  minutes since the Unix epoch in decimal. At most 62 characters. Stable for the same three, and tells
  nothing else. An id that does not parse in exactly that form, a start off the schedule's grid, or a
  slot that is not offered (past, booked, time off, held, not bookable for this caller, hidden
  clinician) is 404. Read by id answers free slots only; a busy slot found by a clinician cannot be
  read back.
- **Patient** is a user of role patient: name (`text`), `birthDate`, `telecom` (email, phone),
  `active`. Readable set, built from the caller first: a patient reads themself, a clinician the
  patients with an appointment with them, an admin every patient; a search only narrows it and
  `total` counts only it. No token is 401. A patient or a clinician reading an id outside the set is
  403, the same body and headers for another patient's id and for an absent id; an admin reading
  an absent id is 404.
- **Patient update.** A patient may change `telecom` phone and `birthDate` (`update_profile`, the
  rules of the profile page); an admin `name`, `telecom` email and `active` (`update_user`, as the
  console does). A clinician may not update. Every other element that differs from the stored
  record, including an omitted one, is 400 and named; `meta` is the server's and ignored. Create
  and delete are 405.
- **Personal data.** Every answer under `/fhir/Patient` is `Cache-Control: no-store`, failures
  included. The request log holds the route, never the query string. Audit metadata holds ids and
  field names. A test plants values in a read, a search by email and phone, an update and a refused
  update, and finds none of them in logs or audit entries.
- **Validation.** `make fhir-validate` samples Schedule, Slot (free, busy, included schedule, read by
  id) and Patient, the request bodies of every write and the answer to a delete.

## Open points for the owner

Collected as "Questions for the owner" at the end of ADR 0007.
