# Plan: task 11, public detail pages (+ carried 10a fixes)

Focal point: one new use case module, `scheduling/use_cases/public_details.py`, that loads
the three details from the existing public catalogue (`search_catalog`) and the existing
slot search (`search.py`). Pages and API are thin formatters over it. Nothing in booking,
placement or the slot engine changes.

## Decisions

- **Not found** = `Failure.not_found()` from the use case; page raises `Http404`, API uses
  `failure_response`. The catalogue already filters inactive hospital, inactive clinician
  user, inactive specialty and "no online-bookable type", so provider 404s come for free.
- **Hospital**: 404 only when missing or inactive (own row, `is_active=True`). An active
  hospital with no bookable provider renders with an empty state (it is not in search, but
  nothing in task item 5 forbids it). **Specialty**: same, 404 when missing or inactive;
  zero providers shows an empty state.
- **Provider type choice**: `?type=<uuid>`, unknown or not in the provider's bookable
  types falls back to the shortest (as search does), never an error. `?week=` reuses
  `week_from` and the clamp in `booking_page_data._week_shown`.
- **Hospital "first available"**: a link per (department, bookable type) to
  `times_href(type_id, None)`, the existing booking times page with no provider. No new
  slot computation.
- **API bodies** (explicit lists, never `model_to_dict`):
  provider = id, full_name, title, bio, specialty{id,name}, hospital{id,name,city,time_zone},
  department{id,name}, appointment_types[{id,name,duration_minutes}];
  hospital = id, name, description, street_address, postal_code, city, country, phone,
  time_zone, departments[{id,name}], specialties[{id,name}], providers[search provider body];
  specialty = the existing search specialty body (zero counts when no providers).
  No email, phone, date of birth of a clinician anywhere.
- Heading level of a result card becomes a template parameter (`heading_level`, default 2)
  so the hospital page keeps h1 > h2 > h3.

## Blocks and files, in order

1. `scheduling/domain/search_address.py`: `has_filters(query)` and `widened_query(query)`
   (drop filters if any; else drop text; keep sort, page size, location; page 1). Also
   `search_href(..., path="/")` keyword so the specialty page paginates on its own path.
   Pure, mutation-tested.
2. `scheduling/domain/slot_text.py`: delete `slot_spoken_text`; add nothing. The template
   writes the suffix. (Label-in-name fix.)
3. `scheduling/domain/specialty_icons.py`: unchanged; callers pass the specialty code.
4. `scheduling/use_cases/search_catalog.py`: add `specialty_code` to `CatalogProvider`;
   `load_catalog(*, provider_id=None, hospital_id=None, specialty_id=None)` filters in SQL.
5. `scheduling/use_cases/search_types.py`: `SpecialtyResult.code`.
6. `scheduling/use_cases/search.py`: `_candidates` takes the catalogue as an argument;
   `search_public` loads it with the query's hospital/specialty pushed down; new public
   `provider_results(catalog, query, now) -> list[ProviderResult]` (unpaginated, name order)
   for the hospital page and the provider's horizon check. Same query count as today.
7. `scheduling/use_cases/public_details.py` (new): `load_provider_detail(id, type_id, now)`,
   `load_hospital_detail(id, now)`, `load_specialty_detail(id, page, now)` returning
   `Result[...]`. Extra reads: provider bio by pk, hospital row (explicit fields), specialty
   row. Hospital: one catalogue load, one `provider_results`, so query count is constant.
8. `scheduling/views/pages/booking_times.py`: `week_strip(week, week_href)` takes a
   callable for previous/next links; `TimesPage` passes `times_href`.
9. `scheduling/views/pages/search_context.py`: `provider_row` public (hospital page reuses
   it), slot dicts carry `provider_name` instead of `spoken`, icon from `SpecialtyResult.code`,
   `widen_href` from `widened_query` (empty when nothing to widen), `filters_set`,
   provider/hospital/specialty hrefs on rows. Split a `search_links.py` if it passes 250 lines.
10. `scheduling/views/pages/detail_pages.py` + `detail_context.py` (new): `ProviderPage`,
    `HospitalPage`, `SpecialtyPage`. Each sets its own title and description blocks.
11. `scheduling/views/detail_schemas.py` + `scheduling/views/public_details.py` (new): three
    public `ApiView`s; bodies reuse `search_schemas` body helpers (made non-private).
12. `drlibre/urls.py`: pages `providers/<uuid>`, `hospitals/<uuid>`, `specialties/<uuid>`;
    API `api/v1/hospitals|providers|specialties/<uuid>` above the catch-all.
13. Templates: new `details/{provider,hospital,specialty}.html`; edit `search/index.html`
    (q field + Search button first, `<details class="more-filters">` with the other eight
    fields incl. sort, `open` when `filters_set`), `search/provider_result.html`,
    `hospital_result.html`, `specialty_result.html` (name links, hospital/specialty links,
    `heading_level`), `components/slot_link.html` (no `aria-hidden`; visible text, then
    hidden " with <name>"), `components/list_switch.html` (drop "(current)" text, param
    `label` for aria-label, param `aria_current`), `style.html` if it shows these.
14. `static/css/components.css`: `.search-form__main` (q grows, button aligned to field
    bottom), `.more-filters` summary and grid with `align-items: end`, provider/hospital
    detail layout (reuse card, badge, result classes); no new colours or tokens.

Not touching: models, migrations, booking use cases and pages other than item 8, slot
engine, audit, auth, JS (no script added; `search_location.js` stays), search API wire shape.

## Invariants and blast radius

- Public pages and API read no session and no patient data; only explicit column lists
  (`values_list`) reach a template or a body. Planted clinician email, phone, date of birth,
  patient name and reason must be absent from every body and page.
- Slots shown are the slots booking accepts: same `load_schedules`/`next_starts`/
  `find_free_slots`. Double booking, audit log, authorization untouched (no writes).
- Blast radius: search page markup (slot link, switch, filter layout), `week_strip`
  signature, `search_href` signature, `SpecialtyResult` and `CatalogProvider` fields. Existing
  tests of those are updated in the same step.
- No-inline-code rule: every new template passes `no_inline_code`.

## Trust boundaries

Path ids are `<uuid>` converters (others 404 by routing). Query values (`type`, `week`,
`page`, `page_size`) parsed leniently, never trusted: unknown type falls back, week clamped,
page clamped by `paginate`. Output escaped by Django autoescape; descriptions are built from
names, never from bio or description text. No sensitive data in URLs or logs.

## Domain entities

Hospital, Department, Specialty, ClinicianProfile (public word provider), AppointmentType,
AvailabilityRule/TimeOff/Appointment/BookingHold (read through existing slot loading),
Visitor, ApiClient (no right needed).

## Failing tests first (`returns_X_when_Y`)

Domain (`test_search_address.py`, `test_slot_text.py`):
- `returns_query_without_filters_but_with_text_when_a_filter_is_set`
- `returns_query_without_text_when_no_filter_is_set`
- `returns_same_query_when_neither_text_nor_filter_is_set` (and `has_filters` false)
- `returns_path_prefix_when_search_href_is_given_a_path`

Use cases (`test_public_details.py`):
- `returns_provider_detail_with_bio_types_and_hospital_when_listable`
- `returns_not_found_when_provider_user_inactive`, `..._hospital_inactive`,
  `..._specialty_inactive`, `..._department_has_no_online_bookable_type`
- `returns_not_found_when_hospital_inactive`; `returns_hospital_with_no_providers_when_none_bookable`
- `returns_hospital_phone_description_departments_specialties_types_and_providers_with_three_starts`
- `returns_same_number_of_queries_when_hospital_has_2_or_12_providers`
- `returns_not_found_when_specialty_inactive`; `returns_zero_counts_when_specialty_has_no_provider`

API (`test_public_details_api.py`):
- `returns_200_with_explicit_fields_when_provider_listable`; planted email, phone, date of
  birth, patient name and reason not in the text of any of the three bodies
- `returns_hospital_phone_when_hospital_listable` (public)
- `returns_404_when_provider_hospital_or_specialty_inactive`, `..._provider_has_no_bookable_type`,
  `..._id_unknown`; no sign-in needed (no cookie) answers 200

Pages (`test_detail_pages.py`, browser client with Origin and CSRF check):
- `returns_provider_page_with_name_title_specialty_bio_department_hospital_and_types`
- `returns_week_strip_monday_to_sunday_with_previous_and_next_links_on_the_provider_page`
  (links stay on `/providers/<id>`, keep `type`); `returns_types_switch_with_aria_current`
- `returns_slot_link_into_details_page_when_provider_slot_followed` (follow it: 200, names
  provider and slot)
- `returns_hospital_zone_name_on_every_page` ; `returns_no_availability_text_when_nothing_free_in_90_days`
  on provider and hospital page
- `returns_first_available_link_per_type_with_no_provider_when_hospital_page_opened` (href is
  `/book/<type>` without `provider`, follows to 200)
- `returns_hospital_page_with_address_phone_description_departments_specialties_providers`
- `returns_specialty_page_with_providers_of_that_specialty_only_and_pagination_on_its_own_path`
- `returns_404_page_when_inactive_or_unlisted` for all three pages
- `returns_own_title_and_meta_description_per_page`; `returns_single_h1_and_labelled_landmarks`;
  `returns_no_inline_script_or_style`; planted clinician email, phone, birth date absent
- links: search provider card links name to provider page, hospital name to hospital page,
  specialty name to specialty page; each detail page links the others it names

Search page (`test_search_page.py`, `test_search_assets.py`):
- `returns_wider_link_without_filters_when_filters_set` (keeps text); `returns_wider_link_without_text_when_no_filters`;
  `returns_no_wider_link_when_nothing_to_widen`
- `returns_slot_link_name_containing_visible_text_when_rendered` for search, week strip, new
  pages (accessible name = visible text followed by " with <name>")
- `returns_no_current_text_in_switch_but_aria_current_and_current_class`
- `returns_q_field_and_search_button_before_more_filters_disclosure`;
  `returns_disclosure_open_when_a_filter_is_set` and closed when none; all eight fields inside;
  the form submitted from the parsed HTML (fields inside `<details>` included) as a browser GET
- `returns_q_field_outside_filter_grid_when_rendered` and CSS rule `.more-filters`/`align-items: end` present
- `returns_icon_of_specialty_code_when_specialty_renamed`

Mutation: `make mutate` covers items 1 only (domain); equivalents recorded if any.
Red must fail for the right reason: missing route/function, not import typos.

## Not doing

No new dependency, no JS, no new component beyond a details wrapper in CSS, no API change to
search, no slot list on provider page beyond the week strip and a "no availability" notice,
no sort or filters on the specialty page, no caching, no refactor outside items 6, 8, 9.
Browser checks at 375 and 1440 px and the live booking stay with the orchestrator.

## Risks

Hospital page cost is `catalogue (2) + schedules (4) + hospital row + departments` constant;
the 90 day horizon scan runs once per provider in memory, so a very large hospital is CPU
bound, as search already is. CSS fixes are not provable server-side; Chrome check needed.

## Architect review

Verdict: approve.

- Ladder: reuses the catalogue, slot search, week strip and booking pages. No new dependency, JS or model. Refactors (items 6, 8, 9) are tied to the task.
- Layers: pure address logic in the domain, loading in a use case, thin views and API. Not found is a `Failure` value, and only the page turns it into `Http404`.
- Security: no writes, no session read. Explicit column lists. Tests plant clinician email, phone and date of birth. Path ids use `<uuid>` converters. Query values are parsed leniently.
- Tests: named as behaviours and cover the error paths (404s) and the query-count bound. The forms are tested as a browser sends them. All six carried 10a fixes have a test.
- Notes for the implementer, not blocking:
  - Make the query-count test cover the hospital API body as well as the page.
  - Hospital "first available" is per (department, type). If a type name repeats across departments, make the link text name the department so the links are distinguishable.
  - Test that `?week=` on the provider page outside the clamp falls back and never errors.
  - Check that a `/book/<type>` link with no provider follows to 200 for each type listed.
  - Update `doc/backlog.md` and `doc/retro.md` at merge (orchestrator).
