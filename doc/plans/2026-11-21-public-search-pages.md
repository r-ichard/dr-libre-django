# Plan: task 10a, public search pages

One sentence: the root path becomes a server-rendered GET form over the existing `search_public` use case, with the address built by a pure, mutation-tested function and the results rendered by components that reuse task 05a and the booking links of task 12a.

Focal point: `scheduling/views/pages/search_page.py` (parse, call use case, format). Everything else feeds it.

## Address (section 6.5)

`GET /?q=&list=providers|hospitals|specialties&specialty=&hospital=&city=&appointment_type=&from=&window=&time_of_day=&sort=&page=&page_size=&latitude=&longitude=`. Same names as the API of task 10, parsed by the existing `parse_search_query`, so an unusable value falls back silently (section 4). `list` is new: unknown value falls back to `providers`. Every link the page builds is rebuilt from the parsed query (never echoed from the raw string): shared links come out clean, only known keys.

## Blocks (one sentence each)

1. `scheduling/domain/search_address.py` (new, pure): `search_href(query, kind, **changes)` returns the canonical address with defaults omitted; changing anything but `page` resets `page` to 1; `parse_list_kind(raw)` returns the kind or `providers`.
2. `scheduling/domain/specialty_icons.py` (new, pure): maps a specialty `code` to a vendored icon file name; unknown code returns the one fallback file.
3. `scheduling/domain/slot_text.py` (new, pure): the visible and spoken text of one slot (`Tue 3 Dec, 09:30` visible; `Tuesday 3 December 2030 at 09:30 with Dr Ada Okafor` spoken) in the hospital's zone, and the zone name.
4. `scheduling/use_cases/search_filter_options.py` (new, read-only): choices for the filters (specialties, hospitals, cities, appointment types) from `load_catalog()` public fields only; no write, no audit entry.
5. `scheduling/views/pages/search_page.py` (new): `SearchPage` replaces `RootPage`; reads `request.GET`, calls `search_public(kind, query, current_request_context().now)`, builds the context, renders. Public: no role guard; header user comes from `PageView`.
6. `scheduling/views/pages/search_context.py` (new): view-model: rows per kind, slot links via `details_href` (type, provider, instant) and `times_href` (all times), page links via block 1, list-switch links, page-size links, widen-search link (keeps `q` and list, drops filters and sort).
7. Templates (new): `search/index.html` (form, switch, results), `search/provider_result.html`, `search/hospital_result.html`, `search/specialty_result.html`, `components/slot_link.html`, `components/list_switch.html`, `components/specialty_icon.html`. Reused: `field`, `select`, `empty_state`, `pagination`, `notice`. `base.html`: `{% block description %}` meta description, and header "Sign in" link when nobody is signed in, name plus home link (`/patient/`, `/clinician/`, `/admin-console/` by role) when signed in. `home.html` deleted.
8. Filter form: one GET form, no `csrf_token`; visible `<label>` per control (search box, specialty, hospital, city, appointment type, from date, window, time of day, sort), hidden inputs keep `list`, `page_size`, location; a submit button "Search". Page resets because the form carries no `page`. Sort `distance` option is rendered only when `query.location` is set.
9. `static/js/search_location.js` (new, ~20 lines, served from `/static`): reveals a "Use my location" button (rendered `hidden`), fills `latitude`/`longitude` hidden inputs from `navigator.geolocation` and submits; on refusal shows nothing new. Page fully usable without it. No inline script; CSP `script-src 'self'` unchanged.
10. `static/icons/specialties/*.svg` (new): only icons for the codes in the demo seed (cardiology, dermatology, general practice, paediatrics, orthopaedics) plus `fallback.svg`; `static/icons/specialties/SOURCE.md` records healthicons.org repository, commit revision, the CC0/licence text and the file-to-name mapping. Fetched in the implementation stage from the pinned revision; if the sandbox has no network the stage says so and stops (no icon drawn from memory).
11. `static/css/components.css`: result card, slot link list (2.75rem targets, wraps at 375 px, grid columns at 1440 px), list switch with current marked by text and style (not colour alone), filter grid (one column, then 2 to 4), icon sizing, `.button-row`. `style.html`: show list switch, result card (with slots, without availability), slot link.
12. Carried fix, calendar: `scheduling/domain/calendar_event.py` line 43: `"\;"` becomes `"\;"`. `pyproject.toml`: pytest `filterwarnings = ["error"]`; any other warning surfaced is fixed at its source, not ignored.
13. Carried fix, spacing: `static/css/base.css`: `.page > .notice, .page > .card { margin-block: var(--space-4) }` and `.button-row` (flex, wrap, gap `--space-3`, margin-top `--space-4`); the four booking templates that put buttons in a bare `<p>` (`confirmation.html`, others found by grep) use `.button-row`. Tokens only.
14. `drlibre/urls.py`: `path("", SearchPage.as_view())`, import changed. `public_pages.py`: `RootPage` removed, `StylePage` stays.

## Order of work

Domain 1 to 3 with tests; warnings gate and calendar fix (12); use case 4; icons (10); context and view (5, 6); templates, CSS, script (7 to 9, 11); spacing (13); urls (14).

## Not touching

`search.py` and the search domain modules, API search views and schemas, booking use cases and booking pages' logic, models, migrations, `focus_first_error.js`, the security-header settings. No new dependency, no new setting, no inline script or style.

## Invariants

- No double booking: the page only links; booking checks again. A taken slot fails cleanly on the details page (task 12a).
- Authorization server-side: the page reads no payload identity; the header uses the session's user only. Search reads the catalogue through explicit field lists (task 10), so no private column reaches the context.
- Audit: no write on this page, so none. Clock from request context.
- Never cached: `render_page` sets never-cache headers.
- No sensitive data in URLs or logs: the address holds search text, filters and (if given) location the visitor typed or allowed. Location is never stored or logged. Test: no `latitude` in the response headers or logs beyond the visitor's own address.

Blast radius: `urls.py` root, `base.html` (every page gets a header link and a description block), `components.css`/`base.css`, `pyproject.toml` (every test now fails on a warning), `home.html` removal (existing tests that read the old root text).

## Trust boundaries

| Boundary | Validation |
| --- | --- |
| Query string, every key | `parse_search_query` plus `parse_list_kind`; unusable value silently defaults; text capped at 100; all output auto-escaped. |
| Latitude, longitude | Parsed as finite floats inside range or dropped; distance sort offered only when valid. |
| Slot links | Built from use-case results (ids, UTC instants), never from the query. |
| Geolocation script | Writes two numeric inputs; the server validates them again. |
| Session cookie | Resolved by `PageView`; only for the header. |

## Failing tests to write first

Domain:
- `returns_default_free_address_when_query_is_all_defaults` (`/`); `returns_only_changed_keys_when_query_has_text_and_filters`; `returns_page_one_when_a_filter_changes`; `keeps_page_when_only_page_changes`; `keeps_every_other_parameter_when_page_size_changes` (text, filters, sort, list, location survive); `returns_providers_when_list_is_unknown`; `returns_percent_encoded_text_when_text_has_ampersand_and_space`.
- `returns_fallback_icon_when_specialty_code_is_unknown`; `returns_cardiology_icon_when_code_is_demo_cardiology`.
- `returns_zone_name_and_local_time_when_slot_is_in_sydney` (23:30 UTC shows 10:30 next day, zone `Australia/Sydney`); `returns_spoken_text_with_day_time_and_provider`.

Use case:
- `returns_active_public_choices_only_when_filter_options_are_loaded` (inactive hospital, specialty and offline type absent).

Views (`scheduling/views/pages/`, frozen clock, planted clinic):
- `returns_200_without_sign_in_with_title_and_meta_description_at_root`.
- `returns_provider_list_with_the_columns_of_6_2_by_default`: name, title, specialty, hospital, department, city, type name and minutes, zone named, 3 slot links.
- `returns_slot_link_to_details_with_type_provider_and_start_when_slot_is_listed`; `returns_all_times_link_to_times_page_for_the_type_and_provider`.
- `returns_earliest_slot_and_counts_on_hospital_list`; `returns_provider_count_hospital_count_and_earliest_on_specialty_list`.
- `returns_no_availability_in_the_next_90_days_after_results_with_slots_when_provider_has_none`.
- `returns_total_count_page_and_page_count_and_sizes_10_20_50`; `returns_last_page_when_page_is_out_of_range`; `keeps_every_parameter_in_page_and_size_links`.
- `returns_same_results_when_address_is_shared` (new client, same address, same body).
- `returns_default_filters_silently_when_values_are_invalid` (bad uuid, bad date, bad window, bad page: 200, no error text).
- `offers_distance_sort_only_when_location_is_in_the_address`.
- `returns_empty_state_with_widen_link_when_nothing_matches` (link keeps text and list, drops filters).
- `submits_as_a_plain_get_form_a_browser_sends`: parse the rendered form fields, submit them with `Client.get` and compare to the expected address; asserts no `csrfmiddlewaretoken` in the form and `Origin` irrelevant (GET). Sign-out form in the header, when signed in, posts through `browser_post` and answers 303 (guards the base layout change).
- `shows_sign_in_link_when_visitor_and_name_and_home_link_per_role_when_signed_in`.
- `never_contains_clinician_email_phone_birth_date_or_patient_data` (planted values in clinician, patient, appointment; absent in every list kind, HTML and the address).
- Accessibility the server can prove: one `h1`; list switch is a `nav` with a name, a link per list, `aria-current="page"` on the current and a word "current" not colour alone; every control has a `<label for>`; each slot link text carries day, time and provider (`visually-hidden` part); icons have `aria-hidden` and the name is written beside; results are in an ordered list in the order of the use case; no inline `script`, `style` or `style=`; script file referenced with `src`; icons exist as static files and the fallback file exists.
- Static assets: `returns_icon_files_only_for_used_codes_with_source_and_licence_recorded` (SOURCE.md names revision and licence; every `.svg` referenced by the mapping exists and no unreferenced one).
- Spacing: `puts_button_row_class_on_booking_confirmation_buttons`; CSS file test: base.css contains `.button-row` and the notice/card margin rule using `var(--space-`.
- Warnings: `drlibre/test_warnings_fail.py`: `returns_error_when_a_warning_is_raised_in_a_test` (a warning inside `pytest.raises` proves the filter is on is not enough; check `pytest.ini_options.filterwarnings == ["error"]` via config) and `compiles_every_module_without_syntax_warning` (`compileall` with `-W error` over `scheduling` and `drlibre`, which fails on `"\;"` today).
- Calendar: `returns_escaped_semicolon_when_text_has_a_semicolon` (exists; stays green).

## Domain entities (section 3)

Visitor, Patient, Clinician (public word provider), Hospital, Department, Specialty, AppointmentType, ClinicianProfile, Appointment (only as the target of a booking link, none read), User (header name only).

## Not doing

No detail pages (6.6), no client-side filtering, no map, no autocomplete, no new component beyond slot link, list switch and specialty icon, no caching layer, no refactor of the search use case, no change to the API. Browser check at 375 and 1440 px, keyboard-only booking from a result, and the accessibility audit are for the orchestrator; this suite proves only the server-rendered HTML.

## Architect review

Verdict: approve. Smallest sufficient change, right layers (pure domain, read-only use case, thin view), no new dependency, security and scope covered.

Notes for the implementation stage (not blockers):
- Block 12 reads `"\;"` becomes `"\;"`: identical strings, a typo. The fix is `"\;"` (line 43 of `calendar_event.py`). Keep the existing escape test green and let the compileall test prove it.
- The view tests name the columns of 6.2 only for providers. Add expected values for the hospital columns (address, city, specialties offered, bookable-provider count) and the specialty columns (provider count, hospital count), not only "earliest slot and counts".
- Add a test that results with no availability sort after those with slots (6.2), at the page level.
- `filterwarnings = ["error"]` may surface third-party warnings; fix at source or narrow with a named, commented entry, never a blanket ignore.
- Icons: stopping when the sandbox has no network is right; do not draw icons from memory.
