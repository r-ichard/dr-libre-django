Task 25d: UX pass, page titles, status words and empty states.

What tasks 25 to 25c left of `doc/backlog/25-accessibility-and-ux-pass.md`, and one
defect found in the browser. Impeccable mode is on: read `PRODUCT.md`, `DESIGN.md` and
the `impeccable` skill, reuse the existing components, no inline script or style.
Reproduce what the rendered HTML can show with a failing test first.

1. Found in Chrome: the admin appointments page's `<title>` holds a whole form. In
   `scheduling/templates/admin/appointments.html` the export form sits inside
   `{% block title %}`, so the browser tab, the history and a bookmark read
   "Appointments · DrLibre<form class="form" method="post" ...>" followed by the
   cross-site token of the session. The form belongs in the page, once. Rule: a page
   title is plain text. The page quality test (`scheduling/views/pages/test_page_quality.py`)
   fails on a title that contains `<`, a token, more than 80 characters, or that two
   different pages share; and no cross-site token appears anywhere outside a form.
2. Every status the product shows is a word, with an icon where there is one, never
   colour alone: appointment, waitlist entry, user, clinician, hospital, room,
   appointment type, specialty. The admin lists print "Active" and a bare status as
   plain text while the patient's pages use the badge component. One component, used
   wherever a status is rendered; a test lists every status value of the domain
   vocabulary and fails when one has no word and no badge where it is rendered.
3. Every list has an empty state that says what is not there and what to do next: the
   dashboard's "Appointments per day" with no day, a search that finds nothing, a
   filter that leaves nothing, a clinician with no patient, no rule, no time off, a
   patient with no appointment, no waitlist entry, no notification. A test opens every
   list page of the product with an empty database, and with a search that finds
   nothing, and fails on a list without one.
4. Every refused form keeps what was typed, except a password. A test posts a refused
   value to every form of the product and compares.

The orchestrator opens five pages in Chrome and reads their tab titles, and empties the
database behind one list of each role.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
