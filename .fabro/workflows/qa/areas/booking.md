Area: scheduling and booking integrity, through the API.

Specification: `drlibre-specs.md` sections 4, 5 and the booking rows of section 14.
Sign in through `POST /api/v1/auth/login` as the demo patient, a clinician and the admin
(`DEMO_PASSWORD` in `.env.example`).

Try at least:
- Free slots (5.1): rules, slot step, duration, buffer of the type being booked, time
  off, the 31 day cap, a range across a daylight saving change, the weekday convention
  (0 is Sunday), slots in the past, a clinician of another department.
- Placing (5.2): each step and its failure code, the end time never taken from the
  caller, room choice, a type that needs no room, an inactive type or clinician.
- No double booking: many requests in parallel for the same clinician, the same patient
  and the same room (`xargs -P`), then count overlaps in the database. Also a booking
  racing a reschedule, a cancel racing a reschedule, two accepts of one waitlist offer.
- Booking rules (5.3) at their exact boundaries: 120 minutes, 24 hours, 3 open bookings,
  a type not bookable online, a start that is no slot. Who is bound by which rule.
- Who books for whom (5.4) and first available (5.5): ranking, weights, the stamp.
- Status changes (5.6): every pair of the table, allowed and refused, by each role.
- Reminders (5.7): once only, also when the job runs twice at the same time.
- Waitlist (5.8): join, automatic offer on cancel, manual offer, accept, a taken slot,
  expiry.
- Every write has its audit entry in the same transaction, and no audit metadata holds a
  name, an address, a phone number, a birth date, a reason or a note.
- Input: unknown fields, wrong types, huge strings, odd Unicode, a date without an
  offset, negative and enormous numbers, a malformed id. No request may answer 500.
