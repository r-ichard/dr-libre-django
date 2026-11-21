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

Write the commit so that merging it closes the issues: the reply of the last stage lists
"Closes #11, #15, #16, #17, #19, #20, #21, #22, #23, #24".

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
