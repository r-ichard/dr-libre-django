# Task 27a2: the one text rule, as a person fills a form

Slice: items 1 to 4, 7, 8, 9. Branch `task/27a-qa-round-3-inputs` (held, not merged).

## Focal point

`scheduling/domain/text_rules.py`: the rule takes `single_line` from its caller and never looks
at a field name. Each field says "one line or free" once, where it is declared; everything else
passes that value through.

## The one declaration (answers architect 1, 2, 4)

- Pages: the `FormField` in `admin_record_kinds.py` (`widget == TEXTAREA` means free text). The
  three shared fields become named constants `DESCRIPTION`, `BIO`, `EQUIPMENT`; the parser of
  each is built from that same `FormField` (`text_parser(form_field, maximum)` in
  `admin_record_forms.py` passes `single_line = form_field.widget != TEXTAREA`). No name set,
  no `FREE_TEXT_*` table, no `single_line=False` typed by hand at a caller.
- Domain callers get the flag as a required keyword: `record_fields.check_text(..., *,
  single_line)` (no default, so a new caller must decide). `check_equipment` and
  `clinical_note_rules` are free by their own declaration (equipment is a page textarea; the
  note is a page textarea). `check_name/code`, `check_title`, `full_name`, address fields pass
  `single_line=True`.
- `/api/v1`: the declaration is the schema field's class (`StrictText` free, `StrictLine` one
  line), already at the field. Its free texts are `reason` and cancellation `reason`, which are
  one-line `<input>` on pages but free in the API and in FHIR `description` of time off (as on
  `main`; tightening them would refuse text API clients send today). Listed as an open decision
  in the review under "For the owner", not decided here.
- FHIR: the element mapping in `fhir_record_write.py` / `fhir_role_write.py` carries the flag
  per element (description, `role-bio`, `room-equipment` free; names, codes, address one line).
- Comparing test: moved out of this run, see "Not in this run".

## Blocks (one sentence each)

1. `domain/text_rules.py`: message says where, from the allowed text before the refused
   character: `Remove the character after "<last 3 words, at most 30 chars>".` or `...at the start
   of the text.`; a line break in a one-line field: `This field takes one line. Remove the line
   break after "...".` The refused character is never echoed. Item 4.
2. `domain/record_fields.check_text`: required `single_line`; passes `field` and the flag to the
   rule and returns the rule's failure untouched (strip only; inner lines kept). Item 1, 3.
3. `use_cases/admin_user_support._clean_field`: delete the fixed-message check; `full_name` and
   `email` go through `record_fields.check_text`/`user_rules`, so the rule's own FieldMessage
   reaches `cleaned_values`, which already copies each `FieldMessage` (path: rule -> Failure ->
   `cleaned_values` -> `errors_by_field`; nothing rebuilds the message). `password` and `role`
   keep their checks. Item 1, 3.
4. `views/pages/admin_record_kinds.py` + `admin_record_forms.py`: as above. Item 1.
5. `views/schemas.py`: `StrictTextRules` raises the rule's message, not `NOT_STORABLE_MESSAGE`.
6. `time_off_rules`, `clinician_rules.check_title`, `clinical_note_rules`: return the rule's
   failure. Item 3, 4. `clinician_rules` reads `single_line=True`, note and time-off reason free.
7. Pages that print a fixed sentence instead of the rule's message (item 3 list):
   - `clinician_appointment.py:144` note, `NOTE_TOO_LONG` for any refusal: show the failure's
     message on `clinical_notes`; delete `NOTE_TOO_LONG` only if too-long is also a rule message.
   - `booking_code.py:67` `_verify_refused`: every INVALID_INPUT becomes `wrong_code_message`;
     a code the rule refuses shows the rule's message on `code`.
   - `booking_details.py:155` `reason_error`, `patient_waitlist.py` `_use_case_errors`,
     `admin_records.py:276`, `clinician_time_off.py`, `clinician_availability.py`: read, and
     fixed in the green stage only if a red test shows a replaced message; the red stage records
     the outcome of each in the review.
8. Item 7: `fhir_role_write.py` reads `role-round-robin-weight` as `valueInteger` only; any
   other `value[x]` key on a declared extension is refused 400 naming `PractitionerRole.extension`.
   One helper `extension_value(body, name, key)` already exists (line 85): it refuses a wrong
   key instead of ignoring it; the room and service mappers already call it, no new abstraction.
9. Item 8: `waitlist_window.window_words` returns `from <day> to <day> (zone)`; one day alone is
   `<day> (zone)`. `waitlist_card.html` label "Wanted between" becomes "Wanted".
10. Item 9: delete `fhir_common.carries_only_storable_text`; `fhir_search.py:49` calls
    `check_storable_text`. `admin_filters.search_text` and `admin_records.py:105` call the rule
    for `q`; a refused `q` is treated as empty (a search is not a write).

## The walker (item 2, answers architect 3)

`views/pages/test_text_fields_as_filled.py` over `page_walk_support` routes, signed out and each
role. For each rendered `<form method="post">`: each `<textarea>` gets `"one\r\n\r\n\ttwo"`; each
text `<input type=text|search|tel|email>` gets `"a\nb"`. Expected: textarea saved and read back
with both lines (admin forms: reading the edit page); one-line input answers 422 on that field
with "takes one line". Page forms are posted with the cross-site check enforced and `Origin` set.
Named skips, each with a reason in a dict `SKIPPED_FIELDS`:
- `reason` on booking details/review, the three cancel forms, time-off: one-line input, free in
  API/FHIR (see above); a browser cannot type a line break in it.
- `q` search inputs: GET, not a write.
- `code` on `booking/code.html`, `password`, `sign_in` `email`: not text a person saves
  (code and password are never echoed; the sign-in email is refused by the email rule with its
  own message, checked by its own existing test).
Coverage test `fails_when_a_rendered_text_field_is_neither_walked_nor_skipped`: collect every
text/textarea name of every rendered form; the set must equal walked plus `SKIPPED_FIELDS`.
Forms the world cannot render (needs a record that `make_world` does not build) are named in
`UNREACHED_FORMS` with a reason and also fail the coverage test when they become reachable.

## Files, in order

`domain/text_rules.py` (+test), `record_fields.py`, `clinical_note_rules.py`,
`clinician_rules.py`, `time_off_rules.py`, `fhir_common.py`, `fhir_search.py`,
`fhir_record_write.py`, `fhir_role_write.py`, `waitlist_window.py`,
`use_cases/admin_user_support.py`, `use_cases/admin_clinicians.py` (flag), `views/schemas.py`,
`views/pages/admin_record_kinds.py`, `admin_record_forms.py`, `clinician_appointment.py`,
`booking_code.py`, `admin_filters.py`, `admin_records.py`, `templates/components/waitlist_card.html`,
new `views/pages/test_text_fields_as_filled.py`.

Not touched: `drlibre-specs.md`, models, migrations, cross-site check, audit writing,
`mutation-equivalents.txt` unless a survivor is explained.

## Invariants and blast radius

Authorization from the session; audit entry inside each transaction; booking-hold and
double-booking code untouched. Blast radius: every text write (pages, `/api/v1`, `/fhir`) sees
the rule with a caller flag; tests that pin `NOT_STORABLE_MESSAGE` change to the new words.

## Trust boundaries

Browser form, JSON body, FHIR resource, query `q`: all validated by the domain rule before any
query or write. The message quotes at most 30 characters of allowed text before the refused
one, in the response body only (already typed by the sender). Test: a refused note with a
form feed leaves no log record (caplog) and no `AuditLogEntry` carrying the quoted words.

## Failing tests first (`returns_X_when_Y`)

- `returns_saved_text_with_lines_when_free_text_has_crlf_blank_line_and_tab` (domain, each of
  bio, description, equipment, note): both paragraphs back.
- `returns_page_saved_with_lines_when_admin_form_textarea_posts_two_paragraphs` for hospital
  and department description, room equipment, clinician bio (red now: refused).
- `returns_refusal_on_the_field_saying_one_line_when_a_one_line_field_gets_a_line_break`.
- `returns_message_with_words_before_when_text_has_a_form_feed` (`"Dear doctor\x0cthanks"` gives
  `after "Dear doctor"`, message has no `\x0c`); `returns_message_at_start_when_first`.
- `returns_the_rules_message_on_clinical_notes_when_a_note_has_a_control_character` (422, not
  "Use at most 5000 characters."); same for booking code and `/api/v1` text field.
- API: `returns_reason_with_lines_when_api_booking_reason_has_crlf_blank_line_and_tab` (cookie,
  `Origin`, CSRF enforced); `full_name` with `\n` is 422 on `full_name`, "takes one line".
- FHIR (bearer, no cookie, no Origin): `returns_saved_with_lines_when_fhir_write_carries_bio_
  description_or_equipment_with_crlf`; `returns_400_naming_Practitioner_name_when_name_has_
  line_break`; `returns_400_naming_PractitionerRole_extension_when_round_robin_weight_is_value_
  string`.
- `returns_from_to_words_when_window_covers_days`: "from Monday 23 November 2026 to Sunday 29
  November 2026"; one day: no "from", no "to".
- `returns_empty_search_when_q_holds_nul` stays, now through the one rule; no other NUL check
  remains (grep test in the review: `"\x00"` only in `text_rules.py`).
- The comparing test and the walker coverage test above.

## Domain entities

Hospital, Department, ClinicianProfile, Room, Appointment, TimeOff, WaitlistEntry, User,
VerificationCode (booking code message).

## Not doing

No dependency, model change, config file, or table of field names.

## Not in this run

- Comparing test `returns_same_free_text_fields_on_page_api_and_fhir`: every page `<textarea>` name
  (from `KIND_VIEWS`, plus `clinical_notes`) is free in the domain parser, and in the FHIR element or
  API schema when it has one; every one-line page field is one line. Needs its own run.
- Item 5: hostile-input test derived from forms, request schemas, FHIR declaration. Cost to be
  stated in its run: ~40 forms x ~6 fields x 6 values x 4 actors (~5,500 page posts, ~15 s),
  ~25 schemas x ~5 fields x 6 values (~750), ~40 FHIR elements x 6 values (~240): ~7,000
  requests, under a minute.
- Item 6: every refused form returns what was typed, apart from password and code.

## Architect review

Verdict: approve. The earlier `revise` reasons are answered in this version.

- One declaration per field: the page `FormField` widget, the API `StrictText`/`StrictLine` class and the FHIR element mapping. The domain callers have no default, so a new caller must choose. The comparing test closes the loop.
- The walker has a named `SKIPPED_FIELDS` and a coverage test that fails on an unlisted textarea or text input.
- The message path (rule, Failure, `cleaned_values`, `errors_by_field`) is named. The refused character is not echoed, and the caplog and audit test covers the quoted words.
- The slice (items 1 to 4, 7, 8, 9) contains the merge-enabling items 1 to 3. Items 5 and 6 are listed under "Not in this run" with a cost estimate for item 5.
- Watch in green: the slice is wide (about 22 files), so keep to the stated order and do not let item 10 or the walker grow past the file and function caps.
- Watch in green: `reason` stays free in the API and FHIR. This is an open owner decision, so it must appear in the review under "For the owner".
- Watch in green: the item 3 list of other pages (`booking_details`, `patient_waitlist`, `admin_records`, `clinician_time_off`, `clinician_availability`) must have each outcome recorded, not only the ones with a red test.
