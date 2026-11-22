# Plan: task 19, admin console for users and clinician profiles, plus carried fixes 17 to 22

Date 2026-11-22. Spec section 10 (+3.1, 3.2, 4, 12.2, 12.3). Impeccable Operate mode: before any UI edit the
build stages read `PRODUCT.md`, `DESIGN.md`, the skill and its `reference/craft-floor.md`. No inline script or style;
every step is a plain form or link.

## Focal point

The task 18 flow (list, show, form, delete pages, one `RecordSpec`/`KindView` table) gains two more kinds, `user`
and `clinician`, and the pages stay unchanged in shape. What differs (password, locks, role rules, profile rules,
side effects) lives in two new use case modules behind one seam: a `WRITERS` table mapping kind to
create, update and delete.

One sentence: *two more kinds on the same admin flow, where every write is a locked, versioned, audited use case,
and every rule that needs no stored data is a pure domain function.*

## Decisions the task asks to state

**Replacing a temporary password (item 2).** `change_password` (task 15, `use_cases/profile.py`) is already
role-neutral (it takes the actor, checks the current password, ends the other sessions). Only the page is
patient-only. Add one route `/account/password` for Clinician and Admin (`PasswordPage` made a base with
`allowed_roles` and nav passed by the subclass; the patient route and page stay as they are). Link "Change your
password" from the admin home and the clinician home. No forced-change flag (a new column nobody asked for); the
create form hint says "Tell the person to change it after the first sign-in" and the admin console is the only place a
temporary password exists. Risk noted below.

**Changed email (item 5).** Inside the update transaction, after locking the user row, when the normalised email
differs: (a) `email_verified_at` is set to empty (the new address is unproven); (b) unused sign-in links of the user
get `cancelled_at = now` (first statement, before sessions, so a `use_link` racing it either finished first and its
session is deleted by (c), or waits on the row lock and then sees `cancelled_at`); (c) every session of the user is
deleted. A passwordless patient (no usable password; the model constraint `user_passwordless_has_verified_email`
needs the verified time) cannot have the email changed: refused with the reason "This patient has no password, so
the verified email is the only way in" (pure rule). Audit: changed field names (`email`, `email_verified_at`) and
counts `sessions_ended`, `links_cancelled`; never the address.

**Deactivation (item 4).** Same transaction: sessions deleted (so `resolve_session` fails at once, also by its
existing `is_active` check), unused links cancelled, audit counts. The confirmation page (edit form when the active box is
cleared would be a silent change, so deactivation is its own step: `/admin-console/users/<id>/deactivate`, GET =
confirmation naming the number of upcoming active appointments as patient or clinician, "they stay booked", POST =
use case; the edit form shows the active flag read-only with a link to that step; re-activation is the edit form
checkbox, which only ever turns it on). Every step works without JavaScript.

**Last admin (item 3).** Use case first locks the actor row, then `select_for_update` on all active admin rows ordered by
pk (one lock order for everyone), then reloads the actor under that lock and re-checks "still active admin". Two
admins deactivating or demoting each other: the second waits, then is refused as `forbidden` (actor now inactive) or
sees one active admin and is refused with the reason. Own account: refused by pure rule before any write.

**Role change (item 6).** Pure rule over counts: from Clinician with a profile; from Patient with appointments or
waitlist entries; from or to a role while the account is a passwordless patient (constraint); last admin;
own role. Every reason is listed together, not just the first.

**Delete user (item 7).** Table rule extended in the pure `delete_refusal`: own account, appointments as patient,
appointments as clinician, audit entries as actor, plus two reasons so nothing ends as a 500: a clinician profile
(delete the profile first) and waitlist entries. Sessions, sign-in links and notifications of the user are deleted
in the same transaction before the user (they are the person's own, not history); the existing
`ProtectedError/IntegrityError` recount path covers a dependent that appears late. Advice line "Deactivate
instead" is on the refusal page.

**Clinician profile.** Attach to an active Clinician user without one; edit; delete refused with appointments.
Department move refused (pure rule over counts: upcoming active appointments, availability rules, default room set)
naming each count; the default room (active, of the saved department) and active specialty are checked in the use case
only when they changed, so an old inactive specialty does not block editing a bio. Weight integer >= 1, title 1 to 50
(model max 50), bio optional.

## Blocks, one sentence each

1. `domain/user_rules.py` (new, pure): `normalise_email`, `check_password(10..72)`, `check_full_name`, `own_account_refusals`,
   `last_admin_refusal`, `role_change_refusals`, `email_change_refusal`; returns lists of `FieldMessage`/reasons, no I/O.
2. `domain/clinician_rules.py` (new, pure): `check_title`, `check_weight`, `department_move_refusals(counts)`, and
   `availability_summary(rules)` (weekday groups with time ranges, "No weekly availability" when none).
3. `domain/delete_dependents.py`: add kinds `user` and `clinician` (clinician: appointments); the "own account" reason
   comes as a count of 1 or 0 so the signature stays `delete_refusal(kind, counts)`.
4. `domain/audit_labels.py`: add `user.create|update|deactivate|activate|delete` and `clinician.create|update|delete`
   (additive, generated from the existing `RECORD_WORDS`/`VERB_WORDS` with `deactivate`/`activate` added).
5. `use_cases/admin_record_specs.py`: `RecordSpec` gains `title_field` (default `name`), `search_fields`, and
   `identifier_field` (the "Code" column; email for users) so list/show/delete reuse it; user and clinician specs added.
6. `use_cases/admin_record_reads.py`: `list_records` counts with `.count()` and slices `[first:first+20]` in the
   database (page clamp by new pure `page_bounds(total, page, size)` in `domain/search_ordering.py`, `paginate` stays for
   its other callers); two queries a page (count, rows with `select_related`), the clinician list adds one query for the
   availability rules of the page's profiles; user/clinician reads: upcoming appointment counts, selectable clinician
   users without a profile, department rooms.
7. `use_cases/admin_users.py` (new): `create_user`, `update_user`, `deactivate_user`, `delete_user`; each in one
   `transaction.atomic`, admin from the actor (checked again under lock), row lock, version compare, rules, save in a
   savepoint (`IntegrityError` on `user_email_unique` becomes the field message "Email is taken."), side effects above,
   audit. Password: `make_password` in the use case, never in `values` after hashing, never in audit metadata (create lists
   changed fields without `password`; a password reset by the edit form is not offered: only the person changes it).
8. `use_cases/admin_clinicians.py` (new): `attach_profile`, `update_profile`, `delete_profile` (named `*_clinician` to avoid
   the task 15 `update_profile`), same transaction shape; locks the profile row and the user row; public search needs
   no invalidation (loaders read live rows).
9. `use_cases/admin_record_writers.py` (new, 20 lines): `WRITERS = {kind: (create, update, delete)}`; the five task 18 kinds
   point at the generic functions. `views/pages/admin_records.py` calls the table; no `if kind == "user"` in a view.
10. `views/pages/admin_record_kinds.py`: `KindView` entries for users and clinicians; new widgets `PASSWORD` (create form only,
   `type=password`, `autocomplete=new-password`, never refilled) and `ROLE` select; `admin_record_forms.py` parses them and
   drops `password` from `typed_text`, so no page after the send holds it; `@sensitive_post_parameters("password")` on the
   form view keeps it out of Django's error reports.
11. New pages: `RecordDeactivatePage` (confirmation + POST) and `ClinicianCalendarPage`
   (`/admin-console/clinicians/<id>/calendar?week=`, previous/next week, no action, items without `href`, no notes: the
   lines never read `ClinicalNote`). Routes joined in `admin_record_routes()`; nav items Users and Clinicians become links.
   The calendar reuses the clinician calendar's builders, moved to `views/pages/time_grid.py`-adjacent
   `calendar_week.py` (extract, not copy) and takes the profile instead of the session user. The type colours
   stylesheet gets an admin route `/admin-console/type-colours.css` (all types' colours, same generator) because
   `/clinician/type-colours.css` is clinician-only.
12. `templates/admin/*.html`: list header says the identifier label; show gets Edit/Deactivate/Delete/Calendar links;
   new `admin/deactivate.html`, `admin/calendar.html`; `account/password.html` extends the existing one.
13. Item 17: see block 6. Item 18: test only (block in tests). Item 20: `list.html` count paragraph gets class `list-count`;
   `components.css` `.list-count { margin-top: var(--space-4); }` (spacing token, `.search-form` sibling gap).
14. Item 19, seed: `catalogue.SPECIALTIES` codes become the vendored ones (`cardiology`, `dermatology`,
   `general-practice`, `paediatrics`, `orthopaedics`). `writer.py` specialty step: look up the new code, else the legacy
   `demo-<code>` row and rename it in place (keeps its id, so clinicians stay attached); after the upserts delete legacy
   `demo-*` specialties nothing references, so an old database never holds two sets. Builder greps `scenarios.py` and tests for
   `demo-cardiology` style specialty uses. `VENDORED_CODES` is derived from the files in `static/icons/specialties`
   (no hand list that can drift); test: seeded codes equal vendored codes, both ways.
15. Items 21, 22 (CSS and the grid item template, details in "Time grid"). 

## Time grid (items 21, 22)

- Item 21: the status icon stays on the first line, but the drawn time text is `13:00–13:15` (en dash, tabular width about
  80 px) instead of "13:00 to 13:15"; the spoken `visually-hidden` text keeps "to". Icon is sized `1em` with
  `vertical-align: middle` so its box is not taller than the 18 px line, which removes the 26 px content height; icon (14) +
  gap (4) + time (about 80) fits the 105 px worst case (with the rail). Time-off first line shows the part's clock span
  `09:00–17:00`; the real start and end of a multi-day period move to its second line. Drawn time line therefore
  never needs `text-overflow`. Rule stays: no line holds anything taller than itself.
- Item 22: the element holding the out-of-flow text is **`.time-grid`** (the scroll frame, `overflow-x: auto` from 64rem). It gets
  `position: relative` so the `.visually-hidden` spans (`position: absolute`) in every item and heading are
  contained and clipped by it, not by the viewport. Asserted in `test_time_grid_css.py`: the `.time-grid` rule declares
  `position: relative`, the 64rem rule declares `overflow-x: auto`, and `.visually-hidden` stays `position: absolute`.
  Covers calendar, rooms timeline and the new admin calendar (one component).
- The orchestrator measures both in Chrome; the sandbox has no browser.

## Files to touch, in order

1. `domain/user_rules.py`, `domain/clinician_rules.py`, `domain/delete_dependents.py`, `domain/audit_labels.py`,
   `domain/search_ordering.py` (+`page_bounds`), `domain/specialty_icons.py` + `test_*.py` for each
2. `use_cases/admin_record_specs.py`, `admin_record_reads.py`, `admin_users.py`, `admin_clinicians.py`, `admin_record_writers.py`
   + tests (several files, each < 300 lines)
3. `views/pages/admin_record_kinds.py`, `admin_record_forms.py`, `admin_records.py` (+ `admin_user_pages.py` for the
   deactivate and calendar pages to keep files < 300), `clinician_calendar.py` (extract), `drlibre/urls.py`, account password page
4. `templates/admin/*`, `account/password.html`, `components/admin_nav.html`, `homes/admin.html`, clinician home link,
   `components/time_grid_item.html`, `components/icon.html` size class, `static/css/time-grid.css`, `components.css`
5. `demo_seed/catalogue.py`, `writer.py` + seed tests
6. Tests: view, access, hostile input, public follow, unique ids, CSS

Deliberately not touched: the booking, placement and free-slot code; `search_catalog.py` (it already filters
`user__is_active`, specialty and hospital active); the sign-in, session and `change_password` use cases; models (no
migration: all columns exist, `cancelled_at` too); patient routes; API and FHIR.

## Invariants and blast radius

- Audit log append-only; entry in the same transaction; audit failure rolls the write back (test, as task 18).
- Authorization: role from session in `allowed_roles` and again in each use case under lock; no role, id or actor from the body;
  unknown POST fields ignored by the whitelist; a deactivated admin's in-flight request is refused under the lock.
- Version trigger (ADR 0003): all writes through `Model.save()`; sessions/links bulk statements touch other tables only.
- Never leaves an admin-less system; never a record contradicting its role; no appointment cancelled by these writes.
- Blast radius: shared `RecordSpec` and `list_records` (five existing lists change query shape), `time_grid_item.html`
  and `time-grid.css` (calendar and rooms timeline), the seed catalogue (specialty codes on existing databases).

## Failing tests first (behaviour, expected value in words)

Domain (mutation-tight, both sides of each boundary):
- `returns_no_message_when_password_has_10_characters` / `returns_message_when_password_has_9` / `accepts_72` / `rejects_73`.
- `returns_lower_case_trimmed_email_when_typed_with_capitals_and_spaces`; blank and no-`@` refused.
- `returns_refusals_when_admin_deactivates_own_account` and `when_changes_own_role`; none when editing own name.
- `returns_last_admin_refusal_when_one_active_admin_is_deactivated_or_demoted`; none when two.
- `returns_every_reason_when_clinician_with_profile_becomes_patient_and_has_waitlist_entries`; none for Clinician without profile to Admin.
- `returns_refusal_when_passwordless_patient_changes_email_or_role`.
- `returns_three_reasons_when_department_changes_with_appointments_rules_and_default_room`; none when counts 0; zero counts omitted.
- `returns_error_when_weight_is_0` / accepts 1 / rejects 1.5 text; title blank and 51 chars.
- `returns_text_for_availability_summary`: Mon and Wed 09:00–12:00 -> "Mon, Wed 09:00–12:00"; empty -> "No weekly availability".
- `delete_refusal` rows for user (own, patient appointments, clinician appointments, audit, profile, waitlist) and clinician.
- `page_bounds`: page 0, 1, last, last+1, empty total.
- `returns_plain_words_for_every_user_and_clinician_audit_action`.

Use cases (real PostgreSQL):
- `creates_user_with_lower_case_email_hashed_password_version_1_one_audit_entry`; planted password `Pl4nted-Secret-9x` is
  in no `AuditLogEntry.metadata`, no `User` column except as hash (`check_password` true, plain text absent), no log record
  (caplog at DEBUG over the call and the view request), no rendered page after POST (422 and 303 target).
- `returns_email_taken_when_email_differs_only_by_case`; same with two threads (one wins, no IntegrityError out).
- `returns_forbidden_when_patient_or_clinician_calls_each_user_and_clinician_use_case`, nothing written.
- `writes_nothing_and_keeps_version_when_edit_changes_nothing`; `raises_version_and_audits_changed_names_only`
  (metadata holds no name, email or phone: assert planted name, email, phone strings absent).
- `returns_conflict_when_second_admin_saves_older_version`, first admin's values stay.
- `ends_sessions_and_cancels_unused_links_when_user_deactivated`; `resolve_session` fails right after; used links untouched; upcoming
  appointments unchanged and counted on the confirmation for a clinician and a patient.
- `clears_verified_time_cancels_links_and_ends_sessions_when_email_changes`; a link issued to the old address fails in
  `use_link`; also `use_link` racing the edit (two connections) never leaves a usable session.
- `refuses_with_reasons_when_role_change_would_contradict_records`.
- `returns_refusal_when_last_admin_deactivated_by_two_admins_at_once` (two threads, barrier, A deactivates B and B
  deactivates A: exactly one succeeds, one active admin remains).
- `returns_has_dependents_with_reasons_when_deleting_user_with_appointments_or_audit_entries`; deletes and audits a user with only
  sessions and notifications; own account refused.
- Clinician: `attaches_profile_to_active_clinician_user_only` (patient, admin, inactive, already attached refused);
  inactive specialty and room of another department or inactive refused; default weight 1; edit; department move refused with
  three counts; deleting profile with an appointment -> `has_dependents`, without -> deleted and audited.
- `rolls_back_when_audit_cannot_be_written` for one user and one clinician write.
- Item 15 through `search_public`: `stops_offering_clinician_when_user_deactivated`, `offers_clinician_when_profile_just_attached`
  (absent before, present after, with an availability rule).
- Item 17: `list_records` makes 2 queries for each of the seven kinds with 25 rows (`django_assert_num_queries`), and the list
  page's query count equals the same with 1 or 20 rows.
- Item 18: `returns_has_dependents_when_a_child_appears_between_count_and_delete`: patch the counter to insert a department
  after counting; delete answers `has_dependents`, row remains, no audit entry.
- Item 19: seeded codes equal the vendored icon files; seeding a database that holds `demo-cardiology` keeps its id,
  renames it, leaves five specialties and the clinician attached; unreferenced legacy rows are deleted.

Views, browser style (`browser_support.py`: cross-site check on, `Origin` set):
- Routes of this task (list, new, show, edit, deactivate, delete for users and clinicians, calendar, colours, `/account/password`)
  join `test_admin_access.py` and `test_access_rules.py`: anonymous 303 to sign-in, patient/clinician 403, admin 200; every admin
  view class has `allowed_roles == {ADMIN}` (enumerated from the resolver).
- `test_hostile_input.py`: add ids `user_id`, `profile_id`, fields `email`, `role`, `password`, `title`, `bio`,
  `round_robin_weight`, `default_room`, `specialty`; no 500 for any actor and method.
- Forms: 422 keeps typed values except the password (field empty, planted value absent from body); 403 when `Origin` missing;
  303 on success; stale version -> 409 with notice, as task 18.
- Own account: edit form shows no role select and no deactivate link for oneself; POST that forges it is refused with the reasons.
- List: 25 users -> 20 rows, "25 users", `q` matches name and email in any case, `%` and `_` literal; clinicians list shows
  department, specialty, active, availability summary.
- Calendar: week navigation links, no form, no `href` inside blocks, planted clinical note text absent, 404 for unknown profile.
- Page invariants over every new page: no duplicate id, labelled inputs, one `aria-current`, table caption and `th scope`, no
  inline `style=` or `<script>` without `src`, error summary targets exist.
- Time grid blocks: first line text is `HH:MM–HH:MM`, status icon on it, spoken text keeps "to"; CSS test as above; list count class.

Run time: seven-kind query test and concurrency tests share fixtures (three thread tests total); measure `make test`
against the 30 s ceiling after the build.

## Trust boundaries

Browser -> admin pages: session cookie resolved server-side, role check, CSRF and Origin (middleware), whitelist
parser, domain validation, DB constraints as last guard. Path ids are UUID converters; `q`, `page`, `week` fall back to defaults.
Password enters only on the create form and the account page, is hashed in the use case, and leaves no trace. Use case -> DB:
ORM only; typed `AuditMetadata` cannot hold free text.

## Vocabulary

Admin, User, Clinician, Patient, ClinicianProfile, Department, Specialty, Room, Appointment, AvailabilityRule, WaitlistEntry,
Session, SignInLink, AuditLogEntry. Admin pages say "clinician"; public pages keep "provider".

## Not doing

No forced password change, no admin password reset, no email to the new address, no bulk actions, no re-assign of appointments
on deactivation (they stay booked), no new dependency, no model or migration, no API/FHIR changes, no refactor of
existing pages beyond the extract of the calendar builders.

## Open points the orchestrator may overrule

- Deactivation as its own confirmation step, not the edit form checkbox.
- Passwordless patient cannot change email or role (constraint-driven); alternative is a new migration, rejected.
- Temporary password is not forced to change; risk accepted until a task adds the flag.
- Seed renames legacy `demo-*` specialties in place rather than creating new ones.

## Architect review

Verdict: approve. Layers, transaction shape, lock order, security and scope hold; the points below are for the build stage to settle, none needs a new plan.

- Ladder: one `WRITERS` table plus two use case modules and two pure domain modules is the smallest shape that avoids `if kind == "user"` in views. No new dependency, no migration. The `RecordSpec` extension (`title_field`, `search_fields`, `identifier_field`) has a second caller (users, clinicians), so it is justified.
- Item 17 contradiction: block 6 says the clinician list adds a third query (availability rules), the test says "2 queries for each of the seven kinds". Pick one: assert 2 for six kinds and 3 for clinicians, or fold rules in with `prefetch_related` and state the count. Keep the "same count at 1 or 20 rows" assertion.
- Item 22: `position: relative` on `.time-grid` contains the hidden spans only if the frame clips them; below 64rem the plan sets no `overflow`. Either state that the spans are 1 px and clipped by `.visually-hidden` itself at narrow widths, or give `.time-grid` `overflow-x: clip` or `auto` at every width. Assert the choice in `test_time_grid_css.py`.
- Item 1 asks to edit the active flag in the edit form; the plan moves deactivation to its own confirmation step and keeps only re-activation in the form. This is declared as an open point and is acceptable: the confirmation with the appointment count is required by item 4. The orchestrator must accept it knowingly.
- Version on the deactivate and delete steps: the plan says each use case compares the version, so the confirmation forms must carry the version read at GET. Add a test that a stale deactivate answers conflict and ends no session.
- Temporary password: accepted risk, with `/account/password` for clinician and admin. Add a view test that the page for a clinician and an admin works end to end (current password checked, other sessions ended) and the patient route is unchanged.
- Passwordless patient email/role refusal is constraint-driven and well reasoned; the refusal wording is tested through the pure rule.
- Seed migration: renaming legacy `demo-*` rows in place and deleting unreferenced legacy rows is sound; keep a test where a legacy row is referenced by a clinician and one where it is not.
- Mutation gate: new domain modules need killing tests on every boundary (10/72 password, weight 1, title 50, page bounds); list any equivalent mutants in `mutation-equivalents.txt` with a reason.
