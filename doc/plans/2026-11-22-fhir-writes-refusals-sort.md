# Plan: task 27d2, what a FHIR write must declare, what a refusal says, sorting by time

Slice: items 1, 2, 7, 4, 5, 6, in that order (each is small and independent of the rest).
Item 3 (a message of its own on every 400 under `/fhir`) is the widest: it touches about ten
use cases and every search refusal. See "Not in this run". Item 4 starts it for one element.

## Focal point

One pure rule in the domain layer, `scheduling/domain/write_body.py`, answers "does this write
carry a body, and does it say JSON". Both `/api/v1` and `/fhir` call it. It replaces the inline
logic of `refuse_non_json_write` (`scheduling/views/input_limits.py:29`). The rest of the slice
hangs off two other single places: the declaration (`fhir_declaration.py`, sort) and the one
value splitter (`fhir_search.py:_read_value`, escape).

## Blocks (one sentence each)

1. `scheduling/domain/write_body.py` (new, pure, mutation-gated):
   `unsupported_media_type(content_length, transfer_encoding, content_type, accepted) -> str | None`.
   Body = `Transfer-Encoding` present, or `Content-Length` a number above 0. Absent or `""` =
   no body (RFC 9112 6.3). Returns the offending media type when a body is not in `accepted`.
2. `scheduling/views/input_limits.py:refuse_non_json_write`: calls block 1 with
   `("application/json",)`; no logic of its own, still raises `UnsupportedMediaType`.
3. `scheduling/views/fhir/writes.py:write` (top, after the unauthenticated check, before
   `refusal_before_body` and before `request.body` is read): calls block 1 with
   `("application/json", "application/fhir+json")`. A hit returns 415 and an
   `OperationOutcome` (`not-supported`) from a new `unsupported_media_response` in
   `scheduling/views/fhir/responses.py`, next to `not_acceptable_response`. The text is fixed;
   the media type is never echoed.
4. `scheduling/domain/fhir_appointment_write.py:_moved_element`: accept `end` equal to the stored
   end or to `start + stored duration`; any other stays `Appointment.end`. A missing `end`
   stays refused.
5. `scheduling/use_cases/fhir_appointment_writes.py:_refused`: a message for
   `Appointment.end` of its own ("The end is never taken from the client: leave it as stored or
   give the start plus the duration."), the generic one for the rest. This is the seed of
   item 3, kept to one element.
6. `scheduling/domain/fhir_search.py`: `split_alternatives(value)` (new, pure) reads `\,` as a
   comma and `\\` as a backslash, splits on every other comma. `_read_value` uses it for every
   kind that splits. A backslash before anything else stays a backslash.
7. `scheduling/domain/fhir_declaration.py:sortable`: names in `SORTABLE_PARAMETERS` plus every
   parameter of kind DATE (`date`, `sent`, `start`, `birthdate`). `parse_search` already reads
   `-name` and `descending`.
8. `scheduling/use_cases/fhir_reads.py:Part.sort_columns` and `_candidates`: add `date`/`sent`/
   `birthdate` columns per part: booked `starts_at`, waitlist `offered_appointment__starts_at`,
   hold `starts_at`, Communication `created_at`, AuditEvent `created_at`, Patient `date_of_birth`,
   Schedule `valid_from`. The current `prefix` line flips direction whenever a part has
   `newest_column`; it must flip only when no `_sort` was given, or `_sort=date` on AuditEvent
   would be descending. Rows with no value (a waitlist entry without an offer, a patient without
   a birth date) sort as PostgreSQL does: last ascending, first descending; the ADR says so.
9. `scheduling/use_cases/fhir_slot_reads.py:search_slots` (line 135): sort by `start`,
   reversed for `-start`; ties by schedule id, ascending in both directions so a page is stable.
10. `scheduling/domain/fhir_capability.py:_resource`: `documentation` of each type names its
    `_sort` values, both directions ("`_sort`: name, -name, ..."), read from `declaration.sortable`.
    A type with none says so. The validator accepts `documentation` (markdown).
11. `drlibre-specs.md`: `git checkout 917edd1 -- drlibre-specs.md`. Nothing else edits it.
12. `scheduling/views/fhir_spec_tables.py`: `AuditEvent` parameters lose `type` again (the letter of
    15.5). A new list `ADDITIONS` beside the tables, each entry `Addition(type, parameter, adr,
    quote)`, names `AuditEvent.type` and ADR 0009 with the sentence it holds. Also names the other
    additions the first run put in the paragraph, if the test shows any served and unnamed.
13. `scheduling/views/test_fhir_surface.py`: served parameters = spec parameters plus the list's
    entries for the type; each entry's quote must be in its ADR (reuses `_adr_text`). Still fails
    on anything served that neither names.
14. `doc/adr/0010-fhir-write-declaration-sort-and-escape.md` (new): media types, no body without
    `Content-Length`, the `end` rule, `_sort` values and null placement, escape, and that it
    narrows ADR 0005's `_sort` line. Move the first run's paragraph on search values (prefixes,
    UTC day, comma = either, closed lists, `action` vs `type`, NUL) into ADR 0009/0010 if 0009
    does not hold it all; 0009 line 57 holds `action` only.
15. `doc/reviews/2026-11-22-fhir-writes-refusals-sort.md` (review stage): "For the owner" says what
    the spec leaves open and the ADR decides: 415 for a wrong type, `_sort` on dates, the `end`
    rule, the escape, and that the spec was put back.

## Files, in order

`write_body.py` + test, `input_limits.py`, `views/fhir/responses.py`, `views/fhir/writes.py`,
`fhir_appointment_write.py`, `fhir_appointment_writes.py`, `fhir_search.py`,
`fhir_declaration.py`, `fhir_reads.py`, `fhir_slot_reads.py`, `fhir_capability.py`,
`fhir_spec_tables.py`, `test_fhir_surface.py`, `drlibre-specs.md` (restore), ADR 0010,
`mutation-equivalents.txt` only if a survivor is truly equivalent.

Not touched: authorization (`refusal_before_body`, `fhir_caller`), the database schema,
`fhir_outcome.py`, `/api/v1` response shapes, `fhir_search.py` date parsing, `fhir_dates.py`,
audit writing, templates and CSS.

## Invariants and blast radius

- Authorization stays server-side and first: 415 comes after "unauthenticated", before any
  database read. It reveals nothing a caller without rights could not already learn from the media type.
- Double booking and append-only audit: not touched. The `end` rule only widens what
  `decode_update` accepts; the reschedule still goes through `place_appointment` and its audit entry.
- The end is never taken from the client (5.2): the accepted `end` is checked, never stored.
- Blast radius: every write under `/api/v1` and `/fhir` (block 1). A write with no body and
  any type passes, as before. A write with a body and `text/plain` or `application/xml` is now
  415 under `/fhir`. `application/json; charset=utf-8` still passes (parameters are cut).
- Sorting changes only requests that were 400 before, except AuditEvent default order, which must
  stay newest first.

## Failing tests first (`returns_X_when_Y`)

Domain, `scheduling/domain/test_write_body.py`, a table:
- `returns_none_when_content_length_is_absent_or_empty_and_type_is_text_plain`
- `returns_none_when_content_length_is_0`
- `returns_text_plain_when_content_length_is_2_and_type_is_text_plain`
- `returns_text_plain_when_transfer_encoding_is_chunked_and_there_is_no_content_length`
- `returns_none_when_a_body_says_application_fhir_json` and with `; charset=utf-8`, upper case
- `returns_application_xml_when_a_body_says_so`; the empty media type of a body is refused.

Views:
- `returns_415_and_an_operation_outcome_when_a_fhir_write_says_text_plain` (booking body that was
  201 before: expect 415, no appointment row). Same for `application/xml`.
- `returns_the_validation_outcome_when_a_fhir_write_says_application_json` and `fhir+json`.
- `returns_no_415_when_a_fhir_delete_has_no_body_and_no_type`.
- `test_api_bodyless_writes.py`: also with `CONTENT_LENGTH=""` set in the environ, every write
  route of the walk: no "not readable" and no 415.
- Live server, `test_api_live_server.py`, bytes over a raw `socket`, no `urllib`: exactly the
  request line, `Host`, and the credentials (session cookie for `/api/v1/auth/logout`, bearer
  for `DELETE /fhir/Schedule/<id>` or another own write). Expect not 400 and not 415. Then a
  `text/plain` body with its `Content-Length` to each API: expect 415 (api: `unsupported_media_type`
  contract answer, fhir: OperationOutcome).
- Reschedule: `returns_200_and_moves_the_appointment_when_only_start_is_changed` (stored end kept,
  expect new start and end = new start + duration); `returns_200_when_end_is_start_plus_duration`;
  `returns_400_naming_Appointment.end_with_its_own_message_when_end_is_another_time`.
- Sort: for each date parameter, a table with hand-written ids in time order, ascending and
  descending: `Appointment.date`, `Communication.sent`, `AuditEvent.date`, `Slot.start`,
  `Schedule.date`, `Patient.birthdate`; `AuditEvent` default stays newest first; `_sort=bogus`
  still 400. Rows with no value land where the ADR says.
- Capability: `returns_the_sort_values_of_each_type_in_its_documentation`, over the declaration
  (a new date parameter is covered by itself).
- Paging (`test_fhir_paging.py`): parametrise the follow-`next` test over each type's `sortable`
  values and both directions.
- Escape, domain table: `name=Smith\, John` is one alternative `Smith, John`; `a,b` two; `a\\,b`
  is `a\` and `b`; a trailing `\` stays; a reference and a code split the same way. A view test:
  `returns_the_patient_named_Smith_comma_John_when_the_comma_is_escaped`.
- Spec: `test_fhir_surface` fails with `type` on `AuditEvent` served and the ADR missing its quote
  (prove by removing the list entry). A test that `drlibre-specs.md` equals its `917edd1` blob is
  not written: a test of the owner's file would pin it; the diff is checked at review.

Each red test is shown failing for the right reason (415 missing, `end` refused, `_sort` 400,
escape split) before code is written.

## Trust boundaries

- Request headers (`Content-Type`, `Content-Length`, `Transfer-Encoding`): read as text only by
  block 1, a number or nothing; a non-number stays 400 from `declared_length` as now.
- `_sort` value: checked against `declaration.sortable`, never passed to the ORM as a column name;
  the column comes from the `Part` table.
- Search values: the escape is read before any piece is validated, so each piece still passes
  `carries_only_storable_text`, the length cap and the code lists.
- Body of an appointment: `end` compared as a parsed instant, never used.

## Vocabulary

Appointment, AppointmentType (duration), WaitlistEntry (sort of a waitlist row), Patient,
Communication (Notification), AuditLogEntry, AvailabilityRule (Schedule, Slot), ApiClient (bearer
token), Visitor (no body, no rights, 401).

## Will not do

No new dependency. No middleware: the two doors differ in answer shape, so each calls the
rule. No change to the Appointment decode beyond the `end` check. No generic sort framework:
one column per part. No edit of `drlibre-specs.md` other than the restore. No HTML or CSS.

## Not in this run

- Item 3: every 400 under `/fhir` carries the message `/api/v1` gives for the same refusal, with
  one test over the declaration. The generic strings to replace: `REFUSED_MESSAGE` (five
  modules), "This element is not valid." (four), "Not valid FHIR.", `UNREADABLE_MESSAGE`; the
  search refusals in `fhir_search.py` ("The value cannot be read."). Next task: a table of
  element to message in the domain, one test over `WRITE_SHAPES` and `declaration.parameters`.

## Checks that stay unrun here

`make fhir-validate` needs Java and a download (the sandbox may refuse); the sort and the
capability documentation are the new output it must pass. Live-server test needs
`transaction=True`. No browser: no layout change.

## Architect review

Verdict: approve.

- Ladder: one pure rule for both doors, one splitter, one declaration; no new dependency, no middleware. Right layers (pure domain rule, thin views, use cases own sort columns).
- Tests first are named as behaviours with expected values; the raw-socket live test (no `urllib`) and the `CONTENT_LENGTH=""` environ test cover the carried 26a2 gap. Edge and error paths present.
- Security: 415 after authentication and before any body or database read; `_sort` checked against the declaration, column from the `Part` table, never from the client; `end` compared, never stored.
- Slice: items 1, 2, 4, 5, 6, 7 are coherent and leave the product whole. Item 3 (about ten use cases plus every search refusal) is declared under "Not in this run" and is a separable, widest piece.
- Conditions (not blocking): (a) the run must create `doc/backlog/27d3-*.md` for item 3 and the review must list it under "For the owner", so the item is not lost while 27d2 is marked done; (b) the "Done when" of the task names item 3, so the review must say plainly that it was not delivered; (c) item 8's null placement and item 12's list of unnamed additions must be proven by test, not asserted in the ADR.
