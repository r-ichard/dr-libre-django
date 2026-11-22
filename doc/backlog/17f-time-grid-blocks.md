Task 17f: time grid, blocks stay in their column and show whole lines.

The shared time grid of the clinician calendar week and the rooms timeline
(`static/css/time-grid.css`, `scheduling/templates/`, `scheduling/domain/calendar_grid.py`).
Task 17c put the blocks on their hour. Two defects remain, measured by the orchestrator in
Chrome at 1440 px on `/clinician/calendar?week=2026-11-23` as the demo clinician, after
recording a time off from 12:00 to 14:00 on a Monday that has an appointment at 13:00.
Issue #30 (`doc/qa/2026-11-21-round-2-clinician.md`) is the same area. Impeccable mode is
on: read `PRODUCT.md`, `DESIGN.md` and the `impeccable` skill, no inline script or style.

1. A block leaves its day. The Monday column runs from 232 px to 376 px. Its two
   overlapping blocks are 128 px each: the appointment from 232 to 360, the time off from
   362 to 488, on top of Tuesday's column (384 to 528), where it reads as Tuesday's time
   off. Recording time off over a booked appointment is a normal case: the time off page
   says the appointment stays. Rule: no block is ever drawn outside the column of its
   day or its room, whatever overlaps it and however many.
2. A line is cut through its letters. A 30 minute appointment alone in its column is
   66 px high and shows "12:00 to 12:30", "Cardiology" and "consultation" on two lines,
   then the top half of the patient's name; the status is gone. A reason of 200
   characters is cut the same way. Rule: a block shows whole lines only. A line that
   does not fit its width ends with an ellipsis instead of wrapping, and a line that
   does not fit the height is not drawn at all.

What a block must show, so the calendar can be read without opening anything:

3. An appointment of 30 minutes or less, alone in its column: its time, its type and
   its patient, one line each. Longer blocks add the room and the status while lines
   are left. A time off: its time and the words "Time off", then its reason while lines
   are left.
4. An appointment and a time off that overlap are both recognisable at their real start
   and end, and the appointment still shows its time and its patient. Choose the layout
   (side by side inside the column, or the time off as a band behind the appointments)
   and say in the plan why it stays readable in a column 144 px wide.
5. Everything a block cannot show is in its accessible name, and one step away: the
   appointment page for an appointment, the time off page for a time off, which lists
   the full reason. The list a screen reader and a 375 px screen get keeps every word.
6. Status is never shown by colour alone, also in a block too small for the status word.

Proof, because the sandbox has no browser:

7. State in the plan the numbers the layout rests on: column width at 1440 px, row
   height, line height, padding, lines in a 30 minute block, the width of a block when
   two and when three share a column. Derive from them that rules 1 and 2 hold, and
   assert in tests what the style sheet and the rendered HTML can prove (as
   `test_time_grid_css.py` does for the alignment).
8. Where blocks share a column, the share is decided by a pure function in the domain
   layer, under the mutation gate: which blocks overlap, how many lanes a day needs,
   which lane each block takes. Test three blocks that overlap in a chain, blocks that
   only touch (one ends when the next starts: no overlap), and a whole day of time off
   over several appointments.
9. The orchestrator then measures in Chrome, for every block of the calendar and the
   rooms timeline at 1440 px and 1024 px: its left and right edges against its column's,
   `scrollWidth` against `clientWidth`, and that its height holds a whole number of
   lines. Write the plan so these three measurements pass.

Write the commit so that merging it closes the issue: the reply of the last stage lists
"Closes #30".

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone, and `make test` stays under 30 seconds in the sandbox.
