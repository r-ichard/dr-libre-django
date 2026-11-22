Task 27b: QA round 3, what a person reads and where they land.

Findings of QA round 3 (`doc/qa/2026-11-22-round-3.md`, each with steps, observed and
expected) about a message that does not help, a page with no way on, and a write that
should not have happened. Impeccable mode is on: read `PRODUCT.md`, `DESIGN.md`, the
`impeccable` skill and its `reference/craft-floor.md`; reuse the existing components;
every step works without JavaScript. Reproduce each finding with a failing test before
the fix.

Messages:

1. #34: an admin's booking or reschedule that breaks a booking rule prints the internal
   rule codes ("outside_availability"). Every rule of section 5.3 has one sentence a
   person can act on, in one place, used by the admin console, the clinician workspace
   and the patient's pages. A test fails when a rule has no sentence, and when a page
   of the product prints a rule's code.
2. #35: a status action that is not allowed from the current status says "The status
   changed since this page was opened". It says what is true: the current status and
   that the action is not possible from it. The stale-page message stays for a page
   that really was stale.
3. #37: the admin waitlist form answers "Enter a date and a time" for a well-formed
   window far in the future. The message names the limit.
4. #40: a whole-day time off reads "00:00 to 00:00" on the week grid: it reads "All
   day". A date that does not exist (30 February, the year 0001 or 10000) is refused as
   a date that does not exist, not with the sentence about a clock change.
5. #43: the empty waitlist form lists two identical errors. Each error names its field,
   and no two links of an error summary read the same: assert the second over every
   form the product renders, submitted empty.

Ways on:

6. #42: after a session ended before an action, signing in sends the browser a GET of
   an address that only takes a POST, which answers an empty 405. Signing in never
   leads to an address that refuses a GET: it leads to the page the action was on. A
   405 of a page names in `Allow` what it accepts and is a product page.
7. #49: the patient's reschedule pages answer 404 for an own appointment whose type is
   not bookable online. 404 is for a record that is missing or not the caller's (12.3).
   Such an appointment does not offer "Reschedule"; its page says to call the hospital
   and gives the hospital's phone number; the address itself answers with that refusal.
8. #44: week strips (provider page, hospital page, booking, reschedule) open on the
   current week when it has no free time, and "Previous week" walks into the past
   without end. A strip opens on the week of the first free time within the booking
   horizon, and offers no week that lies wholly in the past. Bounded queries: say the
   number in the plan and assert it.

Writes:

9. #39: a clinician's reschedule to the start the appointment already has succeeds
   again, with a second audit entry and a second "moved" notification. A reschedule to
   the same start changes nothing and writes nothing, on the pages, `/api/v1` and
   `/fhir`; say in the plan whether it is a refusal or a quiet success, and why.
10. #36: saving a hospital with another time zone moves the local time of every
    appointment it has, without a word. Before the save the admin sees a confirmation
    step that says how many future appointments will show another local time, with one
    example before and after. Whether patients are told is the owner's decision
    (`doc/backlog.md`, questions): no notification in this task.

Layout (`CLAUDE.md`, "Layout"): items 4 and 8 change what a block and a strip show. State
for each the invariant and its measurement at 375 px and 1440 px, and what must still
fit beside it.

The orchestrator walks each finding's steps in a browser at 375 px and 1440 px.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
