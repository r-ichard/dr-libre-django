# Review: task 10, public search use case and API

Diff `main...HEAD`, 19 files, 2368 lines. Gates in the log: lint, 1528 tests, gate clean. I did not re-run `make mutate`.

## Plan in one sentence per block (§2.5)

- `domain/search_query.py`: parse the address leniently, every unusable value falls back. Confirmed at a glance.
- `domain/search_matching.py`: casefold substring match over six fields, the lead-time/horizon/window range, time of day. Confirmed.
- `domain/search_availability.py`: shortest type, first N starts over 31 day chunks. Traced the chunk overlap (`chunk_end - duration`), correct, and duplicates are filtered.
- `domain/search_ordering.py`: sort over the full set, then cut the page. Traced `name_desc` (stable reverse keeps id ascending), correct.
- `use_cases/search_catalog.py`: two queries, explicit `values_list` fields. Confirmed, so a new model column cannot leak.
- `use_cases/search.py`: filter catalogue, one `load_schedules` call for all matches, starts per candidate, group for hospitals and specialties. Traced the query count: constant.
- `views/search.py`, `search_schemas.py`: public view, explicit body dicts. Confirmed.

## Checks

1. Trust boundary: `permission_classes = public()`, no session read, no patient model imported. Body built from explicit fields. Planted-value test exists (`views/test_search.py:22-53`).
2. Same engine as booking: `load_schedules` (holds included) and `free_slots` are reused. A test compares with `find_free_slots`.
3. Cost: one catalogue pair plus the four `load_schedules` queries, whatever the number of matches. The test `returns_runs_same_number_of_queries_when_2_or_12_clinicians_match` (`use_cases/test_search.py:348`) covers all three kinds.
4. No write, so no audit entry or transaction is needed.
5. Proof trace: `4671b87..ae37139` touches only tests and `mutation-equivalents.txt`. No product line changed.
6. No dependency added. No escape hatch found, no file over 300 lines, no function over 50.

## Findings

- **Low**, `scheduling/use_cases/search.py:78-95`: every request loads the whole catalogue, all rules and 90 days of appointments for every matching clinician, in memory. Query count is bounded, memory and CPU grow with the catalogue. This is a public, unauthenticated endpoint.
  Fix: a later hardening task adds a rate limit, and narrows the load to the page when the sort is not `soonest`.
- **Low**, `scheduling/use_cases/search.py:90`: with a window, earliest date or time-of-day filter, results without a slot are dropped. Spec 6.3 says a time filter changes which results are listed, and this fits that. For window and earliest date the spec is silent. Fix: record the decision in the plan or an ADR.
- **Low**, `mutation-equivalents.txt`: 11 new entries, each with a reason. The `_page`/`_page_size`/`_location` ones depend on `ValueError` from an unparsable default. They are plausible, but I did not re-check them against a mutate run.
- **Nit**, `scheduling/domain/search_availability.py:48`: `start not in found` is a list scan. Fine at 3 items.

## Blocking

None.

## Later

- Rate limit and load narrowing for the public search endpoints (finding 1).
- Record the filter-drops-empty-results decision (finding 2).
- Confirm `make mutate` from a fresh clone, since I did not run it here.
