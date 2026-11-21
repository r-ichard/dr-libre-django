Task 17c: QA round 2, the clinician workspace.

Seven findings of the clinician QA run, two rated P1. Each is written up with steps that
reproduce it in `doc/qa/2026-11-21-round-2-clinician.md`; read them there and reproduce
each with a failing test before you fix it. Impeccable mode is on: read `PRODUCT.md`,
`DESIGN.md` and the `impeccable` skill, reuse the existing components, no inline script
or style.

The shared time grid of the calendar week and the rooms timeline. A clinician plans a day
from it, so a block in the wrong place is a wrong time:

1. #25 (P1): blocks are drawn 48 px, about 21 minutes, below the label of their hour. The
   axis starts at the column heading and the items start under it. A block starts level
   with the line of its start time and ends at the line of its end time. The sandbox has
   no browser: say in the plan what in the rendered HTML and the style sheet proves the
   alignment, so a test holds it.
2. #26 (P1): a time off that spans several days is drawn in no day and reads "01:00 to
   01:00" under "Outside 07:00 to 19:00". Each day shows the part of the period that
   falls in it: a whole day off covers 07:00 to 19:00, and the text gives the real start
   and end with their dates. The cut of a period into days is a pure function in the
   domain layer, under the mutation gate, correct across a daylight saving change.
3. #30: overlapping blocks become too narrow to read and their text breaks per
   character; a long reason without spaces and the status badge run out of their block;
   "Nothing booked" is cut off in the last column. Overlaps sit side by side with a width
   a word fits in, long words wrap, and nothing a block shows leaves it at 1440 px or at
   375 px. What does not fit belongs on the appointment page.

Time off and reschedule:

4. #31: the hour that occurs twice when summer time ends is refused as a time that "does
   not exist". Decide one rule for an ambiguous local time, apply it wherever the product
   reads a local date and time, and say it in the message or beside the field. A time
   that really does not exist (the skipped hour in spring) keeps its refusal.
5. #28: the time off page has two forms that share `id_starts_at` and `id_ends_at`, so a
   label of the second form focuses a field of the first. Ids are unique on every page:
   add a test over every page the product renders that fails on a duplicate id.
6. #29: reviewing a reschedule to a time in the past or beyond what is offered answers
   "That time was just taken". The refusal names the real reason and offers the way back
   to the week strip, for the clinician and for the patient.

Appointment page:

7. #27: the history prints the raw audit code "appointment.book". Every audit action the
   product can write has its plain words; a test fails when an action has none.

Write the commit so that merging it closes the issues: the reply of the last stage lists
"Closes #25, #26, #27, #28, #29, #30, #31".

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
