# Review: task 22a, FHIR valid resources and a real client (second pass)

Diff `main...HEAD`, 54 files. Commits after `verify_green` (`28d8a57`) up to `prove` (`8b20319`) touch only `mutation-equivalents.txt` (mutant renumbering after the `fhir_search.py` change) and test files: no product or migration line changed there. Clean. `make gate` re-run: clean.

The four blockers of the first pass are closed in `ef82e97`: `make fhir-validate` (`Makefile:35`, `scripts/fhir_validate.sh`), the sample walk (`views/fhir/test_samples.py:36`), the database-side page cut (`use_cases/fhir_reads.py:222`, `_candidates`), and ADR 0005.

## Confirmed at a glance
- `domain/fhir_clean.py`: strip empties children first, keep `False` and `0`. Pure, domain layer.
- `views/fhir/views.py:42`: `csrf_exempt`, `Vary: Authorization` on every answer, `no-store` when `Authorization` is sent. Includes 401, 405 and 500 paths because the header patch runs after the `try`.
- `api_tokens.py:55`: a valid token reads no counter; failures go through `take_hit` under the advisory lock. Findings 2 and 3 of task 22 closed.
- `fhir_reads.py:_candidates`: one `UNION` ordered by `(sort_key, identifier)`, `count()` and slice in the database; test asserts `LIMIT 2 OFFSET 2` and `COUNT`.
- `views/api_clients.py` and `test_api_clients_guard.py`: shared clients enforce the cross-site check; a guard forbids a bare `Client(`.
- Pinned validator: version and SHA-256 in the script, checked after download and on cache reuse.

## Findings

1. Low, `scripts/fhir_validate.sh:26`: each run creates `drlibre_validate_<pid>` and never drops it. Databases pile up on a dev machine. Fix: drop it in the `trap`.
2. Low, `fhir_reads.py:_candidates`: sorting by `Lower(Cast(...))` now uses the database collation, where Python sorted by code point. Order of names with accents or punctuation can differ from before, and from what ADR 0005 implies. Fix: say so in the ADR, or collate `"C"`.
3. Low, `management/commands/fhir_samples.py:8` imports `scheduling.views.fhir.samples`: a command reaches into the view layer. Fine for a tool that exercises the real routes; note it.
4. Low, `scripts/fhir_validate.sh:30`: `-extension any` stops the validator judging our own extensions. Recorded in ADR 0005 with the reason.
5. Low, `without_empty` is `object -> object`; callers lose the `Resource` type.
6. Info, `views.py:49`: broad `except Exception` is logged with `logger.exception` and answered 500 with the correlation id. Not swallowed.
7. Not run by this review: `make mutate` and `make fhir-validate` (needs network and Java). The implementer reports `fhir-validate` passes in about 20 s with the jar cached; the `check` stage ran lint, test (3087 passed, 31 s) and gate.

## Blocking
None.

## Later
- Drop the throwaway validate database in the script trap.
- State or fix the sort collation difference (finding 2).
- Keep `Resource` typing through `without_empty`.
- Orchestrator: run `make mutate` and `make fhir-validate` on the host before merging.
