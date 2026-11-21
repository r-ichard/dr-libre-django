Area: the clinician workspace.

Specification: `drlibre-specs.md` sections 5.6, 9 and 12.3. Demo clinicians:
`clinician@example.test`, `clinician.heart@example.test` (same department),
`clinician.skin@example.test`, `clinician.general@example.test`,
`clinician.child@example.test`, all with `DEMO_PASSWORD`. Use the browser for the pages
and `curl` for direct requests.

Try at least:
- Today, calendar and appointment pages: what section 9 says each shows; the status
  actions offered against the table of section 5.6; each action done twice, in two tabs,
  and on an appointment in a status that no longer allows it.
- Clinical notes: only the appointment's clinician reads and writes them. Plant a note,
  then look for it as a clinician of the same department, an admin and the patient, in
  every page, every API answer, the mail log, the server log, the audit table and the
  notifications. Try 5000 and 5001 characters, markup, and a script tag.
- Another clinician's data: appointments, availability rules and time off by id, through
  the pages and by direct POST. A missing id and someone else's id must not answer alike
  in a way that leaks, and must never show the record.
- Availability: every rule of section 9 (touch but not overlap, room of the department
  and active, valid from today), odd times, a rule across midnight, slot step limits, the
  weekday shown against the weekday stored, and that public slots follow a change.
  Deleting a rule that has future appointments.
- Time off: identical periods, end before start, a reason of 200 and 201 characters,
  that it hides slots, and that the page says which booked appointments fall inside it.
- Patients: only this clinician's own patients, whatever the search text, including
  wildcard characters and another patient's exact name or email address.
- Rooms: other clinicians' appointments show as "Occupied" and nothing else, in the page
  source too.
- The week grid and the rooms timeline at 375 px and 1440 px: do the blocks sit at the
  hour their label says, is the text readable, does it work with the keyboard and read
  sensibly without the layout.
- Accessibility (section 16) and console errors on every page of the workspace.
