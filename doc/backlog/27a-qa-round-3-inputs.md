Task 27a: QA round 3, the inputs that reach the database.

Findings of QA round 3 (`doc/qa/2026-11-22-round-3.md`, each with steps, observed and
expected) where a value a person or a client sends reaches the database unchecked, or
comes back wrong. Two of them answered 500, and both had passed the hostile-input test,
because that test sends hostile values to a fixed list of field names. Reproduce each
finding with a failing test before the fix. The rule belongs where the value enters the
domain, once, so the pages, `/api/v1` and `/fhir` refuse the same value the same way.

1. #33 (P1): the clinician form answers 500 for a round robin weight above 32767. Every
   whole number a form, an `/api/v1` body or a FHIR resource accepts has the bounds of
   its column, and a value outside them is a refusal on the field. List in the plan
   every integer column a write can reach, with its bounds and where they are checked.
2. #38 (P1): a NUL byte in a clinical note or a time-off reason answers 500. No text a
   write accepts may hold a NUL byte or another control character PostgreSQL or a page
   cannot carry; say in the plan which characters, and why a line break and a tab stay
   allowed where the field is free text. One rule, used by every text input.
3. #45 (P2): `POST /api/v1/appointments` accepts a JSON number for `reason` and stores
   it as text. A text field of `/api/v1` refuses a number, as it refuses a boolean:
   every text field of every request schema, shown by one test over the schemas.
4. The hostile-input test derives its targets instead of listing them: for every page
   the product renders with a form (signed out and as each role, from the URL
   configuration, as the accessibility walk of task 25 does), every field of that form
   by its `name`; for `/api/v1`, every field of every request schema; for `/fhir`, every
   element a write of the declaration accepts. Each gets the hostile values (a NUL byte,
   an over-long text, a number beyond 64 bits, a negative number, a wrong type, markup)
   and none answers 500. A new field is covered without an edit of the test. Keep the
   suite's time in view: say in the plan how many requests this is and what it costs.
5. Carried from the review of task 25: one test shows that every form of the product,
   refused, comes back with what was typed, apart from a password and a code.
6. #41 (P1): a waitlist entry shows its last day one day late: the page prints the
   exclusive end of the window as a date. One function writes a window of days for a
   person, in the domain layer under the mutation gate, used by the patient's list, the
   admin's list, the clinician's view, the notifications and the emails. Test a window
   of one day, a window that ends on the last day of a month, and a hospital on each
   side of UTC.

Not in this task: the messages and the pages of the other round 3 findings (27b).

The orchestrator sends a weight of 40000, a NUL byte in a note through the page, the API
and FHIR, a number as a reason, and reads a two-day waitlist window in each place that
shows one.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
