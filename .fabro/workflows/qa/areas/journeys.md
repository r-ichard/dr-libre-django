Area: the journeys of a visitor and a patient, in the browser.

Specification: `drlibre-specs.md` sections 6, 7, 8 and 16. Use the `browser` tools for
everything, as a person would, at 375 px wide and at 1440 px, and with the keyboard
only for at least one full journey.

Walk at least:
- A visitor: search, filter, switch lists, open a provider and a hospital page, pick a
  time, give details, enter the code from `scratch/qa/mail.log`, reach the confirmation,
  download the calendar file.
- The same visitor later: ask for a sign-in link, follow it from the mail log, land in
  the portal.
- A patient (`patient@example.test`, `DEMO_PASSWORD`): home, book through the four steps,
  reschedule, cancel, join the waitlist, accept an offer, read and mark notifications,
  edit the profile, change the password, sign out.
- Every way out of the happy path: empty forms, wrong values, a slot taken in another
  tab, the back button after a POST, a second tab, an expired hold, a used link.

Report:
- Feature gaps against sections 6, 7 and 8: something the specification says the page
  shows or does that is missing or different.
- Bugs: a dead link, a 500, a form that loses what was typed, a wrong time or a time
  without its zone, a state with no way forward, a message that does not say what to do.
- Accessibility against section 16 (WCAG 2.2 level AA): a field without a label, an
  error not tied to its field, focus that does not move to the first invalid field,
  status shown by colour alone, a control that cannot be reached or used with the
  keyboard, text that overflows or a page that scrolls sideways at 375 px, poor
  contrast. Run the browser's accessibility audit on each page and also look yourself.
- Wording against section 16: plain, warm, precise, sentence case, no marketing text.
- Console errors and failed requests on every page.
