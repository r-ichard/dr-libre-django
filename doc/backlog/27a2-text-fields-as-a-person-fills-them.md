Task 27a2: the one text rule, as a person fills a form.

Runs on the branch of task 27a (`task/27a-qa-round-3-inputs`), which is verified and
held, not merged. Its gates pass from a fresh clone, and in the container stack #33
(a weight above 32767), #38 (a NUL byte), #45 (a number as a reason) and #41 (the
waitlist window, at hospitals on both sides of UTC) are fixed on the pages, `/api/v1`
and `/fhir`. The orchestrator found the defects below with a browser's requests against
that stack. If the whole does not fit one run, the slice is items 1 to 3: they alone let
the held branch merge. Reproduce each defect with a failing test before the fix.

What task 27a broke:

1. A text of two paragraphs is refused in three admin forms, with "Remove the character
   that cannot be saved.": the clinician's `bio`, the department's `description` and
   the hospital's `description`. Each is a `<textarea>`, and a browser sends its line
   break as `\r\n`. On `main` they are saved. `record_fields.check_text` and
   `admin_user_support._clean_field` now call the text rule with `single_line=True` for
   every field they see. A field that is a textarea on a page is free text everywhere:
   on the page, in `/api/v1` and in the FHIR element that carries it. Whether a field is
   one line is said once, where the field is declared, and the form reads its widget
   from that, so the two cannot disagree again.
2. One test walks every form the product renders, signed out and as each role (the
   walker of `page_walk_support.py`), and for every `<textarea>` posts a text with
   `\r\n`, an empty line and a tab: it is saved, and read back with its lines. For every
   one-line text input it posts a line break: refused on that field, with a message
   that says the field takes one line.

What a refusal says:

3. The clinician's note page answers "Use at most 5000 characters." for a note that
   holds a control character: the page prints its own sentence for any refusal of the
   note. A page shows the message the rule returned, on the field it names. Find the
   other pages that replace a rule's message with a fixed one, list them in the plan,
   and fix them.
4. "Remove the character that cannot be saved." asks a person to find a character they
   cannot see; a form feed or a vertical tab comes in with text pasted from a document.
   The message says where it is, by the words in front of it, without echoing the
   character.

Carried from task 27a (items 4 and 5 of `doc/backlog/27a-qa-round-3-inputs.md`):

5. The hostile-input test derives its targets instead of listing them: every field of
   every form the product renders, by its `name`; every field of every request schema
   of `/api/v1`; every element a write of the FHIR declaration accepts. Each gets the
   hostile values (a NUL byte, an over-long text, a number beyond 64 bits, a negative
   number, a wrong type, markup) and none answers 500. Say in the plan how many requests
   this is and what it costs.
6. One test shows that every form of the product, refused, comes back with what was
   typed, apart from a password and a code.

Small, seen on the way:

7. `PractitionerRole` accepts the round robin weight as `valueString` ("5") where the
   server writes `valueInteger`: an extension's value has the type the declaration
   gives it, or the write is refused naming the element (task 23, rule 11).
8. The waitlist reads "Wanted between Monday 23 November 2026 to Sunday 29 November
   2026": "from … to …", or one day alone, from the function task 27a added.
9. From the review of 27a: `fhir_common.carries_only_storable_text`,
   `admin_filters.py` and `admin_records.py` still have their own check for a NUL byte.
   One rule.

The orchestrator saves two paragraphs in every textarea of every admin form, pastes a
form feed into a clinical note, and reads the messages.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
