# Task 27a plan: inputs that reach the database

Slice: items 1, 2, 3 and 6 (findings #33, #38, #45, #41, plus the one text rule and the one
window function). Each is reproduced by a failing test first.

## Not in this run
- Item 4: the derived hostile-input test (pages from the URL configuration per role, every
  `/api/v1` request schema field, every `/fhir` write element). Next slice. It will derive
  forms with the walker of `page_walk_support.py`, send each hostile value (NUL, 20 000
  characters, 10**30, -1, wrong type, `<script>` markup) one field at a time plus once to all
  fields, and cost about forms x fields x 6 values requests; the count is measured and
  written into that plan before it is built. It replaces `FIELD_NAMES` in
  `scheduling/views/test_hostile_input.py`.
- Item 5: one test over every form, refused, echoing what was typed (except password, code).
- #50 (NUL in FHIR search parameters) and the other round 3 findings: 27b.

## Focal point
`scheduling/domain/text_rules.py` (new) and `scheduling/domain/whole_numbers.py` (new): one
text rule and one integer rule, called where each value enters the domain. Plus
`window_words` in `scheduling/domain/waitlist_window.py`.

## Blocks (one sentence each)
1. `domain/whole_numbers.py`: `check_whole_number(field, raw, minimum, maximum)` and
   `SMALLINT_MAXIMUM = 32767`; refusal text "Use a whole number of at most 32767".
   `record_fields._whole_number` and `clinician_rules.check_weight` call it.
2. `domain/text_rules.py`: `check_storable_text(field, raw, *, single_line)` refuses what
   PostgreSQL or a page cannot carry; replaces the five ad hoc `"\x00" in` checks
   (`record_fields.py`, `fhir_common.carries_only_storable_text`, `admin_records.py`,
   `admin_user_support.py`, `admin_filters.py`) and is added to `validate_clinical_note`,
   `time_off_rules`, `check_title`, bio, cancel reason, booking reason, hold name/phone.
3. `views/schemas.py`: `StrictText(CharField)` refuses any non-string and calls the text rule;
   every `CharField` of a request schema (`auth_schemas`, `booking_schemas`, `hold_schemas`,
   `waitlist_schemas`, `booking_forms`) becomes `StrictText`.
4. `domain/waitlist_window.py`: `window_words(earliest_at, latest_at, time_zone)`; `day_label`
   moves to a domain `date_words.py` and `booking_links` re-imports it.
   `patient_waitlist_rows.waitlist_row` calls it (this row is also the admin list's row).

## Integer columns a write can reach (bounds, where checked)
| Column | Bounds | Checked in |
|---|---|---|
| ClinicianProfile.round_robin_weight (smallint) | 1..32767 | `clinician_rules.check_weight` (page, `admin_clinicians` use case, FHIR role extension via the same use case). Bug: no upper bound |
| Room.capacity (smallint) | 1..32767 | `record_fields.check_capacity`; FHIR `room-capacity` calls it |
| AppointmentType.duration_minutes (smallint) | 1..32767 | `record_fields.check_duration_minutes`; FHIR calls it |
| AppointmentType.buffer_minutes (smallint) | 0..32767 | `record_fields.check_buffer_minutes`; FHIR calls it |
| AvailabilityRule.weekday (smallint) | 0..6 | `availability_rules._weekday_failures` (page, API, FHIR) |
| AvailabilityRule.slot_step_minutes (smallint) | SLOT_STEP_MINIMUM..MAXIMUM | `availability_rules` step check |
| `version` on every record (positive integer) | 0..2147483647 | client sends it (page hidden field `int(version)`, FHIR `meta.versionId`, `If-Match`): a test decides if a value above the column is a conflict or a crash; fix in `whole_numbers` only if it fails |
| inherited_version, attempts_used | server set | not reachable by a write; no check |
`bool` is an `int` in Python: a test sends `true` as `valueInteger` and as weight.

## Text rule (item 2)
Refused in every text a write accepts: NUL (PostgreSQL text cannot hold it), other C0
controls U+0001..U+001F, DEL U+007F, C1 controls U+0080..U+009F (a page or a terminal
renders them as nothing or as commands), lone surrogates U+D800..U+DFFF (cannot encode to
UTF-8, a `DataError`/`UnicodeEncodeError` in the driver). Free text (clinical note, time-off
reason, cancel and booking reason, bio, equipment lines) keeps TAB, LF, CR: people write
paragraphs and lists. Single-line text (names, titles, codes, phone, email) refuses those
three as well, so a line break cannot split an email subject or a CSV cell. Message:
"Remove the character that cannot be saved." (the existing `NULL_MESSAGE`), on the field.

## Files, in order
Tests first (red): `domain/test_whole_numbers.py`, `domain/test_text_rules.py`,
`domain/test_waitlist_window.py`, `views/test_api_text_fields.py`,
`views/pages/test_admin_clinician_weight.py` (and beside the existing page tests: note,
time off), `views/fhir/` write tests for weight and NUL. Then: `domain/whole_numbers.py`,
`domain/text_rules.py`, `domain/date_words.py`, edits to the files named in the blocks.
Not touched: `drlibre-specs.md`, models and migrations (no column change), FHIR search
(27b), `test_hostile_input.py` (next slice).

## Failing tests first (`returns_X_when_Y`)
- `returns_field_refusal_when_weight_is_32768` (page create and edit: 422 on
  `round_robin_weight`, nothing saved; 32767 saves). Same for 99999999999 and a FHIR
  `valueInteger` 40000 (400 naming `PractitionerRole.extension`), `true` refused.
- `returns_422_naming_clinical_notes_when_note_has_nul_byte`; `..._time_off_reason_...`;
  through the page; `/api/v1` and FHIR text writes with a NUL byte answer 400/422, never 500.
- `returns_refusal_when_text_has_control_character`, `returns_text_when_free_text_has_line_break_and_tab`,
  `returns_refusal_when_single_line_text_has_line_break`, lone surrogate refused.
- `returns_invalid_input_when_api_text_field_gets_a_number`: one test over every
  `StrictSerializer` request schema, each `CharField` must be `StrictText` and refuse 12345,
  `true`, a list and an object (`POST /api/v1/appointments` reason 12345 answers 400).
- `window_words`: `returns_one_day_when_window_is_one_day` (26 Nov 00:00 to 27 Nov 00:00
  Berlin -> "Thursday 26 November 2026 (Europe/Berlin)"), `returns_30_november_when_window_ends_on_last_day_of_month`,
  `returns_chosen_days_when_hospital_is_east_of_utc` (Pacific/Auckland),
  `returns_chosen_days_when_hospital_is_west_of_utc` (America/Los_Angeles),
  `returns_last_day_two_days_on_when_window_is_two_days` (26 to 27 November, as #41),
  `returns_day_of_end_when_end_is_not_midnight` (admin instant 27 Nov 17:00),
  DST-change day. Page test: patient list and admin list show "to Friday 27 November 2026"
  for the #41 steps. Clinician view, notifications and emails print no window today
  (grep of `latest_at` found none); the build stage re-checks and routes any it finds through
  `window_words`.

## Invariants and blast radius
No change to booking, double booking, authorization or audit: refusals happen before the
use case writes, inside the same transaction rules; no new write path. Messages of existing
refusals stay. Blast radius: every text field gains a control-character refusal (a pasted
form feed is now refused), every API text field refuses non-strings (clients sending numbers
get 400, wanted by #45), weights above 32767 refused. Mutation gate covers the three new
domain files; survivors explained in `mutation-equivalents.txt` or killed.

## Trust boundaries
Page forms, `/api/v1` bodies, FHIR resources: values are untrusted; rule runs at the domain
check each path already calls, so the three refuse the same value the same way. Authorization
untouched (session/token). Hostile values never logged.

## Vocabulary
ClinicianProfile, Room, AppointmentType, AvailabilityRule, TimeOff, Appointment (clinical
note, reason), WaitlistEntry, Hospital (time zone), ApiClient (token for FHIR).

## Will not do
No new dependency, no model or migration, no refactor of the text checks beyond swapping
them for the one rule, no new error type (`Failure.invalid_input`).

## Architect review
Verdict: approve.
- Slice (items 1, 2, 3, 6) is coherent: one integer rule, one text rule, one window function, each at the domain check every path already calls. Product stays whole; items 4 and 5 are the guard, not a dependency of the fixes.
- Condition: items 4 and 5 are the reason #33 and #38 passed the hostile-input test. They must exist as a backlog file (27a-2 or similar) and in `doc/backlog.md` before this run merges, so the slice is not silently dropped. Reviewer and orchestrator should check that.
- Build stage: the `version` row must be settled by a test (above-column value is a conflict, never a 500); `true` as an integer must be tested on every integer path. Page-form tests need Origin and the cross-site check on; the FHIR writes need bearer token without cookie (CLAUDE.md rules).
- Build stage: re-grep for window prints (`latest_at`, `earliest_at`) in templates, emails and notifications, and route each through `window_words`; the task names those places.
- Mutation: the three new domain files must pass `make mutate`; explain survivors in `mutation-equivalents.txt`.
