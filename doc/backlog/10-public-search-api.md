Task 10: public search, use case and API.

`drlibre-specs.md` sections 6.1 to 6.5 and the three search endpoints of section 14. The
search pages are task 10a and the detail pages task 11. Everything here is public: no
session is read and nothing about a patient can be reached.

1. What is searched (6.1). One text, matched case-insensitively and on partial words
   against hospital name, city, clinician name, specialty name, department name and
   appointment type name. Three lists: providers, hospitals, specialties. Only public,
   bookable data: active hospitals, active clinicians, active specialties, active types
   that allow online booking; a clinician whose department has no such type is not
   listed.
2. What each result shows (6.2), exactly the columns of the table and nothing else. Never
   a clinician's email, phone or date of birth. Build the answer from an explicit list of
   fields, so a new model column cannot leak by default, and test it with planted values.
3. Next availabilities. For the filtered appointment type, otherwise for the shortest
   active online-bookable type of the clinician's department, which the result names.
   Looked for from now plus the 120 minute lead time up to 90 days ahead (6.2). The slots
   shown are exactly those booking would accept when the list is built: same engine, same
   loading as `GET /slots` and placing, holds included.
4. A result with nothing free in the horizon is still listed, after those with a free
   slot, and says so.
5. Filters (6.3), all combined with AND: specialty, hospital, city, appointment type,
   earliest date, availability window (any, today, within 3 days, within 7 days), time of
   day (morning, afternoon, evening) in the hospital's time zone. A time filter changes
   both which results are listed and which slots they show.
6. Sorting (6.4) over the whole result set, not within a page: soonest availability
   (default), name ascending, name descending, and distance when the visitor gave a
   location and the hospital has coordinates. Ties break on name, then id.
7. Pages (6.5): 20 results by default, 10, 20 or 50 by choice, with the total count, the
   current page and the page count. A page past the end answers with the last page. An
   unusable value in the address (page, size, sort, filter, date) falls back to its
   default instead of failing (section 4).
8. Cost. Sorting by soonest availability needs the first free slot of every match, over a
   horizon three times the engine's 31 day query cap. State in the plan how the work is
   bounded, and prove with a test that the number of database queries does not grow with
   the number of results.
9. API (section 14): `GET /api/v1/search/providers`, `/search/hospitals` and
   `/search/specialties`, public, each result with its next availabilities, times in UTC
   with the hospital's time zone named.
10. The matching, filtering, sorting and paging decisions are pure functions in the
    domain layer, under the mutation gate.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
