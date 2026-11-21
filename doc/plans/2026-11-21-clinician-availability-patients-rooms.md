# Plan: task 17, availability, time off, patients, rooms, and the shared time grid

One sentence: two audited write use cases (availability rule, time off) whose rules are pure
domain functions backed by DB constraints, two read pages (patients, rooms), and one time-grid
component that the calendar and the rooms timeline both render.

## Findings that shape the plan

- `AvailabilityRule` and `TimeOff` exist with the DB checks for weekday 0..6, whole minutes,
  end after start, step 5..240, `valid_to >= valid_from`, `TimeOff` end after start, reason
  `max_length=200`. Missing in DB: rule overlap per weekday, identical time off.
- `AvailabilityRule.weekday` constants in `models/availability.py` are named
  `WEEKDAY_MONDAY = 0`, `WEEKDAY_SUNDAY = 6`. Wrong against the spec (0 Sunday, 6 Saturday;
  `free_slots.py:86` already uses Sunday = 0). Rename to `WEEKDAY_SUNDAY = 0`, `WEEKDAY_SATURDAY = 6`
  (no migration: names only; constraint values unchanged). Grep callers first.
- Public search, `/api/v1/slots`, booking pages and placement all load through
  `use_cases/schedule_loading.load_schedules`, which reads `AvailabilityRule` and `TimeOff` rows
  fresh each call. Requirement 4 needs no code, only tests proving it. No cache to invalidate.
- `Versioned.save()` raises the version on update; the trigger refuses anything else. Delete has
  no version to raise: the audit entry of the delete carries the entity id (same as other deletes).
- `PageView`/`render_page` already set no-store headers; `ClinicianPage` gives role guard and
  profile. Record rule helper `guard_record` exists.
- `calendar_week.html` + `place_in_grid` + `workspace.css` `.cal-*` classes (24 rows of 2.75rem,
  no axis, no visible rows, clipped block text). Rooms timeline needs the same grid with rooms as
  columns, so the grid is generalised once.
- Audit metadata cannot hold free text (`AuditMetadata`): reason of time off never enters it.

## Focal point

`scheduling/domain/availability_rules.py` (the decisions) and `use_cases/availability.py`
(the audited writes). Everything else formats or reads.

## Blocks, one sentence each

Domain (pure, under mutation gate, tests beside):
- `domain/availability_rules.py`: `rule_failures(weekday, start, end, step, room_is_valid, others)`
  as `FieldMessage`s: weekday 0..6, end after start, whole minutes, step 5..240, room must be an active room of the clinician's department (decided from a
  boolean the use case computes: `RoomChoice(exists_in_department, is_active)`), overlap with
  another rule of the same weekday (touching allowed: half-open intervals).
- `domain/availability_rules.py`: `WEEKDAY_NAMES` (Sunday first) and `weekday_name(weekday)`;
  `new_rule_validity(today)` returns `(today, None)`.
- `domain/time_off_rules.py`: `time_off_failures(starts, ends, reason, existing_periods)`: end
  after start, reason at most 200 characters after trimming, identical period (same start and
  end instant) already recorded. `appointments_inside(period, appointments)` picks active
  appointments overlapping the period (half-open).
- `domain/patient_directory.py`: `matches_name(full_name, query)` (case-insensitive,
  whitespace-split terms all contained, empty query matches all) and `last_and_next_visit(now,
  visit_starts)` picking last past and next future active visit.
- `domain/calendar_grid.py` (existing): add `HOUR_LABELS` rows (07:00..19:00 every 2 rows) and
  `grid_rows()` so one function owns the axis; `place_in_grid` unchanged.
- `domain/room_timeline.py`: `occupancy_label(is_own, patient_name)`: own shows the name, other
  returns exactly "Occupied" and takes no patient argument at all (cannot leak by construction:
  the loader passes the name only for own rows).

Models and migration `0012`:
- `AvailabilityRule`: `ExclusionConstraint` per (clinician =, weekday =, minute-of-day range
  overlaps, half-open), name `availabilityrule_no_overlap_for_weekday`; validity dates ignored
  (stricter and simpler: two rules never overlap on a weekday). Seed has one rule per weekday.
- `TimeOff`: `UniqueConstraint(clinician, starts_at, ends_at)` name `timeoff_period_unique`.
- Room active and department membership is cross-table: held by the domain + use case under a
  row lock on the room, not by the DB. Said in the module docstring.
- Constant rename above. Regenerate `doc/data-model.md` via `render_data_model`.

Use cases (`use_cases/`):
- `availability.py`: `create_rule`, `update_rule`, `delete_rule` (command dataclass, actor).
  Each: lock the clinician's rules (`select_for_update` on the profile row to serialise
  overlaps), record rule (own rule only: missing `not_found`, other's `forbidden`), domain
  validation, save (version +1 on update), `record_audit` in the same transaction: actions
  `availability.create|update|delete`, entity `AvailabilityRule`, metadata clinician id, room id,
  `changed_fields`. Overlap race: DB exclusion is the backstop; an `IntegrityError` on it maps to
  the same `invalid_input` value, never a 500.
- `time_off.py`: `create_time_off`, `delete_time_off` with the same shape; actions
  `time_off.create|delete`; no reason in metadata. Create does not touch appointments.
- `clinician_availability.py` (reads): `own_rules(profile)`, `own_time_off(profile)`,
  `bookable_rooms(profile)` (active rooms of the department), `appointments_in(profile, period)`.
- `clinician_patients.py` (read): `patients_of(profile, query, now)`: patients through
  `Appointment.objects.filter(clinician=profile)` only (never `User` first), name search applied
  after that scope, by the ORM `icontains` per term; returns name, phone, last, next. A query
  can only narrow the scoped set, so no other patient is reachable.
- `clinician_rooms.py` (read): `room_day(profile, day)`: active rooms of the department, active
  appointments of that local day in those rooms; each cell carries the patient name only when
  `appointment.clinician == profile`, else the plain label. Cancelled/no-show excluded.

Views and templates (`views/pages/`, `ClinicianPage`, thin):
- `clinician_availability.py`: `/clinician/availability` list (days by name, times, step, room,
  edit and delete links); `/new`; `/<uuid>/edit`; `/<uuid>/delete` (GET confirmation, POST).
  Forms are plain posts with 303 to the list; failures re-render 422 with `error_summary` and
  `field.html`. Weekday is a `<select>` of names; room a `<select>` of active department rooms
  plus "No fixed room".
- `clinician_time_off.py`: `/clinician/time-off` list, create form on the same page, delete
  confirmation. The page says "Time off does not cancel appointments already booked in it."
  Before recording: step 1 `GET` preview lists appointments inside the entered period (links to
  them); step 2 POST records. Works without JavaScript. Datetimes are entered in the hospital
  zone (`datetime-local`, zone named on the page) and converted by one helper, DST-safe, bad
  or ambiguous value is a field error.
- `clinician_patients.py`: `/clinician/patients?q=` list, GET search form with a label.
- `clinician_rooms.py`: `/clinician/rooms?date=` with previous/next/today.
- `components/workspace_nav.html`: the four "soon" items become links with `aria-current`.
- `components/time_grid.html` (new, one component): columns of items on the 07:00 to 19:00
  grid. Columns are days (calendar) or rooms (timeline). Renders hour labels from
  `calendar_grid.grid_rows`, visible 30 minute row lines (CSS backgrounds on the column), and
  each block as a list item with text. Replaces `calendar_week.html`; `calendar_block.html` kept
  and extended. Below the wide breakpoint it is the stacked list (screen reader and 375 px).
- Block readability fix: wide row height 3.25rem; block shows time, type and patient on separate
  lines (`display: block`), no `overflow: hidden` clip on text; room, status and the rest only
  on the appointment page for the grid view (the list view keeps the full sentence). A 30
  minute block is two lines high at least: row height set so that holds, else the block takes
  `min-height: min-content` and overlays (decision for the builder, checked by the orchestrator
  in Chrome).
- Appointment history: `_history` time format gains the zone abbreviation (`%Z`, "CET").
  Show the zone name in the heading text too.
- CSS: `workspace.css` is already large; grid rules move to a new `static/css/time-grid.css`
  linked from `base.html`'s head block of the pages that use it (not global). Rows classes stay
  static. No inline style, no script.
- `/style` page gains the time grid and the new forms' components (reuse of existing field,
  notice, empty_state, error_summary).

## Files to touch, in order

1. `scheduling/domain/` five new modules (+ tests), `calendar_grid.py` addition.
2. `models/availability.py`, migration `0012`, `doc/data-model.md`, constant rename callers.
3. `use_cases/availability.py`, `time_off.py`, `clinician_availability.py`,
   `clinician_patients.py`, `clinician_rooms.py` (+ tests).
4. `views/pages/clinician_availability.py`, `clinician_time_off.py`, `clinician_patients.py`,
   `clinician_rooms.py`, `clinician_calendar.py` (use the shared grid), `clinician_appointment.py`
   (history zone), `clinician_support.py` (path constants), `drlibre/urls.py`.
5. Templates (`clinician/availability*.html`, `time_off*.html`, `patients.html`, `rooms.html`,
   `components/time_grid.html`, nav), CSS, `style.html`.
6. `mutation-equivalents.txt` only for an explained survivor.

Not touched: `schedule_loading.py`, `free_slots*` (same loading is the point), API/FHIR
layers, admin console, seed (unless the demo clinician has no free room; then a note),
settings, CSP, `appointment_changes`, placement, JS (none).

## Invariants and blast radius

- No double booking: untouched. Time off and rules only shrink or grow what the engine offers;
  existing appointments stay as booked.
- Authorization server-side: clinician from session; rule and time off ids go through the
  record rule in the use case (other's id `forbidden`, shown as the existing 403 page; missing
  404); room id must belong to the clinician's department; patients and rooms scoped by profile.
- Audit append-only and in the same transaction; reason and patient names never in metadata.
- Blast radius: one migration (two constraints); constant rename; calendar markup changes
  (task 16 calendar tests are retargeted to the new component); history text gains a zone.
  Migration must fail loudly if existing rows overlap; seed and builders are checked.

## Failing tests first (`returns_X_when_Y`)

Domain:
- `refuses_rule_when_ends_at_or_before_start`; `accepts_rule_when_touching_other_rule_1200_1200`;
  `refuses_rule_when_overlapping_other_by_one_minute`; `accepts_rule_when_same_times_other_weekday`;
  `refuses_rule_when_step_is_4_or_241`, accepts 5 and 240; `refuses_rule_when_room_inactive`;
  `refuses_rule_when_room_of_other_department`; `names_weekday_sunday_when_0_and_saturday_when_6`;
  `starts_new_rule_today_with_no_end`.
- `refuses_time_off_when_end_not_after_start`; `refuses_reason_of_201_characters`, accepts 200;
  `refuses_time_off_when_identical_period_exists`, accepts a period shifted by one minute;
  `lists_appointment_when_inside_period`, `skips_cancelled`, `skips_appointment_touching_end`.
- `matches_name_when_terms_in_any_order_ignoring_case`; `matches_all_when_query_empty`;
  `picks_last_past_and_next_future_visit`.
- `shows_patient_name_when_own`, `shows_only_Occupied_when_not_own`.
- Grid: `labels_every_hour_from_0700_to_1900`.
- Mutation: `make mutate` covers all new `domain` modules.

Models (real PostgreSQL): `refuses_overlapping_rules_in_database`; touching rules insert;
`refuses_identical_time_off_in_database`.

Use cases: `creates_rule_and_audits_in_same_transaction` (version 1, one entry, metadata ids
only); `update_raises_version_to_2_and_audits`; `delete_removes_row_and_audits`;
`rolls_back_when_audit_write_fails`; `returns_forbidden_when_other_clinicians_rule`
(row unchanged, no audit); `returns_not_found_when_missing`; `returns_invalid_input_when_room_
of_other_department`; time off equivalents; reason not in audit metadata; time off leaves an
appointment inside it booked and active.
- Requirement 4: `new_rule_slots_appear_in_api_slots_when_rule_created` and
  `deleted_rule_slots_disappear_from_api_slots_when_rule_deleted` (call create/delete use case
  then `GET /api/v1/slots`, expected exact slot starts); same for the booking page week strip.
- Patients: `lists_only_patients_with_appointment_with_this_clinician` (planted patient of another
  clinician absent from list and from searches by his full name, a first name, `%`, `_`, empty
  string and a wildcard); phone, last and next visit values exact.
- Rooms: only active rooms of the department; own cell has the patient name; other clinician's
  cell has "Occupied" and none of patient name, phone, type, reason in the HTML.

Pages (rendered HTML, `browser_post`: Origin set, token enforced; 403 with other Origin, `null`
Origin, no token): create, edit, delete rule; create, delete time off; preview of appointments
inside period; 422 with error summary and field errors; weekday shown by name; no `style=`,
inline script, one `h1`, no skipped heading, labelled controls, `Cache-Control` no-store on
availability, time off, patients, rooms and the calendar; other clinician's ids give 403; patient
and anonymous refused; nav links with `aria-current`; time grid has hour labels 07:00..19:00,
24 row elements, each block's text has time, type and patient; rooms page list reading order;
history times carry the zone abbreviation; time off page contains the not-cancelling sentence.

## Trust boundaries

Browser to server: ids by `<uuid:>` converter then record rule; weekday, times, step, room id,
datetimes, reason, query all parsed and validated in domain and use case; never trust the
clinician id in a form (none sent). Search text reaches the ORM only as a parameter, after the
clinician scope. Server to browser: autoescape; no colour or user text enters CSS.

## Vocabulary used

Clinician, ClinicianProfile, AvailabilityRule, TimeOff, Room, Department, Hospital (time zone),
Appointment, Patient (User), AuditLogEntry.

## What I will not do

No JavaScript, dependency, calendar library or cache. No change to slot engine or loading. No
recurring or bulk time off, no cancelling of appointments inside time off. No rule validity
editing (new rule is today, open end). No abstraction beyond the one time grid (second caller:
rooms). No patient export or profile page.

## Not verified here

No browser: 375 px and 1440 px layout, block readability, contrast and focus order are the
orchestrator's Chrome check, with the add/remove rule against public search.

## Architect review

Verdict: approve.

- Ladder: one shared time grid, no new dependency, no loading change. Requirement 4 is tests only. Right call.
- Layers: rules pure in `domain/`, audited writes in use cases, views thin. Matches §8.
- Tests: first failing tests are named as behaviours with edge values (touching, one minute overlap, step 4/241/5/240, reason 200/201). Patient isolation test includes `%`, `_`, empty.
- Security: patients scoped via `Appointment` before search; "Occupied" cannot leak by signature; reason kept out of audit metadata; record rule in the use case.

Notes for the builder (not blockers):
1. PostgreSQL has no `timerange`. The exclusion constraint needs an immutable expression, for example an `int4range` over minutes of day, or a custom range type. Prove it in the migration test, with a touching row accepted. `btree_gist` is already installed (0001).
2. Constraint ignores `valid_from`/`valid_to`. Say so in the model comment, and check the seed and builders for rules that would now collide.
3. Time-off identical-period race: map `IntegrityError` from `timeoff_period_unique` to the same `invalid_input` value, as for rules.
4. Two-step preview of appointments inside the period must not record on GET; the POST re-validates, since the preview is not trusted.
5. Task 16 calendar tests move to the shared component; keep them asserting the same facts.
