Task 25b: UX pass, booking and the patient's pages.

Three items of task 25 (`doc/backlog/25-accessibility-and-ux-pass.md`, items 3, 4 and 9)
that its run did not reach; each needs a page, a form or a rule of its own. Impeccable
mode is on: read `PRODUCT.md`, `DESIGN.md` and the `impeccable` skill, reuse the existing
components, no inline script or style, every step works without JavaScript. Reproduce
what the rendered HTML can show with a failing test first.

1. The terms and the privacy notice a visitor accepts when booking have no page to read.
   Add both, with plain placeholder text that says the hospital must supply its own
   wording, reachable without signing in and from the footer of every page. The checkbox
   of the booking details form links to them; a visitor who reads one and comes back
   finds everything they typed (no script: say in the plan how).
2. The date of birth is a date picker, which makes a birth year a long way to scroll.
   One group of three fields, day, month and year, with one legend, numeric keyboards on
   a phone, the right `autocomplete` values, and one error for the group that names what
   is wrong ("Enter a year", "That date does not exist", "A date of birth is in the
   past"). The same component in the booking details form and the patient's profile; the
   value the use cases receive does not change.
3. One way to write a date and time for a person. Pages write "Monday 23 November 2026,
   13:00 (Europe/Berlin)"; the notifications "Appointment booked", "Waitlist slot
   offered" and "Appointment reminder", and every email, write "2026-11-23 at 13:00".
   One pure function in the domain layer, under the mutation gate, used by pages,
   notification bodies and emails; the zone is always named. A test over every
   notification kind and every email the product sends fails on an ISO date. The demo
   seed's notifications follow, because it books through the use cases.
4. Every new page and the changed forms pass the page quality test of task 25
   (`scheduling/views/pages/test_page_quality.py`) and the hostile-input test. Every
   form is tested as a browser sends it.

The orchestrator books as a visitor in Chrome at 375 px, reads the terms on the way,
types a birth date with the keyboard only, and reads the emails in the inbox.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
