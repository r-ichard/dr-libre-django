Task 20: admin console, appointments, waitlist, audit log and settings.

`drlibre-specs.md` section 10 (appointments, waitlist, audit log, settings) with the
rules of sections 4, 5.2 to 5.8 and 12, for signed-in admins, on top of tasks 18 and 19:
reuse their list flow and navigation. Booking, cancelling, rescheduling, status changes,
waitlist offers and the reminder job already exist as use cases (tasks 08 and 09); this
task adds pages and only the use case code those pages lack. The CSV export of the
appointment list is task 21. Impeccable mode is on: read `PRODUCT.md`, `DESIGN.md` and
the `impeccable` skill, reuse the existing components, no inline script or style, every
step works without JavaScript.

Appointments:

1. A list filtered by date range, department, clinician, status and source, newest
   first, 20 rows per page with the total count. The filters live in the address, so a
   filtered list can be reloaded and shared; an unusable value falls back to the default
   (section 4). Times are shown in the zone of the appointment's hospital, named.
2. One appointment: patient, clinician, type, room, time, status, source, reason and its
   history, with the actions section 5.6 gives an admin: check in, complete, no-show,
   cancel with a required reason. Never a clinical note, whoever wrote it.
3. Book for a patient: find the patient by name or email, then the booking steps of the
   portal without "first available", with every active type, the ones that are not
   bookable online included. An admin is bound by availability and conflicts only
   (section 5.3). The appointment's source is `STAFF`.
4. Reschedule any appointment that is `BOOKED` or `CONFIRMED`, from the week strip.
5. Every refusal a use case returns is shown with its message and a way forward.

Waitlist:

6. A list filtered by status, oldest first, with patient, type, preferred clinician,
   window, status and the offered slot.
7. Add a patient to the waitlist. Offer a `WAITING` entry the first future cancelled
   slot of its type inside its window (section 5.8, "Manual offer"): refused with the
   reason when no such slot exists, when the clinician is no longer free then, or when
   another entry holds that offer. Accept an `OFFERED` entry for the patient.
8. Carried from the review of task 09: an offer that went stale is detected by an
   overlap of the clinician only, and the manual offer loads every future cancelled slot
   of the type. Check the room and the patient too, and load the first slot that fits.

Audit log:

9. A read-only list, newest first, filtered by actor, entity type and date range, 20
   rows per page with the total count: time, actor, action in plain words with its code,
   entity and correlation id. No metadata, no form, no route that changes an entry.
10. The log only grows. Say in the plan how a page deep in a long log stays fast, and
    test the list on a log of 50 000 entries inside the time budget below.

Settings:

11. The booking policy constants of section 5.3 (120 minutes, 24 hours, 3 open
    bookings), read-only and taken from where the rules read them, and a button that
    runs the reminder job (section 5.7) and says how many reminders it created.

Everywhere:

12. A patient, a clinician and a visitor reach none of these pages. Every new route
    joins the role test and the hostile-input test of the earlier tasks. Every audit
    action has its plain words; no page holds the same element id twice.
13. Pages that show patient data are never cached. Accessibility to WCAG 2.2 level AA and
    375 px to 1440 px. Test what the server can prove in the rendered HTML. Every form
    is tested as a browser sends it.

The sandbox has no browser. The orchestrator books for a patient as the demo admin in
Chrome, cancels the appointment, offers the freed slot to a waiting entry, accepts it for
the patient, and finds each step in the audit log.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone, and `make test` stays under 30 seconds in the sandbox.
