# Task 27b, items 1 and 2: sentences for booking rules and for a status action not allowed

Slice: items 1 to 2 (#34 and #35). Items 3 to 10 are not in this run.

## Focal point

An admin sees internal codes ("outside_availability") after a booking or reschedule breaks
a rule, and a status action that is not allowed says "The status changed since this page
was opened". Both texts come from `scheduling/views/pages/admin_refusal.py`. The fix: the
admin page uses the sentence table that patient and clinician pages already use, and an
invalid status action names the current status.

## Ladder

1. Rule sentences exist. `scheduling/domain/booking_refusals.py`: `refusal_for` (line 23)
   and `_RULE_SENTENCES` (line 54) hold one sentence per `BookingRule` (six values).
   `change_refused_page` (`patient_refusal.py`) serves patient and clinician pages through
   `refusal_for`. The admin page skips it and joins the codes. Chosen: admin uses
   `refusal_for`. No new module.
2. Status words exist: `STAFF_APPOINTMENT_BADGES` in `scheduling/views/pages/status_words.py`
   (keys: `AppointmentStatus`). `Failure.invalid_transition(current_status)` carries the
   status as a raw string (`appointment_changes.py`), and the FHIR path and waitlist pass
   other strings. Chosen: reuse the badge table with `.get` and a fallback.

## Blocks and files, in order

1. `scheduling/domain/booking_refusals.py`
   - Plan: add public `rules_sentence(rules: Sequence[str]) -> str`: the sentences of the
     known rules, in the order given, joined by one space; unknown codes skipped; empty
     string when none is known. `_rule_refusal` (line 43) returns `rules_sentence(...)`
     with 422, or `SLOT_TAKEN` with 409 when the result is empty (as today).
   - Why all sentences: spec 4 says a rule violation lists the violated rules. Today the
     first known rule only is shown; this changes patient and clinician pages too, for
     bookings that break two rules. Intended.
2. `scheduling/views/pages/admin_refusal.py`
   - Plan: delete the `RULE_VIOLATION` branch of `_message_and_status`. Its codes-join is
     the cause of #34; without the branch the final line `refusal_for(failure)` answers
     with the sentence and 422, or `SLOT_TAKEN` and 409 when no rule is known. The admin
     page inherits the non-empty fallback; no empty message is rendered.
   - Plan: `INVALID_TRANSITION` branch: `_status_message(failure, action_phrase)`:
     - `current = failure.details.get("current_status")`;
     - `badge = STAFF_APPOINTMENT_BADGES.get(AppointmentStatus(current))` only when
       `current` is a valid `AppointmentStatus` value (catch `ValueError`); otherwise
       `None`;
     - no phrase, or no badge: `STATUS_CHANGED`, 409;
     - else `f"This appointment is {badge_text.lower()}, so it cannot be {action_phrase}."`,
       409.
   - Plan: `admin_refused_page` gets keyword `action_phrase: str = ""`, passed to
     `_message_and_status`. Six parameters; the file's existing five already exceed the
     "about three" guide. A later task groups the keywords.
   - Plan: sentence form "This appointment is booked, so it cannot be completed." uses
     the badge text, so every status reads with one template. Issue #35 gave "A booked
     appointment cannot be completed." as an example; the template is chosen to read
     correctly for "checked in" and "no-show" too.
3. `scheduling/views/pages/admin_appointments.py`
   - Plan: `StatusActionPage` gets class attribute `action_phrase`. `CheckInPage` sets
     "checked in", `CompletePage` "completed", `NoShowPage` "marked as no-show". Its
     `post` (the `admin_refused_page` call) passes `action_phrase=self.action_phrase`.
   - Plan: `CancelPage.post` passes `action_phrase="cancelled"`.
4. `scheduling/views/pages/admin_appointment_reschedule.py`
   - Plan: `RescheduleReviewPage._refused` passes `action_phrase="rescheduled"`. Only the
     POST path reaches `INVALID_TRANSITION` with a phrase; the GET reschedule page keeps
     its own `STATUS_CHANGED` (see Not in this run).
5. `scheduling/views/pages/admin_appointment_book.py`: no edit. It calls `admin_refused_page`
   and reaches the changed `_message_and_status` through it; its failures are not
   invalid transitions.

Files deliberately not touched: `drlibre-specs.md`, `status_words.py` (read only),
`appointment_changes.py`, `patient_refusal.py`, `clinician_reschedule.py`,
`admin_waitlist.py`, `waitlist_refused_page`, any template, CSS, migration.

## Failing tests first (behaviour names; expected values from the spec and the issues)

Domain, `scheduling/domain/test_booking_refusals.py`:
- `returns_a_sentence_for_every_booking_rule` (parametrized over `BookingRule`): message
  is not "That time was just taken." and holds no underscore. Passes today for all six;
  its red is proven by a temporary removal of one `_RULE_SENTENCES` entry (see Red proof).
- `returns_every_sentence_in_order_when_several_rules_are_violated`: input
  `[lead_time_too_short, type_not_bookable_online]` gives "Appointments must start at least
  2 hours from now. This appointment type cannot be booked online." Red today (first only).
- `returns_slot_taken_when_no_violated_rule_is_known`: input `["made_up_rule"]` gives
  "That time was just taken.", 409. Guard for the empty-string fallback.

Views, `scheduling/views/pages/test_admin_refusal_words.py` (calls `admin_refused_page`
directly, as its existing test does):
- `returns_the_rule_sentence_and_no_code_on_every_booking_page_for_every_rule`
  (parametrized over `BookingRule` and over two callers: `admin_refused_page` and
  `change_refused_page`, which serves patient and clinician pages). Body holds the
  sentence from `refusal_for`; body holds no `rule.value`. Red today for the admin
  caller; green for `change_refused_page` (state this in the review). Covers the
  "page prints a rule's code" guard across admin, patient and clinician.
- `returns_the_status_sentence_when_status_action_is_not_allowed` (parametrized):
  - `BOOKED`, "completed" -> "This appointment is booked, so it cannot be completed."
  - `CHECKED_IN`, "checked in" -> "This appointment is checked in, so it cannot be checked in."
  - `COMPLETED`, "cancelled" -> "This appointment is completed, so it cannot be cancelled."
  All 409, none contains "changed since".
- `returns_the_stale_sentence_when_the_status_is_not_an_appointment_status`: raw
  `invalid_transition("OFFERED")` with phrase "completed" -> stale sentence, 409, no error.
  Covers the waitlist and FHIR strings; no KeyError.
- `returns_the_stale_sentence_when_no_action_is_named`: `invalid_transition("BOOKED")` with
  no phrase -> stale sentence, 409. Keeps the waitlist path unchanged.

Views, `scheduling/views/pages/test_admin_appointment_pages.py` (uses the existing
`_appointment` and `admin_post` helpers):
- `returns_409_and_the_booked_sentence_when_an_admin_completes_a_booked_appointment`: body
  holds "This appointment is booked, so it cannot be completed."; status stays `BOOKED`;
  `AuditLogEntry` and `Notification` row counts unchanged.
- `returns_409_and_the_checked_in_sentence_when_an_admin_checks_in_twice`: status stays
  `CHECKED_IN`; counts unchanged.
- `returns_409_and_the_completed_sentence_when_an_admin_cancels_a_completed_appointment`:
  existing test at line 217 gets the sentence assert; counts unchanged.

Views, `scheduling/views/pages/test_admin_booking_pages.py`:
- `returns_422_and_the_not_offered_sentence_when_admin_reschedules_off_the_grid`: POST
  `.../reschedule/review?starts_at=<off the grid>` answers 422; body holds "That time is
  not offered. Choose one from the week."; no `outside_availability`. Red today.
- `returns_409_and_the_cancelled_sentence_when_a_cancelled_appointment_is_rescheduled_by_post`:
  POST review on CANCELLED -> "This appointment is cancelled, so it cannot be rescheduled."
  Red today. Existing GET test at line 138 stays green (it asserts only status and the link).

Red proof, recorded in the review, not committed: temporarily delete one `_RULE_SENTENCES`
entry; `returns_a_sentence_for_every_booking_rule` must fail; restore.

## Invariants

- Authorization: unchanged. Admin pages keep `allowed_roles = {ADMIN}` from the session.
  Sentences use only the server status and server rule codes; no request value is echoed.
- Append-only audit, one transaction: unchanged. Refused actions write nothing; the tests
  assert counts.
- Double booking: no change to placement or conflict code.
- Sensitive data: no sentence contains a name, reason, contact or code.
- Status lookup never raises: `ValueError` on `AppointmentStatus(...)` and `.get` on the
  badge table both fall back to the stale sentence (a 500 is the failure to avoid).

## Blast radius

- `booking_refusals.py` is in `scheduling/domain`: `make mutate` mutates it. The joined
  function must die through the multi-rule test; table survivors through the every-rule test.
- Patient and clinician booking pages with two violated rules show two sentences. Intended.
- Admin reschedule and admin book 422 pages now carry sentences.
- Admin status actions: 409 pages carry the status sentence.

## Trust boundaries

- Admin HTTP form (`starts_at`, action path): validated and authorized in the existing use
  cases; not changed. Refusal text is built from server values only.
- The `current_status` string may come from the FHIR path or the waitlist; it is treated as
  untrusted text and only looked up, never echoed.

## Domain entities (CLAUDE.md §3)

Appointment, AppointmentType, AvailabilityRule, Clinician, Patient, Admin, AuditLogEntry,
Notification, Session.

## Impeccable (UI copy)

Before editing, the executor reads the impeccable skill's `reference/craft-floor.md`.
`PRODUCT.md` does not exist; `drlibre-specs.md` section 16 is product truth. Text-only
change: no layout, no CSS, no component, so the 375 px and 1440 px checks do not apply.
The orchestrator reads the sentences in a browser.

## Commits

Intermediate commits: `Refs #34` for the rule sentences, `Refs #35` for the status
sentence. The orchestrator's squash message carries `fixes #34` and `fixes #35`; no
closing words elsewhere.

## Not in this run

- Items 3 to 10 and 5a (#37, #40, #43, #42, #49, #44, #39, #36): separate tasks.
- Admin reschedule GET for a status that forbids it (`admin_appointment_reschedule.py`
  `RescheduleTimesPage`, `STATUS_CHANGED`) and the clinician one (`clinician_reschedule.py:42`):
  still the stale sentence. Same helper; a one-line follow-up.
- Admin waitlist accept and cancel-offer invalid transitions: still the stale sentence
  (`WaitlistStatus` values; no phrase passed).
- Patient and clinician POST invalid transitions (`change_refused_page`): text "The status
  of this appointment no longer allows this change." stays.

## For the owner

- No admin status page can be truly stale: no page sends `expected_version` (grep of
  `scheduling/views/pages/`). So the stale sentence has no admin status case left. Decide
  whether it stays for the status POST, or whether stale status should be detected, which
  needs the page to send the version.
- `start_in_the_past` has a sentence and a `BookingRule` value, but `drlibre-specs.md` 5.3
  lists five rules and no start-in-the-past row. Add it to 5.3, or drop the sentence.

## What I will not do

No new abstraction, module, dependency or refactor of the refusal pipeline; no change to
`drlibre-specs.md`; no keyword grouping on `admin_refused_page` (later task).

## Verification plan

`make lint`, `make test`, `make gate`, `make mutate` on the run branch. No browser check
in this run; the orchestrator reads the sentences at 375 px and 1440 px in a browser.

## Architect review, addressed

1. Missing every-rule page test: added `returns_the_rule_sentence_and_no_code_on_every_booking_page_for_every_rule`
   over admin and `change_refused_page` (patient and clinician). Red for admin, green for
   the other, stated.
2. Status lookup fallback: `ValueError` and `.get` both fall back to the stale sentence;
   tests `returns_the_stale_sentence_when_the_status_is_not_an_appointment_status` and
   `returns_the_stale_sentence_when_no_action_is_named`.
- Non-blocking: `admin_appointment_book.py` reaches the change through `admin_refused_page`
  (stated in Blocks, item 5). Test modules named. Six parameters noted. The non-empty
  fallback is stated.

## Architect review

Second independent read against `CLAUDE.md`, the source and the QA steps. Earlier review
points are addressed: the every-rule page test covers admin and `change_refused_page`
(patient and clinician), and the status lookup falls back on `ValueError` and on `.get`.

Checked against the code, all correct: `refusal_for`, `_RULE_SENTENCES` and `_rule_refusal`
(`booking_refusals.py`); `STAFF_APPOINTMENT_BADGES`; `invalid_transition` also raised from
the FHIR path and the waitlist with raw strings; `reschedule_appointment` returns
`invalid_transition` for CANCELLED (the admin lock passes, then `RESCHEDULABLE_STATUSES`
refuses); `StatusActionPage`, `CancelPage` and `RescheduleReviewPage._refused` call
`admin_refused_page` as the plan says; `RescheduleTimesPage` keeps its own `STATUS_CHANGED`.
Spec 5.3 has five rows and no start-in-the-past row, as the plan's owner note says.

Non-blocking:
1. "This appointment is no-show, so it cannot be completed." is not "reads correctly for
   no-show" as the plan claims. Either accept the awkward wording and drop the claim, or
   give NO_SHOW its own phrase.
2. `test_booking_refusals.py:124`, `returns_the_first_known_rule_sentence_when_unknown_rules_come_first`,
   becomes false once `_rule_refusal` joins every sentence. Rename it in the same commit.
3. The join changes patient and clinician output beyond #34. Spec 4 ("lists the violated
   rules") supports it and the plan states it. Add a page-level two-rule assertion so
   the change is seen, not only a domain test.
4. `rules_sentence` has one caller (`_rule_refusal`). Inlining it is smaller; keeping it is
   fine if the owner wants it public.
5. `admin_refused_page` gets six parameters. Accepted by the plan; the later keyword task
   covers it.

Scope: the slice (items 1 and 2) is coherent. The product stays whole: the admin page
uses the same table as the other pages, and no waitlist or FHIR text changes. Security:
the status text comes from server enums, and the raw `current_status` is looked up, never
echoed. No new dependency, no migration, no spec edit.

Verdict: approve.
