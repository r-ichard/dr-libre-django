# Plan: task 24a, valid AuditEvent, samples for every type, leftovers of task 24

Slice: items 0 to 7, all of them. Each is small, none depends on a new layer; one run holds them.
If green stage runs long, the cut line is: items 6 and 7 go to the end, in that order.

## Focal point

`AuditEvent.action` in `scheduling/domain/fhir_audit_event.py:46`. Everything else is a gap
`make fhir-validate` could not see because `samples.py` has no sample for four types.

## Blocks, one sentence each

1. **Domain `audit_action_code(action) -> "C"|"R"|"U"|"D"|"E"`** in a new
   `scheduling/domain/fhir_audit_action.py`: one table keyed by the product action, a suffix rule
   only where the table says so; `fhir_audit_event.py` writes it to `action`, keeps the product
   action in `type.code`. Covered by `make mutate` (inside `scheduling/domain`).
2. **Search `action`** (`fhir_audit_reads.py:_action`) keeps `filter(action=value)` on the product
   name, which is the `type.code` element; the ADR says so. No code change expected beyond a test
   that the parameter finds by product name and not by `C`.
3. **Detail allow-list**: `_details` in `fhir_audit_event.py` copies only the keys `AuditMetadata.to_json`
   can emit, by name, derived from one constant in `audit_metadata.py` (`ids`, `counts`, `statuses`,
   `changed_fields`, `email_domain`; read `to_json` for the exact output shape before writing).
4. **Communication category display**: `fhir_communication.py:67` passes `facts.kind` as display.
   Pages show the stored notification `title`, and no kind-to-words map exists. Add one domain map
   `NOTIFICATION_KIND_WORDS` (five `NotificationKind` members) next to `fhir_communication.py`, and a
   test that fails when a member has no words. First step of the red stage: re-grep for an existing
   map (`use_cases/notifications.py`, `reminders.py`, `waitlist.py` title constants); reuse if
   there is one per kind.
5. **Authorize first** in `create_response` (`fhir_response_reads.py:44`): the actor comparison moves
   after `accept_offer`'s authorization, or accept_offer's own check is the only one; read
   `waitlist.accept_offer` to choose, and keep the "actor" refusal for a payload that names
   another patient.
6. **Samples** (`samples.py`, 108 lines; will pass 200, so split into `samples_staff.py` for the
   new documents, keeping files under 300): for `Appointment` (every status the product serves:
   booked, hold, waitlist entry as found in `fhir_appointment_reads.py`; search with each of
   `_include=Appointment:patient|practitioner|location`; PUT body; POST body; refusal naming a
   violated rule), `AppointmentResponse` (read, search, POST body of `accepted`, one refusal),
   `Communication` (every kind in the seed or planted by the sampler, search with no include since
   the declaration has none, PUT body marking received, one refusal), `AuditEvent` (read, search, one
   per distinct `C/R/U/D/E` the seed produces, refusal 403 for a non-admin). Refusals are
   `OperationOutcome` documents the real route answered. Staff-only types are read with the token.
7. **Sample guard tests** in `test_samples.py`: a test fails when a `FHIR_RESOURCES` type has no
   `<Type>-` document, and when an interaction of a type (`read`, `search-type`, `create`, `update`,
   `delete`) has no sample name from a fixed table interaction -> suffix. Also `includes` of every
   declaration have a `-include` sample per include.
8. **Audit search cost and size** in `views/test_fhir_audit_event.py`: `assertNumQueries`-style bound
   (a constant, stated) on a search page; a 50 000-entry bulk-inserted log answers within a stated
   time limit and the same constant of queries.
9. **Demo seed privacy test**: after `run_seed()`, walk every `AuditEvent` of the search; no value
   equal to a user's name, email local part, phone, birth date, reason or note; an email carries only
   a domain; the walk is over serialized JSON strings, and regex-free comparison with planted seed values.
10. **Mutants**: write tests that kill `fhir_communication.x_decode_update__mutmut_21` and
    `x__is_date_time__mutmut_4`. First step: `mutmut show <name>` on the branch to read each mutant;
    the likely cases are the `received` compare (malformed string, non-string, a valid instant with
    zone) and `_is_date_time` returning True for a non-str or a bad string. An entry in
    `mutation-equivalents.txt` only if `mutmut show` proves no behaviour change.
11. **ADR** `doc/adr/0007-fhir-appointment-and-the-rest.md`: Appointment (status and source
    extensions, `violated-rule`, `conflicting-resource`, hold and waitlist entry shape, what a body
    may change), AppointmentResponse (only `accepted`; declining is not in the specification),
    Communication (recipient may only set `received` once), AuditEvent (action table, `type`
    holds the product action, `action` search reads `type.code`, `entity.detail` allow-list). Add the
    sentence to the ADRs (new 0007, and the line "a FHIR search sorts by database collation") .
12. **Small items**: `fhir_validate.sh` adds `dropdb` of `$DB_NAME` into the existing `trap`
    (use `scripts/ensure_database.py` conventions; a failing drop never hides the validator's exit
    status); move `_busy_clinicians`, `_busy_placed`, `_busy_intervals`, `Blocks` out of
    `fhir_slot_reads.py` (290 lines) into `fhir_busy_slots.py`; `_allowed_methods` in
    `views/fhir/views.py:98` returns `()` for an undeclared type instead of `assert`;
    `update_appointment` does one lookup (`fhir_appointment_writes.py:55-63`: `read_appointment`
    already resolved the row; reuse its hit); type the signatures and fixtures in
    `test_fhir_appointment_race.py`.

## Files, in order

Tests first (red): `domain/test_fhir_audit_action.py`, `domain/test_fhir_audit_event.py` (new, action
code, type code, allow-list), `domain/test_fhir_communication.py` (two mutant killers, display),
`views/test_fhir_audit_event.py`, `views/test_fhir_appointment_response.py` (authorize-first),
`views/fhir/test_samples.py`. Then product: `fhir_audit_action.py`, `fhir_audit_event.py`,
`audit_metadata.py`, `fhir_communication.py`, `fhir_response_reads.py`, `samples.py` (+ split),
`fhir_busy_slots.py`, `fhir_slot_reads.py`, `views.py`, `fhir_appointment_writes.py`,
`test_fhir_appointment_race.py`, `fhir_validate.sh`, `doc/adr/0007-...md`, `mutation-equivalents.txt`
only if justified.

Deliberately not touched: write paths for AuditEvent (none exist), admin writes (24b, 24c), section 15
closing (24d), the audit writer, `audit_labels.py` (read only: its keys are the action list), the
HL7 validator pin.

## Invariants and blast radius

- Audit log stays append-only and admin-only on `/fhir/AuditEvent`; no write path added.
- Authorization stays server-side from the session; item 5 only reorders it.
- No double booking affected: slot reads move code only; the existing slot and race tests must pass
  untouched.
- `action` on the wire changes value (product name -> one letter). Any client of `action` search
  keeps working, because search reads `type.code`. Existing tests asserting `action == "appointment.book"`
  change; list them via grep before editing.

## Failing tests first (behaviour, expected values in words)

- `returns_C_when_action_is_appointment_book`, `returns_U_when_action_is_appointment_cancel`,
  `returns_D_when_action_is_time_off_delete`, `returns_R_when_action_is_notification_read`... one row per
  code, plus `returns_E_when_action_is_auth_login_failed`-style case for the "execute" bucket
  (decide the E bucket in the ADR: logins, exports, reminder runs, demo seed: operations rather than
  record changes). AuditEventAction value set: C create, R read/view/print/query, U update, D delete,
  E execute.
- `returns_a_code_for_every_action_the_product_writes`: every key of `AUDIT_LABELS` maps to one of the five.
- `returns_type_code_with_product_action_when_event_is_built`.
- `returns_event_found_by_product_action_when_searching_action` and `returns_nothing_when_searching_action_C`.
- `returns_only_named_detail_keys_when_metadata_holds_an_unlisted_key` (plant `note`, `name`: absent).
- `returns_words_when_communication_category_is_built`: `SCHEDULE_CHANGED` shows as the words
  of the map, code stays `SCHEDULE_CHANGED`; and every `NotificationKind` has words.
- `returns_refused_before_actor_compared_when_caller_is_a_clinician` and with a patient who
  names another patient's entry: no information about the entry leaks (same refusal for absent and present).
- `returns_error_when_received_is_malformed` / `returns_no_change_when_received_equals_stored`
  (targets of mutants 21 and 4, fixed after `mutmut show`).
- Search of AuditEvent: query count bounded by a named constant, page of 50 000 rows within a named time.
- Seed privacy: no event contains the strings listed in point 4.
- Samples: every declared type has a sample; every interaction has a sample; every include has a sample;
  `returns_no_empty_value_when_every_sample_is_walked` still passes.

## Trust boundaries

- HTTP body of a write (`AppointmentResponse`, `Communication` PUT, `Appointment` PUT/POST): decoded by the
  existing shape decoders (`decode_acceptance`, `decode_update`), authorization in the use case
  (item 5 moves it first). Query parameters: existing `SearchQuery` parse, `action`/`entity` are ORM
  filters only.
- Audit metadata to wire: allow-list by key, values stringified; nothing from a request reaches it.
- Samples: built through the real routes with a token created in the process and kept nowhere.

## Domain entities

AuditLogEntry, Appointment, BookingHold, WaitlistEntry, Notification, Patient, Clinician, Admin,
ApiClient (the sample token).

## What I will not do

No new abstraction beyond the one mapping function and the one new module for busy slots; no new
dependency; no change to the validator version; no refactor of the Part machinery; no admin writes.

## Not in this run

None cut at present. Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass; the stage that runs them must run both slow gates itself and report output.

## Architect review

Verdict: approve. Whole task in one slice, coherent, right layers, tests first.

Notes for the green stage, none blocking:
- Block 4: the task says the display comes "from the place the pages take them". Do the re-grep
  first and reuse that source; a new `NOTIFICATION_KIND_WORDS` only if pages truly have no per-kind
  words, and then have pages and FHIR share it (one source, not two).
- Block 5: choose one authorization order and test both refusals (absent entry, another patient's
  entry) return the identical outcome, so no existence leak.
- Block 6/7: the interaction-to-suffix table in `test_samples.py` must come from the declaration, not
  a hand-copied list, or a new interaction passes unseen.
- Block 8: state the time limit generously enough not to flake in the sandbox; the query-count
  bound is the real assertion.
- Block 10: if a mutant is judged equivalent, `mutmut show` output goes in the reason line.
- Run `make fhir-validate` after the sample additions; the 4 new types may reveal further invalid
  documents beyond `action`. Fix them in this run.
