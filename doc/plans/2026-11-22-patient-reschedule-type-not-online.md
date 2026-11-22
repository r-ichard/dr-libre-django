# Patient reschedule for a type not bookable online: refusal, no offer (task 27b item 7, #49)

Slice: item 7 only of task 27b. Items 1 to 6 and 8 to 10 stay in `doc/backlog/27b-qa-round-3-pages.md`.

## Focal point

`scheduling/domain/portal_options.py`, `appointment_options`. It decides what a patient may do with an
appointment. It does not know the type's `is_bookable_online`, so the reschedule option says "allowed"
for a type the booking rules (spec 5.3, `type_not_bookable_online`, patients on book and reschedule) refuse.
The pages then fall through to `week_of_slots(..., online_only=True)`, which returns `not_found` for that type,
and `patient_reschedule.py` maps every Failure to 404.

Fix in one place: the domain option answers "no, and here is the rule's sentence". Existing page code
(`blocked_page_or_none`, already used by cancel and reschedule) then gives the 409 refusal page with the
hospital's phone. The row hides the Reschedule button through the same option.

## Blocks, in order

1. `scheduling/domain/portal_options.py`: `appointment_options` takes a fourth parameter
   `type_bookable_online: bool`. Reschedule is allowed only when the status is rescheduable and the type is
   bookable online. Its reason is the sentence of rule `type_not_bookable_online`, taken from
   `refusal_for(Failure.rule_violation([BookingRule.TYPE_NOT_BOOKABLE_ONLINE])).message`, so the sentence is
   not copied (item 1 of 27b moves sentences into one place later). Earlier blocked reasons (finished, started,
   24-hour window) keep precedence. Cancel is untouched.
2. `scheduling/views/pages/patient_rows.py:20`: pass `appointment.appointment_type.is_bookable_online`.
   The row then has no Reschedule button, and the card's existing hint shows the reason and the phone
   (`appointment_card.html` lines 12 to 13). Cancel still shows.
3. `scheduling/views/pages/patient_refusal.py:43` (`blocked_page_or_none`): same argument. Both reschedule
   GET pages call it before `week_of_slots` (`patient_reschedule.py:46`, `:81`), so `/reschedule` and
   `/reschedule/review` answer the 409 refusal page with the sentence and the phone, never the 404.
4. `scheduling/domain/test_portal_options.py`: add `True` as fourth argument to the existing calls (about
   12 sites; mechanical), and add the new domain test below.
5. `scheduling/views/pages/test_patient_appointments_page.py`: add the view tests below.

No change to `patient_reschedule.py` (its 404 mapping stays for `not_found`, which spec 12.3 keeps).
No change to the POST of `/review`: `reschedule_appointment` already refuses through
`placement_checks.violated_booking_rules`, which passes `slot.appointment_type.is_bookable_online`
(`scheduling/use_cases/placement_checks.py:125`).

## Files touched, in order

`scheduling/domain/test_portal_options.py`, `scheduling/domain/portal_options.py`,
`scheduling/views/pages/test_patient_appointments_page.py`, `scheduling/views/pages/patient_rows.py`,
`scheduling/views/pages/patient_refusal.py`.

Deliberately not touched: `patient_reschedule.py`, `booking_page_data.py`, `schedule_loading.py`,
`appointment_changes.py`, `placement_checks.py`, `booking_refusals.py`, the templates, `drlibre-specs.md`,
any clinician or admin page (they reschedule with `online_only=False` and are not affected).

## Failing tests first (red, then green)

Domain, `scheduling/domain/test_portal_options.py`:
- `returns_reschedule_refused_with_type_sentence_when_type_not_bookable_online`: BOOKED, starts in 25 hours,
  `type_bookable_online=False` → `reschedule.allowed` is False, `reschedule.reason` is
  "This appointment type cannot be booked online.", `cancel.allowed` is True.
- `returns_both_allowed_when_type_bookable_online_and_starts_in_25_hours`: existing test, updated call, same expectation.

View, `scheduling/views/pages/test_patient_appointments_page.py` (set the type with `update_row(..., is_bookable_online=False)`,
helper in `scheduling/views/pages/search_pages_support.py:49`; patient is the own patient, `_later` appointment):
- `returns_409_refusal_with_hospital_phone_when_reschedule_type_not_bookable_online`: GET `.../reschedule`
  → status 409 (not 404), body contains "This appointment type cannot be booked online." and "+49 30 1234",
  and no week link.
- `returns_409_refusal_when_review_asked_for_type_not_bookable_online`: GET `.../reschedule/review?starts_at=<a free start>`
  → 409, same sentence and phone.
- `returns_no_reschedule_button_and_call_hint_when_type_not_bookable_online`: list page → no
  `.../reschedule` link, "Call" hint with the phone, `.../cancel` link present.
- `returns_refusal_and_keeps_time_when_patient_posts_reschedule_for_type_not_bookable_online` (guard):
  POST `.../reschedule/review?starts_at=...` → 422 refusal, `starts_at` and `ends_at` of the appointment
  unchanged, no `appointment.reschedule` audit row. Expected green before the fix (the use case already
  refuses); it guards the server-side write rule (spec 5.3, 12.3). It is not red-proven, and the plan says so.

Expected values come from the spec: reschedule needs the type to allow online booking (5.3); a refusal of a
rule answers with a way forward (7.1); 404 only for a missing record or another's record (12.3). Sentences
come from the rule table in `booking_refusals.py`, not new text.

## Invariants and blast radius

- Double booking: no change to placement or conflict checks.
- Server-side authorization: `own_appointment` and `appointment_or_refusal` unchanged; the option is a
  display decision, the use case still refuses writes (guard test above).
- Audit log append-only: untouched; the guard test asserts no reschedule audit row is written.
- Blast radius: patient appointment list rows and the two patient reschedule pages. `appointment_options` has
  three callers (`patient_rows.py`, `patient_refusal.py`, its tests). The domain change is covered by
  `make mutate` (`scheduling/domain`); the sentence and the flag must each kill a mutant.

## Trust boundaries

- Patient → `/patient/appointments/<id>/reschedule[/review]`: session user → `own_appointment` (server); the
  type flag is read from the database, never from the request.
- `starts_at` query value: unchanged (`asked_start`).

## Domain entities (CLAUDE.md §3 vocabulary)

Patient, Appointment, AppointmentType (`is_bookable_online`), Hospital (name, phone), Clinician. Rule
`type_not_bookable_online` (BookingRule). Status BOOKED / CONFIRMED (RESCHEDULABLE_STATUSES).

## What I will not do

- No new abstraction, no new rule table, no shared sentence module (item 1 of 27b does that later).
- No change to the 404 mapping in `patient_reschedule.py`.
- No change to `drlibre-specs.md`.
- No change to the POST path or the use case.
- No hint text rewrite; the existing card hint is reused.

## Layout

No template or CSS change. The card hint and the 409 refusal page are existing components (`booking/refused.html`).
Impeccable: no UI edit; orchestrator checks the 409 page in the browser at 375 px and 1440 px.

## Not in this run

- Items 1 to 6, 8 to 10 of task 27b (each its own run).
- Risk, not fixed: a type with `is_active=False` still answers 404 on reschedule
  (`active_appointment_type` returns None → `not_found`). It is not "not bookable online", so it stays out of
  this slice; raise as a follow-up finding.

## Open for the owner

None for this slice.

## Architect review

Verdict: approve. Checked against CLAUDE.md and the cited code.

1. Ladder: one domain decision (`appointment_options`) gets the flag. The page refusal (`blocked_page_or_none`) and
   the row already exist and are reused. No new abstraction, dependency or refactor. Right layer: the option is the
   display decision; the use case keeps the write refusal.
2. Purpose per block: each block is one sentence. Entities use the §3 names (Patient, Appointment, AppointmentType,
   BookingRule, RESCHEDULABLE_STATUSES). Verified: the call sites at `patient_rows.py:20`, `patient_refusal.py:43`,
   `patient_reschedule.py:46` and `:81` match the plan.
3. Tests: the first red tests are named as behaviours with expected values: the sentence from `booking_refusals.py:61`,
   the phone (`+49 30 1234`, seed builder), the 409 status, and no audit row. Edge paths: list page, direct GET, review
   GET, and a POST guard. The guard is honestly marked as green before the fix.
4. Security: the type flag comes from the database, not the request. `own_appointment` is unchanged. The POST path is
   already refused by `placement_checks.violated_booking_rules`. Audit is untouched and asserted.
5. Architecture: no wire/storage change. One transaction is unaffected (no write path changes). Expected refusal is a
   value (`Failure` → `Refusal`), not an exception.
6. Scope: complete for item 7. Items 1 to 6 and 8 to 10 stay out and are stated. Follow-up risk (inactive type → 404)
   is named.

Corrections for the implementer (not blocking):
- Test sites: `scheduling/domain/test_portal_options.py` has 9 `appointment_options(` calls, not "about 12". Update the
  count when adding the fourth argument.
- Precedence not stated: a CHECKED_IN appointment of a type not bookable online. Today its reschedule reason is
  "already checked in". With the new check, the type sentence would replace it because the status check and the type
  check are both in the reschedule branch. Decide the order in the plan and add a case, or state that the type
  sentence wins and why.
- Spec citation: the plan says "404 only for a missing record or another's record (12.3)". `drlibre-specs.md` 12.3
  says a missing record gives `not_found` and another's record gives `forbidden`. This slice does not change the
  other-record path, so no code change follows. Do not repeat the misquote in the review; raise the 404-vs-403 point
  under "For the owner" if it matters.
