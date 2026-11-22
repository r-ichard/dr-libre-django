# Plan: task 17c, QA round 2, the clinician workspace

One sentence: seven defects, each fixed at its rule (grid CSS and clipping, a pure day-cut,
one ambiguous-time rule, unique field ids, a typed refusal reason, a complete audit-label
table), each first reproduced by a failing test. No new dependency, no new component.

Read: `doc/qa/2026-11-21-round-2-clinician.md`, `PRODUCT.md`, `DESIGN.md`, impeccable
craft-floor (before the CSS edit), spec sections 5.6, 9, 16.

## Focal point

`components/time_grid.html` + `static/css/time-grid.css` + `views/pages/time_grid.py` +
`domain/calendar_grid.py`: the one grid behind calendar and rooms. Items 1, 2, 3 live here.

## Root causes found (so the fixes are small)

- #25: `.time-grid ol { margin: 0 }` (specificity 0,1,1) beats `.time-grid__axis { margin-top:
  var(--heading-height) }`-in-media (0,1,0). The axis starts at the heading, items 3rem
  (48 px) lower. Fix: the axis margin rule gets selector `.time-grid .time-grid__axis`.
- #26: `place_in_grid` returns None when the start is before 07:00, and a window-cut multi-day
  period starts at local midnight, so it lands in "Outside". Its text shows only clock times
  of the whole period, no dates.
- #30: items carry only `grid-row`, so overlaps are auto-placed into implicit columns that
  shrink to the day column's width / n. No `min-width: 0`, no clip, no column floor.
- #31: `utc_from_local` refuses `early.utcoffset() != late.utcoffset()`.
- #28: `components/field.html` hardcodes `id_{{ name }}`; time off page includes it twice.
- #29: `_rule_refusal` falls through to `SLOT_TAKEN` for `OUTSIDE_AVAILABILITY`; a start in
  the past has no rule at all (staff skip lead time), so it is just "not free".
- #27: `AUDIT_LABELS` has `appointment.booked`, writer uses `appointment.book`; many other
  written actions have no label.

## Blocks, one sentence each, files in order

1. `scheduling/domain/calendar_grid.py` `place_in_grid`: clip the span to 07:00-19:00 of its
   local day; None only when no overlap with the grid (end past midnight counts as 24:00).
2. `scheduling/domain/period_days.py` (new, pure) `cut_into_days(starts_at, ends_at, days,
   time_zone) -> list[DayPart]`: for each local day the part of the period inside
   `[local midnight, next local midnight)` (uses `local_day_bounds`, so 23 and 25 hour days
   are right); `DayPart(day, starts_at, ends_at, whole_day)`. Added to the mutation gate
   automatically (`scheduling/domain`); equivalents go in `mutation-equivalents.txt` with reasons.
3. `scheduling/views/pages/clinician_calendar.py` `_blocks`/`_day`: time off becomes one
   `GridItem` per day from `cut_into_days`; placement uses the clipped times, the text uses
   the real period: `Tue 1 Dec 01:00 to Fri 4 Dec 01:00` (dates whenever the period is not
   within the shown day). Rooms keeps `grid_column`, gets the clipping through block 1.
4. `static/css/time-grid.css`: axis rule specificity (#25); items grid
   `grid-auto-columns: minmax(8rem, 1fr)`, so overlaps sit side by side and the day column
   grows (the grid already scrolls in x); item `min-width: 0; overflow: hidden;
   overflow-wrap: anywhere`; badge inside the clipped item; `.time-grid__none` spans
   `grid-column: 1 / -1` and wraps (#30). No inline style or script; 375 px list layout unchanged.
5. `scheduling/views/pages/local_time.py` `utc_from_local`: rule = **an ambiguous time means
   its first occurrence (fold 0, summer time)**, the same rule `free_slots` and the seed already
   use; a skipped time stays None. Time off template: hint beside both fields and the
   refusal message says clocks skip that hour. Other readers of a local date+time: none besides
   time off (week/date params are dates; availability times are zone-free wall times
   expanded by `free_slots`, fold 0); I will grep again and say so in the review.
6. `scheduling/templates/components/field.html`: optional `id_prefix`; every id derived from
   it (input, hint, error, label `for`, aria-describedby). `time_off.html` check form uses
   `id_prefix="check_"`; the record form keeps its ids, so the error summary links hold.
7. `scheduling/domain/booking_rules.py`: new `BookingRule.START_IN_THE_PAST` for every actor;
   `scheduling/domain/booking_refusals.py`: sentences for it ("That time has already passed.")
   and for `OUTSIDE_AVAILABILITY` ("That time is not offered. Choose one from the week.");
   both 422 and way forward `times`. `change_refused_page` already sends `times` to the
   week strip for clinician (`clinician_reschedule.py`) and patient (`patient_reschedule.py`);
   `SLOT_TAKEN` stays for `CONFLICT`. Check the review GET page too: it renders a time never
   offered without a word; it will refuse the same way if the test shows it renders.
8. `scheduling/domain/audit_labels.py`: add `appointment.book` and a plain label for every
   action written (auth.*, availability.*, time_off.*, booking_*, notification.read,
   profile.update, reminder.run, user.patient_created, housekeeping.purge, demo_seed.*, the
   status actions of `STATUS_ACTION_NAMES`). Unknown fallback becomes a generic "Changed the
   appointment" so a raw code never prints.

Not touched: models, migrations, use cases of booking, API, seed (task 17d), `tokens.css`,
other templates, specs.

## Proof for the grid with no browser (#25, #30)

Alignment is arithmetic of three things, all in files a test reads:
- HTML: `.time-grid__axis` holds exactly 24 `.time-grid-row` + one `.time-grid__end`, and each
  column holds `h2.time-grid__heading` then `ol.time-grid__items`; item classes
  `time-grid-at-N time-grid-span-M` map to row N..N+M-1 with N = (start-07:00)/30 min + 1.
- CSS (parsed in a test): axis and items both use `var(--row-height)` for 24 rows; heading and
  axis offset are the same `var(--heading-height)`; the axis offset rule's selector specificity
  is greater than the `.time-grid ol` margin reset (the actual defect); no `padding`/`margin`
  on `.time-grid__items`; item `margin` is symmetric 1px only; every `time-grid-at-1..24` and
  `span-1..24` class exists once.
- Overlap/overflow: the same parse asserts `grid-auto-columns` minimum >= 7rem on items, and
  `min-width: 0`, `overflow: hidden`, `overflow-wrap: anywhere` on `.time-grid-item`.
Said in the review: pixel results unmeasured, no browser in the sandbox.

## Failing tests first (`returns_X_when_Y`)

Domain (mutated):
- `returns_whole_grid_part_when_period_covers_the_day` (cut_into_days: Wed of 1 Dec 01:00 to
  4 Dec 01:00 = local 00:00 to 24:00; Tue 01:00 to 24:00; Fri 00:00 to 01:00).
- `returns_twenty_five_hour_day_when_clocks_go_back` (Berlin 25 Oct 2026: part ends at the
  next local midnight, 25 h later); `returns_twenty_three_hour_day_when_clocks_go_forward`.
- `returns_no_part_when_period_ends_exactly_at_local_midnight`; `..._starts_exactly_...`.
- `place_in_grid`: `returns_rows_one_to_twenty_four_when_span_covers_the_day`;
  `returns_first_row_when_span_starts_before_seven_and_ends_at_eight`;
  `returns_none_when_span_ends_at_seven`; `returns_last_row_when_span_starts_at_18_30`.
- booking rules: `returns_start_in_the_past_when_new_start_is_before_now` (clinician, patient);
  refusals: `returns_422_with_not_offered_sentence_when_outside_availability`;
  conflict still `That time was just taken.` 409.
- audit labels: `returns_plain_words_for_every_action_the_product_writes` (AST scan of
  `use_cases/` and `demo_seed/` for action strings passed to `AuditEvent`/`_audit` or held in
  `*_ACTION*` constants; fails naming the action with no label), `returns_booked_when_action_is_appointment_book`.
Views:
- `returns_first_occurrence_when_local_time_is_ambiguous` (Berlin 2026-10-25T02:30 = 00:30Z);
  `returns_none_when_local_time_is_skipped` (2026-03-29T02:30); POST of the 02:30-04:30
  period answers 303 and stores 00:30Z to 03:30Z; hint text present beside the fields.
- time off page: `returns_unique_ids_when_page_renders`, label `for` of the record form's
  "From" points to an input inside the same form.
- every page: `returns_no_duplicate_id_when_any_page_renders` over all non-API URL patterns
  of the resolver, parametrised with fixtures per path argument, for each role that may see it,
  also the 422 renderings of the forms; a pattern with no fixture entry fails the test, so a
  new page cannot skip it. Must stay quick (one DB fixture set, module scope).
- calendar: fixtures built in the test (not the seed): multi-day time off 01:00-01:00 over 4 days
  renders in Tue..Fri inside `.time-grid__items`, none under "Outside", text with dates,
  Wed/Thu rows 1..24; `returns_overlapping_items_in_one_column_with_row_classes`; escaped
  reason `lunch <b>x</b>`; 200 char reason without spaces rendered once, in the item.
- rooms: same time grid assertions for a time off / appointment block.
- reschedule (clinician POST review with `2020-01-01T10:00:00Z` and `9999-12-31T10:00:00Z`,
  and the patient flow): 422, message names the reason (not "just taken"), link back to the
  week strip (`times_path`); a real double booking still 409 "just taken".
- CSS test file (above), in `scheduling/views/pages/test_time_grid_css.py`.

## Invariants and blast radius

Double booking: `find_conflicts` untouched; the new past rule only adds a refusal before write.
Authorization stays server-side (profile from session; ids from path checked by
`appointment_or_refusal`). Audit log append-only: only labels read. Booking rule change reaches
patient book/reschedule and staff booking (start in the past is refused for all; seed uses
future days, to be checked by running `make test`). Grid change reaches calendar and rooms
only. `field.html` change reaches every form: default prefix empty keeps ids byte-identical,
so the all-pages test and existing tests hold.

## Trust boundaries

`datetime-local` POST/GET values and `starts_at` query param are untrusted: parsed by
`utc_from_local` / `instant_from`, range-checked by `day_in_range`, zone from the hospital
row, never the payload. Reason text stays auto-escaped. Reschedule start validated by the use
case inside its transaction.

## Vocabulary

Clinician, ClinicianProfile, Hospital (time zone), TimeOff, Appointment, AppointmentType, Room,
AvailabilityRule (slot offers), AuditLogEntry, Patient, User.

## Will not do

No JS, no inline style, no framework, no rewrite of the grid to pixel positions, no new
dependency, no change to the seed (17d) or specs, no generic id-prefix system beyond one
`field.html` parameter, no change to waitlist or API behaviour.

## Done

`make setup && make lint && make test && make gate && make mutate`; `make test` timed under
30 s; reply ends with "Closes #25, #26, #27, #28, #29, #30, #31". Squash message hand-written.

## Architect review

Verdict: approve.

- Ladder: fixes sit at the rule (grid CSS, one pure domain function, one `field.html` parameter, one label table). No new dependency or component. Fine.
- Tests first: each item has a named failing test with concrete values (Berlin 2026-10-25T02:30, 2026-03-29T02:30, 23 and 25 hour days). No-browser proof for #25 and #30 is stated and checkable (selector specificity, row classes, `min-width`, `overflow`).
- Architecture: day-cut is pure and under the mutation gate. Refusal reasons are values. No model, migration or API change.
- Security: untrusted `datetime-local` and `starts_at` are parsed server-side, and the zone comes from the Hospital row. Audit log is only read.
- Notes for the implementer (not blockers):
  1. #31 "wherever the product reads a local date and time": the grep found only `utc_from_local` (time off). `booking_links.py:68` parses an instant, which must carry an offset. Confirm and say so in the review. If it accepts a naive value, it needs the same rule.
  2. `field.html` prefix must also cover the `error_id` and `aria-describedby` paths. The all-pages id test covers this.
  3. The new START_IN_THE_PAST rule for every actor can break existing staff-booking and seed tests. Run the suite early.
  4. The audit-label AST scan must also see action names built through constants or helpers. Add a runtime check against the written `AuditLogEntry` actions in the use-case tests if the scan misses any.
