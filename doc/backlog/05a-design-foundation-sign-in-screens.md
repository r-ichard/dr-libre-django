Task 05a: design foundation, sign-in screens, role homes and error pages.

The first screens of the product. Every later screen reuses this layout, these components
and this CSS, so build them to be reused. Server-rendered Django templates, hand-written
CSS, no CSS framework, no Node build, and no inline script or style: the content security
policy of task 04b forbids them. Impeccable mode is on for this task: read the
`impeccable` skill and its `reference/craft-floor.md` before the first template.
`drlibre-specs.md` section 16 is the product truth.

1. Product and design context, short, so later tasks reuse instead of reinventing:
   `PRODUCT.md` (who uses DrLibre, what they come to do, the voice: plain, warm, precise,
   sentence case, no marketing text) and `DESIGN.md` (tokens for colour, type scale,
   spacing, radius and focus ring, and the component list with its states).
2. Base layout: skip link, header with the product name and the signed-in user's name and
   sign-out when there is one, one `main` landmark, footer. The page declares its
   language. Usable from 375 px to 1440 px wide.
3. CSS foundation, served as static files: tokens as custom properties, base typography,
   and the components the coming screens need: buttons (primary, secondary, danger), text
   field with label, hint and error, select, checkbox, error summary, notices (information,
   success, warning, error), card, table, pagination, status badge, empty state and
   loading state. Status is never shown by colour alone.
4. A style page at a route that exists only when `DEBUG` is on, showing every component
   in every state, so the result can be checked in a browser now and by later tasks.
5. Sign-in screen (section 12.1): email and password in a form that works without
   JavaScript, through the sign-in use case of task 05. Same message for a wrong email
   and a wrong password, a message for the lockout, errors tied to their field with
   focus on the first invalid one, protected against cross-site requests. Sign-out is a
   POST.
6. Role homes: three pages (patient portal, clinician workspace, admin console), each
   behind its access rule, greeting the user by name, otherwise empty for now. A user in
   another role's area sees a forbidden page. Without a session the user is sent to
   sign-in and, after signing in, back to the page they asked for: only ever to a local
   path, test an external address in that parameter.
7. Error pages for 403, 404 and 500 in the layout, with a plain message and the
   correlation id so a user can quote it. They are what users see when `DEBUG` is off;
   record in `CLAUDE.md` what a developer sees when it is on.
8. The root path answers with a page: for now the product name and a link to sign-in.
   The public search replaces it in task 10.
9. Accessibility to WCAG 2.2 level AA (section 16): keyboard operable, visible focus,
   labelled fields, contrast, headings in order, targets large enough to tap. Test what
   the server can prove in the rendered HTML: one `h1`, every field with its label, each
   error referenced from its field, the first invalid field marked for focus, the
   language declared.

The sandbox has no browser. Say in your reply that the visual result is unverified. The
orchestrator checks every page in Chrome at 375, 768 and 1440 px, with the keyboard only,
and with an accessibility audit.

Done when `make setup && make lint && make test && make gate` pass from a fresh clone.
