# Task 21: admin dashboard, reporting and the CSV export

Focal point: six pure figure functions plus one CSV-cell escape in `scheduling/domain/`,
fed by one report use case; the dashboard page and the export route only format.

## Decisions asked for in the task

**Which day an appointment is counted on (3).** The day on the wall clock of its hospital
(`Hospital.time_zone`), the same rule as the task 20 list filter. One appointment has one
hospital, so it has one day and is counted once, whoever reads and wherever they sit.
**"Today"** is the latest current date among the hospital time zones (UTC when there is no
hospital). A range is N dates ending on that date: 1, 7 or 30. A hospital whose clock is a day
behind has an empty last date, which is true. Rule printed on the page, under the tiles:
"Days are days on each hospital's own clock. Today is the latest date at any hospital."
`range=` anything but `today|7|30` falls back to 7.

**Bar height under the CSP (6).** No style attribute. Each day is a row of ONE table (day,
appointments, bar). The bar is an inline `<svg viewBox="0 0 100 10" preserveAspectRatio="none"
aria-hidden="true">` holding a track `<rect>` and a value `<rect width="N">` where N is an integer
0 to 100 computed on the server. `width` is an SVG presentation attribute, not CSS, so
`style-src 'self'` is untouched. The value rect gets a solid fill and a stroke from a CSS class (shape and length carry the
value, not hue), the number sits in the next cell in text: colour is never the only signal. The
table is the chart and the accessible data, so the two cannot disagree. At 375 px the table
has three narrow columns and no horizontal scroll (`.table-wrap` exists already).
Invariant to measure: `scrollWidth == clientWidth` of the page at 375 px.

**Query count (7).** Dashboard queries beyond session and user lookup: hospitals zones (1),
appointments of the range as one `values_list` of six small columns (1), availability rules of
active clinicians (1), time off overlapping the range (1), waitlist counts grouped by status (1),
names of the top 5 clinicians (1) = **6**. Test asserts the count is equal for 2 and for 40
appointments and at most 8 including session lookups (measured, written in the test).
Memory is linear in appointments of the range (six fields each), queries are constant.

**Export limit (11).** Refused above **50,000 rows** with a message and a link back, status 422;
no streaming, because the read and its audit entry must share one transaction and one
`count()` before the read. 50,000 rows of ten ids is about 5 MB.

## Blocks, one sentence each

1. `domain/report_range.py` - turns the `range` value and the zones' current dates into the list of N dates. Pure.
2. `domain/report_figures.py` - appointments, cancellations, no_show_rate, online_share, waitlist_size, `percent_text` ("n/a" for denominator 0), appointments_per_day, busiest_clinicians (top 5, count then id). Pure.
3. `domain/report_utilisation.py` - active minutes inside the range divided by rule minutes minus merged time off, per local day, DST by converting each local rule window to UTC. Pure.
4. `domain/csv_cells.py` - `escape_cell` prefixes `'` when a cell starts with `=`, `+`, `-`, `@` (and tab, carriage return: same attack, cheap); `csv_row` applies it to every cell. Pure.
5. `domain/audit_entity_types.py` - the registry of audited entity types, SignInLink included.
6. `use_cases/admin_report.py` - loads the six queries above, calls the domain, returns a dataclass. Read only.
7. `use_cases/admin_appointment_export.py` - one `transaction.atomic`: count, refuse above limit, read ids, `record_audit("appointment.export", "Appointment", "export", counts={"row_count": n})`, return rows.
8. `views/pages/admin_dashboard.py` + `templates/admin/dashboard.html` - replaces `homes/admin.html` content; range as a GET form of links, tiles as the existing `.stat`/definition-list pattern, busiest list, rule text.
9. `views/pages/admin_appointment_export.py` - POST only form handler, same filter parsing as the list, `never_cache`, `Content-Disposition: attachment; filename="appointments-<first>-<last>.csv"` (name built only from validated dates), `text/csv; charset=utf-8`.
10. `templates/admin/appointments.html` - the export form (POST, `{% csrf_token %}`, hidden filters) under the list.
11. `domain/audit_labels.py` - add `appointment.export`: "Appointments exported".
12. Carried items, see below.

## Carried items

- **14** Filter options = registry union the distinct `entity_type` values in the table (one query), so a type in the data can always be filtered. `ENTITY_TYPES` hand list in `admin_audit.py` removed. Test: AST-scan `scheduling/use_cases` for entity type literals and `ENTITY_TYPE` constants, assert each is in the registry (fails when someone audits a new type and forgets it); another test: an entry of every registry type is returned by the page filter.
- **15** `_first_free_cancelled_slot` (`use_cases/waitlist.py`): the candidate query excludes, with `Exists` on the same predicate `find_conflicts` uses, rows where the clinician, the patient or the room has an overlapping active appointment, or the clinician has time off. The first row is the first that fits; the Python guard stays for rule hours. When the query returns nothing, one capped query of candidates with conflict flags names the busy resources so the Failure words stay as today. `MAX_SLOTS_CHECKED` stays only on that naming query.
- **16** `reference_messages` loses `transaction.atomic` and `select_for_update`: the three existence helpers take a `lock` flag (default True for the save path, False here). Test captures SQL of `reference_messages` and finds no `FOR UPDATE`.
- **17 Admin actions that change something and answer without a notice** (all fixed): appointment check in / complete / no-show; cancel; reschedule; book for a patient; waitlist add, offer, accept; record create, update, delete (7 kinds); user create, update, deactivate / activate; clinician profile create / update; reminder run (its text rides `?reminders=N` in the address, which 17b forbids: moved to the cookie). Mechanism: `redirect_with_notice` of 17b with the cookie value `key:uuid` of the record touched; `views/pages/admin_notices.py` maps key to a sentence and resolves the name server-side ("Accepted the offer for Ana Silva."). Unknown key or uuid is no notice. Shown once, cookie deleted by `forget_notice`. The notice include goes in one shared admin base block so each page does not repeat it.

## Files, in order

Domain first (blocks 1-5, 11), then use cases (6, 7, 15, 16), then views and templates (8-10, 17), CSS in `static/css/components.css` (bar, tile row, 20 lines), `drlibre/urls.py` (dashboard at `admin-console/`, export route), `admin_nav` unchanged.
Deliberately not touched: models and migrations (none needed), FHIR, settings/CSP, the 17b cookie helpers' signature beyond a `key:uuid` value, other portals.

## Invariants and blast radius

- Authorization: both new views `allowed_roles = {ADMIN}`; role from session only.
- Audit append-only, entry inside the read's transaction; export of a refused set writes nothing.
- No double booking affected; item 15 changes only which cancelled slot is offered first, the accept path still locks and re-checks.
- CSV carries ids only: patient id, clinician profile id, department id, type id, room id (blank when none); no name, email, reason. Every cell, header included, through `escape_cell`.
- Blast radius: waitlist offer (15), clinician form validation (16), every admin redirect (17).

## Tests first (name: expected, in words from the spec)

Domain, under mutation: `returns_appointments_not_cancelled_count`; `returns_cancellations_count`; `returns_no_show_rate_over_non_cancelled`; `returns_na_when_no_appointment_is_not_cancelled` (no-show, online share); `returns_online_share_counting_online_and_round_robin_only`; `returns_waitlist_size_of_waiting_and_offered_regardless_of_range`; `returns_na_when_available_minutes_are_zero`; `returns_utilisation_minutes_over_available_minutes` (hand numbers: 4 h of appointments over a 8 h rule day = 50 %); `returns_23_hour_rule_day_across_spring_forward` and a 25 hour day on autumn change; `returns_rule_minutes_only_from_valid_from_in_range` and `..._until_valid_to`; `returns_available_minutes_less_time_off_covering_part_of_a_day`; overlapping time off counted once; time off outside the rule hours subtracts nothing; inactive clinician excluded; `counts_appointment_on_hospital_day_once` (23:30 UTC in Sydney is next day; same in a New York reader); range falls back to 7 for `""`, `"90"`, `"7;"`, unicode digits; `returns_top_five_busiest_by_count`; `escape_cell` for each of `= + - @ \t \r`, a plain cell and an empty cell unchanged, a cell with a leading space unchanged; `csv_row` escapes every cell.
Use cases: export refuses above the limit (limit patched low) and writes no audit; export audit holds `row_count`; audit and read in one transaction (a failing audit leaves no output); report query count equal for 2 and 40 appointments.
Pages: dashboard shows zeros and "n/a" with no appointment; shows the rule text; `range=30` and a hostile `range` fall back; tiles equal database counts; busiest list max 5; the per-day table has one row per day and the same total as the tile; chart has no `style=` and no `<script`; no duplicate element ids on every console page (parse, all GET console routes, the dashboard filled and empty); export through `browser_post` (Origin set, CSRF enforced) returns CSV with the ten columns, UTC ISO instants, no name or email of the seeded patient anywhere in the body, `Cache-Control: no-store`, attachment filename; GET on the export route answers 405; export honours every list filter; `=cmd` injected through a status filter value is ignored by `choice_param`.
Role and hostile: `EXTRA_ROUTES` 23 to 24 in `test_admin_access.py` (dashboard replaces the home, export is new); the export route in the role test (visitor redirect, patient and clinician 403, via POST too) and in `test_hostile_input.py`.
Carried: the 14 tests above; 15: 101 busy cancelled times before a fitting one, offer returns the fitting one; 16: no `FOR UPDATE`; 17: for each action in the list, the redirect target shows the notice once with the name, and a second GET shows none; `?notice=x` in the address shows nothing.
Audit labels: `test_audit_action_labels.py` already fails on an action without words; `appointment.export` passes it.

## Trust boundaries

`range`, filter values, page: GET params parsed by `choice_param`, `uuid_param`, `day_range`, unusable means default. Export form hidden fields re-parsed server-side the same way, never trusted. Notice cookie: key looked up in a fixed dict, uuid parsed, name read for an admin only. CSV cells escaped. Filename from validated dates only.

## Entities (CLAUDE.md §3)

Appointment, AppointmentType, Hospital (zone), Department, ClinicianProfile, AvailabilityRule, TimeOff, WaitlistEntry, AuditLogEntry, User (admin, patient ids only in CSV).

## Will not do

No chart library, no script, no new dependency, no caching of figures, no new model, no streaming, no export of anything but appointments, no refactor of the task 20 list beyond sharing its filter parsing.

## Checks by the orchestrator (not runnable here)

Browser at 375 px and 1440 px, two figures against SQL, CSV in a spreadsheet reader.
