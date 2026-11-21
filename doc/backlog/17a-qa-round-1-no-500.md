Task 17a: QA round 1, no input answers 500.

Five findings of the QA runs, all the same failure: an input the product did not expect
answers HTTP 500 where `drlibre-specs.md` section 4 wants a result ("validation at every
boundary", "expected failures are results, not crashes"). Each is written up with steps
that reproduce it in `doc/qa/2026-11-21-round-1.md`; read them there.

1. #10: the sign-in page answers 500 for a malformed email address (`a@b`), while the API
   route answers 400.
2. #12: slots and booking answer 500 for dates at the edge of the calendar (year 9999 or
   0001), `GET /api/v1/slots` without a session.
3. #13: `GET /api/v1/appointments` answers 500 for a huge page number.
4. #14 and #18: an oversized or deeply nested JSON body, or too many query fields,
   answers 500 on public and signed-in routes.

Fix each at the boundary where the value enters, not where it finally breaks, and give
each the `invalid_input` answer naming the field, or the page's own error message.

Then close the class, not only the five cases:
5. A test that sends hostile values to every route of the product, pages and API, with
   and without a session: empty, very long, wrong type, wrong encoding, out of range
   numbers and dates, malformed ids, nested and oversized bodies, too many fields. No
   answer may be 500. Derive the list of routes from the URL configuration so a new route
   is covered when it is added, and say in the plan how. A property-based test fits
   (hypothesis is already a development dependency).
6. State in the plan the limits the product accepts (body size, number of fields, nesting
   depth, string lengths, date range, page number) and where each is enforced.

Write the commit so that merging it closes the issues: the reply of the last stage lists
"Closes #10, #12, #13, #14, #18".

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
