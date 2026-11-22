Task 23a: FHIR API, Appointment and booking.

`drlibre-specs.md` sections 15.2 to 15.6 for `Appointment`, on the conventions of tasks
22, 22a and 23 (ADR 0005, ADR 0003): one declaration, pure mappers under the mutation
gate, the write rules and the failure table of task 23, every answer FHIR JSON,
`make fhir-validate` over every new view. `AppointmentResponse`, `Communication` and
`AuditEvent` are task 24. A FHIR write runs the same use cases as the screens (tasks 08
and 09): the same booking rules, placement locks, audit entries, notifications and
emails. This task adds no second way to book.

Reading:

1. Read and search: the patient sees the own appointments, a clinician the own calendar,
   an admin all. No token: 401. Search: `patient`, `practitioner`, `location`, `status`,
   `date`, `service-type`; `_include` for `Appointment:patient`,
   `Appointment:practitioner` and `Appointment:location`. An included resource obeys its
   own access rule: a patient never receives another patient, and a clinician's email or
   phone only goes to staff.
2. Participants: patient, practitioner, room. `serviceType` is the appointment type.
   Source as an extension. Status by the table of 15.3, the internal value kept in an
   extension where two map to one. The patient's reason is `reasonCode.text`; the
   cancellation reason `cancelationReason.text`.
3. Clinical notes are `Appointment.comment` and are returned to the appointment's
   clinician only: not to the patient, not to an admin, not to another clinician, and
   not inside an `_include` or a Bundle of someone else. Prove each with a planted note.
   `ClinicalNote` declares `fhir_not_exposed`: correct the declaration and
   `doc/data-model.md` (carried from task 16).
4. One appointment, three origins, one resource type (ADR 0003):
   - a booking hold is an `Appointment` with status `pending`, for staff only;
   - a waitlist entry is `waitlist`, then `proposed` with the offered start, end and
     practitioner, then, from acceptance on, the booked appointment itself under the
     same id (`booked`), and `cancelled` when expired;
   - `requestedPeriod` is the window, an optional practitioner the preferred clinician.
   A search by `status` finds each under its FHIR status and nothing twice.
5. Answers are personal data: never stored, nothing of them in a log.

Booking (15.6):

6. Book: `POST /fhir/Appointment` with status `proposed`, the patient, the `serviceType`
   and either a `slot` reference (the ids of task 23) or a start with a practitioner.
   Without a practitioner it is "first available" (5.5), for a patient only (5.4). The
   answer is the appointment with status `booked`, the assigned practitioner and room,
   201, `Location`, `ETag`.
7. Who may book for whom is section 5.4, from the token: a patient for themself, a
   clinician into the own calendar for an active patient, an admin for any active
   patient with a named clinician. A `patient` participant the token may not book for is
   403, never a booking for the token's own user under another name.
8. Reschedule: `PUT` with a new start, same clinician and type. Cancel: status
   `cancelled` with a `cancelationReason`. Check in, complete, no-show: status
   `checked-in`, `fulfilled`, `noshow`. Any other change of status, and any change of
   another element (patient, type, clinician, room, end), is refused: 409 for a status
   the table of 5.6 does not allow, 400 naming the element otherwise. The end is never
   taken from the client (5.2).
9. `If-Match` on every update: a stale version is 412. Two clients that book the same
   slot: one gets 201, the other 409, and the database holds one appointment. Test the
   race with two transactions, as the tests of task 08 do.
10. Waitlist: `POST` with status `waitlist` and a `requestedPeriod` joins (5.8), for the
    patient's own token or an admin's. Accepting an offer is task 24.
11. Every refusal of a use case reaches the client as the `OperationOutcome` of task 23's
    table: each booking rule of 5.3 by its name (`lead_time_too_short`,
    `cancellation_window_closed`, `too_many_open_bookings`, `type_not_bookable_online`,
    `outside_availability`), a conflict with what is in conflict, `no_room_available`,
    `no_clinician_available`.
12. A booking made through FHIR is indistinguishable from one made on the screens: the
    same audit action and metadata, the same notification, the same email in the inbox,
    the same row in the patient's portal. Assert each for one booking, one reschedule
    and one cancellation.

Tasks 20 and 21 (admin console) may run beside this one. Keep out of their files.

The orchestrator books, reschedules and cancels with the demo patient's token and reads
the result in the portal and the inbox; books the same slot from two shells; and reads
an appointment that carries a clinical note with each role's token.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone, and `make test` stays under 45 seconds on a
machine that runs nothing else.
