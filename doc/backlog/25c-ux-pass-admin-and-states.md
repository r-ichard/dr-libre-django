Task 25c: UX pass, admin lists, the conflict page, and the states of every page.

Five items of task 25 (`doc/backlog/25-accessibility-and-ux-pass.md`, items 11, 12, 14,
15 and 16) that its run did not reach. Impeccable mode is on: read `PRODUCT.md`,
`DESIGN.md` and the `impeccable` skill, reuse the existing components, no inline script
or style, every step works without JavaScript. Reproduce what the rendered HTML can show
with a failing test first; where a fix is about size or place, state the invariant and
its measurement (`CLAUDE.md`, "Layout").

1. Admin lists and the dashboard's table at 375 px: the table is wider than its frame
   and scrolls sideways (the appointment types list is 762 px in a 341 px frame; the
   dashboard table 507 px), so a phone shows the first column and half of the second.
   Under 40rem each row reads as a card with every value labelled; from 40rem it is the
   table. One component for every admin list. Measured at 375 px on every list: the
   frame does not scroll (`frame.scrollWidth <= frame.clientWidth`) and the page does
   not either. A screen reader still gets a table with headers, or a list that says the
   same: say which in the plan and why.
2. After a save over a newer version the page says "Another admin saved this record
   first ... Saving again replaces theirs" and shows nothing of the other save. Show,
   field by field, the value the admin read, the value now stored and the value the
   admin typed, for the fields that differ, before the admin decides. The values come
   from a use case read, not from the view.
3. Every status the product shows is a word, with an icon where there is one, never
   colour alone: appointment, waitlist entry, user, clinician, record, token. A test
   lists every status value of the domain vocabulary and fails when one has no word in
   the place it is rendered.
4. Every list has an empty state that says what is not there and what to do next, and
   every refused form keeps what was typed. List in the plan the lists and forms found
   without one, and fix them; a test over every list page with an empty database.
5. Destructive actions confirm first (section 16): list every action that deletes,
   cancels, deactivates or revokes, and show that each has a confirmation step that
   names what will happen; a test fails when a route that destroys has none.
6. Every changed page passes the page quality test of task 25.

The orchestrator opens every admin list and the dashboard in Chrome at 375 px and
1440 px, saves one record from two tabs, and empties a list.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
