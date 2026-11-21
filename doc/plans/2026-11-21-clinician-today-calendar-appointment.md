# Plan: task 16, clinician workspace (today, calendar, appointment)

One sentence: server-rendered clinician pages over thin read loaders, the task 08 use cases
for every change, and one new use case that stores clinical notes in their own table.

## Findings that shape the plan

- `Appointment.clinical_notes` exists (CharField 5000) on the appointment row. Anything that
  loads or serialises an Appointment (API mapper, FHIR layer, emails, admin loaders) can
  touch it. "Saved separately" is not met by keeping it there. **Decision for the architect:**
  new table `ClinicalNote` (one row per appointment), and drop the `Appointment` column.
  Nothing writes the column in product code today; only builders and two planted-note tests
  reference it (retargeted, see tests). Fallback if rejected: keep the column, `defer()` it
  everywhere; weaker, not recommended.
- `reschedule_appointment`, `change_status`, `cancel_appointment` already guard the record
  (clinician own, admin any), audit and notify. Staff are not bound by 5.3 there. Reuse as is.
- `week_of_slots` + `booking_times.week_strip` + `components/week_strip.html` already give
  the week strip with free slots for one clinician and type. Reuse.
- `render_page` already sets never-cache headers on every page response. Pages go through it.
- CSP: `style-src 'self'` (no inline style, no nonce).

## Focal point

`scheduling/use_cases/clinical_notes.py` (new use case) and the appointment page that hosts
every action. Everything else is read and format.

## Blocks, one sentence each

Domain (pure, mutated):
- `domain/workspace_day.py`: local day bounds in the hospital zone (DST-safe), grouping
  appointments by local hour, tile counts (active, cancelled, completed, no-show).
- `domain/staff_actions.py`: which of check in, complete, no-show, cancel, reschedule section
  5.6 allows for a status (built on `can_transition` and `RESCHEDULABLE_STATUSES`).
- `domain/calendar_grid.py`: a start and end to a 30 minute row index and span in the
  07:00 to 19:00 grid in the hospital zone; clamps; tells what lies outside the grid.
- `domain/clinical_note_rules.py`: a note is at most 5000 characters after trimming; returns
  a `Failure.invalid_input` value, never raises.
- `domain/audit_labels.py`: audit action name to a plain label for the history; unknown action
  falls back to the raw action.

Models:
- `ClinicalNote(Versioned)`: `appointment` OneToOne PROTECT, `clinical_notes` text up to 5000
  (check constraint). `fhir_not_exposed` states why (private to the clinician). Migration
  `0011`: create table, drop `Appointment.clinical_notes`. Regenerate `doc/data-model.md`.

Use cases:
- `use_cases/clinical_notes.py`: `save_clinical_note(appointment_id, text, actor)` locks the
  appointment, record rule (only that appointment's clinician; admin and patient get
  forbidden, missing gets not_found), validates, upserts, writes one audit entry in the same
  transaction: action `appointment.note_save`, entity `Appointment`, metadata ids plus
  `changed_fields=["clinical_notes"]`, no content. `read_clinical_note(appointment_id, actor)`
  with the same rule. No list and no delete: the spec has neither, and a clinical record is
  not deleted by this task. Say so in the module docstring.
- `use_cases/clinician_agenda.py`: read loaders scoped by `clinician.user == actor`:
  `day_agenda(actor, day)`, `week_calendar(actor, week_start)` (active appointments and
  TimeOff overlapping the week), `next_free_slot(actor)`.
- `next_free_slot`: calls `find_free_slots` for the shortest active AppointmentType of the
  clinician's department, window now to now + 14 days; tile says "None in 14 days" when empty.
- `use_cases/clinician_appointment.py`: `own_appointment_of_clinician(id, actor)` through
  `guard_record` (missing: not_found, someone else's: forbidden) and
  `appointment_history(appointment_id)`: AuditLogEntry with entity `Appointment` and that id,
  oldest first, actor name from the user, never metadata beyond the action.

Views (thin, `PageView`, `allowed_roles={CLINICIAN}`, new files under `views/pages/`):
- `clinician_today.py`: `/clinician/?date=YYYY-MM-DD` (replaces the empty home; bad date
  falls back to today in the hospital zone). Status actions are POST forms (CSRF) to
  `/clinician/appointments/<id>/check-in|complete|no-show`, answering 303 to a fixed
  target chosen from an enum (`today` or `appointment`), never from a URL in the request.
- `clinician_calendar.py`: `/clinician/calendar?week=`, previous and next week.
- `clinician_appointment.py`: `/clinician/appointments/<id>` page; `.../cancel` GET form and
  POST (reason required, trimmed, max `CANCELLATION_REASON_MAXIMUM`, same checks as the
  patient page); `.../notes` POST; `.../reschedule` (week strip) and `.../reschedule/review`
  GET and POST. Other clinician's appointment: 403 page whose only content is "Not your
  appointment" and a link to Today; missing: `Http404`.
- `clinician_colours.py`: `/clinician/type-colours.css`, see "Colour".
- `clinician_refusal.py`: a refused use case result as the existing `booking/refused.html`
  with `refusal_for` message (invalid transition: the existing status-changed sentence) and a
  way forward link back to the appointment or the week strip. Staff-only wording is not
  needed: staff are not bound by 5.3, so what they see is conflicts, availability, status.
  Small edit to `patient_refusal.change_refused_page`: a `back_action` parameter defaulting
  to today's `LIST_ACTION`. `patient_reschedule._asked_start` becomes public `asked_start`
  (rename, same module callers) so the staff review page reuses it.

Templates and CSS:
- `components/workspace_nav.html` (one nav, `aria-label="Clinician workspace"`,
  `aria-current="page"` on the current section). Sections: Today, Calendar link; Availability,
  Time off, Patients, Rooms listed as plain text "Soon" items, not links (task 17 makes them
  links; no dead links). Modelled on `portal_nav.html`; CSS shared with `.portal-nav`.
- New components, added to `/style`: `stat_tile.html`, `agenda_row.html`, `calendar_week.html`,
  `history_list.html`. Reuse `badge.html` (status words and icons), `notice.html`,
  `field.html`, `error_summary.html`, `week_strip.html`, `empty_state.html`, `refused.html`.
- Pages: `clinician/today.html`, `calendar.html`, `appointment.html`, `cancel.html`,
  `reschedule_times.html`, `reschedule_review.html`, `not_yours.html`. Headings h1 then h2.
- CSS in `static/css/components.css` (or a new `workspace.css` linked from `base.html` only
  if components.css would exceed 300 lines): tiles, agenda, grid. Read
  `impeccable/reference/craft-floor.md`, `PRODUCT.md`, `DESIGN.md` before the edit.

## Colour: how a type's colour reaches the page

The colour is stored as `#rrggbb` (DB regex check). Inline style is forbidden. A clinician-only
view serves `/clinician/type-colours.css` (`text/css`, same origin, allowed by `style-src
'self'`): one rule per active AppointmentType of the clinician's department,
`.type-colour--<uuid hex> { --type-colour: #rrggbb; }`. Each calendar block carries the class
`type-colour--<hex>`; CSS draws a 6px left border and a small swatch from `var(--type-colour)`.
Text stays on the neutral surface token, so contrast never depends on the stored colour.
The emitter re-checks each value against `^#[0-9a-f]{6}$` and each class name against hex
before writing (no CSS injection from data); a bad row is skipped, never raised. Linked with
`<link rel="stylesheet">` in the calendar page head block only. Response is
`Cache-Control: private, max-age=300`. It holds no patient data. A type that is not in the file
(created after cache) falls back to the neutral border.

## Calendar grid reads as a list

Markup is an `<ol>` of seven days, each an `<ol>` of events and time off, in time order, each
item text like "09:30 to 10:00, Check-up, Ada Patient, Room 3" plus the status badge. That is
the screen reader and the 375 px view (stacked by day, no grid). From the wide breakpoint CSS
turns each day list into a grid column with `display: grid` and the 24 row classes
`.cal-row-1..24` and `.cal-span-1..24` (static classes from `calendar_grid`, no inline style),
with the hour labels in a decorative column marked `aria-hidden`. Time off blocks have the word
"Time off" and the reason. Items outside 07:00 to 19:00 are shown in an "Outside 07:00 to
19:00" list under the day, so none is hidden. Block names type and patient in text.

## Files to touch, in order

1. `scheduling/domain/` five new modules and their tests.
2. `scheduling/models/booking.py` (ClinicalNote, drop column), `models/__init__.py`,
   `models/builders.py` (builder for ClinicalNote, drop the column lambda), migration
   `0011`, `doc/data-model.md`; retarget `test_value_rules.py` rows.
3. `scheduling/use_cases/clinical_notes.py`, `clinician_agenda.py`, `clinician_appointment.py`.
4. `scheduling/views/pages/clinician_*.py`, `drlibre/urls.py`, `homes.py` (remove the empty
   `ClinicianWorkspace`), `patient_refusal.py`, `patient_reschedule.py` (the two small edits).
5. Templates, components, CSS, `style.html`.
6. `mutation-equivalents.txt` only if a survivor is explained.
7. `doc/backlog.md` is the orchestrator's.

Deliberately not touched: availability, time off CRUD, patients and rooms pages (task 17);
the API and FHIR layers (notes must stay absent from them; tests prove it); admin console;
`appointment_changes.py` and `placement*` (reused as is); JS (none added); settings and CSP.

## Invariants and blast radius

- No double booking: reschedule goes through `replace_placement` and its locks and DB
  exclusion constraints; no new write path to times.
- Authorization server-side: clinician identity from the session; every loader filters by
  `clinician.user_id == actor.pk`; use cases check again. Never from the payload or URL.
- Audit append-only and in the same transaction: note save writes through `record_audit`;
  `AuditMetadata` has no free-text slot, so a note cannot enter it by construction.
- Notes absent from: API bodies, FHIR, notifications, emails, audit metadata, log lines,
  patient pages, admin pages, the type-colour CSS, error pages.
- Blast radius: one migration (new table, dropped unused column); `clinician/` home route
  changes from placeholder to Today; two tiny edits in patient pages (parameter, rename).
  Patient flows must stay green.

## Failing tests first (`returns_X_when_Y`)

Domain:
- `returns_bounds_of_local_day_when_zone_is_berlin` (23 h day on the March clock change,
  25 h in October); `groups_by_local_hour_when_zone_is_not_utc`.
- `counts_cancelled_apart_from_active_when_day_has_both`; completed and no-show counted.
- `allows_check_in_no_show_cancel_reschedule_when_booked`; `allows_only_complete_and_cancel_when_checked_in`;
  `allows_nothing_when_completed_cancelled_or_no_show`.
- `places_block_at_row_5_span_3_when_starts_0930_ends_1100`; `returns_outside_grid_when_starts_0630`;
  `clamps_span_when_ends_after_1900`.
- `refuses_note_when_5001_characters`; `accepts_note_when_5000_characters`; empty note clears it.

Use cases (real PostgreSQL):
- `saves_note_and_audits_in_same_transaction_when_own_appointment`: row exists, one audit entry,
  `changed_fields == ["clinical_notes"]`, metadata JSON does not contain the planted text.
- `rolls_back_note_when_audit_write_fails`.
- `returns_forbidden_when_admin_saves_or_reads_note`, same for another clinician and the patient;
  `returns_not_found_when_appointment_missing`.
- Planted note proofs, each with a distinctive string: not in the patient's API list and detail
  bodies, FHIR bodies if present, notification rows, outbox emails, any `AuditLogEntry.metadata`,
  captured log output (`caplog` plus the JSON logger), the patient's pages, `/admin-console/`, the type-colour CSS; present on the clinician's own appointment page.
- `returns_only_own_appointments_when_two_clinicians_share_a_day`; agenda in hospital zone near midnight UTC.
- `returns_next_free_slot_when_one_exists`; `returns_none_when_no_slot_in_14_days`.
- `returns_history_oldest_first_with_actor_name_when_appointment_has_entries`.

Pages (rendered HTML):
- Today: tiles with exact counts (3 active, 1 cancelled, 1 completed, 1 no-show, next slot
  time); rows grouped under hour headings; each row shows patient, type, room, status badge
  text and exactly the forms the status allows; prev, next, today links with `?date=`.
- Calendar: week has 7 day lists; block text names type and patient; class
  `type-colour--<hex>` present, no `style=` attribute anywhere; time off block present;
  cancelled appointment absent; previous and next links.
- `serves_css_rule_per_type_when_signed_in_clinician`, `skips_row_when_colour_is_malformed`,
  403 for patient and anonymous redirect to sign in.
- Appointment: name, phone, age, time, type, room, reason, status; history rows in order with
  time, label, actor; note textarea with `maxlength=5000` and a label; cancel form requires
  reason (422 with error summary and field error when blank, 422 when too long).
- `shows_not_your_appointment_and_nothing_else_when_other_clinician` (planted name, phone,
  reason, note absent from the body; status 403); `answers_404_when_appointment_missing`.
- Refusals: reschedule to a taken slot shows message plus way-forward link; status changed
  since page load shows the status-changed sentence with 409; shown to a clinician who is not
  bound by 5.3 with the use case's message.
- Navigation: one `nav`, current section `aria-current="page"` on Today, on Calendar, and on
  appointment pages the section it came from; task 17 sections named, not links.
- Every page response has `Cache-Control` with `no-store`; every page has one `h1`, no
  heading level skipped, `lang`, labelled controls, no inline `style`, `<script>` only from
  `/static/`.
- Every form (status actions, cancel, notes, reschedule confirm) posted with `browser_post`:
  200/303 with the Origin set; 403 with another Origin, `null` Origin, and without the token.
- The pages work without JavaScript: each action is a plain form post and a redirect.

## Trust boundaries

- Browser to server: path ids (`<uuid:>` converter), `date`, `week`, `starts_at` (parsed by
  existing `week_from`, `instant_from`; bad value falls back or 404), `reason` and note text
  (trimmed, length-checked in domain and by `validate_body`), status action name fixed by
  URL, return target an enum. All POST: CSRF plus `Origin` enforced by Django.
- Session to identity: `PageView` resolves the cookie; role Clinician only; the appointment
  record rule decides ownership; the use case repeats it.
- Server to database: ORM only. Note text is stored as given, escaped on output by the
  template engine; never logged; the request log carries path and correlation id only (ids,
  not names). The `reason` and note go in POST bodies, never URLs.
- Server to browser: type colour validated before it enters CSS.

## Vocabulary used

Clinician (public word "provider" only on patient pages), ClinicianProfile, Appointment,
AppointmentType (colour), Room, Hospital (time zone), TimeOff, AuditLogEntry, User (patient),
Notification (untouched, proves absence), plus new `ClinicalNote` (add to the vocabulary list in
`doc/data-model.md`, not to CLAUDE.md).

## What I will not do

No JavaScript, no framework, no new dependency, no caching layer, no generic calendar
library, no new abstraction without a second caller (the staff refusal and review pages are
the second caller of the patient ones, hence the two small edits). No encryption of notes
(open point 1 of ADR 0002 stays open: note it in the task retro). No note history or delete.
No admin view of notes. No task 17 pages. No change to the seed unless the demo clinician has
no appointment today in the hospital zone; if so, a note to the orchestrator, not a seed rewrite.

## Not verified here

No browser: focus order, real colour contrast, 375 px and 1440 px layout are the
orchestrator's Chrome check; the server proves markup, headers and text only.

## Architect review

Verdict: approve.

- Ladder: new table for notes is justified by "saved separately" and "not in any API body"; dropping the unused column is the right call (grep: only migration 0001, builders and two tests touch it). Five domain modules is a lot but each is pure and mutation-tested; acceptable. The `refusal`/`asked_start` edits have a second caller. OK.
- Security: server-side ownership twice, enum redirect targets, CSS value validation, notes absent from audit by construction, planted-note tests for every "not". Covered.
- Spec conflict to record, not block: `drlibre-specs.md` §15.3 says clinical notes map to FHIR `Appointment.comment` for the clinician. The task says "not in any API body". Task wins; builder must not add a FHIR mapping, and the retro should flag §15.3 for an owner decision.
- Non-blocking: (a) the migration must move any existing `clinical_notes` values into `ClinicalNote` before dropping the column (data-preserving, even if the seed holds none); (b) `save_clinical_note` audit action `appointment.note_save` should match the existing action naming in `record_audit`; (c) add a test that the 403 "Not your appointment" page does not leak through the correlation-id/error page; (d) `homes.py` removal needs a check that the sign-in redirect for clinicians lands on the new Today.
