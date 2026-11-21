Task 07: booking use cases and API.

Placing an appointment (`drlibre-specs.md` sections 5.2, 5.4, 5.5) on top of the pure
engine of task 06, with the three endpoints of section 14 that read slots and book.
Cancel, reschedule and status changes are task 08; the waitlist is task 09; screens come
later. This is the code that must never double book.

1. Free slots query. Loads the rules, time off, active appointments and unexpired booking
   holds a clinician needs and calls the engine. With no clinician: every active
   clinician of the type's department, without one query per clinician. An unexpired
   `BookingHold` makes its slot busy (section 7.1); creating holds is task 12, counting
   them is now.
2. Placing (5.2): one use case that every booking path will call, running the six steps
   in the order of the specification and stopping at the first failure with the code the
   specification names. `conflict` lists the resources in conflict: clinician, patient,
   room. The end time is start plus the type's duration and is never taken from the
   caller. Room choice follows step 5 exactly.
3. No double booking under concurrency. Say in the plan what is locked and in which
   order so two placements cannot both pass the checks and cannot deadlock. The
   exclusion constraints stay the last line: a constraint violation becomes `conflict`
   naming the resource, never a 500. Test with two real transactions racing for the same
   clinician, the same patient and the same room: exactly one wins each time.
4. One transaction per booking (section 4): the appointment, its audit entry through the
   audit writer and the in-app notification "Appointment booked" for the patient
   (section 11; text carries the time only). Email is task 08.
5. Who may book for whom (5.4), with identity from the session only: a patient for
   themself and never a room; a clinician into their own calendar for a named active
   patient; an admin for any active patient with a named clinician.
6. First available (5.5) when a patient names no clinician: candidates, ranking by the
   engine, booking with source `ROUND_ROBIN`, last assignment time set to now, all in the
   placing transaction. No candidate gives `no_clinician_available`.
7. API (section 14), strict schemas, the failure contract, declared access:
   `GET /api/v1/slots` (public; type, optional clinician, a range of at most 31 days),
   `GET /api/v1/appointments` (signed in; filters by patient, clinician, status and
   range, never more than the caller may see; paged), `POST /api/v1/appointments`.
   Times go out in UTC with the hospital's time zone named beside them.
8. The rules the model plan left to use cases
   (`doc/plans/2026-11-21-domain-model.md`, "Waits for its use case") that concern
   booking are enforced here and tested: same department for clinician and type, roles
   behind `patient` and `clinician`, active room, room of the clinician's department.

Done when `make setup && make lint && make test && make gate` pass from a fresh clone and
`make mutate` still reports on the domain modules.
