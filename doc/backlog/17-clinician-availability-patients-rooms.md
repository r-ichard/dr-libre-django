Task 17: clinician workspace, availability, time off, patients and rooms.

The rest of `drlibre-specs.md` section 9, for signed-in clinicians, on top of task 16.
Availability and time off are new writes: each is a use case with its audit entry in the
same transaction and raises the record's version (ADR 0003). Impeccable mode is on: read
`PRODUCT.md`, `DESIGN.md` and the `impeccable` skill, reuse the existing components, no
inline script or style, every step works without JavaScript.

1. Availability. List, create, edit and delete the clinician's own availability rules:
   weekday, start and end time, slot step, optional room. A rule's room must be an
   active room of the clinician's department. Two rules of the same clinician on the same
   weekday may touch but not overlap. A new rule is valid from today with no end date.
   Weekdays are stored 0 Sunday to 6 Saturday and shown by name.
2. Time off. List, create and delete the clinician's own time off: start, end after
   start, optional reason of up to 200 characters. An identical period cannot be
   recorded twice. Time off does not cancel appointments already booked in it: say so on
   the page, and list the appointments that fall inside a period being recorded.
3. Each rule the specification states here is decided by a pure function in the domain
   layer, under the mutation gate, and held by the database where one row or one table
   can express it. Add what the model needs with a migration and regenerate
   `doc/data-model.md`.
4. A change of availability changes what the public search and the booking pages offer,
   at once and through the same loading. Test that a new rule's slots appear in
   `GET /api/v1/slots` and a deleted rule's disappear.
5. Patients. The patients who have at least one appointment with this clinician, with
   phone, last visit and next visit, and a search by name. No other patient is ever
   listed or found, whatever the search text. In pages.
6. Rooms. A day timeline from 07:00 to 19:00 of the active rooms of the clinician's
   department. The clinician's own appointments show the patient's name; others show
   "Occupied" and nothing else about them. Colour is never the only signal, and the
   timeline also reads as a list for a screen reader and at 375 px.
7. A clinician reaches only their own rules and time off: another clinician's ids answer
   by the record rule. Pages that show patient data are never cached.
8. The workspace navigation of task 16 gains these sections. Accessibility to WCAG 2.2
   level AA and 375 px to 1440 px. Test what the server can prove in the rendered HTML.
   Every form is tested as a browser sends it.

The sandbox has no browser. The orchestrator adds and removes a rule as the demo
clinician in Chrome and watches the public search follow.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
