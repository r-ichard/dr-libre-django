# Task 27a3: the mutation gate on the held branch

Slice: items 1 to 4, whole task (tests and `mutation-equivalents.txt` only, no product code).

## Starting state (`make mutate` run here, matches the task list)
Survivors: `parse_search` 96, 132; `time_off_failures` 16, 22, 23; `check_code` 5, 17;
`role_values` 98, 99, 103-107, 109-111. Stale entries: `parse_search` 98, 134.

## Focal point
`scheduling/domain/test_*.py` of the four modules, plus `mutation-equivalents.txt`.

## Blocks (one sentence each)
1. `test_time_off_rules.py`: add three tests.
   - `returns_no_failure_when_the_reason_holds_a_line_break`: reason `"Back\nsoon"` gives `[]`; the reason is free text (§9.3), so mutant 22 (`single_line=True`) dies.
   - `returns_end_and_reason_failures_when_both_are_wrong`: `ends=START` with reason `"a\x00b"` gives fields `["ends_at", "reason"]`; mutant 23 (`=` for `+=`) drops `ends_at` and dies.
   - Mutant 16 (`single_line=None`) is equivalent: `None` is falsy exactly like `False` in `_is_refused`. One line in `mutation-equivalents.txt`.
2. `test_record_fields.py`: `returns_message_on_field_when_a_code_holds_a_line_break`: `check_code("ab\ncd")` fails on `code` with the single-line message `This field takes one line. Remove the line break after "ab".`. A code is one line, so mutants 5 (`None`) and 17 (`False`) both die.
3. `test_fhir_role_write.py` (240 lines now, stays under 300): `role_values` extension type rule. Only assertions that pass on current code are committed. What the code refuses today (`fhir_role_write.py:93-97`):
   - `role-round-robin-weight` (declared `valueInteger`): `valueInteger=3` accepted into `round_robin_weight`; `valueString="3"` refused, returns `"PractitionerRole.extension"`. `valueBoolean` and `valueDecimal` are NOT refused (ignored, no weight set). No test for those two.
   - `role-bio` (declared `valueString`): `valueString="Hello"` accepted as `bio`; no `bio` extension gives `bio == ""`. A non-string `value[x]` is NOT refused (read as `""`). No test for it.
   - Tests: `returns_weight_when_the_weight_is_an_integer`, `returns_extension_name_when_the_weight_is_a_string`, `returns_bio_when_the_bio_is_a_string`, `returns_empty_bio_when_no_bio_extension`.
   - Mutants 98, 99, 103-107, 109-111 (verified with `mutmut show`: each alters the url, key or returned name of the `valueString` refusal line) all die from the weight-string test alone: it pins the url, the key and the returned name. The test is run against each of them, not assumed.
   - Gaps for the review, under "Later": weight with `valueBoolean`/`valueDecimal` and bio with a non-string value are accepted silently, though item 3 of the task asks every other `value[x]` refused naming the element. Under "For the owner": `drlibre-specs.md` does not name these extensions or their types (grep found no `role-bio`, `round-robin-weight` or `valueInteger`), so the declaration in `fhir_practitioner_role.py:54-56` is the only source; the owner decides whether to refuse them (product code, a later task).
4. `mutation-equivalents.txt`:
   - `parse_search` 98 and 134: delete the entries. 98 is now killed (`alternatives = None` fails any valid value).
   - Add `x_parse_search__mutmut_96` (`problem = False` to `None`) and `x_parse_search__mutmut_132` (`_sort` default `[""]` to `["XXXX"]`) with the reasons of the old 98 and 134.
     Same mutants: shown by `uv run mutmut show` on each (the diff text equals the old reason) and by `git show` of the function before `f4d6503` for the old numbers. The function gained two lines above them, so every number shifted by 2. The report says so.
   - Add the time off 16 entry.

## Files, in order
`test_time_off_rules.py`, `test_record_fields.py`, `test_fhir_role_write.py`, `mutation-equivalents.txt`.
Not touched: every non-test `*.py`, `drlibre-specs.md`, `scripts/`, `Makefile`.

## Failing tests first
Run each new test against the mutant it targets: `mutmut run <mutant>` or `mutmut show` and apply by hand. The test must fail on it and pass on the real code. The real code passes all of them today, so "red" is the mutant, not the product.

## Invariants and blast radius
Test and text-file changes only. Double booking, server-side authorization and append-only audit are untouched. No trust boundary is crossed: these are pure domain functions, with no request, no session, no ORM.

## Vocabulary
Clinician (ClinicianProfile bio and round-robin weight), TimeOff, Room, Department, Specialty.

## Will not do
No product code (a branch nobody needs is named under "Later"). No new abstraction or dependency. No edit to the specification.

## Done when
`make mutate` prints nothing stale or unlisted. Then `make setup && make lint && make test && make gate && make mutate` and `make fhir-validate` from a fresh clone.

## Architect review
Round 1 verdict: revise. Addressed: block 3 now lists per extension what is refused today, commits only passing assertions, names both gaps under Later / For the owner, and shows mutants 98-111 die from the passing weight-string test alone. The garbled xfail sentence is gone. The parse_search 96/132 equality is shown in the report with `mutmut show` diffs against the old 98/134 text, and the kills of 22/23 are run.

Round 2 verdict: approve. Slice is the whole task, tests and one text file, nothing in product code. Claims about `role_values` (lines 93-97) match the code: only a `valueString` weight is refused. Each block states its purpose in one sentence. Kills are run against each mutant, with the real code green. Block 3 commits only assertions that pass today and names the two silent-acceptance gaps (weight with `valueBoolean`/`valueDecimal`, bio with a non-string value) under "Later" and "For the owner". That is the honest reading of item 3 given "tests and equivalents only". Item 3's "each other value[x] refused" is therefore met only for `valueString` on the weight; the review must say so plainly. Remaining checks for the implementer: run `mutmut show` for 96/132 against the old 98/134 text before moving the entries, and keep `test_fhir_role_write.py` under 300 lines.
