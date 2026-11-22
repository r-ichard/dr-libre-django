# Review: task 27b items 1 and 2 (rule sentences, status sentence)

Branch `fabro/run/01M82M5WGW9EYSWSXQK9X4S2P2`, against local `main`. Plan:
`doc/plans/2026-11-22-task-27b-rule-and-status-sentences.md`. Issues #34 and #35.

Verdict: **approve**. No blocking item.

## Commit order (proof trace, §7)

| Commit | Stage | Product code | Tests |
|---|---|---|---|
| `420a727` | green | yes | yes |
| `678a8ad` | verify_green | none (empty) | none |
| `9a61ed7` | prove | no | yes |
| `73fe08a` | refactor | `booking_refusals.py` (constant rename) | no |
| `e18778a` | check | none | none |

Between `verify_green` and `prove` only test files changed (`git diff 678a8ad..9a61ed7`:
two test files). The product change after `prove` is the refactor stage, which the stage
order allows. No mutation was left behind.

Test count: 4938 at `verify_green`, 4935 at `check`. The difference is explained by
`prove`: it deleted the six-case `returns_a_sentence_for_every_booking_rule` and added three
rows to `returns_plain_sentence_when_a_booking_rule_is_violated` (net -3).

## Block by block (§2.5)

- `scheduling/domain/booking_refusals.py:43-49` `_rule_refusal`: joins the known sentences
  in the order given; 422 when any is known, else `SLOT_TAKEN` 409. Confirmed at a glance.
- `booking_refusals.py:13`, `:52` `SECONDS_PER_HOUR`: renamed from `MINUTES_PER_HOUR`
  squared. The value is 3600 both ways. Traced to confirm; no change in behaviour.
- `scheduling/views/pages/admin_refusal.py:28-44` `admin_refused_page` gains
  `action_phrase`. Traced: the signature and the single call site.
- `admin_refusal.py:47-52` `_message_and_status`: the `RULE_VIOLATION` branch is gone, so
  rule failures fall through to `refusal_for`. The `INVALID_TRANSITION` branch calls
  `_transition_message`. Traced.
- `admin_refusal.py:66-71` `_transition_message`: stale sentence when no phrase or no badge;
  else one template. Confirmed.
- `admin_refusal.py:74-79` `_current_badge`: parses the raw `current_status` through
  `AppointmentStatus(...)`, catches `ValueError`, looks up the badge table. Traced; see
  checks below.
- `admin_appointments.py:186, 195, 212, 218, 238`: phrases per action. Confirmed.
- `admin_appointment_reschedule.py:113`: `action_phrase="rescheduled"`. Confirmed.
- `admin_appointment_export.py:27-31`: not in the plan; see Later 4.

## Checks

1. **Correctness and errors.** `_current_badge` turns an untrusted string into the stale
   sentence when it is not an `AppointmentStatus` (FHIR and waitlist strings). This is an
   expected value in the contract, not a swallowed error (§9). `STAFF_APPOINTMENT_BADGES`
   covers all six `AppointmentStatus` members, so `.get` returns `None` only for a future
   member, and that also falls back to the stale sentence (no 500).
2. **Authorization and boundaries (§11).** No route, role or session check changed.
   `admin_refused_page` takes its text from the server status and the server rule codes.
   No request value is echoed. The new strings name no person, reason or contact.
3. **Double booking (section 5.2).** No change to placement or conflict code.
4. **Audit and transaction.** No write path changed. Refused actions still write nothing;
   the new tests for booked and checked-in assert the audit and notification counts.
5. **Callers of `admin_refused_page`.** `admin_appointment_book.py:217` now shows sentences
   for rule failures (intended). `admin_waitlist.py:103, 188, 201` pass no phrase, so
   `INVALID_TRANSITION` stays on the stale sentence (as planned). The waitlist use cases
   return no `rule_violation`, so their text is unchanged. `admin_users.py:155` and the FHIR
   path do not reach this page.
6. **Specification.** `drlibre-specs.md` is not in the diff. No `doc/` file other than the
   plan is in the diff.
7. **Names and comments (§3, §4).** Names state roles. The two docstrings are short and
   say why. No comment is over 255 characters (gate clean).
8. **Hard rules.** No `Any`, `cast`, bare `# type: ignore` or bare `# noqa` in the diff. The
   only `# noqa: S101` is on an existing line. No function over 50 lines, no file over 300
   in the touched files (gate clean).

## Tests (§10.1)

Derived from the specification and the issues, not from the implementation, except as
noted. Checked against the plan's named list:

- Present: `returns_the_rule_sentence_and_no_code_on_every_booking_page_for_every_rule`
  (admin, patient and clinician callers, six rules; the sentences are now literal, not
  taken from `refusal_for`, from `prove`), `returns_the_status_sentence_when_status_action_is_not_allowed`,
  `returns_the_stale_sentence_when_the_status_is_not_an_appointment_status`,
  `returns_the_stale_sentence_when_no_action_is_named`, `returns_every_sentence_in_order_when_several_rules_are_violated`,
  `returns_slot_taken_when_no_violated_rule_is_known`, the booked and checked-in admin
  tests (with count asserts), the completed assert, both reschedule tests (named
  `returns_409_and_the_cancelled_sentence_when_rescheduled_by_post` in the file).
- Missing by name: `returns_a_sentence_for_every_booking_rule` was deleted in `prove`
  (`9a61ed7`). Its guard is kept by the six exact-sentence rows at
  `test_booking_refusals.py:46-56` and by the page test. Not a blocker; see Later 1.
- The plan's red proof (temporary removal of one `_RULE_SENTENCES` entry) is not recorded
  anywhere. With the test deleted it no longer applies; see Later 5.

## Blocking

None.

## Later

1. `scheduling/domain/test_booking_refusals.py:46-56` (the rows, and the deletion at
   `9a61ed7`). Plan promised `returns_a_sentence_for_every_booking_rule`; `prove` deleted it.
   Risk: none measured; the six exact rows are stronger. Smallest fix: keep as is, or restore
   the test by name and note in the plan.
2. `scheduling/domain/test_booking_refusals.py:130-135`. Renamed to
   `returns_the_known_rule_sentence_when_unknown_rules_come_first`, but it asserts only
   `status == 422`. The name promises a message check. Risk: a regression in the message
   passes. Fix: assert the joined message of the two known rules.
3. Page-level two-rule assertion is missing (architect non-blocking 3). Patient, clinician
   and admin pages now show two sentences for two violated rules; only the domain test
   covers it. Fix: one parametrized page test with two rules.
4. `scheduling/views/pages/admin_appointment_export.py:27-31`. Not in the plan. Needed: the
   `RULE_VIOLATION` branch went away, so the export's `TOO_MANY_ROWS` would otherwise have
   become "That time was just taken.". Output is the same text, status 422. The export use
   case returns only `rule_violation` (`admin_appointment_export.py:42`), so the new
   `message_page` call cannot show "too many rows" for another failure. Fix: keep; add a line
   to the plan.
5. Plan and code differ: `rules_sentence` is not created. The join is inline in
   `_rule_refusal` (`booking_refusals.py:43-49`), as architect non-blocking 4 suggested. Fix:
   update the plan text.
6. `SECONDS_PER_HOUR` rename (`booking_refusals.py:13`, `:52`) is unplanned. It is correct and
   the value is unchanged. `scheduling/views/pages/admin_settings.py:14` defines the same
   constant again. Fix: later, one shared constant.
7. `returns_409_with_a_way_forward_when_a_completed_appointment_is_cancelled`
   (`test_admin_appointment_pages.py:217-225`) asserts the sentence only. The plan promised
   unchanged audit and notification counts there. Fix: add the two count asserts as in the
   booked test.
8. NO_SHOW wording. `admin_appointments.py:218` gives "marked as no-show", so a refused
   check gives "This appointment is no-show, so it cannot be marked as no-show." The plan
   said it reads correctly; it does not. Fix: a NO_SHOW-specific sentence, or accept the
   wording and drop the plan's claim.
9. Test runtime, measured here on a shared machine (not a blocker, §budget): `make test`
   70.78 s at `verify_green`, 68.27 s at `check`, 94.54 s on the red run. The orchestrator
   measures on a quiet machine.
10. Red proof of the every-booking-rule guard was not recorded (see Tests). Moot after
    deletion; record the red proof of the new page test instead if the plan's red-proof step
    is kept.

## Left for the orchestrator

From the plan's "Not in this run" (out of this slice, not blocking):

- Items 3 to 10 and 5a (#37, #40, #43, #42, #49, #44, #39, #36): separate tasks.
- Admin reschedule GET for a status that forbids it (`admin_appointment_reschedule.py:37-45`,
  `STATUS_CHANGED` from `patient_refusal.py:15`) and clinician reschedule
  (`clinician_reschedule.py:42`): still the stale sentence.
- Admin waitlist accept and cancel-offer invalid transitions (`admin_waitlist.py`): still the
  stale sentence.
- Patient and clinician POST invalid transitions (`change_refused_page`): text "The status of
  this appointment no longer allows this change." stays.

From the plan's verification plan, not run here:

- `make mutate` on `scheduling/domain` (the last scripted gate). The multi-rule join is the
  survivor target named in the plan.
- Browser read of the sentences at 375 px and 1440 px. No browser in this sandbox.

## For the owner

- No admin status page can be stale: no page sends `expected_version`
  (grep of `scheduling/views/pages/`). So the stale sentence has no admin status case left.
  Decide whether it stays for the status POST, or whether stale status should be detected,
  which needs the page to send the version.
- `start_in_the_past` has a sentence and a `BookingRule` value ("That time has already
  passed."), but `drlibre-specs.md` section 5.3 lists five rules and no start-in-the-past
  row. Add it to 5.3, or drop the sentence.
