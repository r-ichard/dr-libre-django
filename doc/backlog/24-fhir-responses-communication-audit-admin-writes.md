Task 24: FHIR API, the remaining resources and the admin writes.

`drlibre-specs.md` sections 15.2, 15.4 and 15.5 for `AppointmentResponse`,
`Communication` and `AuditEvent`, and the writes of 15.4 that tasks 22 to 23a left out,
on the conventions of those tasks (ADR 0005, ADR 0003): one declaration, pure mappers
under the mutation gate, the write rules and the failure table of task 23, every answer
FHIR JSON, `make fhir-validate` over every new view. After this task the
CapabilityStatement names every resource, interaction and search parameter of section
15, and nothing else.

AppointmentResponse (waitlist acceptance):

1. Create: the patient accepts the own offer, or an admin accepts it for the patient,
   with participant status `accepted`, through the accept use case of task 09. The
   answer links the `Appointment`, which is now `booked` under the same id (ADR 0003).
   A second acceptance, an offer that is gone, a slot someone else took: the refusal of
   the use case, by the failure table (5.8: "accepting fails with `conflict`").
2. Read and search: the patient the own, an admin all. Any other participant status is
   refused: declining is not in the specification; say so in the ADR.

Communication (notification):

3. Read and search for the recipient only: `recipient`, `category` (the kind), `sent`.
   Payload text, `sent`, `received` (the read time), `about` the appointment or the
   waitlist entry's appointment. An admin does not read another user's notifications.
4. Update: the recipient may set `received`, through the mark-as-read use case of task
   15, once; any other change is refused and named. No create, no delete: 405.

AuditEvent:

5. Read and search for an admin only: `agent`, `entity`, `entity-type`, `action`,
   `date`. Action, time, agent, entity, the metadata as entity details, the correlation
   id. Read-only: every write is 405. The log only grows: a search page costs a bounded
   number of queries and stays fast on 50 000 entries; assert both.
6. What the audit log may not hold (section 4) it cannot leak: assert on the demo seed
   that no AuditEvent carries a name, an email address beyond its domain, a phone
   number, a birth date, a reason or a note.

Admin writes (15.4, "Create, update, delete: Admin"):

7. `Organization`, `Location`, `HealthcareService`, `CodeSystem` and `ValueSet`: create,
   update and delete with an admin's token, through the use cases of the admin console
   (task 18): the same field checks, the same refusals of a delete with what still uses
   the record (`has_dependents`), the same audit. A hospital is two resources and one
   record: say in the ADR which of the two a client writes and what the other answers.
   The specialty list is one `CodeSystem` and one `ValueSet`: say how a client adds,
   renames and removes one specialty.
8. `Practitioner` and `PractitionerRole`: create, update and delete with an admin's
   token, through the use cases of task 19. A clinician's token may update the own
   `PractitionerRole.notAvailable` and nothing else: adding a period records time off,
   removing one deletes it, through the use cases of task 17. A period that changed in
   place is refused: time off is recorded and removed, not edited.
9. `If-Match` on every update and delete: a stale version is 412. The version of a
   resource built from several rows follows ADR 0003; test that a change of a child row
   moves the parent's `versionId`.
10. Every write is tested as a FHIR client sends it, with each role's token and with
    none; joins the hostile-input test; and has its samples in `make fhir-validate`.

Closing section 15:

11. A test walks the tables of 15.2, 15.4 and 15.5 as data and asserts, against the
    CapabilityStatement and against the running routes, that each resource, interaction,
    search parameter and `_include` named there is served and that nothing else is.
12. ADR 0005: every open point is closed or handed to the owner with the choice made.
    The README gains a section on the FHIR API: how to issue a token, one read, one
    search, one booking, with curl.

The orchestrator accepts a waitlist offer, marks a notification as read and reads the
audit trail of both through `/fhir`; creates and deletes a hospital with the admin's
token; and records time off with the clinician's token and sees it in the calendar.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone, and `make test` stays under 50 seconds on a
machine that runs nothing else.
