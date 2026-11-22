Task 25a: UX pass, the week fits again, and what the first run left small.

This branch holds the part of task 25 (`doc/backlog/25-accessibility-and-ux-pass.md`)
that its run finished: the sign-in page, the notice cookie, notification times, the page
quality test, headings. Its review is in `doc/reviews/`. It is not merged, because one of
its fixes broke the week view. This task repairs that and closes the small leftovers; the
large items the run did not reach are tasks 25b and 25c and are not yours. Impeccable
mode is on; no inline script or style.

Measured by the orchestrator in Chrome on `/clinician/calendar?week=2026-11-23`:

1. To give the time line of an appointment 9 more pixels, the day columns went from 9rem
   to 10rem (`static/css/time-grid.css`, `grid-auto-columns: minmax(10rem, 1fr)`). Seven
   columns of 160 px no longer fit the page: at 1440 px the week grid scrolls sideways by
   136 px inside its frame and the weekend is cut off. Two rules, both measured, both
   stated as arithmetic in the plan and held by the style sheet test:
   - at 1440 px the seven day columns fit: `grid.scrollWidth <= grid.clientWidth`;
   - the first line of every block shows the start and the end in full, alone in its
     column and beside the rail of a time off band:
     `line.scrollWidth <= line.clientWidth`.
   The page is 1088 px wide inside its margins at 1440 px, the axis takes 56 px, and the
   gap is 8 px: derive the column width from that and find the 9 pixels inside the
   block (the rail, the icon, the padding, where the status icon sits), not in the
   column. Below 1440 px the grid may scroll inside its frame as it does today; the
   page itself never does.
2. The sign-in page says "We send a link that works for 15 minutes" as text. It follows
   `LINK_LIFETIME`, as the lockout message follows its constant.
3. The sign-in page says "Patients use the email link. Clinicians and admins use a
   password." A patient an admin created has a password too. Say who uses which without
   saying something false.
4. Review of task 25, second pass: `notice_sentences.py` queries the database from the
   views layer; read through a use case (section 8). `_shown_at` in
   `patient_notifications.py` loads appointment, type, department and hospital once per
   notification; load them with the page, and assert the number of queries.
5. The favicon's colour is typed in twice; a test ties `static/favicon.svg` to the
   primary colour token.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
