Slice: items 1 to 3 (searches never answer a wrong set). Items 4 to 6 are under `## Not in this run`.

# Task 27d, slice 1: date, hostile-text and comma-list searches under `/fhir`

## Cause of #51, and why nothing saw it
`fhir_dates.day_bounds` returns the first and last calendar *day*, both included (right for a
`DateField`). `starts_within` (`use_cases/fhir_appointment_reads.py:164`, also used by
Communication and AuditEvent) feeds those dates to a *datetime* column as
`__gte first` and `__lt last`. A date compared with a datetime is its midnight, so:
- the last day is excluded (`__lt` an included day): `date=2026-11-24` is `[24 00:00, 24 00:00)`, empty;
  `lt2026-11-24T00:00:00Z` ends at 23rd 00:00, so the 23rd is gone;
- an instant bound is rounded to its day (`gt…T20:00` returns the whole day).
`bounds_of` and `combined_bounds` already return the exact half-open datetimes `[low, high)`; the
seam throws them away.
Not seen because: (a) `test_fhir_dates.py` pins `day_bounds` to the inclusive-date contract it has
and never applies a range to a column; (b) no view or use-case test searches `date=`/`sent=` with
a time, and the one-day case has no appointment at 00:00 to expose it; (c) mutmut covers
`scheduling/domain` only and the domain is right; the defect lives in `use_cases/`, where the
two contracts (inclusive day, exclusive instant) meet with no test. Fix by test at the seam, not by
widening the mutation scope.

## Focal point
`starts_within` and the parser's `_read_value`. Everything else follows from one range rule used by
every datetime column and one text rule used by every parameter.

## Blocks (one sentence each)
1. `domain/fhir_dates.py`: `combined_bounds` is the rule, no new function. Document in the module that `day_bounds` is for `DateField` columns only; a datetime column
   uses `combined_bounds` (`gte low`, `lt high`).
2. `use_cases/fhir_appointment_reads.py:starts_within`: read `combined_bounds([value])` and filter
   `__gte low`, `__lt high` (replaces the date pair); Communication and AuditEvent already reuse it.
   `Patient.birthdate` (`DateField`) and `Schedule.date` (horizon `DateField`s) keep `day_bounds`:
   by FHIR's ambiguity rule a day matches `gt`/`lt` against an instant when its range overlaps, so
   that is already the definition; tests pin it.
3. `domain/fhir_dates.py`: refuse (value unreadable, 400) the prefixes `ne`, `sa`, `eb`, `ap`, which
   R4 defines for a date and the product does not serve; serve `eq`, `ge`, `gt`, `le`, `lt` by their
   definition. A bare day is the whole UTC day; a value with offset is converted to UTC; a value with
   no zone is UTC. `normalised_date` stays the one parser (already refuses `ne2030-01-07`).
4. `domain/fhir_search.py:_read_value`: one text rule: a character a database column cannot carry
   (NUL) makes the value unreadable; the refusal names the parameter (`_refuse(name, ...)` already
   does) for TEXT, CODE, REFERENCE, DATE, NEAR alike. New pure function `carries_only_storable_text`
   in `domain/fhir_common.py` or beside the parser, mutation-gated.
5. `domain/fhir_declaration.py`: `SearchParameter` gets `codes: tuple[str, ...] = ()`, the closed
   list: Appointment.status, Slot.status, AuditEvent.action (`C R U D E`), Communication.category if
   it is closed in the code (read it; leave open if not). The CapabilityStatement may list them in
   `documentation`.
6. `domain/fhir_search.py`: a comma in a CODE/TEXT/REFERENCE value splits into alternatives ("either").
   `SearchQuery.filters` becomes `tuple[tuple[str, tuple[str, ...]], ...]` (name, alternatives).
   A DATE value with a comma is refused 400 (R4 allows OR on dates; the product does not, ADR
   says so). With `codes`, an alternative outside the list is 400 naming the parameter and listing
   the codes; never an empty set.
7. `use_cases/fhir_reads.py:_candidates` (line ~304): apply a filter over alternatives as the union
   of the filter's rows (`rows.filter(pk__in=...)` OR-ed, one query); `fhir_slot_reads.py` and
   `fhir_appointment_reads.py` readers that read `query.filters` follow the new shape (Slot: `status`
   already takes up to 4 repeats; both repeats and commas end up as one set).
8. `use_cases/fhir_audit_reads.py:_action`: `action=C` finds the events whose *shown* code is `C`:
   map the code to the product actions through `fhir_audit_action` (new pure
   `product_actions_of(code)` there, the inverse of the existing mapping, mutation-gated; covers
   SUFFIX_CODES and EXPLICIT_CODES). The product's own action stays searchable as
   `AuditEvent?type=<product action>` is NOT added; instead ADR 0009 says it stays in `AuditEvent.type`
   and in `/api/v1` audit filters, and `entity`/`entity-type` remain. (Smallest: no new parameter.)
9. ADR 0005 and 0009 (edit, no new ADR): list prefixes served and refused, UTC for day precision,
   the closed-code rule, comma = either, no comma on dates, NUL is 400, how the product action stays
   searchable. Spec 15.5 gets one line per rule.

## Files to touch, in order
tests first (red): `domain/test_fhir_dates.py` (table + properties), `domain/test_fhir_search.py`
(NUL, comma, closed list), `domain/test_fhir_audit_action.py` (inverse), `views/test_fhir_date_search.py`
(new, over HTTP), `views/test_hostile_input.py` (declaration-driven NUL case).
then: `domain/fhir_dates.py`, `domain/fhir_search.py`, `domain/fhir_declaration.py`,
`domain/fhir_audit_action.py`, `use_cases/fhir_appointment_reads.py`, `use_cases/fhir_reads.py`,
`use_cases/fhir_audit_reads.py`, `use_cases/fhir_slot_reads.py`, `use_cases/fhir_communication_reads.py`
(only if it reads `filters` directly), ADR 0005, ADR 0009, spec 15.5, `doc/backlog.md` untouched (orchestrator).
Not touched: `views/input_limits.py`, `views/fhir/writes.py`, `fhir_outcome.py`, `fhir_capability.py`
(items 4 to 6), `models/`, migrations, templates, HTML pages.

## Failing tests to write first (`returns_X_when_Y`, expected ids written by hand)
Table, over HTTP as admin on Appointment, same rows on Communication.sent and AuditEvent.date
(three types, one table, helper builds rows at fixed UTC instants). Bound B = 2026-11-24T00:00:00Z;
rows at B-1d, B-12h, B-1s, B, B+1s, B+12h, B+1d, ids a..g in that order:
- `returns_the_rows_each_prefix_names_when_the_value_is_a_second`: `lt` B: a,b,c; `le` B: a,b,c,d;
  `eq` B: d; `ge` B: d,e,f,g; `gt` B: e,f,g (instant precision is one second). Hand-written.
- `returns_the_whole_day_when_value_has_day_precision`: `date=2026-11-24` -> d,e,f (09:00 and 23:00
  fixture variants too); `eq2026-11-23` -> the 23rd only.
- `returns_the_same_set_when_offset_names_the_same_instant`: `lt2026-11-24T01:00:00+01:00` == `lt` B.
- the issue's cases: 09:00Z/23:00Z on the 24th, 12:00Z/21:00Z on the 23rd; `date=ge2026-11-23&date=lt2026-11-24`
  -> the two of the 23rd; `le2026-11-23T23:59:59Z` -> the two of the 23rd; `gt2026-11-23T20:00:00Z`
  excludes the 12:00 one.
- `returns_400_naming_date_when_prefix_is_ne_sa_eb_or_ap`, and when a date has a comma.
- Properties (hypothesis, datetime column via the use-case filter, not the pure function): for any
  bound, `lt` set and `ge` set are disjoint and their union is all rows; for any day, `ge day` with
  `lt day+1` equals `eq day`.
- Patient.birthdate and Schedule.date: table with a date-column row on, before, after the bound
  (day precision), so the day-column rule is pinned by hand-written ids.
- NUL: `returns_400_naming_the_parameter_when_value_has_a_nul_byte`, parametrised over
  `FHIR_RESOURCES` x `parameters` (read from the declaration, so a new parameter is covered), as
  anonymous and as admin; none is 500. The existing hostile test gains the same loop.
- Comma: `returns_either_when_status_has_a_comma` (`booked,cancelled`), `type=prov,dept` on
  Organization; `returns_400_listing_the_codes_when_status_is_not_a_code`; `action=C` finds the
  events whose resource shows `C` (compare with the resource's own `action`, plus one hand-written
  product action "appointment.book" -> `C`); `action=C,D` either.
Prove each red for the right reason: the date table fails on missing rows, not on a typo.

## Invariants and blast radius
Read-only search paths; no write, no audit, no double booking or authorization code touched.
Visibility rules (`part.rows(viewer)`) stay the first narrowing; the union of alternatives is applied
after them, never instead. Blast radius: every `/fhir` search (filter shape changes) and the
Slot reader, so the full FHIR test files, `test_fhir_paging`, `test_fhir_surface` and
`fhir_validate` samples must stay green.

## Trust boundaries
Query string is the only input: parsed once in `parse_search` (domain, pure): NUL, comma, closed
codes, prefixes, length (`MAXIMUM_TEXT` per alternative) there. Authorization unchanged and from the
token (`_caller`). No value reaches the ORM except as a parameter of `filter()`.

## Vocabulary
Appointment, Notification (Communication), AuditLogEntry (AuditEvent), AvailabilityRule (Schedule),
Patient, Clinician (Practitioner), Hospital/Department (Organization), Specialty. No new entity.

## What I will not do
No new abstraction beyond the two pure helpers named above, no dependency, no change to the
mutation scope, no `ne`/`sa`/`eb`/`ap` support, no OR on dates, no new search parameter.

## Not in this run
- Item 4 (#52): one `request_has_body` / media-type rule for `/api/v1` and `/fhir`; 415 + OperationOutcome
  before the body is read; empty `CONTENT_LENGTH` is no body; raw-socket live-server test.
- Item 5: per-field 400 messages in the OperationOutcome, and `end` equal to stored or derived accepted on
  reschedule (`fhir_appointment_write._moved_element`).
- Item 6: `_sort` on every date parameter, both directions, CapabilityStatement says which values.
- 414/431 pages: task 26d.

Risks: the filter shape change touches every reader of `query.filters`; a missed reader answers an
empty set silently, so grep `query.filters` and cover each type with one comma test.

## Architect review
Verdict: approve.
- Cause of #51 confirmed in code: `starts_within` feeds `day_bounds` dates to a datetime column; `combined_bounds` already holds the exact half-open range. Fix is the smallest one, at the seam; the mutation gate stays unchanged, and the plan says why it missed.
- Slice 1 to 3 is coherent and leaves `/fhir` whole; items 4 to 6 are under `## Not in this run`.
- Tests are first, hand-written ids, boundary table (-1d, -12h, -1s, 0, +1s, +12h, +1d), properties, declaration-driven NUL test.
- Watch for the filter-shape change: `domain/fhir_bundle.py:42` (paging links) also reads `query.filters` and is not in the file list. Rebuild `next`/`self` links from alternatives joined by comma, with a test that a comma search pages correctly. `fhir_slot_reads.py:108` too (already listed).
- NUL rule must also cover `_sort`, `_include` and other `_` parameters, not only declared search parameters; the test should send NUL there as well.
- State in the ADR that day precision is UTC and why (hospital time zones differ across hospitals), as the task asks for "a zone the ADR names".
- Closed-list 400 must list the codes in the OperationOutcome text (item 3), and the `Appointment.status` list should be the FHIR codes, not the internal ones.
