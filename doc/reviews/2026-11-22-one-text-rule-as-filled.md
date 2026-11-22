# Review: task 27a2, the one text rule as a person fills a form

Base: `1991449` (run start). Slice declared in the plan: items 1 to 4, 7, 8, 9.
Proof commits (`verify_green`..`prove`) changed tests only: confirmed, no trace left.
`drlibre-specs.md` not changed. No dependency added. No type escape hatch seen in the diff.

## Confirmed at a glance
- `text_rules._message`, `failure.field_messages`, `waitlist_window.window_words`,
  `fhir_role_write.role_values` weight check, `time_off_rules`, `schemas.StrictTextRules`:
  one-sentence plans hold.
- `clinician_appointment.py:143` `saved.field_messages[0]`: safe, both refusals of
  `validate_clinical_note` build `invalid_input` with a field.

## Findings

1. **Blocker, item 1, `scheduling/domain/record_fields.py:16,30-38`.** The "said once where
   the field is declared" requirement is not met. The run adds a name set
   `FREE_TEXT_FIELDS = {"description","equipment","bio"}` and `single_line: bool | None = None`,
   which the plan rejected ("no name set", "required keyword, no default"). The page
   `FormField` widget (`admin_record_kinds.py:47,88,131`) is untouched, so widget and rule are
   two declarations again: a new textarea field named otherwise is refused as one line, the
   defect this task exists to remove. Fix: make `single_line` required, build each parser from
   its `FormField` (`widget != TEXTAREA`), delete the set.
2. **Blocker, item 2, no walker test.** `views/pages/test_text_fields_as_filled.py` (plan,
   "The walker") is absent; also the comparing test
   `returns_same_free_text_fields_on_page_api_and_fhir` and the coverage test. Only five
   hand-picked page tests exist (`test_text_as_filled.py`), covering hospital/department
   description, hospital name and clinician bio. Room equipment, FHIR bio/description/equipment
   with `\r\n` and API `reason` are not shown as promised. Item 2 is inside the merge-enabling
   items 1 to 3.
3. **Blocker, item 3, `scheduling/views/pages/booking_code.py:67-72`.** `_verify_refused` still
   replaces every INVALID_INPUT with `wrong_code_message`; plan block 7 listed it. The plan's
   list of other pages (`booking_details`, `patient_waitlist`, `admin_records`,
   `clinician_time_off`, `clinician_availability`) has no recorded outcome in the plan or here;
   the task asks them listed and fixed. Fix: record each outcome in the plan; show the rule's
   message on `code` where the rule refused.
4. **Blocker, item 9, one NUL rule.** Still own checks:
   `scheduling/domain/fhir_common.py:50-52` (`carries_only_storable_text`, used at
   `fhir_search.py:49`), `views/pages/admin_filters.py:71`, `views/pages/admin_records.py:105`
   (`.replace("\x00", "")`). Plan block 10 not done. Fix: call `check_storable_text`, treat a
   refused `q` as empty, delete the helper.
5. **Later, `record_fields.py:34` docstring** says the declaration is "the same the form's widget
   follows"; false until finding 1 is fixed.
6. **Later, `fhir_role_write.py:94`** refuses only `valueString`; `valueDecimal`, `valueBoolean`
   and other keys on the weight extension still ignored. Plan says any other `value[x]` key is
   refused. Wrong-typed `valueInteger` is left to the later check.
7. **Later, test quality.** `test_text_as_filled.py:41` asserts only the substring "This field
   takes one line."; does not check it appears on the named field.

## Blocking
- Item 1: name set `FREE_TEXT_FIELDS` and defaulted `single_line` instead of one declaration
  (`record_fields.py:16,30-38`).
- Item 2: walker, comparing test and coverage test missing.
- Item 3: `booking_code.py:67-72` still fixed message; other pages' outcomes unrecorded.
- Item 9: three own NUL checks remain.

## Later
- Findings 5 to 7.
- `make mutate` and `make fhir-validate` not run by this stage; the last gate must run them.
- Test suite took ~66 s in the sandbox (shared machine; orchestrator to measure).

## Left for the orchestrator (plan, "Not in this run")
- Item 5: derived hostile-input test (cost stated in the plan: ~7,000 requests, under a minute).
- Item 6: every refused form returns what was typed, apart from password and code.
- Plus the unfinished slice items 1 (declaration), 2, 3 and 9 above.

## For the owner
- `reason` (booking, cancellation, time off) is one-line `<input>` on pages but free text in
  `/api/v1` and FHIR as on `main`. Tightening would refuse text API clients send today. Open.

## Outcomes (address stage)

| # | Outcome |
|---|---------|
| 1 | fixed. `single_line` is a required keyword of `check_text`; the name set is gone. Page parsers read it from the `FormField` widget (`admin_record_forms.FREE_TEXT_NAMES`); domain and use-case callers say it explicitly. Proof: `test_text_fields_as_filled.py::returns_no_refusal_when_a_textarea_gets_paragraphs_and_a_tab`, red when the page rule is made one-line everywhere. |
| 2 | partly fixed. Walker (`form_walk_support.py`, `test_text_fields_as_filled.py`): both walk tests and the coverage test `returns_every_declared_textarea_walked_when_the_forms_render`. The walker proves no refusal for a textarea, not a read back of both lines. Not fixed: the comparing test across page, API and FHIR (`returns_same_free_text_fields_on_page_api_and_fhir`); needs its own run. Skipped fields are named with reasons in `SKIPPED_FIELDS`. |
| 3 | fixed. `booking_code.py` shows the rule's message on `code`: `test_booking_code_page.py::returns_the_rules_message_when_the_code_holds_a_form_feed`. Other pages checked, each already shows the rule's message on its field: `booking_details` (`form.add_failure`), `patient_waitlist` (`failure_messages`), `admin_records` (`errors_by_field`), `clinician_time_off` (`errors_by_field`), `clinician_availability` (`errors_by_field`). The wrong-code message with tries left stays: it is a use case refusal, not a rule. |
| 9 | fixed. `fhir_common.carries_only_storable_text` deleted; `fhir_search`, `admin_filters.search_text` and `admin_records` use `text_rules.check_storable_text` (via `storable_search`); a refused search text searches for nothing. Existing FHIR and page search tests cover NUL. |

## Second read (after address)

Base `1991449`. `drlibre-specs.md` unchanged, no dependency added, proof commits (`verify_green`..`prove`)
touched tests only.

Confirmed fixed by reading the code: item 1 (`record_fields.py:26-37` `single_line` is a required
keyword; page parsers read the widget through `admin_record_forms.py:29-37`), item 3
(`booking_code.py:53` shows the rule's message), item 9 (`"\x00"` no longer appears in product code
outside `text_rules.py`; `storable_search` at `text_rules.py:24`). Items 4, 7, 8 as before.

### Findings

1. **Blocker, item 2, `scheduling/views/pages/test_text_fields_as_filled.py:84-98`.** The task says a
   textarea text is "saved, and read back with its lines". The walker only asserts that the
   sentences "This field takes one line." and "Remove the" are absent from the answer. A post that
   fails for another reason (a required field missing, a 403, a 500 page without those words) or
   that saves nothing passes. The plan (line 75) promised a read back. The address stage says so in
   its outcome table ("proves no refusal, not a read back") and leaves it. A promised test is
   missing, and item 2 is inside the merge-enabling items 1 to 3. Fix: after the post, assert a
   303 (or the form's success status) and read the value from the edit page or the database and
   compare it with `PARAGRAPHS` (trimmed).
2. **Blocker, item 2, comparing test missing.** `returns_same_free_text_fields_on_page_api_and_fhir`
   (plan lines 30-34, 137) does not exist. Item 1 of the task requires that a textarea field is
   free text in `/api/v1` and FHIR as well; only hand-picked tests (`test_api_text_fields.py`,
   `test_fhir_role_writes.py`) show it for some fields. Nothing makes a future mismatch fail. Fix:
   add the test as planned, or move it out of the slice in the plan and list it under
   `## Not in this run` (the plan still promises it).
3. **Later, `admin_record_forms.py:29-31`.** `FREE_TEXT_NAMES` is derived from the widgets, but by
   field name across all kinds: a name that is a textarea in one kind and an input in another would
   be free in both. No such collision today; the comparing test would catch it.
4. **Later, `test_text_fields_as_filled.py:91-98`.** The one-line walk checks the sentence
   anywhere on the page, not on the named field.
5. **Later, `fhir_role_write.py:94`.** Only `valueString` is refused on the weight extension;
   `valueDecimal`, `valueBoolean` stay ignored. Task item 7 says an extension's value has the type
   the declaration gives it.
6. **Later, `test_text_fields_as_filled.py:83`.** Local import inside a test function; move to the top.

## Blocking (second read)
- Item 2: walker does not read back what it saved (`test_text_fields_as_filled.py:84-98`).
- Item 2: comparing test across page, API and FHIR is promised in the plan and absent.

## Later (second read)
- Findings 3 to 6 above; the first read's finding 7 stands.
- `make mutate` and `make fhir-validate` not run in this stage; the last gate runs them.
- Test suite ~49 s in the sandbox (shared machine; orchestrator measures).

## Left for the orchestrator
- Item 5: derived hostile-input test (cost in plan: ~7,000 requests, under a minute).
- Item 6: every refused form returns what was typed, apart from password and code.
- Plus the two blockers above if not finished.

## For the owner
- `reason` is a one-line `<input>` on pages but free text in `/api/v1` and FHIR. Tightening refuses
  text API clients send today. Open.

## Outcomes (address stage, second read)

| # | Outcome |
|---|---------|
| 1 | fixed. The walker posts to each textarea and asserts 303 on edit forms (create forms are posted with other fields empty, so only the refusal sentence is checked), then reads the text back from the form's page and compares it: `test_text_fields_as_filled.py::returns_no_refusal_when_a_textarea_gets_paragraphs_and_a_tab` (needs `saved >= 4`). The walk now reaches the hospital, department, room and clinician edit pages (`page_walk_support._record_ids`); before, their ids were a zero UUID and answered 404. Equipment reads back as items. |
| 2 | not fixed, moved out. Plan "Not in this run" now holds the comparing test; it needs its own run. |

## Third read (after the second address)

Base `210f0fb` (end of the previous task run). `drlibre-specs.md` unchanged, no dependency added,
proof commits (`verify_green`..`prove`) touched tests only. The only suppression added is
`# type: ignore[arg-type]` with its code, in a test.

Confirmed: the walker now asserts 303 on edit forms and reads the saved text back
(`test_text_fields_as_filled.py:84-98`, `saved >= 4`). The comparing test is listed under
"Not in this run" in the plan, so it is not a blocker. `"\x00"` appears in product code only in
`text_rules.py`.

### Findings (all Later)
1. `admin_record_forms.py:29-36`: `FREE_TEXT_NAMES` is by field name across all kinds; a name that is
   a textarea in one kind and an input in another is free in both. No collision today.
2. `test_text_fields_as_filled.py:91-98`: the one-line walk checks the sentence anywhere on the page,
   not on the named field.
3. `fhir_role_write.py:94`: only `valueString` refused on the weight extension; `valueDecimal` and
   `valueBoolean` are ignored.
4. Create forms are checked only for the refusal sentence, not a read back.
5. Suite ~47 to 73 s in the sandbox (shared machine; orchestrator measures).
6. `make mutate` and `make fhir-validate` not run in this stage; the last gate runs them.

## Blocking (third read)
None.

## Left for the orchestrator
- Comparing test `returns_same_free_text_fields_on_page_api_and_fhir`.
- Item 5: derived hostile-input test (~7,000 requests, under a minute, per the plan).
- Item 6: every refused form returns what was typed, apart from password and code.

## For the owner
- `reason` is a one-line `<input>` on pages but free text in `/api/v1` and FHIR. Tightening refuses
  text API clients send today. Open.
