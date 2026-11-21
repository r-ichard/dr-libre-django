Task 10a: public search pages.

The landing page of the product (`drlibre-specs.md` sections 6.1 to 6.5) on top of the
search use case of task 10, linking into the booking pages of task 12a. Open to
everyone. Impeccable mode is on: read `PRODUCT.md`, `DESIGN.md` and the `impeccable`
skill, reuse the components of task 05a, no inline script or style.

1. The root path is the search: one search box, the filters of 6.3, the sort of 6.4, and
   three lists the visitor switches between (providers, hospitals, specialties). It works
   without JavaScript as a plain GET form.
2. Results show exactly the columns of 6.2. A provider shows the next 3 free slots, each
   leading to the booking pages for that type, provider and time in one click, and a link
   to all times. A hospital and a specialty show their earliest free slot and counts.
   The result names the appointment type its times are for, and every time is shown in
   the hospital's time zone, which is named. A result with nothing free says "No
   availability in the next 90 days".
3. Search text, filters, sort, list and page all live in the address (6.5), so a search
   can be shared and the back button works. The page shows the total count, the current
   page and the page count, offers 10, 20 or 50 results a page, and keeps every other
   parameter when one changes.
4. Distance sort (6.4) appears only when the visitor gave a location. Giving one may need
   a script: a small file served by the application, the page fully usable without it.
5. Specialty icons from healthicons.org, vendored as SVG files in the static files: only
   the icons used, the source revision and the licence recorded beside them, one fallback
   icon for a specialty without one. Icons are decoration: the name is always written.
6. States (section 16): an empty state when nothing matches, with a way to widen the
   search; filter values that are no longer valid fall back silently (section 4).
7. The header offers "Sign in", or the signed-in user's name and home. The page has a
   title and a meta description.
8. Accessibility to WCAG 2.2 level AA and 375 px to 1440 px: the list switch is a set of
   links that says which one is current, each filter has its label, each slot link says
   the day, the time and the provider, and results read in a sensible order. Test what
   the server can prove in the rendered HTML.
9. Nothing private appears: no clinician email, phone or date of birth, nothing about
   patients. Test with planted values.

Carried from the browser check of task 12a, to fix here:

- `scheduling/domain/calendar_event.py` writes `"\;"`, an invalid escape sequence: it
  works today and is a `SyntaxWarning` that a later Python turns into an error. Fix it,
  and make the suite fail on any warning so the next one is caught when it is written.
- On the booking confirmation page the notice, the card and the two buttons touch each
  other with no space between them. Stacked blocks need the spacing of the design tokens,
  on every booking page.

Every form is tested as a browser sends it, with the helper of task 13a. The sandbox has
no browser: the orchestrator searches, filters, pages and books from a result in Chrome
at 375 and 1440 px, with the keyboard only, and runs an accessibility audit.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
