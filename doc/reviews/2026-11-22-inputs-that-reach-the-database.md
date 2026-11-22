# Review: task 27a, inputs that reach the database (slice: items 1, 2, 3, 6)

Diff read: `git diff main...HEAD`, 25 files. Proof window (`verify_green`..`prove`) changed tests
and `mutation-equivalents.txt` only; `refactor` touched `whole_numbers.py` and
`admin_user_support.py` (allowed). No change to `drlibre-specs.md`, models, migrations or
dependencies.

## Plan in one sentence, per block
- `whole_numbers.py`: one integer check with column bounds; confirmed at a glance, called by weight, capacity, duration, buffer.
- `text_rules.py`: one refusal of NUL, C0, DEL, C1, surrogates; tab/CR/LF only for free text; confirmed at a glance.
- `schemas.py:14`: `StrictTextRules` refuses non-strings and applies the text rule; traced once (`self.fail("invalid")`, then DRF's own length checks).
- `waitlist_window.py:21` `window_words`: last day is the day of `latest_at - 1 microsecond`; traced for midnight end, non-midnight end, zone offsets.

## Findings
- Later, `scheduling/domain/fhir_common.py:50`: still its own `"\x00" not in` check (used by FHIR search, 27b scope). Plan block 2 promised it be replaced. Smallest fix: call `check_storable_text` in 27b.
- Later, `scheduling/views/pages/admin_filters.py:71`, `admin_records.py:105`: search boxes strip NUL by `replace`, not by the rule. Harmless (no 500), but not "one rule". Fix with 27b.
- Later, `scheduling/views/auth_schemas.py:13`: login `password` is `StrictText`, so a password holding a tab or control character is refused at sign-in with the generic message. Low risk, since the password form of the page does not use it; check that no existing password policy allows such characters.
- Later, `scheduling/domain/text_rules.py:20`: per-character Python loop over the raw text; inputs are length-bounded elsewhere, but the clinical note check runs before the length check, so a very large body is scanned before refusal. Swap order or use a compiled regex if it shows in profiles.
- Later, `doc/backlog.md:106`: 27a row still says "todo" and covers items 4 and 5, which the plan put outside this run. The architect's condition (a backlog file for items 4 and 5 before merge) is not met in this diff. Orchestrator action.
- Later: `time_off_rules.py:32` maps the failure through `NOT_STORABLE_MESSAGE` again instead of using the returned failure; fine, duplicated by two lines only.
- Later: suite time: 5000 tests passed in 72.8 s in this sandbox (shared machine, not a measurement).

No swallowed errors (`whole_numbers.py:16` catches `ValueError` for the digit-count limit and returns a refusal). No `Any`, `cast`, bare ignore or noqa in the diff. No authorization or audit paths touched. No new write path.

## Left for the orchestrator
- Item 4: derived hostile-input test (pages per role from the URL configuration, every `/api/v1` request schema field, every `/fhir` write element); replaces `FIELD_NAMES` in `scheduling/views/test_hostile_input.py`.
- Item 5: one test that every refused form returns what was typed, except password and code.
- #50 (NUL in FHIR search parameters) and the other round 3 findings: 27b.
- The task's "done when" lists `make mutate` and `make fhir-validate`; neither ran in the stages shown. Run both on the host.
- The plan's FHIR write tests (weight 40000, NUL byte, `true` as `valueInteger`) and the `version` above-column test: confirm they exist; I found no FHIR test file in the diff.

## For the owner
Nothing open in the specification.

## Blocking
None.

## Later
As listed under Findings.

## Address stage: final gates
`make mutate` listed six unlisted survivors, all `single_line` mutants of `check_storable_text` callers.
- `record_fields.check_text` (mutants 5, 9) and `clinician_rules.check_title` (5, 11): fixed with `returns_message_on_field_when_a_single_line_text_holds_a_line_break` and `returns_message_on_title_field_when_title_holds_a_line_break`.
- `record_fields.check_equipment` (4) and `validate_clinical_note` (5): equivalent (`None` is falsy like `False`); listed in `mutation-equivalents.txt` with the reason.
`make mutate` and `make fhir-validate` now pass.

## Second reader (final read of HEAD)
Commits after `verify_green` to `prove` touch tests and `mutation-equivalents.txt` only; `address` adds tests and two equivalents. No product line changed in the proof window. No `drlibre-specs.md`, model, migration or dependency change. No `Any`, `cast`, bare ignore or noqa. No swallowed error. No write path, authorization or audit touched.

Later:
- `scheduling/domain/text_rules.py:20`: the plan's `fhir_common.carries_only_storable_text`, `admin_filters.py:71`, `admin_records.py:105` still hold ad hoc NUL checks; not yet "one rule". 27b.
- Plan promised FHIR write tests (weight 40000, `true` as `valueInteger`, NUL byte) and a `version` above-column test; the diff has none under `scheduling/views/fhir`. The orchestrator's own sends of 40000 and a NUL through FHIR cover it; add the tests in the next slice.
- `doc/backlog.md:106`: 27a still `todo`, covers items 4 and 5. The architect's condition (a backlog file for 4 and 5) is unmet; orchestrator action before merge.
- `scheduling/domain/time_off_rules.py:32`: discards the returned failure and rebuilds the message; harmless.
- Suite: 5002 tests in 73 s here (shared machine; not a measurement).

## Left for the orchestrator
- Item 4: derived hostile-input test; replaces `FIELD_NAMES` in `scheduling/views/test_hostile_input.py`.
- Item 5: one test that every refused form echoes what was typed, apart from password and code.
- #50 and the other round 3 findings: 27b.
- Backlog file for items 4 and 5, and the `doc/backlog.md` row.

## Blocking
None.
