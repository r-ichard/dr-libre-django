Task 11: public detail pages.

`drlibre-specs.md` section 6.6 and the three detail endpoints of section 14, on top of
the search of tasks 10 and 10a and the booking pages of task 12a. Open to everyone.
Impeccable mode is on: read `PRODUCT.md`, `DESIGN.md` and the `impeccable` skill, reuse
the existing components, no inline script or style.

1. Provider page: name, title, specialty, bio, hospital and department, the
   online-bookable appointment types, and the week strip of free slots for the chosen
   type (the component of task 12a), Monday to Sunday with previous and next week. A
   slot leads into the booking pages.
2. Hospital page: name, address, phone, description, departments, specialties, providers
   and, for each provider, the next free slots. It offers "first available" for each
   online-bookable appointment type, leading into the booking pages with no provider
   named.
3. Specialty page: the provider list of the search, filtered on that specialty.
4. API (section 14): `GET /api/v1/hospitals/{id}`, `GET /api/v1/providers/{id}` and
   `GET /api/v1/specialties/{id}`, public, through explicit field lists.
5. Only public, bookable data, as in section 6.1. An inactive hospital, an inactive
   provider, a provider with no online-bookable type and an inactive specialty answer
   not found, on the page and in the API alike. Never a clinician's email, phone or date
   of birth; the hospital's own phone is public. Test with planted values.
6. Search results link to these pages (the provider's name, the hospital's name, the
   specialty's name), and these pages link to each other where they name one another.
7. Times are in the hospital's time zone, which the page names. A provider or hospital
   with nothing free in the horizon says so.
8. Each page has its own title and meta description. The cost of the hospital page is
   bounded like the search: the number of queries does not grow with the number of
   providers.
9. Accessibility to WCAG 2.2 level AA and 375 px to 1440 px. Test what the server can
   prove in the rendered HTML.

Carried from the browser check of task 10a, to fix here because these pages share the
components:

- The empty state's "Widen the search" link leads to the same search. It must lead to a
  wider one: without the filters, and without the text when there are no filters.
- A slot link shows "Sun 22 Nov, 09:00" and is announced as "Sunday 22 November 2026 at
  09:00 with ...". The accessible name must contain the visible text (WCAG 2.5.3, label
  in name), on the search, the week strip and the new pages.
- The current list in the switch reads "Providers (current)" on screen. Show the state by
  style and `aria-current` only.
- On a phone nine filters come before the first result, more than a thousand pixels
  down. Keep the text box and the search button first and put the other filters in a
  "More filters" disclosure that needs no script and is open when a filter is set.
- At 1440 px the first label wraps to two lines and its field sits lower than the others
  in the row.
- The specialty icon is found by the specialty's name; use its code, so a renamed
  specialty keeps its icon.

Every form is tested as a browser sends it. The sandbox has no browser: the orchestrator
opens each page in Chrome at 375 and 1440 px and books from a provider page and from a
hospital's "first available".

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
