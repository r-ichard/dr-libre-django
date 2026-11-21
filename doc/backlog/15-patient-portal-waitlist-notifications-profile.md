Task 15: patient portal, waitlist, notifications and profile.

The rest of `drlibre-specs.md` section 8, for signed-in patients, on top of task 14 and
the use cases of tasks 08 and 09. Impeccable mode is on: read `PRODUCT.md`, `DESIGN.md`
and the `impeccable` skill, reuse the existing components, no inline script or style,
every step works without JavaScript.

1. Waitlist. A form to join (appointment type, optional preferred provider, a date
   window) and the list of the patient's own entries with their status. An offered entry
   shows the offered time, provider and hospital and an accept button. Accepting goes
   through the use case of task 09, and every refusal (the slot was taken, a booking
   rule) has its message and a way forward.
2. Notifications. The in-app list, newest first, in pages, with "mark as read" for one
   and for all, and the unread count the home page already shows. Marking as read is a
   write: it goes through a use case, is audited (section 4) and changes only the
   patient's own notifications.
3. Profile. Name and email are shown, not edited. Phone (7 to 20 characters of digits,
   spaces, `+ ( ) -`) and date of birth (a real date, not in the future) are editable;
   empty input clears them.
4. Change password: the current password and a different new one of 10 to 72 characters.
   A passwordless patient does not see it and cannot reach it by address either. A wrong
   current password counts as a failed sign-in for the lockout of task 05. Changing the
   password ends the patient's other sessions.
5. Every write is a use case with its audit entry in the same transaction; audit
   metadata holds the names of changed fields, never the phone number, the birth date or
   anything of a password.
6. A patient reaches only their own entries, notifications and profile: ids in an
   address are checked against the session by the record rule, and tested with another
   patient's ids.
7. The portal has one navigation that names its sections (home, appointments, waitlist,
   notifications, profile) and shows which one is current, usable with the keyboard and
   at 375 px.
8. Empty states for no entry and no notification. Accessibility to WCAG 2.2 level AA and
   375 px to 1440 px. Test what the server can prove in the rendered HTML. Every form is
   tested as a browser sends it.

Carried from the browser check of task 14, to fix here:

- In the appointment lists the cards touch each other: the measured space between two
  cards is 0 px. A list of cards uses the spacing token, here and in the new lists.
- A past appointment that is completed, missed or cancelled says "This appointment
  already took place. Call the hospital on ...". Say why an action is missing only where
  the patient could expect one: an upcoming appointment less than 24 hours ahead or one
  that has started.
- A week strip that cannot be loaded for a reschedule answers a bare 404; give it the
  refusal page with a way back to the appointments.

The sandbox has no browser. The orchestrator joins the waitlist, accepts an offer, reads
notifications and edits the profile as the demo patient in Chrome.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
