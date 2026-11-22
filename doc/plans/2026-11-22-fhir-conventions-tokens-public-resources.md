# Plan: task 22, FHIR API conventions, tokens and the seven public resources

Date 2026-11-22. Spec 15.1, 15.2, 15.4, 15.5 (+4, 3.1). ADR 0003 (versions, ids), ADR 0004 (failure
contract, limits) read. No UI, so Impeccable does not apply. Out: `Schedule`, `Slot`, `Patient`,
`Appointment`, every FHIR write, `AppointmentResponse`, `Communication`, `AuditEvent`, admin-user
`Practitioner`.

## Focal point

One declaration (`FHIR_RESOURCES`: type, id kind, interactions, search parameters) drives the
router, the search parser, the CapabilityStatement and the both-ways test.

One sentence: *a read-only `/fhir` door whose single declaration routes, parses and describes the
seven resources, reading through the application API's visibility rule and mapping rows to FHIR in
pure domain functions.*

## Decisions the plan fixes

- **Accept.** Served: absent, `*/*`, `application/*`, `application/json`, `application/fhir+json`
  (any `fhir+json` parameters, e.g. `fhirVersion=4.0`, accepted). `_format=json|application/fhir+json`
  likewise. Anything else (`text/html`, `application/xml`, `_format=xml`) is 406 `OperationOutcome`
  (`not-supported`). Response is always `application/fhir+json; charset=utf-8`. 406 is new to the
  contract; ADR 0005 records it (ADR 0004 says 406 cannot occur for the application API only).
- **Method not allowed.** Section 4 has no 405. Follow ADR 0004's transport rule: `not_found` 404, no
  `Allow` header, `OperationOutcome` `not-supported`. Open point in ADR 0005 (FHIR says 405).
- **Status and codes.** `Failure` code -> `issue.code`: invalid_input `invalid` (unknown parameter
  `not-supported`, unreadable value `invalid`), unauthenticated `login`, forbidden `forbidden`,
  not_found `not-found`, rate_limited `throttled`, internal_error `exception`. Statuses are the table
  in `STATUS_BY_CODE`, reused. `issue.diagnostics` = correlation id only; `issue.expression` = the
  parameter name for a refused parameter. Fixed text, never built from data.
- **Input limits** of ADR 0004 apply unchanged (`refuse_oversized`: 200 fields, body 1 MiB, bad
  `Content-Length`) and answer 400 `OperationOutcome` under `/fhir`.
- **Tokens, failed attempts (item 13).** New scope `RateLimitScope.TOKEN`: 5 failed attempts an hour
  per presented-token hash (keyed hash, `key_hash("email", ...)` slot), 20 an hour per network
  address (`REMOTE_ADDR` only). Only a *failure* records a hit; the count is checked first, a full
  counter answers 429 `throttled` before the token is looked up. Reuses `RateLimitHit` and
  `take_hit`'s lock; adds `record_failure` / `is_full` beside it. A good token is never counted.
- **Token form.** `secrets.token_urlsafe(32)` with prefix `dlk_`; hash is SHA-256 hex via
  `hash_token` from `use_cases/session.py` (one hash, same as sessions). Header only; never the
  query string (a `access_token=` parameter is a refused parameter), never the cookie: the FHIR
  authentication class does not read `SESSION_COOKIE`, and a request with a cookie and no header is
  anonymous.
- **Viewer.** `FhirViewer` = `PUBLIC` (no token, or a patient token) or `STAFF` (clinician or admin
  token). A bad token is never `PUBLIC`: it is 401 `OperationOutcome`.
- **Visibility, one rule (item 9).** Not copied: extract the filters of `load_catalog` (listable
  clinician: active user, active specialty, active hospital, department holds an active type that is
  online-bookable) into `public_clinician_filter()` and `online_only_for(user)` stay the callers' rule
  for types; `load_catalog` and the FHIR reads call the same two. Public sees: active hospital;
  its departments; rooms active in an active hospital; `HealthcareService` active, online-bookable,
  in an active hospital; active specialties; clinicians under the filter above. STAFF sees every
  row, inactive included, plus clinician email and phone. ADR 0005 states the stricter reading as an
  open point for the owner.
- **Ids and versions (ADR 0003).** `Organization` id = hospital id or department id; `Location` id =
  hospital id (site) or room id (the two id spaces are UUIDv7, no clash; the type of a read decides
  the table). `Practitioner` id = user id, `PractitionerRole` id = profile id, `HealthcareService` id
  = appointment type id. `CodeSystem` and `ValueSet` have one logical id each, `specialty`.
  `versionId` = `str(row.version)` (Practitioner: user version; role: profile version);
  CodeSystem/ValueSet: `last_value` of `scheduling_specialty_revision`. `lastUpdated` = `updated_at`
  (CodeSystem/ValueSet: max over specialties, epoch when none). A hospital's two resources share the
  hospital version. ETag `W/"<versionId>"`; `Vary: Authorization`; `Cache-Control: private` because
  content differs by viewer at the same version. No `If-None-Match` handling (not requested).
- **Canonical URLs (item 7).** Base `https://drlibre.example/fhir` is a *name*, not a host to serve:
  setting `FHIR_CANONICAL_BASE` (env, default that value). CodeSystem `<base>/CodeSystem/specialty`,
  ValueSet `<base>/ValueSet/specialty`, extensions `<base>/StructureDefinition/<name>`
  (`room-floor`, `room-capacity`, `room-equipment`, `service-buffer-minutes`, `service-colour`,
  `service-needs-room`, `service-bookable-online`, `role-round-robin-weight`, `hospital-time-zone`,
  `time-zone`). Constants in `domain/fhir_urls.py`. Hospital time zone: the standard R4
  `timezone` extension has no R4 definition, so a product extension on the Location.
- **Mapping details not in 15.2.** Practitioner: `name[0].text` = full name, title as
  `qualification[0].code.text` (titles are roles like "Cardiologist"), `active`; STAFF adds
  `telecom` email and phone; birth date never. Organization hospital: `type` coding `prov` from
  `http://terminology.hl7.org/CodeSystem/organization-type`, `address`, `telecom` phone is on the
  Location only (15.2). Department: type `dept`, `partOf` = `Organization/<hospital id>`, `active`
  true. Room Location: `physicalType` `ro`, `partOf` = `Location/<hospital id>`,
  `managingOrganization` = department Organization, `status` active/inactive. Site Location:
  `physicalType` `si`, `position`, address, phone, time-zone extension. HealthcareService:
  `providedBy` department, `type`/`specialty` from the specialties of the department's clinicians
  (one query, grouped), `active`. PractitionerRole: `practitioner`, `organization` department,
  `specialty[0]` coding in the specialty system, `location` default room, `healthcareService` =
  active types of the department, `availableTime` from `AvailabilityRule` (days of week merged per
  identical start/end, FHIR `daysOfWeek` mon..sun from weekday 0=Sunday), `notAvailable` from
  `TimeOff` (STAFF only, with `description` = reason; PUBLIC gets no `notAvailable`, since 15.4 says
  public fields only and a reason is private; open point in the ADR),
  bio as extension `role-bio` (R4 has no bio element), round robin weight extension. `active` of the
  role = user active and profile reachable.
- **Search (item 3, 11).** Parameters per 15.5 for the seven; unknown name or unreadable value ->
  400 naming it (`issue.expression`). Plain string parameters match case-insensitively on partial
  words like the public search; `type`, `partof`, `organization`, `practitioner`, `location`,
  `service`, `specialty` take `Type/<id>` or a bare id (specialty: code or `system|code`); `active`
  `true|false`; `address-city` case-insensitive contains; `near=lat|lon|distance|unit` (km or
  `[mi_i]`, distance <= 1000 km, haversine in domain over the rows' latitude and longitude, site
  Locations only; rooms have no position and never match). Repeated parameter refused
  (400). `_count` 1..100 default 20 (0 allowed -> `total` only, no entries); `_offset` is the paging
  token for `next`/`previous` (`_count` + `_offset`; huge offset refused at 1,000,000 as the page
  limit); `_sort` accepts a listed parameter or `-` prefix, only parameters that have a sort order
  (`name`, `address-city`, `active`; default by `name` then id so paging is stable); `_include`
  only `PractitionerRole:practitioner`, `PractitionerRole:organization` and only on that type
  (others 400). Included resources get `search.mode=include`; `total` counts matches only. `self`,
  `next`, `previous` built from the parsed parameters (re-encoded, never echoing the raw query).
- **Query budget (item 11).** Each search is one count query + one page query + a fixed set of
  `prefetch_related`/grouped queries per resource; asserted with `assertNumQueries`-style
  `CaptureQueriesContext` at 3 and at 30 rows: equal counts, with a ceiling stated per type.

## Blocks and files, in order

1. `domain/fhir_urls.py`, `domain/fhir_outcome.py` (Failure fields -> OperationOutcome dict),
   `domain/fhir_bundle.py` (searchset, links, entries), `domain/fhir_search.py` (parse and refuse,
   `near`, `_sort`, `_count`, `_include`; pure over a mapping), `domain/fhir_declaration.py`
   (`FHIR_RESOURCES`), `domain/fhir_capability.py` (CapabilityStatement from the declaration).
2. Mappers, one pure function each, frozen input dataclasses, no Django:
   `domain/fhir_organization.py` (`hospital_organization`, `department_organization`),
   `fhir_location.py` (`site_location`, `room_location`), `fhir_healthcare_service.py`,
   `fhir_specialty.py` (`specialty_code_system`, `specialty_value_set`), `fhir_practitioner.py`,
   `fhir_practitioner_role.py`. All under `make mutate` (`scheduling/domain/`); equivalents, if any,
   go to `mutation-equivalents.txt` with a reason.
3. Model `ApiClient` (a `Record`, not `Versioned`: a credential is not exposed, as `Session`) in `models/access.py`: `name`, `user` (PROTECT),
   `token_hash` (64, unique), `created_at`, `last_used_at`, `revoked_at`; constraints as for
   `Session` (hash length, unique, name not blank, `revoked_at >= created_at`); `fhir_not_exposed =
   "credential, never served"`. Export in `models/__init__.py`; `RateLimitScope.TOKEN` widens
   `ratelimithit_scope_listed`. Migration `0014`; `doc/data-model.md` re-rendered by
   `render_data_model`; builder in `models/builders.py`; tests of ADR 0002 (id UUIDv7, check
   constraints, unique, PROTECT, listed in data-model doc, not exposed).
4. `use_cases/api_tokens.py`: `issue_token(user, name)` (returns token once), `list_tokens()`
   (ids, name, user id, dates, no hash), `revoke_token(id)`, `resolve_token(token)` ->
   `Result[User]` (unknown, revoked, inactive user -> `Failure.unauthenticated()`, same failure for
   all three), `last_used_at` updated at most once per minute (avoids a write on every read). Each
   of issue and revoke in one transaction with its audit entry: actions `api_client.issue`,
   `api_client.revoke`; entity `ApiClient`, entity id, metadata `user_id` only (no name: a name may
   be a person). Add both to `domain/audit_labels.py` ("API token issued", "API token revoked").
   Listing is a read, not audited (reads are not).
5. `management/commands/api_tokens.py`: `issue <email> --name`, `list`, `revoke <id>`; actor is
   `None` (a shell is not a user); only `issue` prints the token, once, on stdout alone; `list` shows
   id, name, user id, state, never a hash. A patient may hold a token (item 10: it gives public rights).
6. `use_cases/fhir_visibility.py` (the shared filters; `search_catalog.load_catalog` edited to call
   it), `use_cases/fhir_loading.py` (rows to mapper inputs, bounded queries), `use_cases/fhir_reads.py`
   (`read_resource(type, id, viewer)`, `search_resource(type, query, viewer)` -> `Result`, not found
   for anything the viewer may not see: a hidden record is 404, not 403).
7. `views/fhir/` (new package, outside the forbidden folders): `authentication.py`
   (`BearerTokenAuthentication`: bad or revoked -> 401 via `AuthenticationFailed`, rate limit),
   `negotiation.py` (Accept rules), `outcome_response.py` (renders `Failure` and the 500 as
   `OperationOutcome`, `application/fhir+json`, correlation id header already added by the
   middleware), `views.py` (`FhirView` base from `ApiView` with `authentication_classes`
   overridden and its own `handle_exception`/negotiation; `ReadView`, `SearchView`, `MetadataView`,
   catch-all), `routes.py` (routes generated from `FHIR_RESOURCES`, then a catch-all for
   `^fhir/` so an unknown type, bad id (non-UUID) and wrong method answer in the contract). One
   `fhir_` field-level schema per type is not needed: the domain parser validates.
8. `drlibre/urls.py`: add `*fhir_routes()` before the pages; `RequestContextMiddleware`: treat
   `/fhir` like `/api/v1/` for the generic 500 (`generic_fhir_error()` returns the `OperationOutcome`
   500) and for the non-page error path.
9. `drlibre/settings.py` + `.env.example`: `FHIR_CANONICAL_BASE`.
10. `doc/adr/0005-fhir-conventions.md` (items above, open points: stricter visibility, 404 vs 405,
    no admin page for tokens, admin `Practitioner` deferred, `notAvailable` public exposure, one id
    for CodeSystem/ValueSet, weak ETag with `Vary`). `doc/backlog.md` line is the orchestrator's.
11. Dev dependency and validation: see next section.

Deliberately not touched: `views/pages/`, `templates/`, `use_cases/admin_*`, `static/`, the
application API's views and error body, the `Session` flow, booking and scheduling use cases.
Only edit outside new files: `search_catalog.py` (extract filter, behaviour unchanged, its tests
guard it), `middleware.py`, `urls.py`, `settings.py`, `.env.example`, `models/access.py`,
`models/__init__.py`, `models/builders.py`, `rate_limit_rules.py`, `audit_labels.py`,
`test_hostile_input.py`, `pyproject.toml`/`uv.lock`, `doc/data-model.md`.

## FHIR validity proof (item 8)

Vendor the published HL7 R4 4.0.1 `fhir.schema.json` (official JSON Schema of the standard) under
`scheduling/fhir_definitions/` with its SHA-256 pinned in a test, plus pinned dev dependency
`jsonschema` (exact version, `uv lock`). Helper `assert_valid_fhir(resource)` validates against
`#/definitions/<resourceType>`; the Bundle is validated whole, entries included. Why not
`fhir.resources`: its models are R4B (4.3.0), not 4.0.1, and are lenient on unknown keys by default
configuration; the vendored schema is the exact version and runs offline. Known limit: JSON Schema
does not check bindings or FHIR invariants (e.g. `ele-1`, `dom-6`); the tests add explicit asserts
for the invariants we can break (one `value[x]` per extension, `partOf` references well formed,
`meta.versionId` string, `Bundle.total` integer, `searchset` link relations). Risk: fetching the
schema needs network once; if the build sandbox has none, the file is committed from a host that
has it and the stage reports it.

## Failing tests first (`returns_X_when_Y`; expected values in words)

Domain (beside the code):
- `returns_organization_type_prov_when_hospital_mapped`; `returns_partof_hospital_when_department_mapped`
  (reference `Organization/<hospital id>`, type `dept`); `returns_site_location_with_address_phone_position_time_zone`;
  `returns_no_position_when_hospital_has_no_coordinates`; `returns_room_location_physical_type_ro_partof_site_managing_department`
  with floor, capacity, equipment extensions; `returns_inactive_status_when_room_inactive`.
- `returns_extensions_for_duration_buffer_colour_needs_room_online_bookable` on HealthcareService;
  `returns_code_system_with_one_concept_per_specialty_and_version_from_revision`;
  `returns_value_set_including_the_code_system`; `returns_no_inactive_concept_when_public`.
- `returns_no_email_phone_or_birth_date_when_practitioner_is_public`;
  `returns_email_and_phone_when_viewer_is_staff`; `returns_title_as_qualification`.
- `returns_available_time_merged_by_hours_when_rules_share_hours`; `returns_sunday_for_weekday_0`;
  `returns_no_not_available_when_public`; `returns_not_available_periods_when_staff`;
  `returns_round_robin_weight_extension`.
- Each mapper: `returns_meta_version_id_and_last_updated_in_utc`.
- Search parser: `returns_refusal_naming_the_parameter_when_unknown`; `..._when_value_unreadable`
  (bad uuid, bad `active`, `near` out of range, `_count` 0..101, `-5`, `abc`); `returns_100_when_count_is_100_and_refuses_101`;
  `returns_default_20`; `returns_refusal_when_parameter_repeats`; `returns_sort_descending_when_prefixed`;
  `returns_refusal_when_sort_not_listed`; `returns_refusal_when_include_not_allowed_on_type`.
- Bundle: `returns_self_next_previous_links_and_total`; no `next` on the last page, no `previous` on
  the first; `returns_outcome_with_fixed_text_and_correlation_id_in_diagnostics`.
- Capability: `returns_every_declared_resource_interaction_and_search_parameter`.

Use cases (real PostgreSQL):
- Tokens: `returns_user_when_token_valid`; `returns_unauthenticated_when_unknown_revoked_or_user_inactive`
  (same failure); stored row holds only the hash (planted token not found in any column); issue and
  revoke each write one audit entry in the same transaction (rolled back when the audit fails);
  metadata holds only ids; planted token absent from `AuditLogEntry`, captured logs, command `list`
  output, and the response of any failed call.
- Rate limit: `returns_throttled_after_5_failures_with_same_token_in_an_hour`, `..._20_per_address`,
  `returns_ok_when_good_token_after_failures_below_limit`, window rolls after an hour.
- Visibility: hidden clinician (no online-bookable type) absent from search and 404 on read for
  PUBLIC, present for STAFF; inactive hospital 404 / absent for PUBLIC and present for STAFF; the
  same clinician as `GET /api/v1/search/providers` lists, asserted from both doors with one world.
  Patient token = PUBLIC. Inactive department-room, inactive type, non-bookable type, inactive
  specialty.
- `returns_bounded_queries_when_search_page_has_3_or_30_rows` for each of the seven (equal counts).

Views (HTTP, through `Client`):
- 401 `OperationOutcome` for unknown, revoked, inactive-user token; never the public answer; token in
  `?access_token=` refused 400 and not read; session cookie alone is public, cookie plus no header
  never staff; `Authorization: Bearer` with extra spaces/wrong scheme -> 401.
- 404 unknown type, unknown id, non-UUID id, `/fhir/` and `/fhir/x/y/z`; 404 on POST/PUT/PATCH/DELETE
  with `OperationOutcome`; 406 on `Accept: text/html`; 400 on every refused parameter; 400 for the
  ADR 0004 limits (201 fields, `Content-Length: abc`, 2 MiB body); 500 path: patched mapper raising
  -> 500 `OperationOutcome`, correlation id, no exception text, no HTML, even with `DEBUG` on.
- Every response (2xx and errors): `Content-Type: application/fhir+json`, `X-Correlation-Id`, a
  sane incoming id echoed. Read answers weak `ETag` equal to `W/"<meta.versionId>"`.
- Paging: follow `next` to the end across 45 rows at `_count=20`: 20, 20, 5, each id once, `total`
  45, last page without `next`, `previous` walks back.
- `/fhir/metadata`: both directions. Declared -> answers: every (type, interaction, search param)
  of the CapabilityStatement is requested and not 400/404. Answering -> declared: every URL
  pattern under `/fhir` from the resolver (not from the declaration) is a declared type or
  `metadata`; every parameter the parser accepts is in the statement (iterate the parser's set).
- Validity: every resource of every type and the searchset Bundle (with `_include`) pass the vendored
  R4 schema, as PUBLIC and STAFF.
- `test_hostile_input.py`: the routes walk covers `/fhir/<type>`, `/fhir/<type>/<id>`, `/fhir/metadata`
  and the catch-all (add `fhir_id`/type names to world ids and the catch-all suffix rule, `Authorization`
  variants per actor); for paths starting `fhir/` additionally assert status < 500 *and* body is an
  `OperationOutcome` with `application/fhir+json` when status >= 400.
- `test_audit_action_labels.py` picks up the two new actions; add explicit label test.
- `render_data_model` test: `ApiClient` section present with `FHIR: not exposed, credential`.
- Suite time: new tests use the small builders; budget 40 s total, check with `make test`.

## Invariants and blast radius

- Server-side authorization: viewer is derived from the token's user only, never a parameter or
  header other than `Authorization`; a refused identity never degrades to public.
- Append-only audit log: only inserts via `record_audit`, inside the issue/revoke transaction; no
  FHIR read writes an audit entry.
- Double booking: untouched (no booking code touched, no write endpoints).
- Never leak: no email/phone/birth date/reason/note/hash in any public body, log, audit entry,
  outcome. `load_catalog` change is the one existing-behaviour edit: its existing tests plus a new
  test (both doors list the same clinicians) guard it. Clock from request context; `last_used_at`
  uses `current_request_context().now`.
- Blast radius: new model + migration (additive; widens one check constraint), middleware error
  path for a new prefix, `urls.py` route list, hostile-input test (shared with tasks 19 to 21, edit
  limited to the world ids and one fhir assertion to keep conflicts small).

## Trust boundaries

| Boundary | Validation and authorization |
| --- | --- |
| `Authorization` header | scheme `Bearer`, 1 to 200 chars, hashed, constant-time via DB lookup on hash; rate limited on failure |
| Query string of search | parsed by the pure domain parser against the declaration; unknown/duplicate/unreadable refused and named; size limits first |
| Path `<Type>/<id>` | type must be declared, id a UUID (or `specialty`); anything else outcome 404 |
| `Accept`, `_format` | closed list above; else 406 |
| Management command | runs with shell access; email must name an active user; names stripped, 1..100 chars; token printed once |
| Database to FHIR | explicit field lists into frozen mapper inputs, so a new model column never reaches a body by default (as `search_catalog`) |

## Domain entities (CLAUDE.md vocabulary)

Hospital, Department, Room, Specialty, AppointmentType, User (Clinician, Admin, Patient),
ClinicianProfile, AvailabilityRule, TimeOff, ApiClient (new), AuditLogEntry, BookingHold untouched.

## Not doing

No `Schedule`/`Slot`/writes/`If-Match`; no admin page for tokens (not in the spec; ADR says so);
no token scopes or expiry (spec: exactly the user's rights); no new abstraction beyond the
declaration the task asks for; no `fhir.resources` dependency; no refactor of `ApiView` (the FHIR
base subclasses it); no touching DRF settings globally; no admin `Practitioner`.
Tooling for the PR body: Claude Code via Fabro.

Skipped or unchecked in this plan: R4 invariants beyond the schema; real browser or curl run (that
is the orchestrator's). Risks: schema download needs network once; 405 vs 404 and visibility are
owner questions; `make test` budget (40 s) is tight with the 7-type query-count matrix, so build
worlds once per module.

## Architect review

Verdict: approve.

Checked against the task and conventions:
- Ladder: one declaration drives routing, parsing and the CapabilityStatement; the only existing-behaviour edit is the filter extraction in `search_catalog`, which the task demands (item 9, "same visibility rule"). No new abstraction beyond that. Vendored R4 JSON Schema plus pinned `jsonschema` is the smaller choice and the reason against `fhir.resources` (R4B) is sound.
- Tests first: behaviours named with expected values; edge and error paths covered (hidden clinician and inactive hospital from both sides, planted token, both-ways metadata test, bounded query counts at 3 and 30 rows, paging across 45 rows, 500 with DEBUG on).
- Security: token hash only, same failure for unknown/revoked/inactive, no cookie or query-string auth, failure-only rate limit with numbers, audit with ids only, hidden record is 404. Threat is named and handled.
- Architecture: pure mappers in domain, use cases own visibility and reads, views format only, one transaction with audit for issue and revoke.
- Scope: all 16 items map to a block. Admin-file keep-out list respected (edits to `test_hostile_input.py` are required by item 16).

Things to watch during build (not blocking):
1. `_sort` is limited to `name`, `address-city`, `active`. Task says "works on the parameters of 15.5". Keep the refusal naming the parameter, and state in ADR 0005 which parameters sort, so the limit is a recorded decision.
2. Size caps: seven mappers plus search, bundle and views must keep files under 300 lines and functions under 50; split `fhir_search.py` early.
3. `Practitioner` ids are user ids: restrict the table to users with a `ClinicianProfile`, and test that an admin or patient id answers 404.
4. A token read must not write on every GET: the once-a-minute `last_used_at` rule needs a test.
5. 405 vs 404 and 406 are deviations from FHIR and ADR 0004's wording; ADR 0005 must supersede that sentence explicitly.
6. The schema download needs network; if none, stop and report rather than hand-write the schema.
