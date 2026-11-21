# QA round 2, clinician area, 2026-11-21

One `qa` run (clinician) against `main` at task 17. Each finding was reproduced by a second
agent before it was filed. Issue bodies copied here so a task run can read them without
GitHub access.

## #25 P1: Week grid and rooms timeline draw blocks about 21 minutes below their hour label

### Summary
In the clinician calendar and rooms timeline, appointment and time off blocks sit lower than the hour their label says. The axis starts at the column heading, the items start 48 px lower.

### Steps to reproduce
1. Sign in at `/sign-in` (CSRF token + `Origin: http://127.0.0.1:8000`) with `DEMO_PASSWORD` from `.env.example`. User `clinician@example.test`, browser at 1440 px.
2. Open `/clinician/calendar?week=2026-11-23` (an appointment 12:00 to 12:30 on Monday) and `/clinician/rooms?date=2026-11-23`.
3. In the console compare the top of the axis row "12:00" with the top of `.time-grid-item`; also `.time-grid__axis` top vs `.time-grid__items` top.

### Observed
Axis "12:00" row top 1035 px, appointment block top 1084 px. Rows are 68 px per 30 minutes, so the block is 48 px (about 21 minutes) low, drawn between the 12:00 and 13:00 labels. `.time-grid__axis` top 355, `.time-grid__items` top 403. Same on Rooms. A time off 11:00 to 13:00 starts visually at about 11:20.

### Expected
Blocks start at the line of their start time (spec section 9: week grid 07:00 to 19:00 in 30 minute rows; rooms: day timeline).

### Evidence
Measured positions above; classes `time-grid__axis`, `time-grid__items`, `time-grid-at-N` in `scheduling/templates`.

### Found at
ca07781

## #26 P1: Multi-day time off is not drawn on the week grid and reads "01:00 to 01:00"

### Summary
A time off that spans several days shows in each day column as a single block "01:00 to 01:00" under "Outside 07:00 to 19:00", and nothing inside the grid. A clinician reading the week sees free days.

### Steps to reproduce
1. Sign in at `/sign-in` (CSRF token + `Origin: http://127.0.0.1:8000`) with `DEMO_PASSWORD` from `.env.example`. User `clinician@example.test` (demo time off 1 Dec 01:00 to 4 Dec 01:00, Europe/Berlin).
2. Open `/clinician/calendar?week=2026-11-30`.

### Observed
Tue 1, Wed 2, Thu 3 and Fri 4 Dec each show `<p class="time-grid__outside-title">Outside 07:00 to 19:00</p>` and a block "01:00 to 01:00 Time off"; the grid area is empty.

### Expected
Spec section 9: the calendar shows time off blocks. Wed and Thu are off the whole day, so 07:00 to 19:00 should be covered; Tue should read 01:00 to 24:00 and Fri 00:00 to 01:00.

### Evidence
HTML above, reproduced with `curl -b jar '/clinician/calendar?week=2026-11-30'`.

### Found at
ca07781

## #27 P2: Appointment history shows the raw code "appointment.book"

### Summary
The history list on the clinician appointment page prints the audit action code for bookings. Other actions are in plain words.

### Steps to reproduce
1. Sign in at `/sign-in` (CSRF token + `Origin: http://127.0.0.1:8000`) with `DEMO_PASSWORD` from `.env.example`. User `clinician@example.test`.
2. Open `/clinician/appointments/01a2002c-7c84-71a9-8db5-4488cd9cc415` (a booked then cancelled appointment).

### Observed
History reads "appointment.book by Pia Passwort" beside "Cancelled by ...", "Clinical note saved".

### Expected
Plain language for every entry (spec sections 9 and 16).

### Evidence
`curl -b jar <url> | grep 'appointment\.book'` matches.

### Found at
ca07781

## #28 P2: Time off page has duplicate element ids; label "From" of the second form focuses the first input

### Summary
`/clinician/time-off` holds two forms ("Check a period first", "Record time off") that reuse `id_starts_at` and `id_ends_at`. The HTML is invalid and the second form's labels point at the first form's inputs.

### Steps to reproduce
1. Sign in at `/sign-in` (CSRF token + `Origin: http://127.0.0.1:8000`) with `DEMO_PASSWORD` from `.env.example`. User `clinician@example.test`, open `/clinician/time-off`.
2. Console: `document.querySelectorAll('[id=id_starts_at]').length`.
3. Click the label "From" of the "Record time off" form.

### Observed
Count is 2 (also `id_ends_at`); the click focuses the input of the first form.

### Expected
Unique ids, labels bound to their own field (spec section 16, accessibility).

### Evidence
Count above; `curl -b jar /clinician/time-off | grep -o 'id="id_starts_at"' | wc -l` prints 2.

### Found at
ca07781

## #29 P2: Reschedule review answers "That time was just taken" for a time in the past or out of range

### Summary
Reviewing a reschedule to a time that was never offered gives the message for a lost race, which tells the clinician nothing useful.

### Steps to reproduce
1. Sign in at `/sign-in` (CSRF token + `Origin: http://127.0.0.1:8000`) with `DEMO_PASSWORD` from `.env.example`. User `clinician.skin@example.test`.
2. POST with a valid CSRF token and `Origin` header to `/clinician/appointments/01a2002a-d32b-737e-8a5a-7772a95c1be5/reschedule/review?starts_at=2020-01-01T10:00:00Z`; repeat with `9999-12-31T10:00:00Z`.

### Observed
409, "That time was just taken." for both.

### Expected
Spec 5.6: reschedule applies conflict and booking rules; the refusal should name the real reason (in the past, outside what is offered).

### Evidence
Both answers 409 with that text.

### Found at
ca07781

## #30 P2: Calendar and rooms grid: overlapping blocks are unreadable and long text overflows

### Summary
When blocks overlap, they become narrow and their text breaks per character; the status badge and long reasons spill out of the block.

### Steps to reproduce
1. Sign in at `/sign-in` (CSRF token + `Origin: http://127.0.0.1:8000`) with `DEMO_PASSWORD` from `.env.example`. User `clinician@example.test`, browser at 1440 px.
2. Record time off 2026-11-23 11:00 to 13:00 (reason `lunch <b>x</b>`) and 2026-11-24 11:00 to 12:00 with a 200 character reason without spaces.
3. Open `/clinician/calendar?week=2026-11-23`.

### Observed
Overlapping blocks are 51 px and 93 px wide; the 93 px appointment block has `scrollHeight > clientHeight` (badge sticks out), text reads "Ch / ec / ke / d / in". The 200 character reason runs past its block. "Nothing booked" is cut off in the last column. At 375 px the grid is a day list and reads fine.

### Expected
Readable text at 1440 px (spec section 16): wrapping long words, overlaps laid out side by side with a minimum width, content clipped or contained.

### Evidence
Widths measured with `getBoundingClientRect`.

### Found at
ca07781

## #31 P2: Time off: an ambiguous local time (end of summer time) is refused as "does not exist"

### Summary
The hour that occurs twice when summer time ends is rejected with a message saying the time does not exist. It exists; it is ambiguous.

### Steps to reproduce
1. Sign in at `/sign-in` (CSRF token + `Origin: http://127.0.0.1:8000`) with `DEMO_PASSWORD` from `.env.example`. User `clinician@example.test`.
2. POST `/clinician/time-off` with `starts_at=2026-10-25T02:30&ends_at=2026-10-25T04:30` (valid CSRF token and Origin).

### Observed
422 "Enter a date and time that exists in the hospital's time zone."

### Expected
Either accept with a defined rule or say the time is ambiguous (spec sections 9 and 16, useful messages).

### Evidence
Answer above.

### Found at
ca07781

## #32 P2: Demo seed stores weekdays 0 to 4, so demo clinicians work Sunday to Thursday

### Summary
`WEEKDAYS_WORKED = (0, 1, 2, 3, 4)` in the seed. Spec section 3 defines 0 as Sunday, so seeded availability is Sunday to Thursday, with no Friday.

### Steps to reproduce
1. Fresh `docker compose up --wait`, then `seed_demo`.
2. Sign in at `/sign-in` (CSRF token + `Origin: http://127.0.0.1:8000`) with `DEMO_PASSWORD` from `.env.example`. Open `/clinician/availability` as `clinician@example.test`.

### Observed
Rows run Sunday to Thursday; Friday has no slots and "Next free slot" for demo clinicians is often a Sunday. Page and stored value agree; the seed is wrong (`scheduling/demo_seed/catalogue.py:13`).

### Expected
Monday to Friday availability (stored 1 to 5) per the spec's weekday numbering (section 3, availability rule).

### Evidence
`catalogue.py:13`; `writer.py:164` uses the constant.

### Found at
ca07781

