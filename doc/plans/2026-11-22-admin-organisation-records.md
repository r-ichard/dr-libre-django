# Plan: task 18, admin console for hospitals, specialties, departments, rooms, appointment types

Date 2026-11-22. Spec section 10 (+3.1, 4, 12.3). Impeccable Operate mode: before any UI edit the
build stages read `PRODUCT.md`, `DESIGN.md` and the skill's `reference/craft-floor.md`.

## Focal point

One generic record flow (list, show, form, delete) driven by a per-record spec, so five records cost
one set of pages, one set of use cases and one set of tests, plus a small table of what each adds.

One sentence: *an admin-only, spec-driven CRUD flow where every write is a locked, versioned,
audited use case and delete is decided by one pure domain function.*

## What is shared and what each record adds

Shared (built once):
- Views `scheduling/views/pages/admin_records.py`: `RecordListPage`, `RecordShowPage`,
  `RecordFormPage` (new at `/new`, edit at `/<id>/edit`), `RecordDeletePage`, each `PageView` with
  `allowed_roles={ADMIN}`, parameterised by `as_view(kind=...)`. Routes come from a loop over the kind
  registry in `drlibre/urls.py`: `admin-console/<plural>`, `/new`, `/<uuid:record_id>`,
  `/<uuid:record_id>/edit`, `/<uuid:record_id>/delete`. 25 routes, all POST-capable where forms are.
- Templates `admin/list.html`, `admin/show.html`, `admin/form.html`, `admin/delete.html`; components
  `admin_nav.html` (one nav, `aria-current="page"`), `textarea.html` (new; `field.html` has none),
  detail list `<dl>` styles in `components.css`; both added to `/style`. Reuse `field`, `select`,
  `checkbox`, `error_summary`, `pagination`, `table-wrap`/`table`, `badge`, `notice`, `empty_state`.
- Use cases `use_cases/admin_records.py`: `create_record`, `update_record`, `delete_record`, over
  `RecordSpec` (model, entity type, audit prefix, field names, dependent counters) in
  `use_cases/admin_record_specs.py`; reads (search, 20 per page via existing `paginate`, total,
  counts) in `use_cases/admin_record_reads.py`.
- Domain `domain/record_fields.py` (pure field checks), `domain/delete_dependents.py` (pure delete
  decision), `domain/audit_labels.py` (labels for the 15 new actions).

Each record adds only:
| Record | Adds |
| --- | --- |
| Hospital | address, phone, time zone (known zone), latitude+longitude together, description, active; edit form states "time zone change moves nothing stored, availability read in new zone" with count of upcoming active appointments when > 0 |
| Specialty | name, code, active; show page says which icon: `icon_file_for(code)` vendored or "fallback icon, none vendored for this code" |
| Department | hospital select (required), description |
| Room | department select, floor, capacity >= 1, equipment (one per line, each <= 100 chars), active; department move refused while clinicians of the old department have it as default room, naming the count |
| Appointment type | department select, duration >= 1, buffer >= 0, needs room, colour `#rrggbb` (lower case, as the model constraint), active, bookable online |

## Blocks, one sentence each

1. `domain/record_fields.py`: pure functions per record returning `list[FieldMessage]` and normalised values (trim, code lower-cased, lengths from the model, `#rrggbb`, coordinates paired and in range, capacity/duration/buffer bounds); the known-zone set is passed in (no I/O in domain).
2. `domain/delete_dependents.py`: `delete_refusal(kind, counts) -> tuple[Dependent, ...]` with `Dependent(reason, count)`, exactly the section 10 table for the five kinds; empty = deletable. Under `make mutate`; survivors fixed with tests, not listed.
3. `domain/audit_labels.py`: add `<record>.create|update|delete` for the five records (generated from the kinds, so a sixth kind cannot be forgotten); plain words e.g. "Hospital created". Merge note for 17c: only add entries, keep `audit_label` signature.
4. Use case write path (all three in one `transaction.atomic`): admin check from `actor.role` (forbidden otherwise) -> `select_for_update` on the row (update/delete) -> compare version -> domain checks (parent exists, room move) -> save inside a savepoint -> audit -> done.
   - Code uniqueness: normalised lower-case; pre-check `code__iexact` (excluding self) gives `invalid_input` on field `code` ("Code is taken"); the race is closed by migration `0013` replacing the five case-sensitive unique constraints with `UniqueConstraint(Lower("code"))`, same names kept where possible; `IntegrityError` in the savepoint maps to the same `code` message. A form message on the code field, never a 500.
   - Create sets `created_by=actor`, version 1. Update: changed names computed against stored values; none changed = return success, no save, no audit, version unchanged.
   - Audit: `ids` (own id is the entity id; parent `hospital_id` / `department_id`), `changed_fields` (create = all fields, update = changed, delete = none), counts for delete. No names, codes, phones, addresses.
   - Delete: lock row, count dependents with ORM counts, `delete_refusal`; non-empty -> `Failure.has_dependents(["3 departments", ...])`. The delete itself sits in a savepoint catching `ProtectedError` and `IntegrityError` (a child committed between count and delete, PROTECT FKs and DB FKs both hold): recount and return `has_dependents` again, never raise.
5. Concurrent edits (item 7): the edit form carries a hidden `version` field holding the version it read (so two ids named `id_version` cannot appear: one form per page, test below). `update_record(expected_version=...)` after the row lock: version differs -> `Failure.conflict([entity])`, nothing written. The second admin gets the form again (status 409) with what they typed kept, a warning notice "Another admin saved this record first. Your changes are not saved. Saving again replaces theirs", a link "See the current values", and the hidden version refreshed to the current one so a second Save is a deliberate overwrite. Missing/non-integer version = `invalid_input`, form shown again.
6. Views: parse POST into a values dict (kept for redisplay), domain-check, call use case; `invalid_input` -> 422 with `errors_by_field` (existing helper) and error summary; `has_dependents` -> delete page again, 409, with each reason and count in a list, no delete button; `not_found` / `forbidden` via the existing `refusal_of` path. Success: 303 to the show page (create/edit) or the list (delete) (no flash mechanism exists and none is added; the target page shows the new state).
7. List: `q` icontains name or code, order name then id, 20 per page, `page` unusable -> 1, "N hospitals found" total, empty state, link to new; table with caption, `th scope`, `table-wrap` with `tabindex=0 role=region aria-label`.
8. Nav `components/admin_nav.html` on every admin page including `/admin-console/`: Dashboard, Hospitals, Specialties, Departments, Rooms, Appointment types, then Users, Clinicians, Appointments, Waitlist, Audit log, Settings. Sections of tasks 19 to 21 have no page yet, so they render as plain text items with `aria-disabled="true"` (no dead links); those tasks turn them into links by giving a path. Reuses `.portal-nav` (wraps, 44 px targets, current = bold + underline, not colour alone).
9. Hospital time zone note and upcoming count: `admin_record_reads.upcoming_appointment_count(hospital)` = active status, start after request clock, clinician in the hospital; shown in the edit form only.

## Files to touch, in order

1. `domain/record_fields.py`, `domain/delete_dependents.py`, `domain/audit_labels.py` + their `test_*.py`
2. `models/organisation.py` + migration `0013_code_unique_ignoring_case.py` (hand-written; refuses nothing existing: check seed and builder codes are already unique ignoring case); regenerate `doc/data-model.md` if the render test requires it
3. `use_cases/admin_record_specs.py`, `admin_record_reads.py`, `admin_records.py` + tests (split in several test files, each under 300 lines)
4. `views/pages/admin_records.py` (+ `admin_record_forms.py` for per-record value parsing if over 300 lines), `homes.py` (admin home gets the nav only), `drlibre/urls.py`
5. `templates/admin/*.html`, `components/admin_nav.html`, `components/textarea.html`, `templates/style.html`, `static/css/components.css`
6. Tests in `views/pages/test_admin_*.py`, `views/test_hostile_input.py` (add ids: `record_id` per kind), `views/test_admin_access.py`

Deliberately not touched: `ClinicianProfile`/`User` flows (task 19), `PageView`, auth, the public search and booking code (item 8 is proved by tests, the loaders already read the database per request, no cache), existing audit entries, API/FHIR serving, seed (only checked).

## Invariants and blast radius

- Audit log append-only; every write has its entry in the same transaction, entry failure rolls the write back (test: patch `record_audit` to raise, assert no row and no version change).
- Server-side authorization: role from session in `PageView.allowed_roles` and again in each use case; no id or role from the body; unknown POST fields ignored by the whitelist parser (never reach the model).
- Version trigger (ADR 0003): all writes via `Model.save()`; no `queryset.update`.
- Double booking, availability maths: untouched. Blast radius: the constraint migration (five tables, brief lock), `urls.py`, shared templates/CSS (additive), `audit_labels.py` (17c merge).
- Public effect of deactivating or editing records is immediate because loaders query live rows.

## Failing tests first (behaviour, expected value)

Domain (mutation-tight, boundary values on each side):
- `returns_no_refusal_when_hospital_has_no_departments`; `returns_departments_count_when_hospital_has_three`; one pair per row of the section 10 table (department: clinicians, rooms, types listed together each with count; specialty: clinicians; room: appointments, availability rules, default-room clinicians; type: appointments, waitlist entries); zero counts omitted.
- `returns_code_in_lower_case_when_code_has_capitals_and_spaces`; `returns_error_when_colour_is_not_seven_characters_lower_hex` (`#12345g`, `#fff`); `returns_lower_case_colour_when_colour_typed_in_capitals` (`#FFAA00` becomes `#ffaa00`, matching the stored check); `returns_error_when_only_latitude_given`; `returns_error_when_latitude_91`; `accepts_latitude_90_and_longitude_minus_180`; `returns_error_when_time_zone_unknown`; `returns_error_when_capacity_0` / `accepts_capacity_1`; duration 0/1; buffer -1/0; name blank after trim; name 201 chars / 200.
- `returns_plain_words_for_every_admin_record_action` (all 15).

Use cases (real PostgreSQL):
- `returns_hospital_with_version_1_and_one_audit_entry_when_admin_creates_it`; audit metadata equals `{changed_fields: [all], ids: {}}` and contains no name text.
- `returns_forbidden_when_patient_or_clinician_creates_record`, nothing written.
- `returns_code_taken_on_code_field_when_code_differs_only_by_case` (each of five kinds).
- `returns_code_taken_when_two_threads_save_same_code` (two connections, barrier; exactly one wins, loser gets field error, no IntegrityError out).
- `writes_nothing_and_keeps_version_when_edit_changes_nothing` (no audit, `updated_at` same).
- `raises_version_by_one_and_audits_changed_field_names_when_name_changes`.
- `returns_conflict_when_edit_carries_older_version` and the stored row is the first admin's.
- `returns_invalid_input_naming_count_when_room_moves_while_two_clinicians_use_it_as_default` ("2 clinicians"); `moves_room_when_no_clinician_uses_it`.
- `returns_has_dependents_with_counts_when_deleting_each_kind_with_dependents` (five kinds); `deletes_and_audits_when_nothing_depends`.
- `returns_has_dependents_when_a_department_is_added_between_check_and_delete` (hook the counter to insert a child after counting; also commit-from-other-connection variant).
- `rolls_back_write_when_audit_cannot_be_written`.
- Item 8, through the admin use cases then the public loaders (search API + `/` + `/book`): `stops_offering_provider_when_hospital_deactivated`, same for specialty, appointment type; `stops_offering_room_when_room_deactivated` (booking placement picks no inactive room); `offers_new_type_when_department_has_available_clinician`.
- Item 9: `returns_upcoming_count_when_hospital_has_two_active_future_appointments` (cancelled and past excluded); stored `starts_at` unchanged after zone edit; free slots computed in the new zone.

Views, browser-style (cross-site check on, `Origin` set, via the existing browser helper in `browser_support.py`):
- Each route, each role: anonymous 303 to `/sign-in?next=`, patient/clinician 403 forbidden page, admin 200. Routes enumerated from `get_resolver()` filtered to `admin-console/`; a route added later without an admin guard fails (assert every admin-console view class has `allowed_roles == {ADMIN}`).
- `returns_422_with_typed_values_and_code_error_beside_code_field` per kind; `returns_303_to_show_page_when_created`; `returns_403_when_post_has_no_origin`.
- List: 25 records -> 20 rows, "25 hospitals", page 2 has 5; `q` matches name and code case-insensitively; `page=abc` and `page=999` show page 1 / last; `q` with `%` and `_` matches literally.
- Show: specialty without vendored icon says "fallback"; vendored says its file; hospital show lists departments count.
- Form: hospital edit with 2 upcoming appointments shows "2 upcoming appointments" and the zone sentence; with none, no sentence. Edit page carries hidden `version`. Stale POST shows the notice, typed values, refreshed version.
- Delete page: GET is confirmation and changes nothing; POST refused shows `has_dependents` list with counts and no delete button; POST ok -> 303 list.
- HTML invariants over every admin page rendered: no duplicate `id` (also list page with search form and sign-out form; form page with summary), every input has a label, `aria-current="page"` on exactly one nav item, disabled sections not links, table has caption and `th scope`, no inline `style=` or `<script>` without `src`, error summary targets exist.
- Hostile input: add `record_id` (and each kind id name) to `_world_ids` and `FIELD_NAMES` gets the admin form fields (`name`, `code`, `version`, `hospital`, `department`, `time_zone`, `latitude`, `longitude`, `capacity`, `colour`, `equipment`); no 500 for any actor and method.
- `make test` stays under 30 s: use cases share fixtures, concurrency tests are two; hostile test adds ~25 routes to existing sharding, measure after.

## Trust boundaries

Browser -> admin pages: session cookie resolved server-side, role check, CSRF + Origin (Django middleware, as other pages), whitelist field parser, domain validation, then DB constraints as last guard. Path ids are UUID converters; `q`/`page` fall back to defaults. Use case -> DB: ORM only. Audit: typed `AuditMetadata` cannot hold free text. Nothing sensitive logged; failures carry codes and counts only.

## Vocabulary

Admin, Hospital, Department, Specialty, Room, AppointmentType, ClinicianProfile (default room count only), Appointment and WaitlistEntry (counts), AuditLogEntry. Public word "provider" unchanged on public pages; admin pages say "clinicians" for the count text.

## Not doing

No users/clinicians/appointments/waitlist/audit/settings/dashboard pages (nav items disabled). No JS (none needed; the existing focus script may be reused as on other forms). No new dependency, no list-view framework beyond the one spec-driven flow, no API/JSON endpoints, no caching, no changes to the demo seed, no soft delete, no bulk actions, no refactor of existing pages. Rooms moving department is checked only against default-room clinicians, as the spec says (other uses are not part of the rule).

## Open points the orchestrator may overrule

- Case rule: codes are stored lower case; existing mixed-case seed codes must be checked and lowered by the migration if any exist.
- Unbuilt sections shown as disabled text, not links.
- On a stale save the refreshed version makes the second admin's next Save an explicit overwrite.

## Architect review

Verdict: approve.

- Ladder: one spec-driven flow for five records is justified (task item 2 asks for it, five callers). No new dependency. Migration to `Lower("code")` is needed for the case-insensitive race in item 3.
- Layers: pure domain for field checks, delete decision and labels; use cases own transaction, authorization, lock, version, audit; views thin. Expected errors are values. Good.
- Coverage of task items 1 to 13 is complete, including hostile input, role-by-route from the resolver, no duplicate ids, audit labels, time zone note, icon fallback, public-follow tests.
- Watch during build (not blockers):
  1. Migration number `0013` may collide with task 17c's migrations on merge; check `ls scheduling/migrations` at build time and renumber to the next free one.
  2. `audit_labels.py` is a shared file with 17c: keep `AUDIT_LABELS` additive (generated entries merged into the dict) and the `audit_label` signature unchanged.
  3. Migration must lower-case existing codes and fail loudly (not silently drop) if two codes collide ignoring case; `doc/data-model.md` regenerated if its test requires it.
  4. Room-move count check must run after the row lock, inside the same transaction, so a clinician gaining the default room between check and save is not missed (or rely on the FK being checked in the same lock order).
  5. `AuditMetadata` ids for delete: the deleted record's id only, no names.
  6. Keep every new file under 300 lines and every function under 50 (`make gate`); the generic use case with 3+ args should take a spec/command object.
