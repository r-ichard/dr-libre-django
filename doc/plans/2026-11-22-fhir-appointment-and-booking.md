# Plan: task 23a, FHIR `Appointment` and booking

Plan in one sentence: `Appointment` joins the declaration as one resource type served from three
tables (appointment, waitlist entry, live hold) by a pure mapper; every write is decoded by a pure
domain function into a command that the existing use cases (`place_appointment`, `join_waitlist`,
`reschedule_appointment`, `cancel_appointment`, `change_status`) run, so no second way to book exists.

Read: `drlibre-specs.md` 5.2 to 5.6, 5.8, 15.1 to 15.6; ADR 0003, 0005, plan and code of task 23
(`fhir_resources.py`, `fhir_reads.py` `Part`/`_candidates`, `fhir_patient_*`, `fhir_body.py`,
`fhir_write_failures.py`, `views/fhir/views.py`, `writes.py`), `placement.py`,
`appointment_changes.py`, `waitlist.py`, `clinical_notes.py`, `models/booking.py`.

## Focal point

`scheduling/use_cases/fhir_resources.py` (`read`, `search`, `create`, `update` dispatch) plus the new
`fhir_appointment_*` use-case files behind it. The view layer changes only for `_sort` (point 13), the
`Location`/`ETag` it already produces, and the id check (a waitlist-born appointment keeps the entry's id).

## Decisions (reject here if wrong)

- **Logical id**: `waitlist_entry_id` when set, else the appointment pk (ADR 0003); a hold's id is the hold pk.
  `Part.everything()` annotates `logical_id = Coalesce(waitlist_entry_id, pk)`; the three parts share the
  existing union query, so nothing appears twice: entries with status `BOOKED` are left out of the entry
  part (their appointment carries the id), expired holds out of the hold part.
- **Visibility** (built from the caller first, filters only narrow it, like `readable_patients`):
  patient: own appointments and own waitlist entries, never holds; clinician: appointments of own calendar and
  holds on own calendar, no waitlist entry that is not yet booked; admin: all. No token 401. Another's id: 403 for
  patient and clinician (same body as an absent id), 404 for admin absent (as Patient).
- **Clinical note** (`comment`): added only by the mapper call for the viewer who is that appointment's clinician;
  the `Part` build takes the viewing user and sets `comment` per row where `clinician.user_id == viewer.pk`.
  Includes and other bundles go through the same build, so a note cannot leak. The note is read by the same
  query `read_clinical_note` uses, never stored in the answer.
- **Status**: table 15.3 in the mapper; `BOOKED`/`CONFIRMED` both `booked`, internal value in extension
  `appointment-status`. Hold `pending`; entry `waitlist`, `proposed` (start, end, practitioner of the offered
  appointment), `cancelled` for `EXPIRED`. Source in extension `appointment-source`.
- **Participants**: patient (`Patient/<id>`), practitioner (`Practitioner/<user id>`), room (`Location/<id>`);
  all `status: accepted`. A hold has no patient: a participant of the hold's clinician only.
  Reason `reasonCode[0].text`; `cancelationReason.text`.
- **Update decoder** `decode_update(stored_as_seen, body)` in the domain returns one of `Reschedule(start)`,
  `ChangeStatus(target, reason)`, `NoChange`, or the first refused element name (400, FHIR path). Start moved
  and end must equal start + stored duration, else `Appointment.end`; start unchanged and end different is
  `Appointment.end`. Participants, serviceType, reasonCode, comment, extensions compared with what the caller sees
  (so an echoed resource passes). Start change together with a status change: 400 `Appointment.status`. A status
  outside `booked`, `checked-in`, `fulfilled`, `noshow`, `cancelled` as target (or `booked` moved from another)
  is 409 (`invalid_transition`) by the use case table 5.6, not by the decoder. Unknown status value: 400.
  `cancelled` needs `cancelationReason.text`, else 400 `Appointment.cancelationReason`.
- **PUT on a waitlist- or hold-origin resource that is not a booked appointment** is 409 `invalid_transition`
  (no use case exists; accept is task 24).
- **Create** decoder `decode_create(body)` returns `Book(type id, start, practitioner id, patient id, room id,
  reason)`, `Join(type id, earliest, latest, practitioner id, patient id)`, or the refused element. Status
  `proposed` books, `waitlist` joins, any other 400 `Appointment.status`. `slot` reference is parsed with
  `parse_slot_id`; its type must equal `serviceType`, else 400 `Appointment.slot`; the rule gives the clinician;
  `slot` and `participant` practitioner together must agree. Start must carry a zone.
- **Stale version**: use cases get an optional `expected_version` compared to `inherited_version + version` under
  their lock (default none, pages unchanged), answering `stale_version()`.
- **Reason length** and wording validation: use the existing `reason_error` on the same text; if it lives in the
  view, move it to a shared domain function (one rule, two callers), not copy it.

## Blocks (one sentence each)

Domain, pure, under the mutation gate (`test_*.py` beside each):
1. `fhir_appointment.py`: stored row values to `Appointment` resource for the three origins, status tables, ids,
   versionId, comment only when told the viewer owns it.
2. `fhir_appointment_write.py`: `decode_create`, `decode_update`, the shapes `APPOINTMENT_SHAPE`, `Book`, `Join`,
   `Reschedule`, `ChangeStatus`; added to `WRITE_SHAPES`.
3. `fhir_declaration.py`: `Appointment` with the six parameters (`patient`, `practitioner`, `location` references,
   `status` code repeatable, `date` date repeatable twice, `service-type` code), includes the three,
   interactions read, search-type, create, update; a `default_sort` and `sort_names` field (point 13).
4. `fhir_search.py`, `fhir_bundle.py` (point 13): default sort is the declaration's first sortable name or none;
   `_address` omits `_sort` when none; `Schedule`, `Slot`, `PractitionerRole` stop refusing their own links.
5. `fhir_body.py`: `if_match_version` returns none for version 0 (point 14).
6. `fhir_patient.py` + `fhir_outcome` path form (point 15): `refused_changes` names `Patient.telecom` for phone;
   `patient_values` and the `phone_failure` field name map to FHIR paths through one table
   `FHIR_PATH_OF_FIELD` in `fhir_write_failures.py`; Appointment fields (`patient_id`, `clinician_id`,
   `room_id`, `reason`, `start`) map there too. `failure_outcome` applies the table so every expression is a path.

Use cases (adapters, no new rules):
7. `fhir_appointment_loading.py`: rows to resources for the three origins in batches (no per-row query),
   plus the included `Patient`, `Practitioner`, `Location` through the existing loaders under the includes' own
   access rule (patient reader set, `practitioners_with_contact` only for staff).
8. `fhir_appointment_reads.py`: three `Part`s, visibility per caller, filters (`patient`, `practitioner`,
   `location`, `status` by FHIR status per origin, `date` range in UTC as Slot does, `service-type`), read by id.
   `_included` in `fhir_reads.py` gets an `Appointment` branch via a hook argument, one function added.
9. `fhir_appointment_writes.py`: `create_appointment` (calls `place_appointment` or `join_waitlist` with the
   token's user; patient id from token or body, authorization stays in `authorize_booking`/`authorize_join`),
   `update_appointment` (loads the row under the guard, decodes, calls `reschedule_appointment`,
   `cancel_appointment` or `change_status` with `expected_version`), response is the loaded resource.
10. `appointment_changes.py`: optional `expected_version` on the three functions. `admin_users.update_user`
    returns `stale_version()` for a stale record; `admin_refusal.py` accepts `["version"]` like `["user"]`;
    `fhir_patient_writes.py` loses `_stale_when_conditional` and the `or` trick (point 14).
11. `fhir_resources.py`: route `Appointment` read, search, create, update. Delete stays unrouted (405).
12. Views: `views/fhir/views.py` `_read` accepts the entry/hold id (UUID form, already `parse_id`); `NO_STORE_TYPES`
    gains `Appointment`; `writes.py` unchanged apart from that.
13. `fhir_capability.py` is generated from the declaration (no change expected); `samples.py` and
    `fhir_samples.py`: Appointment search and read for patient, clinician and admin, `_include`, the booking
    request, the 201 and the failure outcomes, a waitlist body and each origin.
14. `models/booking.py` `ClinicalNote.fhir_not_exposed` replaced by `fhir_resources = ("Appointment",)` and
    `doc/data-model.md` regenerated by the existing renderer; the not-exposed check still passes (exactly one).
15. `doc/adr/0007-fhir-appointment-and-booking.md` (decisions above, scope of what a clinician sees of the
    waitlist, the end rule, 409 vs 400 rule), one line each in ADR 0003 and 0005 where changed;
    `doc/backlog.md` row.

## Files to touch, in order

`scheduling/domain/`: `fhir_declaration.py`, `fhir_search.py`, `fhir_bundle.py`, `fhir_body.py`,
`fhir_write_failures.py`, `fhir_outcome.py`, `fhir_patient.py`, `fhir_appointment.py` (new),
`fhir_appointment_write.py` (new), `fhir_write_shapes.py`. `scheduling/use_cases/`: `appointment_changes.py`,
`admin_users.py`, `fhir_patient_writes.py`, `fhir_appointment_loading.py` (new), `fhir_appointment_reads.py` (new),
`fhir_appointment_writes.py` (new), `fhir_reads.py` (hook), `fhir_resources.py`. `scheduling/views/fhir/`: `views.py`,
`samples.py`; `views/pages/admin_refusal.py` (one condition); `management/commands/fhir_samples.py`;
`models/booking.py`; `doc/data-model.md`, ADR, backlog; `mutation-equivalents.txt` only for explained survivors.

Deliberately not touched: `views/pages/` otherwise, `templates/`, `static/`, tasks 20 and 21 files
(`admin_*` pages and their use cases other than the one `update_user` line), the application API,
`placement.py`, `waitlist.py`, `booking_holds.py`, `clinical_notes.py` (read, not edited), models other than the
declaration line, migrations, `AppointmentResponse`, `Communication`, `AuditEvent`.

## Invariants and blast radius

- No double booking: create and reschedule only call `place_appointment` and `replace_placement`; locks,
  exclusion constraints and `IntegrityError` mapping unchanged. Race test below.
- Authorization server-side from the token user: `authorize_booking`, `guard_record`, `_may_change`; a body's
  patient is never replaced by the token's user.
- Audit append-only and inside the use case's transaction: same actions (`appointment.book`, `.reschedule`,
  `.cancel`, `.check_in`, `.complete`, `.no_show`, `waitlist.join`), same metadata, same notification and email.
- Answers hold personal data: `Cache-Control: no-store`, nothing stored, no log field carries a value; the existing
  planted-value log scan is extended to Appointment.
- Blast radius: `parse_search`/`_address` (every search link, point 13), `failure_outcome` (every expression
  becomes a FHIR path, point 15), `update_user` stale answer (admin pages), `if_match_version`. Existing task 22,
  22a, 23 tests stay green except the ones that pinned `_sort=name` or `phone` and are updated to the new form.

## Failing tests first (`returns_X_when_Y`, expected values in words)

Domain:
- `returns_booked_with_internal_status_in_extension_when_status_is_confirmed`; one test per row of 15.3 for
  appointment and waitlist statuses; `returns_pending_without_patient_when_hold`.
- `returns_waitlist_id_when_appointment_comes_from_entry`; `versionId` is inherited plus own version.
- `returns_comment_only_when_viewer_owns_the_appointment`.
- `returns_end_refused_when_end_differs_from_start_plus_duration`; `returns_reschedule_when_only_start_moves`
  (end equals old duration); `returns_no_change_when_body_echoes_the_stored_resource`;
  `returns_element_name_when_patient_serviceType_room_or_practitioner_changes`;
  `returns_status_refused_when_start_and_status_change_together`; `returns_cancelation_reason_named_when_missing`.
- `returns_book_when_status_proposed_with_slot`, `..._start_and_practitioner`, `returns_join_when_status_waitlist`;
  `returns_slot_named_when_slot_type_differs_from_service_type`; `returns_start_named_when_no_zone`.
- `returns_no_sort_in_links_when_type_has_no_name`; `returns_zero_as_absent_when_if_match_is_w_zero`.
- `returns_fhir_path_for_every_product_field_name` (exhaustive over the table, includes `phone`).

API (FHIR client: bearer token, no cookie, no `Origin`, cross-site check enforced):
- Read/search: patient sees own only and `total` counts own; clinician own calendar; admin all; no token 401;
  each filter; `date` range; `_include` for patient, practitioner, location, and a patient never receives another
  patient inside it; clinician email and phone only for staff in an include.
- Notes: plant a note; patient, admin, other clinician read, search and `_include` bundle: planted text absent from
  the body; its own clinician gets it. (Four roles, three routes.)
- Origins: search `status=pending|waitlist|proposed|booked|cancelled` finds hold, entry, offer, accepted entry's
  booking (same id, once), expired entry; patient never sees a hold; unfiltered search has no id twice.
- Book: 201, status `booked`, practitioner, room, `Location`, `ETag`; first available for a patient, round
  robin source and `last_assigned_at`; clinician into own calendar for an active patient; clinician naming
  another clinician or admin without practitioner refused as the use case does; patient naming another patient 403
  and no appointment exists for anyone; admin with named clinician; inactive patient 404.
- Each 5.3 rule by its name in the outcome extension and status 422; conflict 409; `no_room_available`,
  `no_clinician_available` 409; `If-Match` stale 412 on reschedule, cancel, status; `W/"0"` counts as absent.
- Reschedule, cancel (window rule for patient), check in, complete, no-show; disallowed status 409 per 5.6; element
  change 400 with the path; end from client never stored.
- Race: two transactions (as `test_booking_lock_order.py`, `transaction=True`) book one slot through the route:
  one 201, one 409, one row in the database.
- Parity (point 12): one booking, one reschedule, one cancellation each done by screen and by FHIR for like
  parties; equal audit action and metadata keys, equal notification kind/title/body, equal email in the mail outbox,
  equal row in the portal list.
- Waitlist: own token and admin join, clinician 403, other patient 403; offered/accept untouched.
- Paging (point 13): for every searchable type of `FHIR_RESOURCES` (data-driven test), follow `next` from the first
  page to the last: entries equal `total`, each once, `self` re-read gives the same page.
- Hostile input (point 16): for every type with a write, a body whose `resourceType` differs from the address and
  one whose `id` differs: 400, never 500; also deep nesting, wrong types for Appointment.
- Samples test walks the new samples for empty values; `make fhir-validate` over them.

Mutation: new domain modules get tests that kill their mutants; equivalents explained in
`mutation-equivalents.txt`. Speed: builders and one shared clinic fixture; `make test` under 45 seconds checked
at the end; the paging test uses a handful of rows and `_count=2`.

## Trust boundaries

| Boundary | Validation and authorization |
| --- | --- |
| Bearer token | `resolve_token`; write without token 401; role and ownership from the user, never the body |
| Body | size limit, JSON object, `exact_elements` against `APPOINTMENT_SHAPE`, id and type match the URL, decoder checks values, use case validates again |
| `slot` reference, `serviceType`, participants | parsed by `parse_slot_id`/`parse_id`; unknown ids give `not_found` from the use case, never a lookup answer that tells another's existence |
| Query string | declaration parser; `_include` only declared ones |
| `If-Match` | integer, 0 absent, stale 412 under the use case's lock |
| Output | mapper adds `comment` only for the owning clinician; includes use their own readable sets; `no-store`; no values in logs |

## Domain vocabulary used

Appointment, AppointmentType (`serviceType`), Patient, Clinician, ClinicianProfile, Room, Hospital (`location`
search is the room's or the site), WaitlistEntry, BookingHold, Admin, ApiClient (token), Notification and
AuditLogEntry (through the use cases), ClinicalNote (read for its clinician only).

## What I will not do

No new dependency, model, migration or column. No second booking path: no direct `Appointment.objects.create`.
No `AppointmentResponse`, accept, `Communication`, `AuditEvent`, delete of Appointment, hold creation or
deletion through FHIR, comment write (clinical notes are saved on the screen; a changed `comment` is 400).
No generic REST framework. No change to pages, templates, placement, waitlist, hold or note use cases.
Sandbox cannot run the HL7 validator if Java or the jar is missing: `make fhir-validate` result is reported as it is.

## Architect review

Verdict: approve.

- Ladder: no new dependency, model, migration or second booking path; writes decode purely, then call the existing use cases. The size follows from the task's 16 points, not from speculation. `FHIR_PATH_OF_FIELD` is one table with several callers (point 15), so it earns its place.
- Layers: domain mappers and decoders pure and under mutation; use cases own authorization, locks and audit; views change only for `_sort`, id and `no-store`. Expected refusals stay values.
- Security: the note leak is closed at the single `Part` build, so reads, searches and `_include` share it, and the four-role, three-route planted-note test proves it. Patient from the body is authorized by `authorize_booking`, never replaced by the token user. Holds are hidden from patients. Another's id answers the same body as an absent one.
- Tests first: behaviours are named with expected values, including the race (two transactions), parity of audit, notification, email and portal, paging for every type, and hostile `resourceType`/`id`.
- Scope: points 1 to 16 and the `ClinicalNote` declaration and data-model fix are covered.

Watch during build (not blockers):
- The `expected_version` compare must happen under the use case's lock, not before it.
- Parity test must compare the audit metadata values, not only the keys, except for fields that must differ by design, which the test names.
- A booked waitlist entry's id equals the appointment's id; `status=booked` search must not return both. The origins test covers it; keep it.
