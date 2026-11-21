Task 16: clinician workspace, today, calendar and appointment.

`drlibre-specs.md` section 9 (today, calendar, appointment), for signed-in clinicians.
Availability, time off, patients and rooms are task 17. A clinician sees and changes only
their own calendar. Status actions, cancel and reschedule go through the use cases of
task 08; this task adds pages and one new use case, clinical notes. Impeccable mode is
on: read `PRODUCT.md`, `DESIGN.md` and the `impeccable` skill, reuse the existing
components, no inline script or style, every step works without JavaScript.

1. Today. The agenda of one day in the hospital's time zone, with previous, next and
   today navigation. Tiles: appointments (cancelled ones counted separately), completed,
   no-shows, next free slot. Appointments grouped by hour, each with the patient, type,
   room, status and the status actions the table of section 5.6 allows right now.
2. Calendar. A week grid from 07:00 to 19:00 in 30 minute rows with the clinician's
   active appointments in the colour of their type and time off as blocks, with previous
   and next week. The colour is stored data and the content security policy forbids
   inline style: say in the plan how a type's colour reaches the page. Colour is never
   the only signal: each block names its type and patient. The grid must also read as a
   list for a screen reader and at 375 px.
3. Appointment. The patient's name, phone and age, the time, type, room, reason and
   status. Actions: check in, complete, no-show, cancel (with a required reason).
   Reschedule for the patient from the week strip. History: the audit entries of this
   appointment in time order, with the time, the action and who acted.
4. Clinical notes, up to 5000 characters, saved separately from everything else and
   visible to this clinician only: not to the patient, not to an admin, not in any API
   body, notification, email, audit entry or log line. Saving is a use case with its
   audit entry in the same transaction, whose metadata names the changed field and
   nothing of its content. Prove each "not" with a planted note.
5. Opening another clinician's appointment shows "Not your appointment" and nothing of
   it. An appointment that does not exist answers not found. Test both.
6. A clinician who is not bound by the patient rules (section 5.3) still sees every
   refusal a use case returns, with its message and a way forward.
7. The workspace has one navigation that names its sections (today, calendar, and the
   sections task 17 will add) and shows which one is current.
8. Pages that show patient data are never cached. Accessibility to WCAG 2.2 level AA and
   375 px to 1440 px. Test what the server can prove in the rendered HTML. Every form is
   tested as a browser sends it.

The sandbox has no browser. The orchestrator signs in as the demo clinician in Chrome,
runs a day (check in, complete, no-show, cancel), writes a note and checks who can read
it.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
