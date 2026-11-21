# Review: task 11, public detail pages

Diff `main...HEAD`, 34 files. Gates reported green (lint, 1957 tests, gate). Not re-run by me.

## Proof left no trace
`verify_green` (3345def) to `prove` (b22c58f) touches four test files only
(`test_search_address.py`, `test_public_details.py`, `test_detail_pages.py`,
`test_public_details_api.py`). No product or migration line. OK.

## Plan in one sentence, per block
- `use_cases/public_details.py`: detail loaders reuse the search catalogue, so a page never shows what search would not list. Glance-confirmed.
- `search_catalog.load_catalog` filters (`provider_id`, `hospital_id`, `specialty_id`) narrow the same listable query (active user, specialty, hospital; bookable type). Not-found for inactive or non-bookable follows from it. Glance-confirmed.
- `views/detail_schemas.py`: explicit field lists, no email, phone or birth date from clinicians; hospital phone is public. Glance-confirmed.
- `public_details.load_specialty_detail`: needed tracing (hidden-but-used specialty returns not found, unused active specialty returns an empty detail). Behaviour matches the plan.
- `booking_times.week_strip`: the callback `week_href` lets provider page and times page share the strip. Glance-confirmed.

## Findings
1. **Low**, `scheduling/use_cases/public_details.py:67`: `ClinicianProfile.objects...get(pk=...)` is a third query after `load_catalog` (two) and a race could raise `DoesNotExist` if the profile is deleted between queries. Fix: add `bio` to the catalog row, or accept (rare).
2. **Low**, `scheduling/use_cases/public_details.py:108-112`: `load_specialty_detail` runs the search twice (summary and providers). Cost bounded, not growing per provider. Fix: reuse one result if it becomes hot.
3. **Low**, `scheduling/views/public_details.py:41`: specialty API ignores paging and returns the search body only; matches the plan ("same body keys as search"), but the provider list for a specialty is not in the API. Fix: none unless section 14 asks for it.
4. **Info**, `scheduling/domain/search_address.py:49`: `# type: ignore[arg-type]` names its code and predates this diff (main line 18). Not a new hatch.
5. **Info**, `scheduling/use_cases/public_details.py:21`: `PLAIN_QUERY` is module-level and runs `parse_search_query({})` at import. Pure, harmless.

## Checks
- Authorization: all three API views `public()`, pages open to everyone; no identity read; ids from path as UUID converters. No payload-sourced rights.
- Input: `type` and `week` query values parsed defensively (`_uuid_or_none`, `week_from`); garbage falls back, no 500.
- Double booking: no writes in this diff. Not applicable.
- Tests: planted-value test over providers, hospitals, specialties; query-count test with 2 vs 12 providers at API and use-case level; label-in-name, aria-current, widen link, titles and meta, no inline script or style. Derived from the spec list. No test of the HTML hospital page query count (use case count covers the loader; template adds no queries visible here).
- Scope: no dependency added; CSS additions small. Carried 10a fixes all present (widen link, label in name, no "(current)" text, More filters `<details>` open when set, aligned row, icon by code).
- Names, comments: roles clear; docstrings short.

## Blocking
None.

## Later
- Fold `bio` into the catalogue row to drop the extra query and the `DoesNotExist` window (finding 1).
- Decide whether the specialty API should list its providers (finding 3).
- Orchestrator browser check at 375 and 1440 px, booking from provider page and hospital "first available": not runnable in the sandbox.
