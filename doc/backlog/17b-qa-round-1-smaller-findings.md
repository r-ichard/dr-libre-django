Task 17b: QA round 1, the smaller findings.

Ten findings of the QA runs rated P2. Each is written up with steps that reproduce it in
`doc/qa/2026-11-21-round-1.md`; read them there and reproduce each with a failing test
before you fix it.

Access and privacy:
1. #17: `GET /api/v1/slots` and the booking pages serve an appointment type that is not
   bookable online to a caller with no session, and name a clinician the public search
   hides (`drlibre-specs.md` section 6.1). Without a session, and for a patient, only
   online-bookable types exist; staff keep the others (section 10, "Book for a patient").
2. #11: another patient's confirmation page and calendar file answer 404; the record rule
   of section 12.3 says a record that exists and belongs to someone else is `forbidden`.
3. #22: the portal's "done" notice is taken from a `notice` value in the address, so a
   link can show a patient a false "Your appointment is cancelled", and a reload repeats
   it. A notice must come from what the server just did, once.

Booking:
4. #16: a named room is attached to an appointment of a type that needs no room
   (section 5.2 step 5: "Types that need no room get none").
5. #15: the hold request reports an impossible birth date under the field name
   `birth_date`; the field is `date_of_birth`.
6. #20: the booking details form accepts any text as a phone number; the rule of section
   8 (7 to 20 characters of digits, spaces, `+ ( ) -`) applies wherever a phone is typed.
7. #21: the details page shows its form for a time that is not offered, and the failure
   page then loses everything the visitor typed.
8. #23: the "Appointment cancelled" and "Appointment rescheduled" notifications read as
   if the appointment were still on at the old time. Say what happened and when; the
   text still carries the time only (section 11).

Forms (section 16):
9. #19: focus does not move to the first invalid field on the waitlist and password
   forms. Do it once in the shared form component, for every form, the profile form of
   task 15 included.
10. #24: the details form reports its errors in rounds, and an empty current password is
    called wrong. One submission reports every error; an empty field says "enter", not
    "wrong".

Left open by task 17a (input limits, `scheduling/views/input_limits.py`), found by its
reviewer and reproduced by the orchestrator on the running product:

11. `curl -X POST /api/v1/auth/login -H 'Content-Length: abc' -d '{}'` answers 500
    `internal_error`, on every API route and without a session: `refuse_oversized` calls
    `int()` on the header. Before task 17a the same request answered 400. Answer
    `invalid_input` naming `body`, and test it with the raw header, which the test
    client does not send by itself.
12. A page that receives more than 200 fields or a body over 1 MiB shows Django's bare
    "Bad Request (400)" page, with no layout and no correlation id. Give 400 the
    product's error page, like 403, 404 and 500.
13. `json_depth` and the date bounds are pure and sit in the views layer, where the
    mutation gate does not look. Move the pure part into `scheduling/domain` with its
    boundary tests. Record the limits the product ships (body size, number of fields,
    nesting depth, date range, page number) and where each is enforced in
    `doc/adr/0004-failure-contract-and-request-context.md`; the plan of task 17a states
    other numbers.
14. The hostile-input test (`scheduling/views/test_hostile_input.py`) fills every id in
    a path with a random one, so a route that names a record answers "not found" before
    it reads anything else, and the writes on an appointment, a waitlist entry, a
    notification, an availability rule or a time off are never sent hostile values.
    Fill each id with a record the signed-in actor may use, so the request reaches the
    parsing, and keep the random id as one more case. No answer may be 500.
15. That test takes about 60 of the suite's 75 seconds (the suite ran in 15 before task
    17a) and five mutants now time out. Every stage of every later run pays it. Bring
    `make test` back under 30 seconds without dropping a route, an actor or a kind of
    value: say in the plan which combinations prove nothing (a method the route does not
    accept is refused before any parsing) and how the rest is spread over the workers.

Write the commit so that merging it closes the issues: the reply of the last stage lists
"Closes #11, #15, #16, #17, #19, #20, #21, #22, #23, #24".

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
