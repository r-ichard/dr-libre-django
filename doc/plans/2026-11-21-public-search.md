# Plan: task 10, public search use case and API

One sentence: load the public catalogue in a constant number of queries, load every
candidate clinician's schedule once through the existing `load_schedules`, and let pure
domain functions match, filter, aggregate, sort and page; three thin public GET views
format the result.

## Focal point

`scheduling/use_cases/search.py`: `search_public(kind, query, now) -> SearchPage`. It is the
only place that touches the database; everything it decides is delegated to domain code.

## Decisions (stated so they can be rejected)

- **Provider-centric universe.** Listed providers = active clinician (user active) + active
  hospital + active specialty + department with at least one active online-bookable type.
  The text, specialty, hospital, city and type filters pick providers. Hospitals and
  specialties are aggregates of the surviving providers (a hospital with no surviving
  provider is not listed; the counts count surviving providers).
- **Text** = trimmed, capped at 100 characters, casefolded substring match (in Python, no
  SQL `LIKE`, so no wildcard or injection concerns) on hospital name, city, clinician full
  name, specialty name, department name, any bookable type name of the department. Empty
  text matches all.
- **Filters by id** (specialty, hospital, appointment type) are UUIDs; city is a
  casefolded exact match. A malformed value falls back to "no filter"; a well-formed id that
  names nothing matches nothing. Type filter: only the type's department's clinicians match.
- **Which type the slots are for:** the filtered type, else the department's shortest
  active online-bookable type (ties: name, id). Result names it.
- **Availability filters** (earliest date, window, time of day) are per clinician in the
  hospital's zone: the search range is `[max(now+120 min, local midnight of earliest date),
  min(now+90 days, window end))`; window end for "today" = next local midnight, for 3 / 7
  days = now + 3 / 7 days. Slots are then kept by time of day: morning < 12:00, afternoon
  12:00 to 17:00 inclusive, evening > 17:00. If any of the three filters is set, a provider
  with no slot left is not listed; with none set, it stays listed ("no availability").
- **Order.** Soonest: providers with a slot by (first start, name, id), then those without
  by (name, id). Name asc / desc: by casefolded name, ties name then id, availability does
  not move a result (6.2's "after" applies to the default sort; flagged as an
  interpretation). Distance: only with a valid latitude and longitude in the address;
  hospital coordinates missing sort last; hospitals/specialties use their nearest hospital.
  `sort=distance` without location falls back to soonest.
- **Paging.** Sizes 10, 20, 50, default 20; page below 1 or unparsable = 1; past the end =
  last page; zero results = page 1 of 1.
- **Query values** (`q, specialty, hospital, city, appointment_type, from, window, time_of_day,
  sort, page, page_size, latitude, longitude`) are all lenient: unknown keys ignored, bad
  values default. API and the future pages (10a) share this parser.

## Cost bound (item 8)

- Queries do not depend on result count: 1 catalogue query for clinicians (`.values()` of an
  explicit field list, joined to user name, department, hospital, specialty), 1 for the
  bookable types, then `load_schedules` called **once** for all candidate ids over the whole
  horizon = 4 queries (rules, time off, appointments, holds). The buffer passed is the
  largest among candidate types; loading a superset of appointments is safe because the
  domain `free_slots` applies each type's own buffer. Total constant, about 6.
- Only providers that survive the cheap filters (text, specialty, hospital, city, type) get
  slots computed, so CPU is linear in matching clinicians x horizon, not in the catalogue.
- Slot computing walks the range in chunks of at most 31 days (the engine's cap) with the
  engine's `free_slots`, and stops at the first chunk that holds the wanted count (3 for
  a provider list, 1 for aggregates). Worst case 3 chunks per clinician with nothing free.
- The sorted set needs only first starts, so no per-result queries and no N+1 are
  possible: the view receives plain dataclasses.
- Test: same use case with 2 and with 12 matching clinicians (several hospitals, types,
  holds) runs the same number of queries, and that number is at most 8.

## Files to touch, in order

1. `scheduling/domain/search_query.py`: `SearchQuery` + `parse_search_query(raw)` (lenient).
2. `scheduling/domain/search_matching.py`: text match, attribute filters, search range,
   time-of-day.
3. `scheduling/domain/search_availability.py`: shortest type; `next_starts(...)` chunked
   over `free_slots`.
4. `scheduling/domain/search_results.py`: provider records to hospital and specialty
   aggregates.
5. `scheduling/domain/search_ordering.py`: sort keys, haversine distance, `paginate`.
6. `scheduling/use_cases/search_catalog.py`: explicit-field loading into frozen domain
   records (the leak guard: a column not named there cannot reach a result).
7. `scheduling/use_cases/search.py`: orchestration, clock from `current_request_context()`.
8. `scheduling/views/search_schemas.py`: result and page to JSON (explicit fields, UTC ISO
   starts plus `time_zone`).
9. `scheduling/views/search.py`: three `ApiView`s, `permission_classes = public()`; urls.
10. `drlibre/urls.py`: three routes before the `api/v1/` catch-all.
11. `mutation-equivalents.txt`: only for survivors proven equivalent, each with a reason.

Tests sit beside each file (`test_*.py`).

Deliberately not touched: models and migrations (no new column or index; catalogue is small
and the loads already exist), `schedule_loading.py`, `placement*`, `free_slots*`, session
and auth code (the views read no session), pages and templates (task 10a), detail
endpoints (task 11), `doc/backlog*.md` and `doc/retro.md` (orchestrator).

## Response shape (items 2, 9)

Envelope: `results, total, page, page_count, page_size`. Slot: `starts_at` (UTC, `Z`),
`clinician_id`, `appointment_type_id`, `time_zone` (hospital's IANA name).
- Provider: id, full_name, title, specialty {id, name}, hospital {id, name, city, time_zone},
  department {id, name}, appointment_type {id, name, duration_minutes}, next_availabilities
  (up to 3), `has_availability`.
- Hospital: id, name, street_address, postal_code, city, country, time_zone, specialties
  (names), bookable_provider_count, earliest_availability (slot or null),
  providers_with_availability_count, `has_availability`.
- Specialty: id, name, provider_count, hospital_count, earliest_availability, `has_availability`.
No email, phone, date of birth, bio, hospital phone, code, coordinates, patient data. The
"no availability in the next 90 days" text is rendered by the page; the API gives
`has_availability: false`.

## Invariants and blast radius

- No double booking: search is read-only and writes nothing; slots come from the same
  `load_schedules` (appointments, time off, holds with `expires_at > now`) and `free_slots`
  as `GET /slots` and placement, so a listed slot is one placement accepts. Placement still
  re-checks.
- Authorization: public views declare `public()`; no `request.user` or session read; no
  patient model is imported by the search code.
- Audit log: untouched, no write happens.
- Blast radius: new modules plus three URL lines. Existing code only gets imports.

## Trust boundaries

Only the query string crosses in, from an anonymous visitor. Validation: lenient parser in
domain (types, ranges, enums, length cap, finite coordinates in range); no value reaches SQL
except as a UUID or a model-checked id. Output: explicit field mapping at two points
(catalogue `.values()` list, view schema). The ApiView origin guard applies to writes only;
these are GET.

## Failing tests to write first (`returns_X_when_Y`)

Domain (pure, mutation-gated):
- `parse_search_query`: `returns_defaults_when_every_value_is_unusable`; `returns_size_20_when_size_is_25`;
  `returns_size_50_when_size_is_50`; `returns_page_1_when_page_is_zero_or_text`;
  `returns_soonest_when_sort_is_distance_without_location`; `returns_distance_when_location_given`;
  `returns_no_location_when_latitude_is_91_or_nan`; `returns_no_filter_when_uuid_is_malformed`;
  `returns_no_date_when_date_is_2026-13-40`; `truncates_text_at_100_characters`.
- Matching: `returns_true_when_text_is_partial_and_upper_case` for each of the six fields
  (one test each, so each field is proven); `returns_false_when_no_field_contains_text`;
  filters combine with AND (each one alone excludes).
- Time of day: 11:59 morning, 12:00 afternoon, 17:00 afternoon, 17:01 evening, in the
  hospital's zone (a case where UTC and local differ, and a daylight saving day).
- Search range: lead 120 minutes is the start; end is now+90 days; "today" ends at local
  midnight; 3 and 7 days end at now+3/7 days; earliest date after the horizon gives empty range.
- `next_starts`: returns the first 3 starts across the 31 day chunk border; returns fewer
  when fewer exist; stops after the first chunk with enough (assert by counting engine calls
  through a fake schedule, not a mock of the engine).
- Shortest type: returns the shortest; ties by name then id.
- Aggregation: hospital provider count, providers with slot count, earliest slot, specialty
  provider and hospital counts; earliest picks across providers.
- Ordering: soonest puts no-availability last; ties break on name then id; name asc/desc
  case-insensitive; distance nearest first with missing coordinates last (known haversine
  values); sorting runs on the whole set before the page is cut.
- Paging: total 45 / size 20 gives 3 pages; page 9 returns page 3; empty gives page 1 of 1;
  slice offsets correct at the boundaries.

Use case (database):
- `returns_only_active_bookable_data_when_inactive_hospital_clinician_specialty_type_exist`
  and `omits_clinician_when_department_has_no_online_bookable_type`.
- `lists_slots_equal_to_find_free_slots_when_same_type_and_range`; first listed slot is
  accepted by placement; `omits_slot_when_booking_hold_covers_it`; excludes slots with
  appointment or time off.
- `names_shortest_type_when_no_type_filtered`; `uses_filtered_type_for_slots`.
- `lists_result_after_those_with_slots_when_nothing_free_in_90_days`.
- Time filters change both list and slots (evening filter drops a morning-only clinician and
  trims the evening clinician's slots).
- `runs_same_number_of_queries_when_2_or_12_clinicians_match` for each of the three lists.
- `contains_no_planted_value_when_email_phone_birth_date_bio_hospital_phone_are_set`: plant
  distinctive strings and assert none appear in the serialised JSON of any list; plus an
  exact key set per result type.

API (`scheduling/views/test_search.py`):
- `returns_200_without_a_session_for_each_endpoint`; a request with a bad cookie still 200.
- `returns_defaults_when_page_size_is_bogus`; `returns_last_page_when_page_is_past_end`.
- Times end in `Z` and the hospital's `time_zone` is named on each slot.
- `returns_404_contract_error_for_unknown_search_path` stays working (catch-all order).

Each test proven red for the right reason before code (stage rules); `make mutate` run on
the new domain modules, survivors fixed by tests or listed with reasons.

## Domain entities used

Visitor, Hospital, Department, Specialty, Clinician (ClinicianProfile + User name only),
AppointmentType, AvailabilityRule, TimeOff, Appointment (busy intervals only, no patient
fields loaded), BookingHold.

## Will not do

No new dependency, no caching layer, no SQL full-text or trigram search, no abstraction
beyond these modules, no new model field, no refactor of `schedule_loading` or the slots
view, no pages or templates, no detail endpoints, no distance geocoding (the visitor gives
latitude and longitude).

## Architect review

Verdict: approve.

- Ladder: new pure domain modules plus one use case and three thin views; no new dependency, model or refactor. Reusing `load_schedules` and `free_slots` is the right rung. The five domain modules are each one-sentence units.
- Cost bound: checked `schedule_loading.load_schedules`. Passing the largest buffer is sound, because `free_slots` re-applies each type's own buffer to the loaded appointments. The query count is constant, and a test covers it for all three lists.
- Security: only the query string crosses the boundary. Parsing is lenient, with no SQL `LIKE`. Fields are an explicit allow-list at two points, with a planted-value test. No session is read and no write or audit entry happens.
- Tests: first tests are named as behaviours with spec values (11:59/12:00/17:00/17:01, size 25 gives 20, page past the end). Edge and error paths are covered.
- Scope: all ten items are covered. Pages and detail endpoints are correctly left out.

Notes for the implementer (not blocking):
1. 6.2 says an empty result is listed "after the results that have a free slot". The plan applies that only to the default sort and flags it. Keep that flag in the PR body, and test that name sort ignores availability.
2. When a time filter drops providers without a slot, the hospital's `bookable_provider_count` and the specialty's `provider_count` should say whether they count surviving providers. Pick one and test it.
3. The aggregates need only 1 slot per provider, so the chunk loop should stop early. The plan already says so.
