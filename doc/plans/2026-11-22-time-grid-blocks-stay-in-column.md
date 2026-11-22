# Plan: task 17f, time grid blocks stay in their column and show whole lines

Closes #30 (and the two measured defects of the orchestrator at 1440 px).

## Focal point

`grid_column` in `scheduling/views/pages/time_grid.py` plus `static/css/time-grid.css`: the grid
stops creating implicit columns (cause of defect 1) and every block draws a number of whole
lines chosen on the server (cause of defect 2).

Root causes found:
- `.time-grid__items` has `grid-auto-columns: minmax(8rem, 1fr)`; items with a definite row but
  no column auto-place into a new implicit 128 px column when a cell is taken. That column is
  outside the day (Monday's 232..376 px → time off at 362..488 px over Tuesday).
- Lines wrap (`overflow-wrap: anywhere`), the block has a fixed height, `overflow: hidden` cuts
  mid-line; the status badge sits outside the link, after the lines.

## Layout decision (rule 4): time off is a band behind, appointments in front

Appointments of one clinician or one room never overlap each other (no double booking is an
invariant), so the common overlap is exactly one time off band over appointments. Side by side
would give each 72 px − 23 px frame = 49 px of text in a 144 px column: "12:00 to 12:30"
unreadable. Band behind:
- Time off band: full column width, painted at its real rows (z-index 1), warning wash, dashed
  left border. Its top and bottom edge show at the real start and end.
- Appointment in front (z-index 2, opaque): inset by a left rail `--rail: 1rem` (16 px) only
  when it overlaps a band, so the band's dashed border and wash stay visible beside it on every
  row it covers. Text width in the appointment: 144 − 16 − 6 − 1 − 16 = 105 px, enough for the
  bold "12:00 to 12:30" (about 95 px); else it ends in an ellipsis.
- The band's own lines (time, "Time off", reason) show where the appointment does not cover them
  (issue example: band 12:00 to 14:00 has 12:00 to 13:00 free, the appointment is 13:00 to
  13:30). When an appointment starts with the band, the band's text is covered; the rail still
  marks its extent and its words are in its accessible name and on the time off page.
- Blocks of one layer that overlap each other (two time offs; in theory two appointments) share
  lanes side by side inside the layer: width `100%/lanes`, contained by construction. At 2 lanes
  text is about 41..49 px, at 3 about 20..25 px: ellipsised, never outside the column. That
  case is outside the invariant for appointments, so it is accepted, not optimised.

## Numbers the layout rests on (rule 7), rem = 16 px

| Quantity | Value |
|---|---|
| Column width at 1440 px and 1024 px | 144 px (`minmax(9rem, 1fr)`; `.time-grid` scrolls sideways when 7 do not fit, so 144 is the floor) |
| Row (30 min) | `--row-height: 4.25rem` = 68 px |
| Block frame | margin 1 px top and bottom, border 1 px top and bottom, padding `--space-1` 4 px top and bottom = 12 px |
| Line height (new `--line-height`) | `1.125rem` = 18 px, fixed on every line (`height` and `line-height`) |
| Lines in a 30 minute block | floor((68 − 12) / 18) = 3 (54 px of 56 px) |
| Lines in a block of n rows | floor((68·n − 12) / 18): 1→3, 2→6, 3→10, 4→14 |
| Text width alone | 144 − 6 − 1 − 8 − 8 = 121 px |
| Text width with rail | 105 px |
| Block width, 2 lanes / 3 lanes in a layer | 72 px / 48 px (front layer with rail: 64 px / 42.7 px) |

Why rule 1 holds: `.time-grid__items` has one explicit track `minmax(0, 1fr)` and no
`grid-auto-columns`; every item has `grid-column: 1`. No implicit column can exist. Item width
`calc((100% − rail) / lanes)` and margin-left `rail + (100% − rail)·(lane − 1)/lanes`, with
`lane ≤ lanes`, sum to at most 100% of the column. Percentages of a grid item resolve against its
grid area, the column. Lane numbers above `LANE_LIMIT = 8` are clamped to the last lane, so any
number of overlaps stays inside the column.

Why rule 2 holds: each line is `display: block; height: var(--line-height); white-space: nowrap;
overflow: hidden; text-overflow: ellipsis`, so no line wraps (width). The server renders only
`lines_that_fit(span)` lines visible from 64rem; later lines get class
`time-grid-item__line--cut` (`display: none` from 64rem). The visible-lines height is exactly
n × 18 px; the 0..17 px slack is padding. Below 64rem (375 px list) nothing is cut and lines wrap
with `overflow-wrap: anywhere`, so every word shows.

For measurement 9: measure `scrollWidth` vs `clientWidth` on the block (`.time-grid-item`), not
on a line (a line with an ellipsis has `scrollWidth > clientWidth` by design). Height check:
`.time-grid-item__lines` height ÷ 18 px is a whole number, and the block's `scrollHeight` equals
its `clientHeight`. Left and right edges against `.time-grid__items`.

## Blocks to touch (one sentence each, in order)

1. `scheduling/domain/lane_assignment.py` (new, pure, mutation gate): `assign_lanes(intervals)`
   takes `(first_row, end_row)` pairs, returns for each input a `LanePlacement(lane, lane_count)`:
   overlap means `a.start < b.end and b.start < a.end` (touching is not overlap); blocks that
   overlap in a chain form one cluster, a sweep over start order gives each block the lowest lane
   free at its start, `lane_count` is the lanes the cluster used. `covered_by(fronts, behinds)`
   returns for each front interval whether any behind interval overlaps it. `lanes_needed`
   (max lane count) is `max(placement.lane_count)`. Input is visual rows after snapping, not real
   times, so two blocks snapped to one row count as overlapping.
2. `scheduling/domain/calendar_grid.py`: add `ROW_HEIGHT_PIXELS = 68`, `LINE_HEIGHT_PIXELS = 18`,
   `BLOCK_FRAME_PIXELS = 12`, `lines_that_fit(span_rows)`; the CSS test ties them to the style
   sheet.
3. `scheduling/views/pages/time_grid.py`: `GridItem` gets `behind: bool = False` (default keeps
   `public_pages.py` and the rooms page working). `grid_column` runs `assign_lanes` per layer
   over the items placed inside, adds classes `time-grid-lane-K time-grid-lanes-M
   time-grid-behind|time-grid-front [time-grid-over]`, and gives each item `fits` (lines visible)
   and `spoken` (all lines joined with ", "); split into small helpers to stay under 50 lines.
4. `scheduling/views/pages/clinician_calendar.py`: appointment lines become time, type, patient,
   room (when it has one), status word; time off items get `behind=True` and href
   `/clinician/time-off#time-off-<id>`; badge keeps `(kind, text)` for the icon.
5. `scheduling/templates/clinician/time_off.html`: `id="time-off-<id>"` on each row so the link
   lands on the full reason.
6. `scheduling/templates/components/time_grid_item.html`: `<a>` (or `<span>` without href) holds a
   `visually-hidden` `spoken` text (the accessible name: every word, status included) and an
   `aria-hidden` `.time-grid-item__lines` wrapper with the lines; status icon prefix on the first
   line (rule 6: status visible in the smallest block), the status word is the last line; lines
   past `fits` carry the `--cut` class. Remove the badge outside the link.
7. `static/css/time-grid.css`: tokens `--line-height`, `--rail`; single explicit column, no
   `grid-auto-columns`; `grid-column: 1` on items; lane classes 1..8 setting `--lane`/`--lanes`;
   behind/front z-index; line rules above; `--cut` rule from 64rem. No inline style or script.
8. Rooms (`clinician_rooms.py`): no code change expected; it passes through `grid_column` and
   gets the same containment and lines (time, label, 2 lines).

Not touched: `place_in_grid` (rows still snap to 30 minutes: a 12:15 start draws on the 12:00
row; its text keeps the real time; skipped, own task if wanted), models, use cases, tokens.css,
the API, migrations, audit code.

## Failing tests first (`returns_X_when_Y`)

Domain `scheduling/domain/test_lane_assignment.py`:
- `returns_one_lane_each_when_blocks_only_touch`: 0..2 and 2..4 → both lane 1 of 1.
- `returns_two_lanes_when_three_blocks_overlap_in_a_chain`: 0..4, 2..6, 4..8 → lanes 1, 2, 1,
  all with lane_count 2 (first and third touch, not overlap).
- `returns_three_lanes_when_three_blocks_overlap_at_once`: lanes 1, 2, 3, count 3.
- `returns_separate_counts_when_clusters_are_apart`: a pair then a lone block → counts 2 and 1.
- `returns_input_order_when_input_is_unsorted`.
- `returns_lane_one_of_one_for_each_layer_when_a_whole_day_of_time_off_covers_appointments`:
  band 1..24 alone → 1 of 1; appointments rows 3, 7, 12 alone → each 1 of 1;
  `covered_by` → all True. Same spans in one call → appointments lane 2, band lane 1.
- `returns_not_covered_when_the_front_only_touches_the_band`.
- `returns_empty_when_no_blocks`.
- `returns_three_lines_when_block_is_one_row` (and 6, 10, 14 for 2, 3, 4 rows) in
  `test_calendar_grid.py`.

Views `test_time_grid.py` (rendered HTML):
- `returns_lane_classes_inside_the_day_when_time_off_overlaps_an_appointment`: Monday 12..14
  time off, appointment 13:00: band `time-grid-behind time-grid-lane-1 time-grid-lanes-1`,
  appointment `time-grid-front time-grid-over`, both on the Monday list only.
- `returns_last_lane_when_more_overlaps_than_the_limit`.
- `returns_cut_class_on_lines_past_the_fit_when_block_is_one_row` (patient visible, room and
  status cut; time, type, patient visible).
- `returns_all_words_in_the_spoken_text_when_reason_has_200_characters`.
- `returns_status_word_and_icon_when_block_is_one_row`.
- `returns_time_off_link_to_its_row_when_calendar_has_time_off`; time off page has that `id`.
- Page tests post/get with auth as the clinician; the pages stay clinician-only.

Style sheet `test_time_grid_css.py` (replaces the side-by-side min-width test):
- `returns_one_explicit_column_and_no_implicit_columns_when_items_are_laid_out`.
- `returns_grid_column_one_on_every_item`.
- `returns_line_rules_that_never_wrap_and_end_in_an_ellipsis`.
- `returns_pixel_constants_equal_to_the_domain_when_tokens_are_parsed` (68, 18, 12 from
  `--row-height`, `--line-height`, spaces, borders, margin).
- `returns_a_lane_class_for_every_lane_up_to_the_limit`.
- `returns_cut_lines_hidden_only_from_64rem`.
- Containment derivation test: for every lanes 1..8, lane ≤ lanes, so margin + width ≤ 100%.

## Invariants and blast radius

No write path changes; double booking, authorization (clinician-only pages, own data from the
session), audit log untouched. Reason text is user input: rendered autoescaped, in hidden text
and visible lines, never in markup or style. Blast radius: the two grid pages and the style
guide page if it uses `GridItem`. No new dependency.

## Trust boundaries

Time off reason and patient names reach the page: Django autoescaping, no `|safe`. The time off
link is an in-app path built from a UUID primary key of a row the clinician owns.

## Vocabulary

Clinician, Appointment, AppointmentType, Room, TimeOff, Patient, Department's hospital time
zone. Not a domain term: "lane", "band" (view terms only).

## Not doing

No browser or JS, no container queries, no Node, no abstraction beyond the lane module, no
change of row snapping, no new time off detail page (the list page with an anchor is the page).
Orchestrator measures in Chrome at 1440 and 1024 px (measure 9).
Final reply lists "Closes #30".

## Architect review

Verdict: approve.

- Ladder: root causes named (implicit grid column, wrapping lines). One new pure module, one
  view-layer change, CSS; no dependency, no model or API change. Band-behind layout is the
  smaller choice and the 144 px arithmetic backs it.
- Rules 1 to 9 each map to a block and a test; the numbers table is derivable and the CSS test
  ties it to the domain constants. Three-chain, touching, whole-day-of-time-off cases covered.
- Security: user text autoescaped, link built from a pk of an owned row, pages stay clinician-only.
- Layering: lane logic pure in domain, views format only.
- Watch while implementing (not blockers): keep `grid_column` and each helper under 50 lines and
  files under the size cap; mutation survivors in `lane_assignment.py` need real tests or entries
  in `mutation-equivalents.txt`; check the time off link also works for another week's time off
  (anchor on a list that may be paginated or filtered); update the `/style` page if it uses
  `GridItem`; the commit body must carry "Closes #30" and tooling disclosure, no AI trailer.
