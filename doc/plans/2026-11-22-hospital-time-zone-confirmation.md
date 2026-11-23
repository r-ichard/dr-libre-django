# Hospital time-zone change asks for confirmation (task 27b item 10, issue #36)

Slice: item 10 only. One change, one run. Nothing else of `doc/backlog/27b-qa-round-3-pages.md`.

## Focal point

`RecordFormPage.post` in `scheduling/views/pages/admin_records.py` saves a hospital's new
time zone at once. Before the save it must show a confirmation: how many upcoming
appointments will read another local time, and one example before and after. The admin
then confirms by sending the same form again with `confirm_time_zone=1`. Nothing is sent to
patients.

Reused: `admin_record_reads` upcoming filter (same `ACTIVE_STATUSES` as
`upcoming_appointment_count`), `written_moment` (domain formatter, takes `ZoneInfo`),
`_form` and `admin/form.html` (version hidden field, `problem` notice slot),
`components/notice.html` (kind `warning`), `parse_form` (zone already validated by
`check_time_zone`).

Impeccable mode: `PRODUCT.md` and `DESIGN.md` exist and the `reference/craft-floor.md` read
is a step of the generate stage before the template edit (block 5). This plan adds no CSS.

## Types

- `shifted_starts(starts: Iterable[datetime], old_zone: ZoneInfo, new_zone: ZoneInfo) -> list[datetime]`
  (domain). Zones are `ZoneInfo`, never strings: the view builds them.
- `upcoming_starts(hospital_id: UUID, now: datetime) -> list[datetime]` (use case).
- `time_zone_warning(starts: list[datetime], old_zone: ZoneInfo, new_zone: ZoneInfo) -> str`
  (view module). Returns `""` when no start shifts.

## Blocks, one sentence each

1. `scheduling/domain/time_zone_shift.py` (new): `shifted_starts` returns the starts whose
   wall-clock reading (`astimezone(zone)` with tzinfo dropped) differs between the two zones,
   in input order. Pure, no ORM, no clock. Berlin to Paris returns nothing: same wall clock.
2. `scheduling/use_cases/admin_record_reads.py` (add after `upcoming_appointment_count`,
   line 108): `upcoming_starts(hospital_id, now)` with the same filter as the count
   (`clinician__department__hospital_id`, `starts_at__gt=now`, `status__in` `ACTIVE_STATUSES`),
   `values_list("starts_at", flat=True).order_by("starts_at")`, returned as a list.
3. `scheduling/views/pages/admin_time_zone_warning.py` (new): `time_zone_warning(starts,
   old_zone, new_zone)`. Computes `shifted_starts`; with none, returns `""`. Otherwise returns
   exactly:
   `"{N} upcoming appointment{s} will show another local time. For example, {before} will read {after}."`
   where `N` is the shifted count, `s` is `""` for one and `s` for more, and `before` / `after`
   are `written_moment(first_shifted, old_zone)` / `written_moment(first_shifted, new_zone)`.
   "Appointment" is the singular/plural pattern of `_time_zone_note`.
4. `scheduling/views/pages/admin_records.py`:
   - new method `RecordFormPage._time_zone_warning(self, record, values) -> str`: returns `""`
     unless `self.kind == "hospital"` and `record` is a `Hospital` (`isinstance`, no assert, no
     cast). Otherwise `now = current_request_context().now`,
     `starts = admin_record_reads.upcoming_starts(record.pk, now)`, and
     `time_zone_warning(starts, ZoneInfo(record.time_zone), ZoneInfo(str(values["time_zone"])))`.
     `values` is the `dict[str, object]` from `parse_form`; `str()` converts, it is not a cast.
   - in `post`, after the `if errors:` return and the version check, before
     `writers.update`: `if request.POST.get("confirm_time_zone") != "1":` compute
     `warning = self._time_zone_warning(record, values)`; if non-empty, return
     `self._form(request, record, typed, {}, int(version), time_zone_warning=warning)`
     (status 200, nothing saved). `int(version)` keeps the hidden `version` on the page so the
     confirmed POST is not a 422 in a browser.
   - `_form` gains one keyword `time_zone_warning: str = ""` and puts it in the context.
   - Imports: `Hospital` from `scheduling.models`, `ZoneInfo`, and `time_zone_warning`.
   - File grows by about 15 lines (412 to about 427), under the 500-line gate.
5. `scheduling/templates/admin/form.html`: when `time_zone_warning` is set, render
   `components/notice.html` with `kind="warning"` and the text as the first child of the
   `<form>`, before the error summary and the fields. Add
   `<input type="hidden" name="confirm_time_zone" value="1">` inside the form, and label the
   submit button "Save with the new time zone" (else "Save"). Without the context key the page
   is unchanged.
6. Tests (see below): `scheduling/domain/test_time_zone_shift.py` (new) and page tests in
   `scheduling/views/pages/test_admin_records_pages.py`.

## Files touched, in order

1. `scheduling/domain/test_time_zone_shift.py` (new, red first)
2. `scheduling/domain/time_zone_shift.py` (new)
3. `scheduling/use_cases/admin_record_reads.py` (one function added)
4. `scheduling/views/pages/admin_time_zone_warning.py` (new)
5. `scheduling/views/pages/test_admin_records_pages.py` (tests added, red first)
6. `scheduling/views/pages/admin_records.py` (method, post branch, `_form` kwarg, imports)
7. `scheduling/templates/admin/form.html` (three template lines)

## Files deliberately not touched

- `drlibre-specs.md`: the owner's text. The patient question stays open in `doc/backlog.md`.
- `scheduling/use_cases/admin_records.py` and the writers: the save path does not change.
  Authorization, version check and audit entry stay where they are.
- `_time_zone_note` and its three tests: the note on GET stays as it is.
- Notifications, email content, FHIR, patient pages, CSS.

## Failing tests first

Expected values come from the finding (QA #36: "one example before and after") and from
`written_moment`'s format. Fixture: `make_clinic()` (Berlin hospital, `time_zone` default
Europe/Berlin), `NOW` = 2030-01-07 06:00 UTC (test module constant). `make_clinic()` builds
its own department and hospital through the `Department` factory, so a second `make_clinic()`
is a second hospital. The example appointment is at `NOW + 1 day` = 2030-01-08 06:00 UTC,
which reads 07:00 in Berlin and 19:00 in Auckland (winter, NZDT +13). Full strings:
`Tuesday 8 January 2030, 07:00 (Europe/Berlin)` and `Tuesday 8 January 2030, 19:00 (Pacific/Auckland)`.

Domain (`test_time_zone_shift.py`), both red on the missing module:
- `returns_no_starts_when_old_and_new_zone_read_the_same_wall_clock`: Berlin to Paris, one
  start, result empty.
- `returns_every_start_whose_wall_clock_differs_when_zone_changes`: Berlin to Auckland, two
  starts, both returned in order.

Page (`test_admin_records_pages.py`):
- `returns_200_with_warning_sentence_and_button_when_time_zone_changes_with_upcoming_appointment`
  (red): `make_clinic()`, one upcoming appointment at `NOW + 1 day`. POST `time_zone`
  Pacific/Auckland, `version` "1", no confirm flag, via `admin_post`. Expect 200; page contains
  exactly
  `1 upcoming appointment will show another local time. For example, Tuesday 8 January 2030, 07:00 (Europe/Berlin) will read Tuesday 8 January 2030, 19:00 (Pacific/Auckland).`
  (HTML-escaped form is identical: no quotes or ampersands), `Save with the new time zone`,
  and `name="version" value="1"` and `name="confirm_time_zone" value="1"`. Stored zone still
  Europe/Berlin.
- `returns_warning_counting_only_future_active_appointments_of_this_hospital_when_time_zone_changes`
  (red, pins the filter; round 2 reason 1): on the clinic's hospital, one active appointment at
  `NOW + 1 day` (the example), one past at `NOW - 1 day`, one `CANCELLED` at `NOW + 3 days`
  (same fields as the existing cancelled test). On a second `make_clinic()`, one active
  appointment at `NOW + 2 days`. Same POST as above. Expect 200 and the same exact sentence
  with `1 upcoming appointment`. Each excluded row breaks it: a past row would count 2 and
  move the example to 2030-01-06; a cancelled row would count 2; the other hospital's row
  would count 2.
- `returns_303_and_stores_the_new_zone_when_time_zone_change_is_confirmed` (passes before the
  change; guards that confirm does not block the save): same POST plus `confirm_time_zone`
  "1". Expect 303, stored zone Pacific/Auckland.
- `returns_303_without_warning_when_no_upcoming_local_time_changes` (passes before the change;
  guards against over-blocking): Berlin to Paris with the appointment. Expect 303 straight away.
- `returns_303_without_warning_when_only_past_or_cancelled_appointments_would_shift` (passes
  before the change; guards against over-blocking on the excluded rows): Berlin to Auckland,
  with only a past appointment and only a cancelled appointment on the hospital. Expect 303,
  no warning, and no count sentence on the page.

Red-for-right-reason: the domain tests fail on the missing module; the first two page tests
fail on the missing sentence. The three guard tests pass today by design; the plan says so and
the red stage records it.

## Layout

Element added: one warning notice and one button label on the existing form
(`.form` in `static/css/components.css`, max-width 28rem, `justify-items: start`, children
`width: 100%`). No CSS is added, so the block shape of the existing form does not change.

Invariant, at 375 px and at 1440 px, on the warning page (hospital edit, Berlin to Auckland,
one upcoming appointment):
- the document does not scroll sideways: `document.documentElement.scrollWidth` equals
  `document.documentElement.clientWidth`;
- the warning notice (`.notice--warning`) and the form (`form.form`) have their left and right
  edges inside the viewport, and the notice's `getBoundingClientRect()` left and right lie within
  the form's left and right;
- the `.button-row` has `scrollWidth` equal to `clientWidth`, and both buttons ("Save with the
  new time zone" and "Cancel") have right edges no further right than the `.button-row` right
  edge, so the longer label wraps or fits without pushing "Cancel" out of the column.

The sandbox has no browser. The orchestrator measures these numbers in a browser at both
widths. The page test asserts the markup only; nothing in the sandbox proves the layout.

## Invariants that must not break

- Double booking: untouched. No appointment is written.
- Server-side authorization: the warning runs after `record_or_404` and the admin role check.
  `writers.update` still checks role and version. `confirm_time_zone` only skips the warning;
  it grants nothing.
- Append-only audit: the warning writes nothing. The confirmed save writes its existing
  `hospital.update` entry.
- One transaction per change: the warning is a read outside the update transaction; the save
  transaction is unchanged.
- Clock from request context: `current_request_context().now`, not `datetime.now`.
- Times in UTC: appointment `starts_at` is aware UTC; `astimezone` converts.

## Trust boundaries

- `time_zone` from the POST: validated by `parse_form` / `check_time_zone` before the warning.
  Unknown zone: 422 as today, no warning computed.
- `confirm_time_zone` from the POST: client-supplied, only skips the warning. Not trusted for
  authorization.
- `version`: unchanged path; non-numeric returns 422 before the warning.
- Hospital id: from the URL (`path_uuid`), the record from `record_or_404`.
- Output: count and examples are computed server-side and rendered with Django auto-escaping
  through the notice component. No raw HTML.
- Origin/CSRF: tests use `admin_post`, which sends `Origin` and the token, as the browser does.

## Domain entities (CLAUDE.md §3 vocabulary)

Hospital (time zone), Appointment (starts_at, status), Admin (actor). No Patient or
Notification touched.

## Blast radius

- Admin hospital edit form only. The create form is unaffected (no record, no warning).
- Existing hospital-edit tests save a zone change on hospitals without upcoming appointments,
  so they keep 303. The orchestrator's full suite run confirms it.
- Page layout: see `## Layout`. The form's fields and buttons stay where they are on the
  unwarned page; the warned page adds one notice above the fields and a longer label.

## What I will not do

- No notification or email to patients.
- No change to `time_zone_note`, the save use case, or the audit entry.
- No new confirmation page or template. The existing form carries the confirmation.
- No general "warnings" abstraction; a second caller would justify one.
- No change to `drlibre-specs.md` or to `doc/backlog.md` questions.
- No refactor of `_form`'s argument count (eight after the kwarg). Noted for a later refactor,
  not in this slice.

## Open points and known gaps

- The count is read before the save, outside its transaction. An appointment booked between
  the warning and the confirmed save is not counted. Stated, not fixed here.
- Berlin to Paris shows no warning: same wall clock. Intended.
- Two notices show at once on the warning page: the existing note ("moves nothing that is
  stored") and the warning ("will show another local time"). They read as a contradiction to
  an admin. The owner should decide the copy. Not changed here.
- Three upcoming filters now exist (`upcoming_appointment_count`, `upcoming_starts`,
  `upcoming_for_user`). Leaving both is acceptable for one slice.
- `make mutate` covers `scheduling/domain`; the two domain tests may leave a surviving mutant
  in `shifted_starts`. If so, it goes to `mutation-equivalents.txt` only with an explanation,
  or a third domain test is added.

## For the owner

- Whether patients are told about a zone change is still open (`doc/backlog.md`, questions).
  Not decided by this change.
- The copy of the two notices on the warning page (see open points).

## Changes since architect review (verdict `revise`)

Round 1:
1. Hidden version: block 4 now calls `self._form(request, record, typed, {}, int(version),
   time_zone_warning=warning)`, status 200. The first page test asserts
   `name="version" value="1"`.
2. Count assertion: the test asserts the full sentence `1 upcoming appointment will show
   another local time. For example, ...`. The existing `"has 1 upcoming appointment."` string
   comes from `_time_zone_note`, which renders regardless, so it is not used for red.
3. Zone types: the view builds `ZoneInfo(record.time_zone)` and `ZoneInfo(str(values["time_zone"]))`;
   `shifted_starts`, `time_zone_warning` and `written_moment` take `ZoneInfo`.

Round 2:
1. Edge paths untested: added the red test
   `returns_warning_counting_only_future_active_appointments_of_this_hospital_when_time_zone_changes`
   (past, cancelled, other hospital, each with a distinct effect on count and example) and the
   guard `returns_303_without_warning_when_only_past_or_cancelled_appointments_would_shift`.
2. Layout not measured: added `## Layout` with the invariant and its measurement at 375 px
   and 1440 px. The notice sits inside the form (block 5), so it is measured against the form's
   edges.

## Architect review

Round 2, after the round 1 verdict `revise`. The three round 1 reasons are fixed: the hidden
`version` is kept with `int(version)` and asserted; the test asserts the full warning
sentence, not the note's "has 1 upcoming appointment."; the zone types are stated as
`ZoneInfo`.

Checked against the code: `written_moment(moment, zone)` and its format; the filter of
`upcoming_appointment_count` (`ACTIVE_STATUSES`, `starts_at__gt=now`); `RecordFormPage.post`
and `_form`; `form.html` (`{% if version %}`, so version 1 renders); `components/notice.html`
(kind `warning`); `check_time_zone` returns `Success(str)`; `make_clinic()` defaults to
`Europe/Berlin`; `admin_post` sends the `Origin` and the token. The expected strings hold:
2030-01-08 is a Tuesday, and on that date Auckland is NZDT (+13), so 06:00 UTC reads 19:00.
Layering holds: the count is in the use case, the shift is a pure domain function, the
sentence is view formatting, the same split as `_time_zone_note`.

Round 2 reasons for `revise`, both addressed above (`## Changes since architect review`).

Not reasons, for the record:
- `admin_records.py` is 412 lines. CLAUDE.md §5 says files under 300; the gate caps at 500.
  The plan's +15 stays under the gate. The file is already past §5; that is debt for a later
  slice, not this one.
- The note ("moves nothing that is stored") and the warning ("will show another local time")
  read as a contradiction on one page. Owner copy, as the plan says.
- `upcoming_starts` loads every future start to show a count and two examples. Fine at
  current size; a count query plus one `first()` is the alternative if a hospital grows large.

## Architect review, round 3

Checked against the code again: `admin_records.py` is 412 lines; `post` (line 242) has the
`if errors:` and version branches the plan names; `_form` (line 283) takes `problem` as its
last positional, so the kwarg `time_zone_warning` is a clean addition; `_time_zone_note`
already reads `current_request_context().now` and `upcoming_appointment_count` (line 103)
has the filter the plan reuses; `written_moment` uses `zone.key`, so the examples read
`(Europe/Berlin)` and `(Pacific/Auckland)` as the expected strings say; `form.html` renders
the hidden `version` for 1 (`{% if version %}`) and `components/notice.html` takes `kind`
and `text`.

Both round 1 reasons are fixed in the plan (page tests for past, cancelled and other-hospital
rows; layout invariant at 375 px and 1440 px). Round 2 found nothing new that blocks.

Remaining notes, not reasons:
- The count query loads every future start to show one count and one example. Acceptable at
  current size (see Open points).
- `_form` will carry eight parameters; §5 asks for about three. The plan defers it, which is
  the right call for a one-line slice.
- The warning page shows two notices that disagree in tone. Owner copy, already listed.
