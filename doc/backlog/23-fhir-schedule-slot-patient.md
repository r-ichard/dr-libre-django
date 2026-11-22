Task 23: FHIR API, Schedule, Slot and Patient.

`drlibre-specs.md` sections 15.2, 15.4 and 15.5 for `Schedule`, `Slot` and `Patient`, on
the conventions of tasks 22 and 22a (ADR 0005, ADR 0003): one declaration routes, parses
and fills the CapabilityStatement; pure mappers in the domain layer under the mutation
gate; every answer FHIR JSON; `make fhir-validate` covers every new resource and view.
`Appointment` and booking are task 23a. This task brings the first FHIR writes: they go
through the use cases the screens use (15.1: "No FHIR write can do what the application
API would refuse"), never around them.

Schedule (one per availability rule):

1. Read and search for anyone, by the visibility rule of ADR 0005: the schedule of a
   clinician the public search hides is hidden without a staff token. Actors: the
   practitioner and the room. Planning horizon: valid-from to valid-to. Weekday, start
   and end time and slot step as an extension. Search: `actor`, `date`, `active`.
2. Create, update and delete by the owning clinician only, through the use cases of task
   17 (overlap rule, room of the clinician's department, audit, version). An admin's or
   another clinician's token is refused as the application would refuse it.
3. `PractitionerRole.availableTime` mirrors the rules read-only; the two never disagree:
   test it after a create, an update and a delete.

Slot (computed, never stored):

4. Search only, and a read by id. A start range of at most 31 days is required; without
   it, or beyond it, 400 that says so. Parameters: `schedule`, `schedule.actor`,
   `service-type`, `start`, `status`. `_include=Slot:schedule`.
5. The slots are exactly those `GET /api/v1/slots` offers for the same type, clinician
   and range, through the same use case: assert the two answers agree for a week of the
   demo seed.
6. A slot's id is stable for the same schedule, type and start, and a client can read
   the slot back by that id (15.6). The id is built from those three, tells nothing
   else, and an id that does not parse, or that names a slot that is not offered,
   answers 404. Say the format in the ADR.
7. Without a token and for a patient: free slots only. A clinician or an admin may ask
   for `busy`, `busy-tentative` (held while an email is verified) and `busy-unavailable`
   (time off). A busy slot never names the patient or the appointment.

Patient:

8. Read and search: the patient reads the own record, a clinician the patients who have
   an appointment with them, an admin everyone. Anyone else, and no token, gets 401 or
   403 by section 12.3, and a search returns only what the caller may read: never a
   count, a link or an error that tells whether another patient exists. Search: `name`,
   `email`, `phone`, `birthdate`. Name, birth date, email, phone, active.
9. Update: the patient changes the own phone and birth date, by the rules of the profile
   page (task 15); an admin as the admin console does (task 19). Any other element that
   differs from the stored record is refused and named, not ignored. `If-Match` with a
   stale version answers 412; without `If-Match` say in the ADR what happens.
10. A patient record is personal data: answers are never stored (`Cache-Control:
    no-store`), nothing of it reaches a log, and audit metadata holds ids and the names
    of changed fields only. Prove the log with a planted value.

Writes in general, decided once here for tasks 23a and 24:

11. `PUT /fhir/<Type>/<id>` replaces, `POST /fhir/<Type>` creates, `DELETE` deletes; the
    body is validated as a FHIR resource of that type and id before any use case runs; a
    body the server would not have produced itself (unknown element, wrong type, another
    resource's id) is 400 with the element named. A create answers 201 with `Location`
    and `ETag`; an update 200 with the new version.
12. Each failure of a use case maps to the status of section 4 and an `OperationOutcome`
    whose code a client can act on: `invalid_input` 400, `forbidden` 403, `not_found`
    404, `conflict` 409, `has_dependents` 409, `rule_violation` 422, stale version 412.
    One table in the domain layer, under the mutation gate, used by every write.
13. Every write is tested as a FHIR client sends it (bearer token, no cookie, no
    `Origin`, cross-site check enforced), joins the hostile-input test, and has its
    samples in `make fhir-validate`.

Tasks 20 and 21 (admin console) run beside this one. Keep out of their files:
`scheduling/views/pages/`, `scheduling/templates/`, `scheduling/use_cases/admin_*`.

The orchestrator creates and deletes a schedule with the demo clinician's token and
watches the slots follow in both APIs, reads slots by id, and tries to read and change
another patient's record with each role's token.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone, and `make test` stays under 45 seconds on a
machine that runs nothing else.
