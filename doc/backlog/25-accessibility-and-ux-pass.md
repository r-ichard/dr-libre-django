Task 25: accessibility and UX pass.

`drlibre-specs.md` section 16 over every page the product has. Impeccable mode is on:
read `PRODUCT.md`, `DESIGN.md` and the `impeccable` skill and its
`reference/craft-floor.md`; reuse the existing components; no inline script or style;
every step works without JavaScript. This task changes pages, templates, style sheets and
wording. It changes no rule of the product: a fix that needs a use case or a model to
change is named in the reply and left alone.

The findings below were collected while the product was built; each has been seen in a
browser by the orchestrator or a QA run. The sandbox has no browser, so each fix states
its invariant and, where it is about size or place, the measurement that proves it
(`CLAUDE.md`, "Layout"). Reproduce what the rendered HTML can show with a failing test
first.

Public pages and sign-in:

1. The sign-in page shows the password form first; most patients have no password. The
   email link comes first, the password form second, with a line that says who uses
   which. On a wide screen the page sits at the left edge with empty space beside it:
   single-form pages share one centred measure.
2. The "link not valid" page does not show the signed-in user in its header.
3. The terms and the privacy notice a visitor accepts when booking have no page to read.
   Add both pages with plain placeholder text that says the hospital must supply its
   own, link them from the checkbox, and keep what was typed when the visitor returns.
4. The date of birth is a date picker, which makes a birth year a long way to scroll.
   Three fields (day, month, year) in one group, with the group's error tied to it.
5. The lockout message says "15 minutes" as text; it follows `LOCKOUT_WINDOW`. The
   favicon uses the primary colour token.

Patient portal:

6. Accepting a waitlist offer lands on the appointments without a notice.
7. The notifications page jumps from an `h1` to `h3`. Every page has headings in order,
   one `h1`: add a test over every page the product renders.
8. Notification times are shown in UTC; the rest of the portal uses the hospital's zone
   and names it.
9. "Appointment booked", "Waitlist slot offered" and every email write dates as
   "2026-11-23 at 13:00"; pages write "Monday 23 November 2026, 13:00". One way to
   write a date and time for a person, in one place, used by pages, notifications and
   emails. Test that no notification body and no email holds an ISO date.

Clinician workspace:

10. Time grid: an appointment inside a time off band has 105 px for its time line, which
    needs 114 px ("13:00–13:15" in bold after the 14 px status icon), so the end time
    ends in an ellipsis. The time line of every block shows the start and the end in
    full: `scrollWidth <= clientWidth` for the first line of every block at 1440 px and
    1024 px. Say in the plan where the 9 px come from.

Admin console:

11. At 375 px a list is a table that scrolls sideways inside its frame and shows the
    name and half of the code. Under 40rem each row reads as a card with every column
    labelled, with no sideways scroll inside the page or the frame; from 40rem it is
    the table. The same component for every admin list.
12. The page after a save over a newer version says "saving again replaces theirs" and
    shows nothing of the other admin's values. Show, field by field, what the other
    save changed, before the admin decides.

Everywhere:

12a. The notice an admin sees after an action is carried in a signed cookie as a whole
    sentence, with the patient's name in it ("Booked for Greta Holm"). Signed is not
    hidden: the name sits readable in the browser's cookie store. The cookie carries a
    code and ids; the page writes the sentence from what the reader may read.

13. A test walks every page the product can render, signed out and as each role, and
    fails on: a form field without a label, an image without a text alternative, a
    duplicate id (exists since task 17c), headings out of order, a link or button
    without a name, a table without header cells, a page without a `title`, `lang` or
    `main`. Derive the pages from the URL configuration so a new page is covered.
14. Every status the product shows (appointment, waitlist, user, record) is a word, with
    an icon where there is one, never colour alone: assert it where the status is
    rendered.
15. Empty, loading and error states: every list has an empty state that says what is
    not there and what to do; every form's refusal keeps what was typed. List in the
    plan the lists and forms found without one, and fix them.
16. Destructive actions confirm first (section 16): list every action that deletes,
    cancels, deactivates or revokes, and show that each has a confirmation step.

The orchestrator then runs a QA round with a browser over every area, at 375 px and
1440 px, with a keyboard only, and files what is left.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
