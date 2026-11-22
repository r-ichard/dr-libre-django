# Review: task 27d2, FHIR writes, refusals, sort (run 01M827VES12WEM5T0X11ET9WW8)

Diff read: `git diff main...HEAD`, product first. Gates reported green in the `check` stage (4900 tests); not re-run here.

## Plan in one sentence per block (§2.5)
- `domain/write_body.py`: one pure rule, "body = Transfer-Encoding or Content-Length > 0; then the type must be accepted". Confirmed at a glance. Both callers (`views/input_limits.py:36`, `views/fhir/writes.py:38`) use it.
- `fhir_search.py:130` `split_alternatives`: escape-aware splitter. Traced the loop: `\\,` -> backslash then split, correct; trailing `\` kept.
- `fhir_declaration.py:63` `sortable`: every DATE parameter plus `SORTABLE_PARAMETERS`. Use-case `sort_columns` added per type; `fhir_reads.py:316` newest-first default only when no `_sort`; `fhir_slot_reads.py:135` two-pass stable sort.
- `fhir_appointment_write.py:130`: end equal to stored or to start+duration accepted.

## Findings
1. **Blocker**, `drlibre-specs.md:764-774`. `git diff 917edd1 HEAD -- drlibre-specs.md` still shows the first run's edits (`type` in the 15.5 table, the "Search values" paragraph). Item 7 asked for the file as on `917edd1`. The run did not restore it. The specification is the owner's text; a change is blocking.
2. **Blocker**, item 7 second half missing. No list beside the section 15 tables naming what the ADRs add (each entry with its ADR), and no change to the test over the tables. Restoring the spec (finding 1) would make that test fail on `type` and on anything else the first run added, so the two must land together.
3. **Blocker**, no ADR for 27d2 (`ls doc/adr` ends at 0009). The plan promised one (items 8 and 12, null placement and the list of unnamed additions "proven by test, not asserted in the ADR"). Decisions taken here (sort values per type, `documentation` text of the CapabilityStatement, 415 `not-supported` code, end rule) are unrecorded.
4. **Medium**, `doc/backlog/` has no `27d3-*.md`. The plan gate condition (a) required it for item 3. Not in diff.
5. Low, `scheduling/domain/fhir_capability.py:47`: sort values are given in free-text `documentation`; there is no structured field. Acceptable, check with `make fhir-validate`.
6. Low, `scheduling/views/fhir/writes.py:38`: the 415 check runs before `refusal_before_body`, so an unknown resource type with a bad type says 415 not 404. Reasonable ("before the body is read"); note only.
7. Low, `fhir_appointment_writes.py:36`: `END_MESSAGE` lives in the use case, not in a table of element to message; item 3 will need to move it.
8. Proof left no trace: `prove` (8564f53) touched tests only. Good. No dependency added. No escape hatch seen in the diff.

## Tests
Derived from the task: raw-socket tests for logout without Content-Length and for `text/plain` on `/fhir` (`test_api_live_server.py:~100`), parametrized content types, sort both directions, paging under new sorts, escape table. Cannot-fail check done by `red` stage (14 failures). Item 3's single test over the declaration does not exist (declared not in this run).

## Not in this run (plan)
Item 3: every 400 under `/fhir` carries the `/api/v1` message for the same refusal, with one test over `WRITE_SHAPES` and `declaration.parameters`. Strings to replace: `REFUSED_MESSAGE` (five modules), "This element is not valid." (four), "Not valid FHIR.", `UNREADABLE_MESSAGE`, "The value cannot be read." in `fhir_search.py`.

## Left for the orchestrator
- Item 3, whole (above). The task's "Done when" names it; it was not delivered. Needs `doc/backlog/27d3-*.md`.
- Items 7 (restore spec + ADR list in the test) and the ADR: unfinished slice items, see Blocking.
- Not run here: `make mutate`, `make fhir-validate` (Java and download), a quiet-machine `make test` time.

## For the owner
- `drlibre-specs.md` still carries the first run's 27d additions (`type` in the 15.5 table; the search-values paragraph). Restoring them to `917edd1` is item 7; the paragraph's content (date prefixes, either-comma, closed code lists, `action` codes, NUL) should live in an ADR and the list beside the tables instead.
- Section 15.1 `_sort` was narrowed by ADR 0005; this run widens it to all date parameters. Needs an ADR for you to accept.

## Blocking
- Restore `drlibre-specs.md` to its `917edd1` text.
- Add the list of ADR-named additions beside the section 15 tables and make the test read it.
- Write the ADR for 27d2 decisions.

## Later
- Create `doc/backlog/27d3-*.md` for item 3 (finding 4).
- Move `END_MESSAGE` into the future element-to-message table.
- Structured `_sort` documentation, if `make fhir-validate` objects.
- Measure `make test` on a quiet machine (4900 tests, about 51 s here).

## Outcomes (address stage)
| Finding | Outcome |
|---|---|
| 1 spec edits | fixed: `git checkout 917edd1 -- drlibre-specs.md`; the 15.5 `type` row and the search-values paragraph are gone. Test: `returns_every_resource_interaction_and_parameter_of_the_spec_in_the_capability_statement` (the `type` row is out of `SPEC_RESOURCES`, so it fails without the list entry). |
| 2 list beside the tables | fixed: `ADR_ADDITIONS` in `fhir_spec_tables.py` (`AuditEvent` `type`, ADR 0009); tests read it: `returns_no_addition_to_the_spec_without_an_existing_adr_that_names_it` and the capability test. |
| 3 ADR | fixed: `doc/adr/0010-fhir-write-declaration-sort-and-search-values.md`, includes the search-value rules moved out of the specification. |
| 4 no `27d3` task file | not fixed: Later list, left alone as instructed. Item 3 of the task (messages) stays undelivered. |

## Second reading (after address)
- `git diff 917edd1 -- drlibre-specs.md` is empty; the diff against `main` is the restoration. Item 7 holds.
- `ADR_ADDITIONS` (`fhir_spec_tables.py:43`) is read by the tests; `doc/adr/0010-...` exists. Findings 1 to 3 are closed.
- The address commit touched `fhir_spec_tables.py` (test table), the surface test, the ADR and the review only. No product line.
- Item 3 is under "Not in this run" in the plan: not a blocker. It stays undelivered; the "Done when" of the task names it.

## Blocking
None.

## Left for the orchestrator
- Item 3, whole. Create `doc/backlog/27d3-*.md` (not created here).
- Run `make mutate`, `make fhir-validate`, and time `make test` on a quiet machine.

## For the owner
- Accept ADR 0010: `_sort` widened to every date parameter (section 15.1 was narrowed by ADR 0005); the search-value rules left the specification and live in the ADR.

## Third reading (after the failed `final_gates`)
- `final_gates` (3802871) failed; the `address` and `check` commits after it touched `scheduling/domain/test_fhir_clean.py` only (37 lines, tests). No product line.
- Re-ran `make mutate` here on HEAD: 6927 mutants, `scripts/mutation_survivors.py` exit 0, no unexplained survivor. The earlier failure was a survivor, now killed by the added test.
- `git diff 917edd1 HEAD -- drlibre-specs.md` is empty. No dependency added, no escape hatch in the diff, proof commits (`verify_green` to `prove`) touched tests only.
- Not run here: `make fhir-validate` (Java and a download).
- Later: the `Appointment.end` message lives in the use case (`fhir_appointment_writes.py:36`); the 415 check precedes the 404 for an unknown type (`views/fhir/writes.py:38`).

## Blocking
None.
