Task 14: patient portal, home and appointments.

`drlibre-specs.md` section 8 (home, book, appointments, reschedule, cancel, calendar
file) and section 7.4, for signed-in patients whichever way they signed in. Waitlist,
notifications and profile are task 15. Every action goes through the use cases of tasks
07 and 08; this task adds pages, not rules. Impeccable mode is on: read `PRODUCT.md`,
`DESIGN.md` and the `impeccable` skill, reuse the existing components, no inline script
or style, every step works without JavaScript.

1. Home. A greeting, the next upcoming appointment, the count of unread notifications
   and a "Book an appointment" action. A patient who signs in by link or by booking code
   lands here (7.4).
2. Appointments. Two lists. Upcoming: status `BOOKED`, `CONFIRMED` or `CHECKED_IN` and
   not yet started, soonest first. Past: everything else, latest first, in pages. Each
   row shows whom (provider, title, specialty), when (date, start and end, time zone
   named), where (hospital name and address, department, room when assigned), the type,
   the status as a badge that is never colour alone, and the patient's own reason. It
   offers the calendar file, and cancel and reschedule when the rules allow them. When
   they do not, the row says why in plain words (less than 24 hours ahead, already
   started, already cancelled) and gives the hospital's phone number.
3. Book. The four steps of section 8: service (online-bookable appointment types grouped
   by hospital and department), provider (a named one or "first available"), time (the
   week strip) and review with an optional reason. The last two are the pages of task
   12a; add the first two and lead into them. The search and the public pages lead into
   the same steps.
4. Reschedule. The week strip of free slots for the same provider and type, then a
   review that shows the old and the new time before confirming.
5. Cancel. A confirmation step with a required reason: a page, so it works without
   JavaScript.
6. Every refusal from a use case has its message and a way forward, as on the booking
   pages: each booking rule in plain words, a slot taken meanwhile, a status that no
   longer allows the action.
7. A patient sees and changes only their own appointments. The pages take the patient
   from the session; another patient's appointment id in the address answers not found
   or forbidden by the record rule (section 12.3), never the appointment. Test it. Pages
   that show personal data are never cached.
8. Empty states for a patient with no upcoming and no past appointment, each with the
   action that makes sense there.
9. Accessibility to WCAG 2.2 level AA and 375 px to 1440 px. Test what the server can
   prove in the rendered HTML. Every form is tested as a browser sends it.

The sandbox has no browser. The orchestrator signs in as the demo patient in Chrome,
books, reschedules, cancels and downloads a calendar file at 375 and 1440 px, with the
keyboard only, and runs an accessibility audit.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
