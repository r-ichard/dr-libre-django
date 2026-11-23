# Lead time in offered slots (visitors and patients)

Slice: items 1 to 3 (the whole finding, one run; about fifteen minutes of work).

## Focal point

`find_free_slots` (`scheduling/use_cases/free_slots_query.py:51`) passes `now` as the lower
bound of the free-slot search, so a start 60 minutes away is offered. Section 5.3 refuses
such a start for patients at booking (`lead_time_too_short`), and 6.2 says a list shows
exactly what booking accepts. Fix it once, in the domain, at the one use case every slot list
goes through. Staff keep `now`.

## Do the pages already filter? (read in the code, not assumed)

| Surface | Path | Lead time filtered today? |
| --- | --- | --- |
| Search result cards, "next 3 starts" (6.2) | `use_cases/search.py:151` `search_range` (`domain/search_matching.py:46`, `now + LEAD_TIME`) | **Yes** |
| Hospital page, next slots | `use_cases/public_details.py:121` `search_public` | **Yes** (goes through search) |
| Provider detail page, week strip (6.6) | `views/pages/detail_pages.py:39` → `booking_page_data.py:85` `week_of_slots` → `find_free_slots` | **No** |
| Booking times page | `views/pages/booking_times.py:36` → `week_of_slots` → `find_free_slots` | **No** |
| Patient reschedule | `views/pages/patient_reschedule.py:50` → `week_of_slots(online_only=True)` | **No** |
| Booking details GET (slot still offered?) | `views/pages/booking_details.py:52` `slot_is_offered` → `find_free_slots` | **No** |
| `GET /api/v1/slots` | `views/slots.py:42` → `find_free_slots` | **No** |
| `GET /fhir/Slot` search and read | `use_cases/fhir_slot_reads.py:122,154` → `find_free_slots` | **No** |

So only the search-side lists filter. The provider detail page does not: the earlier draft
of this plan said it did, and was wrong.

Staff never reach a lead-time filter: `online_only_for` (`use_cases/schedule_loading.py:92`)
is true for no session and for patients, false for clinicians and admins. Staff pages pass
`online_only=False`.

## Blocks, in order

1. **`scheduling/domain/booking_rules.py`** (after `LEAD_TIME`, line 11, about 5 lines):
   add `earliest_offered_start(now: datetime, online_only: bool) -> datetime`, returning
   `now + LEAD_TIME` when `online_only` and `now` otherwise. Docstring: spec 5.3 and 6.2; the
   flag is the one `find_free_slots` already takes. `_too_soon` (line 96) stays as the
   booking check, same constant.
2. **`scheduling/use_cases/free_slots_query.py:51`** (about 2 lines): compute
   `earliest_offered_start(now, online_only)` and pass it as the `now` argument of
   `free_slots_by_start`. `load_schedules(…, now)` keeps the plain `now` (holds expire
   against it). Signatures of `find_free_slots` and its callers do not change. Every surface
   in the table above that is marked **No** is fixed by this one line.
3. **`scheduling/domain/search_matching.py:10`** (delete the duplicate `LEAD_TIME`, import it
   from `booking_rules`): the rule then lives in one constant. Behaviour unchanged.

Dropped from the earlier draft: the `first_offerable_start` change to `booking_page_data.py:162`
(`_first_free_start`). Its only callers are the booking times page, the provider page and
the patient reschedule page, all visitor or patient, and it already starts at `now + LEAD_TIME`.
No staff page passes `open_on_first_free`, so the change would move nothing for staff and
nothing for visitors. The owner question from the earlier draft does not arise.

No change to `booking_refusals.py`, `violated_rules`, `placement_choice.py`, templates,
views, FHIR code, `drlibre-specs.md`, or ADRs.

## Failing tests to write first (red, then proven red on current code)

Expected values in words from the spec. Clock: now 06:00 UTC. Rule 07:00 to 09:00, 30 minute
steps, type duration 30 minutes. 60 minutes away is 07:00; 120 minutes away is 08:00 (offered,
because the rule is "at least 120 minutes").

- `scheduling/use_cases/test_free_slots_query.py`
  - `returns_no_start_60_minutes_away_when_caller_is_online_only`: 07:00 and 07:30 are absent;
    08:00 and 08:30 are offered. **Red today** (07:00 offered).
  - `returns_start_60_minutes_away_when_caller_is_staff`: 07:00 offered. Passes today and
    after; locks the staff behaviour.
- `scheduling/domain/test_booking_rules.py`
  - `returns_earliest_start_120_minutes_ahead_when_caller_is_online_only`: 08:00. **Red**
    (ImportError on the new name; say so in the run report, the behaviour is not yet tested).
  - `returns_now_as_earliest_start_when_caller_is_staff`: 06:00. Same ImportError red.
- `scheduling/views/test_slots_online_only.py`
  - `returns_no_slot_inside_lead_time_for_a_visitor`: GET `/api/v1/slots` at 06:00 with the
    rule above; no 07:00 start in the body. **Red**.
- `scheduling/views/test_fhir_slots.py`
  - `returns_no_slot_inside_lead_time_for_an_anonymous_caller`: search `Slot` lists no 07:00
    start. **Red**.
  - `returns_no_slot_inside_lead_time_for_a_patient_token`: same, patient bearer token. **Red**.
  - `returns_not_found_when_reading_a_slot_inside_lead_time`: read of the 07:00 slot id for an
    anonymous caller answers 404. Red or green today is decided by the run; record which.
- `scheduling/views/pages/test_booking_times_page.py`
  - `returns_no_time_inside_lead_time_on_the_times_page_for_a_visitor`: no link to the 07:00
    details. **Red**.
- `scheduling/views/pages/test_detail_pages.py`
  - `returns_no_time_inside_lead_time_on_the_provider_page_for_a_visitor`: no 07:00 time on the
    week strip. **Red** (the provider page does not filter today).
- `scheduling/views/pages/test_patient_appointments_page.py`
  - `returns_no_time_inside_lead_time_when_patient_reschedules`: the reschedule week strip has
    no 07:00 time. **Red**. Use the file's existing patient and appointment fixtures.

Existing tests that assume a visitor or patient sees a start inside 120 minutes will fail after
block 2. Fix only the assumed time in that test and list each one in the review. Do not weaken
the rule. `scheduling/use_cases/test_placement.py:214`, `scheduling/use_cases/test_waitlist.py:376`
and `scheduling/use_cases/test_booking_holds.py:95` must stay green unchanged: they use the
booking path, which is not changed.

## Invariants

- Double booking: unchanged. `placement_checks.find_conflicts` and the appointment loading in
  `load_schedules` are not touched.
- Booking rules: `violated_rules` unchanged. A hold for a lead-time start still refuses with
  `lead_time_too_short`, because `create_hold` uses `probe_placement`, not the list.
- Boundary: a start exactly 120 minutes away stays offered and accepted (list drops
  `start < now + 120`; `_too_soon` refuses `< 120`). The list and the refusal now agree.
- Server-side authorization: `online_only` comes from `online_only_for(request user)` on each
  route (`views/slots.py:44`, `fhir_slot_reads.py:115,149`, page views). No query or body field
  decides it.
- Audit log: no writes added.
- Time: `now` from the request context; UTC explicit; `LEAD_TIME` is a `timedelta`, so DST
  does not matter.

## Blast radius

- `find_free_slots` callers: `/api/v1/slots`, FHIR Slot search and read, `week_of_slots`
  (booking times, provider page, patient reschedule, staff reschedule and admin booking; staff
  pass `online_only=False`, so unaffected), `slot_is_offered`, `clinician_agenda` (`online_only=False`,
  unaffected), `_first_free_start` (its chunks now skip lead-time starts for visitors too; its
  own `now + LEAD_TIME` start stays and is now redundant, see Not in this run).
- Visitor-visible change on the booking details GET: a lead-time slot that a visitor still has
  open now shows the existing "slot taken" conflict page, not the lead-time text that the hold
  gave before. Intended (6.2: a slot booking refuses is not listed; a stale one fails cleanly).
  Note it in the review.
- Placement (`placement_choice.py`, `placement_checks.py`) calls `free_slots_by_start` with
  `slot.now` directly; not changed.

## Trust boundaries

- `from`, `to`, `service-type`, `clinician_id` and FHIR `start` stay validated as today
  (`validate_body`, `bounded_window`). No new input.
- The caller's role comes from the session or bearer token via `online_only_for` and `Caller`.
  Unchanged.

## Domain entities (CLAUDE.md §3)

Visitor, Patient, Clinician, Admin, ApiClient, AvailabilityRule, Appointment (via the existing
conflict and load paths), TimeOff, AppointmentType, BookingHold, Slot (computed, not stored).

## Not doing

- No new dependency, abstraction, or caller-supplied flag. The switch is the existing `online_only`.
- No change to the booking rule, refusal wording, templates, CSS, or docs.
- No change to `search_range`'s own `now + LEAD_TIME` (search cards already filter; not touched).
- No change to staff pages.
- No rename of the `now` parameter of `free_slots_by_start`; the review notes that it now
  receives the earliest offerable start.

## Not in this run

- `_first_free_start` (`booking_page_data.py:162`): `now + LEAD_TIME` is now redundant with the
  filtered `find_free_slots`. Remove in a later cleanup, not in this slice.

## For the owner

None. Spec 5.3 and 6.2 decide the rule; no ADR is needed.

## Architect review (revision 1, addressed)

- Block 4 (`_first_free_start`) dropped: no staff caller passes `open_on_first_free`, so it
  changed nothing observable. Listed above.
- Flag renamed to `online_only` everywhere; `patient_facing` is gone.
- Provider-page claim corrected: the week strip on the provider page does not filter today;
  only the search cards and hospital page (through `search_public`) do.
- Hold path confirmed: `create_hold` → `probe_placement` keeps `lead_time_too_short`.

## Architect review

Verdict: approve. Both reasons in the earlier verdict are addressed: block 4 is dropped, and the flag is `online_only` throughout.

Checked against the code: `find_free_slots` (`free_slots_query.py:51`) is the single lower-bound point; `online_only_for` (`schedule_loading.py:92`) returns false for clinicians and admins; `_too_soon` (`booking_rules.py:96`) and `search_range` both use `LEAD_TIME`; the planned test files exist. The table of which surfaces filter today is correct.

Corrections the run must follow (text in the plan is wrong, the code change is not):

1. Block 4 rationale says the `_first_free_start` callers are "all visitor or patient". `booking_times.py:40` and `detail_pages.py:43` use `online_only_for(self.user)`, so staff reach them too, with `online_only=False`. Dropping block 4 is still right: a change there would move staff behaviour.
2. "Not in this run" says `now + LEAD_TIME` in `_first_free_start` is redundant. That holds only for visitors and patients. For staff, `find_free_slots` does not filter, so that line is the only lead-time bound they get. Do not remove it in the cleanup without a staff-side decision.
3. Spec tension for the owner: spec 5.1 defines free slots without any lead time (it drops only past starts). The lead-time filter for visitor lists rests on 6.2 ("slots shown are exactly the slots booking would accept") and 5.3 (patients). That reading is sound and matches the finding, but the review should say that `/api/v1/slots` and `Slot` now return fewer starts than 5.1's literal definition. Raise under "For the owner"; it does not block this run.
4. Red for block 1 is an ImportError. Accepted as the plan states, but the run report must say so and the behaviour test must still fail on the code after the import is fixed (the 06:00 / 08:00 values).

Scope: the slice (items 1 to 3) is coherent and leaves the product whole. Staff paths are untouched by design (`online_only=False`). Invariants hold: booking refusal path (`probe_placement`, `violated_rules`) is unchanged, so holds still refuse with `lead_time_too_short`; the list and the refusal agree at exactly 120 minutes.
