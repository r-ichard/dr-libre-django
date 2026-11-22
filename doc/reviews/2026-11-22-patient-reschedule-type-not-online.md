# Review: task 27b item 7, patient reschedule for a type not bookable online (#49)

Slice: item 7 only. Plan: `doc/plans/2026-11-22-patient-reschedule-type-not-online.md`. Diff: `git diff main...HEAD`, 6 files, +248 −6. HEAD is `5d975e1` (check). Full `make test` re-run on HEAD: 4908 passed.

## Plan in one sentence per block

- `scheduling/domain/portal_options.py:21`: a constant holding the type sentence. Confirmed at a glance; it equals `booking_refusals.py:61` word for word (see F1).
- `portal_options.py:40-52` `appointment_options`: takes the flag; blocked reasons (cancelled, completed, started, 24 h window) still return first, otherwise cancel is allowed and reschedule comes from `_reschedule_option`. Confirmed at a glance.
- `portal_options.py:55-60` `_reschedule_option`: type not online → refuse with the type sentence; status not rescheduable → refuse with "checked in"; else allow. Traced: the type check now runs before the status check, so a checked-in appointment of such a type gets the type sentence (see F2).
- `patient_rows.py:20-22`: passes `appointment.appointment_type.is_bookable_online`; the row loses the Reschedule button and the card hint (`components/appointment_card.html:12-13`) shows the reason and phone. Confirmed.
- `patient_refusal.py:43-48` `blocked_page_or_none`: same argument; a refused reschedule answers 409 with the sentence, the hospital name and phone (`:53`). Confirmed. Both reschedule GETs call it before `week_of_slots` (`patient_reschedule.py:46-48`, `:81-83`), so the 404 `TIMES_UNAVAILABLE` branch (`:57`) is no longer reached for this case.
- `test_portal_options.py:25-34`: one new domain test, a refusal with the sentence and cancel still allowed. Confirmed.
- `test_patient_appointments_page.py:312-375`: four view tests (GET reschedule 409, GET review 409, list without Reschedule and with Cancel plus call hint, POST review 422 with times unchanged and no `appointment.reschedule` audit row). Each names one behaviour and states the spec value. Traced each assertion against the status and the audit action name (`scheduling/use_cases/appointment_changes.py:89` writes `appointment.reschedule`, so the count-zero check is live, not vacuous).

## Commit trace (§13, proof left no trace)

- `681455a` verify_green → `5b58207` prove: prove is empty (`git show --stat 5b58207` prints nothing). Nothing to flag.
- `b40b306` refactor (after prove) changed `portal_options.py` only: `_reschedule_reason` became `_reschedule_option`. That is after the proof window, so it is allowed. The refactor kept the behaviour; the domain test and view tests above still pass on HEAD.
- `5d975e1` check: no change.

## Checks in the order of CLAUDE.md §2 / the review brief

1. Plan per block: above.
2. Correctness: GET and review GET refuse before any slot work; POST refuses through `reschedule_appointment` → `violated_booking_rules` (`placement_checks.py:132` passes `slot.appointment_type.is_bookable_online`), so the write refusal is unchanged. No error is swallowed. No new exception.
3. Authorization: `own_appointment` and `appointment_or_refusal` unchanged. The type flag is read from the database (`appointment.appointment_type`), never from the request. No new route, no payload field, nothing new in URLs or logs.
4. Double booking: no placement, conflict or transaction code changed. Not in this diff.
5. Tests: derived from spec values (5.3 `type_not_bookable_online`; 12.3 404 is for missing/not-own, not used here). Each new test was red before the fix per the red stage; the guard POST test is green before the fix by design and is stated as such in the plan. The existing domain test `returns_both_allowed_when_type_bookable_online_and_starts_in_25_hours` was not edited to pass `True` (see F4).
6. Names: `TYPE_NOT_ONLINE_REASON`, `_reschedule_option`, `type_bookable_online` state roles. Comments: none added in the diff. The `# noqa: S101` lines in `patient_reschedule.py:42,77` predate this change.
7. Scope: diff is the six product and test files plus the plan and the review. No `drlibre-specs.md` change, no dependency change, no template or CSS change, no migration, no contract change (API and FHIR not touched).

## Findings

- **F1, Later**, `scheduling/domain/portal_options.py:21`. The type sentence is written a second time; `booking_refusals.py:61` already holds it. The plan said "taken from `refusal_for(...)`, so the sentence is not copied". Risk: the two copies drift the day the owner rewords one. Smallest fix: `TYPE_NOT_ONLINE_REASON = refusal_for(Failure.rule_violation([BookingRule.TYPE_NOT_BOOKABLE_ONLINE])).message`, or import `_RULE_SENTENCES` through a public name. Not a blocker: the text is identical and the tests pin it.
- **F2, Later**, `portal_options.py:58-59`. Precedence not decided: a CHECKED_IN appointment of a type not bookable online now says the type sentence, not "already checked in". Both refusals are true; the plan's architect review asked for the order to be stated or tested, and neither was done. Smallest fix: add one domain case for CHECKED_IN plus `type_bookable_online=False` and state in the plan which sentence wins.
- **F3, Later**, `portal_options.py:44`. `type_bookable_online: bool = True` defaults to allowing reschedule. A future caller that omits the argument shows a Reschedule button for a type the rules refuse. Server-side the write is still refused (`placement_checks.py:132`), so this is display only. Smallest fix: drop the default (the plan said "a fourth parameter `type_bookable_online: bool`", no default) and pass it explicitly at the three callers, which all do already.
- **F4, Later**, `scheduling/domain/test_portal_options.py:14-20`, `:38-...`. The plan said to add `True` as the fourth argument to the existing calls (about 12 sites; there are 9) so the old expectations run on the new path. Because of F3's default, the calls were not changed, so the tests above still run the default. Fix goes with F3: once the default is gone, add `True` to each call.
- **F5, Later**, test names. The plan named `returns_no_reschedule_button_and_call_hint_when_type_not_bookable_online` and `returns_refusal_and_keeps_time_when_patient_posts_...`; the tests are `returns_no_reschedule_link_and_call_hint_...` and `returns_422_and_keeps_time_...`. The new names are better (the 422 is the contract value). Recorded only so the plan and the code agree when read later.
- **F6, Later** (measured, not a blocker). `make test` on this sandbox: 4908 passed in 77.34 s on HEAD (the run above; the sandbox is shared, so this number is not a budget).

## For the owner

- Same refused reschedule gives **409** on the GET pages (`patient_refusal.py:54`) and **422** on the POST (`booking_refusals.py:49` via `change_refused_page`). Cancel has the same split. Which status the spec wants is not stated in `drlibre-specs.md`. Not decided here; no change made.

## Blocking

None.

## Later

- F1, F2, F3, F4 above (one fix covers F3 and F4).
- F5 naming note.
- F6 measured number.

## Left for the orchestrator

From the plan's "Not in this run" and the task:
- Items 1 to 6 and 8 to 10 of `doc/backlog/27b-qa-round-3-pages.md`: not done here, by design.
- Plan risk, not fixed: an inactive appointment type (`is_active=False`) still answers 404 on reschedule (`active_appointment_type` returns None → `not_found`). Raise as its own finding.
- Not run in this stage: `make mutate` and `make fhir-validate`, the last scripted gates. The domain change needs `make mutate` to kill the sentence, flag and status-order mutants.
- Browser check at 375 px and 1440 px of the 409 refusal page and the card hint (plan, Layout). No template changed, so the orchestrator checks the existing components only.
