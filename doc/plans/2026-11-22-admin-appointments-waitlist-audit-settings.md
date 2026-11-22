# Plan: task 20, admin console for appointments, waitlist, audit log and settings, plus carried fixes 14 to 16

Date 2026-11-22. Spec section 10 (+4, 5.2 to 5.8, 12.3). Impeccable Operate mode: build stages read `PRODUCT.md`,
`DESIGN.md`, the skill and its `reference/craft-floor.md` before any UI edit. No inline script or style; every step
is a link or a plain form; only existing components (list, pagination, badge, history_list, week_strip, field,
select, notice, empty_state, error_summary).

## Focal point

The task 18/19 admin flow (nav, `admin/list.html`, pagination, `admin_support` test clients, role test) gains four
sections, and every write is an existing use case. New code is pages, three read use cases (appointment list,
audit list, patient search), one hardening of the waitlist use case, and an index migration.

One sentence: *four more admin sections that call the use cases of tasks 08 and 09 unchanged, plus a read-only audit
list that stays fast on a log that only grows.*

## Decisions the task asks to state

**Deep pages of the audit log (item 10).** Ordering is `(created_at desc, id desc)`. Migration adds indexes
`(created_at, id)`, `(actor, created_at, id)`, `(entity_type, created_at, id)` (indexes do not touch the append-only
trigger, which refuses update, delete and truncate only). The list runs two queries a page: (1) count with the
filters; (2) the page by *deferred join*: `values_list("pk")` ordered and sliced `[offset:offset+20]` (an index-only
walk, no heap rows and no `metadata` JSON read for the skipped rows), then one `filter(pk__in=ids)` with
`select_related("actor")` for the 20 rows, re-ordered in Python by the id list. A page deep in the log costs an index
walk, not a table read. Page number is clamped to the last page by the existing pure `page_bounds`. Test: insert
50 000 rows by one SQL `INSERT ... generate_series` (bulk_create would eat the 30 s suite budget), request page 1, a
middle page and the last page, with an actor filter and with a date range; assert query count 2 (+ session) and
`EXPLAIN` of the page query uses an index (no `Seq Scan` on the log with the flag `enable_seqscan` off is not a proof,
so the test asserts the plan text contains `Index` for the unfiltered, actor and entity cases), and wall time < 1 s
per request. Metadata is never selected for the list (`only(...)` of the shown columns).

**Appointment date range.** Address `?from=YYYY-MM-DD&to=YYYY-MM-DD` are calendar days. Hospitals have their own
zones, so the filter is one `Q` per distinct hospital zone (`department__hospital__time_zone=z` and `starts_at` in
that zone's local-day bounds); few zones, one query. Unusable value (bad date, from after to, unknown id, unknown
status or source, huge page) falls back to "no filter" / page 1, never an error page (section 4). Filters are GET
parameters of the list address; pagination links carry them.

**Offer stale and manual offer (item 8).**
- `waitlist_expiry._is_taken` becomes `slot_is_taken(offered, patient_id)`: any active appointment overlapping the
  offered window, other than the offered appointment itself, for the clinician, **the offered room (when it has one)**
  or **the entry's patient**. No new overlap code: reuse `placement_checks.find_conflicts(clinician, patient, room, window, ignoring_appointment_id)` which already
  returns the resources in conflict.
- `_first_free_cancelled_slot` loads candidates ordered `(starts_at, id)` in the database, already limited to the
  entry's type, preferred clinician, window and future, with `NOT EXISTS` an `OFFERED` entry on the slot, and walks
  them lazily with `.iterator()`; the first one for which `find_conflicts(...)` (clinician, room, patient) is empty
  and the clinician is free by `free_clinician_ids` wins. It stops there (no list of every future slot). A cap
  `MAX_SLOTS_CHECKED = 100` keeps one click bounded; reaching it counts as "no slot fits".
- The refusal says why, by the first reason found while walking, in this order of precedence: no cancelled slot of
  the type in the window (existing `no_clinician_available`, page text "No cancelled time of this
  type falls inside the window."); every such slot is held by another entry (`conflict`, resource `offer`, "Another
  entry already holds that offer."); every remaining one has the clinician, room or patient busy (`conflict`
  with the resources, "The clinician is no longer free then." / "...room..." / "...patient has another appointment
  then."). Pure function `offer_refusal(counts) -> reason` in `domain/waitlist_rules.py`.
- The auto offer on cancel (`offer_freed_slot`) is unchanged.

**Admin booking (item 3).** Reuse `place_appointment` (admin path already names patient and clinician, source
`STAFF`, no online-only rule, no lead time). Wizard: patient search (`?q=`, name or email, active patients, 20
rows, never lists everyone without a query) -> type (every active type of active hospital, grouped hospital then
department, "not bookable online" marked in words) -> provider (no "first available") -> week strip -> review ->
POST. Patient id travels in the address as a UUID and is re-checked as an active patient in the use case, never
trusted. Slots come from `week_of_slots(..., online_only=False)`; the strip stays the one component. Room stays
automatic (spec 5.2 step 5); no room picker (not asked).

**Admin reschedule (item 4).** Reuse the clinician reschedule pages' pattern (`week_of_slots`, `week_strip`,
`reschedule_appointment`); only the path prefix and `allowed_roles` differ. The two pages are generalised into a
shared base taking the appointment path and the role, not copied. Actions on the show page come from
`staff_actions_for(status)`, so only `BOOKED`/`CONFIRMED` show "Reschedule".

**Refusals (item 5).** One admin function maps a `Failure` to `{message, way forward}` (link back to the record, the
week strip, or the list), reusing `patient_refusal.change_refused_page` where its text fits and adding messages for
`conflict` (named resources), `no_room_available`, `has_dependents`, `invalid_transition`, `rule_violation`.

**Never a clinical note (item 2).** The show page reads `Appointment` and its audit history only; it does not
import `ClinicalNote` or `clinical_notes`. Test: a note body saved by the clinician is absent from the HTML and no
query touches the notes table (query log).

**Plain words for audit actions (item 12).** `audit_labels.py` is complete for every action recorded in the code:
test greps every `AuditEvent("…"` / `_audit("…"`/`f"user.{verb}"` literal in `use_cases/` (the action set is the
test's own: collect from `record_audit` calls by running the writers is too slow) and asserts each is a key of
`AUDIT_LABELS`; missing words are added there. List column shows `Label (code)`.

**Settings (item 11).** Policy constants are read from where the rules read them (`domain/booking_rules.py`:
lead 120 min, cancellation 24 h, 3 open bookings); the page shows `LEAD_MINUTES` etc., not literals. If a rule only
holds them inside a function, name them as module constants in the same file first (one-line change, domain stays
pure) and let the rule use the same name. Button: POST `/admin-console/settings/reminders` -> `send_reminders(actor)`
-> redirect (303) to settings with `?reminders=<n>`; page says "N reminders created" (0 is said too; bad value
ignored). The same use case the API job calls (`views/jobs.py`).

**Never cached.** All pages go through `render_page`, which adds the never-cache headers; a test asserts
`Cache-Control: no-store`/`private` header on every new GET route.

## Carried fixes

**14 `delete_user`.** Wrap the three clean-up deletes and the final delete in one inner `transaction.atomic()`
(savepoint). On `ProtectedError`/`IntegrityError` the savepoint rolls back, sessions, links and notifications are
restored, then the failure is returned. Test: patch `admin_users.user_dependents` so that after its first (empty)
answer an appointment of the user is inserted; call `delete_user`; assert `has_dependents`, the user, their session,
sign-in link and notification all still exist, and no audit entry.

**15 seed clean-up.** `catalogue` already has the five new codes. `writer.py` gets `LEGACY_SPECIALTY_CODES` = the five
`demo-<code>` strings the seed itself used (derived: `f"demo-{code}"` for `catalogue.SPECIALTIES`, no `startswith`).
One step per code: upsert the new row first; if the legacy row exists, point its clinicians at the new row
(`ClinicianProfile.objects.filter(specialty=legacy).update(specialty=new)`), then delete the legacy row (now
unreferenced). Rename-in-place goes (the move covers it, and covers the "both exist" case). Tests: admin-made
`demo-orthopaedics-extra` with no clinician stays; legacy-only moves; both-exist with clinicians on both leaves one
set and no clinician lost; second seed run no change.

**16 one submission, every error.** The cause is in the form view: `parse_form` errors return before the use case
sees the values, so cross-field rules (room of another department) wait for round two. Add a read-only
`admin_clinicians.reference_messages(values, record_id)` (the checks `_reference_messages` and `_move_messages` already
make, no write, no lock) and have the form page merge its messages into the parse errors with `setdefault` before
re-rendering, for kind `clinician`. Same shape for the new forms: each parses every field, collects all messages
into one `errors` dict and renders the error summary once (cancel reason, waitlist add: type, window order,
window passed, preferred clinician of another department, patient). Test: weight 0 + room of another department
shows both messages and both summary links.

## Blocks, one sentence each

1. `domain/audit_labels.py`: add missing action words; `domain/audit_filters.py` (new, pure): parse the audit address
   (actor text, entity type among `ENTITY_TYPES`, from/to days) into a value, fallback per field; plain-words helper
   `action_text(code) -> "Label (code)"`.
2. `domain/admin_list_filters.py` (new, pure): parse appointment and waitlist addresses (`from`, `to`, `department`,
   `clinician`, `status`, `source`, `page`) with fallback; `domain/waitlist_rules.py`: `offer_refusal`.
3. `domain/booking_rules.py`: name the three constants if not named (see settings).
4. `models` + migration `0015_audit_log_indexes`: three indexes on `AuditLogEntry` (index names <= 30 chars).
5. `use_cases/admin_appointments.py` (new): `list_appointments_for_admin(filters, page)` (count, rows with
   `select_related` type/department/hospital/clinician user/patient, 2 queries, order `starts_at desc, pk desc`);
   `appointment_for_admin(id)` with history from `AuditLogEntry` of that entity (labels only, no metadata);
   `search_patients(text)`; `bookable_types_for_admin()`.
6. `use_cases/admin_audit.py` (new): `list_audit(filters, page)` as above.
7. `use_cases/admin_waitlist.py` (new): `list_waitlist(status, page)` oldest first (`created_at, pk`), rows with patient,
   type, preferred clinician, window in the hospital zone, offered slot; add-to-waitlist calls `join_waitlist`
   (admin names the patient: already supported).
8. `use_cases/waitlist.py` + `waitlist_expiry.py`: item 8 above. `use_cases/admin_users.py`: item 14.
9. `views/pages/admin_appointments.py`, `admin_appointment_book.py`, `admin_appointment_reschedule.py`,
   `admin_waitlist.py`, `admin_audit.py`, `admin_settings.py` (new; each < 300 lines, one `*_routes()` list joined in
   `drlibre/urls.py`), `admin_refusal.py` (item 5), `admin_filters.py` (select option lists, hrefs carrying filters).
   Pages parse the address, call a use case, format; no rule in a view.
10. Templates `admin/appointments.html`, `appointment.html`, `book_patient.html`, `book_service.html`,
   `book_provider.html`, `book_times.html`, `book_review.html`, `appointment_cancel.html`,
   `reschedule_times.html`, `reschedule_review.html`, `waitlist.html`, `waitlist_add.html`, `audit.html`,
   `settings.html`, `refused.html`; `components/admin_nav.html`: the four disabled items become links with
   `aria-current`. Filter forms are `method="get"` with labels, a "Filter" button and a "Clear" link; times carry the
   zone name; tables have captions and header scopes (WCAG 2.2 AA; 375 px: the list collapses as the existing list
   component does, no new breakpoint rules unless a test of the CSS says the column overflows).
11. `use_cases/admin_clinicians.py` + `views/pages/admin_records.py`: item 16. `demo_seed/writer.py`: item 15.
12. Docs: `doc/backlog.md` row is the orchestrator's.

## Files to touch, in order

1. `domain/audit_labels.py`, `audit_filters.py`, `admin_list_filters.py`, `waitlist_rules.py`, `booking_rules.py`
   + a `test_*.py` beside each
2. `models/audit.py`, `migrations/0015_*.py`
3. `use_cases/waitlist.py`, `waitlist_expiry.py`, `admin_users.py`, `admin_clinicians.py`,
   `admin_appointments.py`, `admin_audit.py`, `admin_waitlist.py` + tests
4. `views/pages/admin_*.py`, `drlibre/urls.py`, `clinician_reschedule.py` (base extracted), `admin_records.py`
5. Templates, `components/admin_nav.html`, `static/css/components.css` only if a new element lacks a rule
6. `demo_seed/writer.py` + seed tests
7. Tests: page tests per section, `test_admin_access.py` (route counts updated: the new routes join its URL-derived
   list, so the role test and the POST test cover them without a hand list), `test_hostile_input.py` (new routes
   join its parametrised paths), `test_unique_ids.py` (new pages), audit performance test.

Deliberately not touched: `placement*.py` booking rules, free-slot and engine domain code, CSV export (task 21),
dashboard, API and FHIR views, patient and clinician pages, models other than the index meta, the append-only trigger,
`offer_freed_slot` (auto offer).

## Invariants and blast radius

- No double booking: admin booking and reschedule go only through `place_appointment` / `reschedule_appointment`
  (database exclusion constraints stay the backstop); accept goes through `place_appointment`. Stale-offer and manual
  offer now check clinician, room and patient.
- Authorization on the server: `allowed_roles = {ADMIN}` on every page and `actor.role` checked again in use cases
  (`offer_waitlist_entry` already, `join_waitlist` through `authorize_join`, status changes through
  `may_change_status`). Patient id, appointment id and entry id come from the address and are looked up; the actor is
  always the session user.
- Audit log append-only: no route, form or function writes or edits entries; the list is `SELECT` only; migration adds
  indexes only. Every write is audited by its use case in its transaction (existing); `reminder.run` only when
  count > 0 (existing), page says 0 plainly.
- Audit metadata never holds names, emails or reasons: the list does not show metadata at all; the cancel reason goes
  to `cancellation_reason` (as today), not to audit.
- Blast radius: nav template (every admin page), `waitlist_expiry` (job, tests of task 09), `admin_users.delete_user`,
  `admin_records` form page (all record kinds: tests of tasks 18, 19), seed writer.

## Failing tests to write first (`returns_X_when_Y`)

Domain
- `returns_default_filters_when_the_address_holds_unusable_values` (bad date, from after to, unknown status/source,
  `page=-3`, `page=abc`, non-uuid ids -> no filter, page 1).
- `returns_no_slot_reason_first_when_nothing_inside_the_window`, `returns_held_reason_when_every_slot_is_held`,
  `returns_busy_resources_when_slots_exist_but_are_taken` (`offer_refusal`).
- `returns_label_and_code_for_every_recorded_audit_action`.

Use cases
- `returns_offered_when_first_slot_clinician_busy_but_second_fits` (loads the first slot that fits; an earlier busy one
  is skipped).
- `returns_conflict_room_when_the_cancelled_slots_room_is_taken`; `..._patient_when_the_entry_patient_has_another_appointment`.
- `returns_released_when_offered_slot_room_or_patient_is_taken` (stale detection by room and by patient).
- `returns_refused_with_reason_when_another_entry_holds_the_offer`; `returns_forbidden_when_non_admin_offers`.
- `returns_has_dependents_and_keeps_sessions_links_notifications_when_a_dependent_appears_before_the_delete` (item 14).
- `returns_twenty_rows_newest_first_with_total_when_listing_appointments`; filters: `by_department`, `by_clinician`,
  `by_status`, `by_source`, `by_date_range_in_the_hospital_zone` (a 23:30 local start on the `to` day included;
  two hospitals in two zones).
- `returns_two_queries_and_no_metadata_when_listing_the_audit_log`; `returns_last_page_when_page_is_past_the_end`;
  the 50 000-row test (page 1, middle, last; actor, entity type and date filters; < 1 s each; plan shows an index).
- `returns_patients_matching_name_or_email_when_searching` (only active patients, none on empty query).
- `returns_staff_appointment_when_admin_books_a_type_not_bookable_online`; `returns_conflict_when_the_slot_is_taken`.
- `returns_count_of_reminders_created_when_running_the_job_twice` (second 0).

Pages (rendered HTML, browser-sent forms: CSRF enforced, `Origin` set, cookie, via `admin_post`)
- Appointments list: 20 rows, count text, zone named on each time, filters survive in the pagination links, bad
  filter values give 200 with the default list, filter form has labelled fields, no inline script/style.
- Show: patient, clinician, type, room, time, status, source, reason, history; actions exactly per status; a clinical
  note's text is absent; check-in, complete, no-show, cancel with empty reason re-renders with the error (422) and
  every error at once, with reason cancels and shows the new status.
- Book wizard: patient search -> type list includes a not-bookable-online type -> provider list has no "first
  available" -> times -> review POST creates a `STAFF` appointment and redirects (303) to it; a taken slot shows the
  conflict message with a link back to the week.
- Reschedule: only `BOOKED`/`CONFIRMED` offer it; POST moves it; refusal shows message and way forward; `CANCELLED`
  answers 409 page.
- Waitlist: list oldest first with status filter; add form (all errors in one submission: no patient, no type,
  latest before earliest); offer button shows the offered slot or the three refusal reasons; accept for the patient
  creates the appointment and the entry is `BOOKED`.
- Audit: list shows time, actor, label with code, entity, correlation id; no metadata text; no form but the filter
  (`method=get`); POST/PUT/PATCH/DELETE to the route answers 405; filters by actor text, entity type, dates.
- Settings: shows 120, 24, 3 from the constants (test patches the constant and sees the page change); the button
  POST reports the created count; GET on the action route answers 405.
- Every new GET page sends no-store headers; every new route is in the role test (visitor redirected to sign in,
  patient and clinician 403 on GET and POST) and the hostile-input test (null byte, 10 kB values, malformed ids, SQL
  text, repeated parameters: never 500); no page repeats an element id.
- `returns_every_error_when_weight_and_room_are_both_wrong` (item 16).
- Seed tests of item 15.

Red proofs: each test is run first against the unchanged code and must fail for the stated reason; mutation:
`make mutate` covers `domain/` (new pure modules get tests that kill their mutants; survivors need an entry in
`mutation-equivalents.txt` with a reason).

## Trust boundaries

| Boundary | Input | Validation | Authorization |
| --- | --- | --- | --- |
| Page addresses | filters, page, `q`, week, starts_at | pure parsers with fallback; text trimmed, null bytes dropped, length capped (100) | admin role from session |
| Form posts | cancel reason, waitlist fields, patient/type/clinician ids, `starts_at` | parsed into typed values (UUID, aware datetime in the hospital zone, length caps); every error collected | CSRF + Origin enforced; admin from session; ids re-read in the use case |
| Use cases | appointment/entry/patient ids | looked up; inactive or missing -> `not_found` | role re-checked, record rules (`guard_record`) |
| Audit list | actor text, entity type, dates | text is a `icontains` parameter (ORM), entity type must be in `ENTITY_TYPES` | admin only; read-only |

Never logged or put in an address: reasons, notes, birth dates; patient names do not enter the audit list (actor is
the user shown to admins already) and the `q` for patient search is in the address (names/emails in a GET query of an
admin page) -> use POST? No: search is a GET form by design (reload, share); the page sends `Referrer-Policy:
same-origin` as every page does, and access logs of this app do not log query strings (verify in
`json_logging.py`; if they do, search becomes a POST form that redirects to the list with an id only). Builder checks
first, in a test.

## Domain entities (CLAUDE.md vocabulary)

Appointment, AppointmentType, ClinicianProfile (Clinician), Patient (User), Admin, Department, Hospital (time zone),
Room, WaitlistEntry, Notification (reminders), AuditLogEntry, AvailabilityRule (through free slots), Specialty (seed).
No new entity, no new table, one migration (indexes).

## What I will not do

No CSV export (task 21), no dashboard, no new dependency, no JavaScript, no new CSS framework, no room picker, no
"first available" for staff, no new failure codes, no generic admin-page framework beyond the shared reschedule base
and the filter parsers, no change of the automatic offer, no keyset-pagination scheme (deferred join is enough for the
size the task states; revisit when the count query itself is the cost), no editing of the settings constants.
Risk named: `count()` on a very large filtered log is O(matching rows) even index-only; accepted, spec requires the
total.

## Architect review

Verdict: approve. Every item of the task (1 to 16) maps to a block, a first failing test and an invariant. The change sits at the right layers: pure parsers in domain, three read use cases, thin pages, one index migration. There is no new dependency and no speculative framework. The deferred-join answer to item 10 is concrete and testable.

Conditions for the builder (not reasons to revise):
1. Patient search `q` (name or email) and the audit `actor` text (email) end up in GET addresses. §11 says no sensitive data in URLs, and an access-log check does not cover browser history or the Referrer header. Decide in the red stage and write it down. Preferred: patient search stays GET only if the test proves that logs and the `Referrer-Policy` header hold it. Otherwise it is a POST form that renders results without a redirect (works without JavaScript). For the audit actor filter, prefer a select of users by id over free email text.
2. Prove the stale-offer room and patient checks with tests that fail on the old code (clinician-only overlap), as listed. Keep `find_conflicts` as the single overlap source.
3. The audit-label coverage test greps source literals. Also assert that every action that `record_audit` writes in the existing use case tests has a label, so dynamic names such as `user.{verb}` cannot slip through.
4. Item 14: the savepoint must wrap the exception path. Assert the audit entry is absent as well as the sessions, links and notifications.
5. `waitlist_expiry` is shared with the job of task 09. Keep its existing tests green and name the room and patient cases beside them.
6. Gate sizes: new view files must stay under 300 lines (500 hard cap); split `admin_filters.py` early if needed.
