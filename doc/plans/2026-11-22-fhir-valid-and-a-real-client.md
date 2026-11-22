# Plan: task 22a, FHIR API, valid resources and a real client

Date 2026-11-22. Reads: task 22a, ADR 0005, review of task 22, `views/fhir/*`, `use_cases/fhir_reads.py`,
`fhir_loading.py`, `api_tokens.py`, `rate_limits.py`, `fhir_capability.py`, `fhir_search.py`, hostile-input test.
No UI, so Impeccable does not apply. No migration, no new dependency (the validator and a Java runtime are
fetched by a make target, never installed by `make setup`).

## Focal point

*Everything `/fhir` serves is one function away from valid FHIR (`without_empty` at the single response choke
point), proven by the HL7 validator on one sample set; and `/fhir` answers every method and header as FHIR JSON
because it is a bearer-token door that never reads a cookie.*

## Blocks, one sentence each

1. **`domain/fhir_clean.py` `without_empty(value)`**: recursively drops `None`, `""`, `[]`, `{}` (after children
   are cleaned; `False` and `0` stay), returns a new value. Called once in `resource_response`
   (`views/fhir/responses.py`), so mappers, Bundle and OperationOutcome all pass it. Under `make mutate`.
2. **CapabilityStatement** (`domain/fhir_capability.py`): add `description` and `implementation`
   (`description`, `url` = `CANONICAL_BASE`) for cpb-2 and cpb-14; empty `searchParam` is dropped by block 1.
3. **Staff services on PractitionerRole** (`fhir_loading.practitioner_roles` takes the type queryset;
   the staff build passes `AppointmentType.objects.all()`, the public one `bookable_types()`). One viewer, one
   set of visible services, same as `Part.rows`.
4. **`@csrf_exempt` on `fhir_entry`**, and a method that is not GET on a known type or `metadata` answers 405
   with `Allow: GET` and an `OperationOutcome` (`not-supported`, fixed text) via a new
   `method_not_allowed_response` in `responses.py`. Unknown type still 404. The body is never read.
   Order stays: size, Accept, token (bad token 401), route.
5. **Repeatable `_include`** (`domain/fhir_search.py`): `_include` alone may repeat; each value must be
   declared; duplicates collapse; order is the declaration's, so the Bundle `self` link is stable. Every other
   parameter repeated is still 400. `fhir_reads._included` returns the union (practitioners, then organizations).
6. **Headers** (`fhir_entry`, covers the 500 path too): `Vary: Authorization` always (`patch_vary_headers`);
   `Cache-Control: no-store` when the request carried an `Authorization` header, whatever the answer.
7. **Token failures** (`api_tokens.resolve_token`): look the token up first. Valid: success, no counter read, so
   nobody's failures refuse it. Invalid: `take_hit(TOKEN, token_key, address)` (the existing locked check-and-insert):
   `False` is 429, `True` is 401. `is_full` and `record_hits` lose their only caller: delete them and their tests.
   Counter limits unchanged (5 per token, 20 per address); only failures count, as before.
8. **Count and cut in the database** (`fhir_reads`): per part, annotate `sort_key = Collate(Lower(Cast(col, Text)), "C")`
   (C collation = Python codepoint order, so page order is unchanged), `candidate_id`, `part_index`;
   `first.union(*rest)` (DISTINCT, as today's `.distinct()`), `order_by(sort_key, candidate_id)`, `.count()`
   and `[offset:offset+count]`. Only the page is built. Move `Viewer`, `Part` and the part table to
   `use_cases/fhir_parts.py` so `fhir_reads.py` stays under 300 lines.
9. **Samples** (`views/fhir/samples.py`, `fhir_samples(get) -> dict[filename, body]`, `get` = callable taking path and
   optional token): each of the 7 types as public and as staff (first id from a search; staff token passed),
   search Bundle without and with both `_include`s, `metadata`, a 404 `OperationOutcome`. One list serves block 10 and
   the test of block 11. Includes a clinician with no service (the empty-array case).
10. **`make fhir-validate`**: `manage.py fhir_samples <dir>` (new small command beside `render_data_model.py`: issues an
    admin token for the seeded admin, drives Django's in-process client with host `localhost`, writes files; no server,
    no background process) and `scripts/fhir_validate.sh`: throwaway DB `drlibre_validate_$$`, migrate, `seed_demo`,
    command, then fetch (into git-ignored `.cache/fhir-validate/`, checksum verified with `sha256sum -c` from a pinned
    file `scripts/fhir_validate.sha256`) the HL7 `validator_cli.jar` at a pinned release and a pinned Temurin 17 JRE
    tarball; run `java -jar validator_cli.jar -version 4.0.1 -tx n/a <dir>/*.json`; exit non-zero on any error line,
    print warnings. The implementer downloads once to record the two checksums; the plan does not invent them.
    Not in `make test`, not in `make setup`. **Time in the sandbox**: expected 2 to 4 minutes first run
    (about 150 MB download, JVM start, loading the R4 package without terminology), 1 to 2 minutes cached; the
    implementer measures it and writes the real figure into ADR 0005. If the sandbox has no network the target
    fails with a clear message and the run says so plainly instead of claiming a pass.
11. **Tests' clients** (`scheduling/views/api_clients.py`): `browser_api_client()` = `Client(enforce_csrf_checks=True)`
    that sends `Origin` and keeps the cookie; `fhir_client(token=None)` = enforcing client that sends bearer only,
    never `Origin`, never a cookie. A guard test (AST scan, like `collection_guard`) fails when a test module under
    `scheduling/views/` outside `pages/` builds `Client(` directly; those modules move to the helpers mechanically.
    `pages/` is not touched (tasks 19 to 21); it keeps `browser_client`.
12. **ADR 0005**: record decisions for 1 to 10; delete open points "Inactive references", "Caching", "Validation of the
    JSON"; "Which clinicians are public" and "Token expiry" stay. Rewrite the "method other than GET (404)" bullet to
    405, the "Search" bullet for the repeat rule (only `_include` repeats; a repeat adds to the union; nothing else
    repeats, because a repeat of a filter would mean AND/OR we do not serve), the "Failed attempts" bullet (valid
    token never refused; lock; 429 only for a failing token), and the 405 `Allow` note for task 23 to extend.

## Files, in order

`domain/fhir_clean.py` + test; `domain/fhir_capability.py` (+ its test); `domain/fhir_search.py` (+ test);
`views/api_clients.py` + guard test; `use_cases/fhir_loading.py`, `fhir_parts.py` (new), `fhir_reads.py`;
`use_cases/api_tokens.py`, `rate_limits.py` (+ their tests); `views/fhir/responses.py`, `views/fhir/views.py`;
`views/fhir/samples.py`; `management/commands/fhir_samples.py`; `scripts/fhir_validate.sh`,
`scripts/fhir_validate.sha256`, `Makefile`, `.gitignore` (`.cache/`); FHIR and hostile-input tests moved to the
helpers; `mutation-equivalents.txt` only for a survivor with a real reason; ADR 0005; `doc/backlog.md` untouched
(orchestrator).

Deliberately not touched: `scheduling/views/pages/**`, `scheduling/templates/**`, `use_cases/admin_*`, models,
migrations, `/api/v1` views (CSRF there is the Origin check in `ApiView`, unchanged), session code, the sign-in
use of `take_hit`.

## Invariants and blast radius

- Authorization stays server-side from the bearer token; a token still gives exactly its user's rights; the cookie is
  never read under `/fhir`; nothing under `/fhir` writes, so double booking and the audit log are not reachable.
  `csrf_exempt` is safe because no cookie authenticates there (ADR 0005); a test sends a valid session cookie plus
  a foreign `Origin` to a write and asserts 405 JSON, and that the cookie never turned it into a staff answer.
- Failure counters: a valid token is never refused; a failing token or address still hits 429 at 5/20; the
  check-and-insert is under the advisory lock; no token or hash is logged or put in an answer.
- Visibility: staff services shown on a role equal the staff `HealthcareService` set; public unchanged.
- Page order unchanged (collation `C`, same tiebreak by id); `total` equals the old candidate count.
- Blast radius: `/fhir` only, plus `resolve_token` and the two rate-limit helpers (sole caller). Sign-in limits use
  `take_hit` as before.

## Failing tests to write first (red for the right reason, then prove they can fail)

Domain (`test_fhir_clean.py`, hypothesis plus examples, killed under mutmut):
- `returns_value_without_none_empty_string_list_and_object_when_nested_deeply`
- `returns_object_without_key_when_its_children_all_clean_away`
- `keeps_false_zero_and_nonempty_text`; `does_not_change_its_input`; `drops_empty_items_of_a_list_and_keeps_order`
- `capability_statement_has_description_and_implementation_url`; `capability_statement_names_no_empty_search_param_list`
  (after the response clean: no `searchParam` key for `CodeSystem` and `ValueSet`).
- `returns_both_includes_when_include_repeated`, `returns_one_include_when_same_include_repeated`,
  `returns_refusal_naming_parameter_when_filter_repeated`, `returns_refusal_when_repeated_include_is_undeclared`.

Use case / view (enforcing `fhir_client`, no Origin, no cookie):
- `returns_405_with_allow_get_and_operation_outcome_when_post_put_patch_delete_on_known_type` (list, read, `metadata`;
  content type `application/fhir+json`, body `resourceType == "OperationOutcome"`).
- `returns_404_json_when_write_to_unknown_type`; `returns_json_when_foreign_origin_and_session_cookie_sent`;
  `returns_401_json_when_write_with_bad_token`.
- `returns_role_without_healthcareservice_key_when_clinician_has_no_service` (staff and public).
- `returns_healthcare_service_reference_on_role_when_staff_token_can_read_it` (type not online-bookable: referenced for
  staff, absent for public; the referenced id reads 200 with the same token).
- `returns_200_with_practitioners_and_organizations_included_when_include_repeated`.
- `returns_vary_authorization_on_every_answer` (200, 400, 401, 404, 405, 406, 429, 500 path);
  `returns_no_store_when_token_sent_and_not_when_public`.
- `returns_200_for_valid_token_when_twenty_bad_tokens_came_from_its_address` and
  `returns_429_for_bad_token_when_address_counter_full`; `returns_401_then_429_after_five_bad_tries_of_one_token`;
  a concurrent test (`transaction=True`, threads, as the sign-in lock test does) `never_overshoots_limit_when_failures_race`.
- `searches_with_a_fixed_query_count_and_returns_same_pages_as_before` (existing bound test stays) plus
  `returns_correct_total_and_page_when_offset_and_count_cut_two_part_type` (Organization: hospitals and departments,
  sorted by name, by `-name`, by `active`, offset past the end).
- `returns_no_empty_array_object_string_or_null_in_any_sample` (cheap guard in `make test`, walks `fhir_samples`
  over `seed_demo` plus the no-service clinician; error path lists the JSON path of the offender).
- `fails_when_a_test_module_builds_a_bare_client` (guard of block 11).
- Hostile-input test: `/fhir` paths use `fhir_client`, assert status never 500 and `Content-Type` starts with
  `application/fhir+json`, for every method and every hostile header it already sends plus `Origin` and `Cookie`.
  A bad `Host` is rejected by Django before any view and answers HTML 400; the plan does not claim to cover it, the
  ADR says so.

Proof for the HL7 run is `make fhir-validate` itself: first run on current code must show the five known errors
(reproduction), then pass.

## Trust boundaries

Bearer header (parsed exactly, hashed, compared by hash, failure counted under lock); query string (declaration
parser, size limits before parsing); body and cookies (ignored, never read); `Origin` (ignored on `/fhir`,
still enforced by `ApiView` on `/api/v1`); downloaded validator and JRE (pinned version, sha256 verified, run only from
a git-ignored directory, samples passed as file arguments; the make target, not `make setup`, fetches them).

## Vocabulary

ApiClient, User (Clinician, Admin, Patient), Hospital, Department, Room, AppointmentType, ClinicianProfile,
AvailabilityRule, Specialty, RateLimitHit scope `token`. FHIR names stay FHIR (HealthcareService, PractitionerRole).

## Will not do

No write interaction (task 23); no `Allow` for writes yet; no token expiry or scopes; no change to `/api/v1` CSRF; no
global patch of Django's `Client`; no second serializer; no cache layer beyond the two headers; no new dependency;
no Node; no edit of `pages/`; no `HEAD`/`OPTIONS` interaction (405 with `Allow: GET`).

## Checks at hand-off

`make lint`, `make test` (under 40 s: the union query and sample test add little; measure), `make gate`,
`make mutate`, `make fhir-validate` (measured time written into ADR 0005). Anything not runnable in the sandbox
(network for the validator) is reported as not run.

## Architect review

Verdict: approve.

- Ladder: one cleaning function at the single response choke point, no new dependency, no abstraction without a second caller. Moving `Viewer`/`Part` to `fhir_parts.py` is justified by the 300-line cap. Samples serve both the validator target and the guard test, so they have two callers.
- Every block states its purpose in one sentence; vocabulary matches CLAUDE.md.
- Tests are named as behaviours and are red-first. They cover the error paths: 405 for every method on list, read and `metadata`, a foreign `Origin` plus session cookie, a bad token, a valid token behind 20 bad ones, a concurrent race, and the offset past the end.
- Security: `csrf_exempt` is justified because `/fhir` never reads a cookie, and a test proves the cookie never changes the answer. A valid token is never refused. The failure counter sits under the existing lock. The validator download is pinned and checksummed, and the target only runs it from an ignored directory.
- Scope: points 1 to 10 and the ADR are all mapped to blocks. The `/api/v1` tests are covered by the bare-client guard, and `pages/` is untouched.

Watch items for the implementer (not blockers):
- The `union` with `Collate(Lower(Cast(...)), "C")` can fail on PostgreSQL when the column types differ across parts. Keep the query-count test and the page-order equivalence test against the old Python order.
- Record the real validator checksums and measured time. If the network is missing, report `make fhir-validate` as not run.
- The sample set must include `Cache-Control` and `Vary` only where the guard walks the bodies, so the headers need their own test (already planned).
