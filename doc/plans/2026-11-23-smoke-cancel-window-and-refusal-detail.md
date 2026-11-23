# Task 27c item 2: smoke search window past the cancel window, and refusal detail in step failures

Slice: both changes of the orchestrator's run on the fresh stack. This is the whole of this run.

## Focal point

`scripts/smoke.py`. Two defects, both in the smoke test only. (1) `_first_free_start` searches from now, so the first slot can start under 24 hours away, and the patient's online cancel is refused with 422 `cancellation_window_closed` (drlibre-specs.md 5.3). (2) A failed step says `cancel answered 422, wanted 200` and nothing else, so the code and the violated rules are lost.

## Blocks and one-sentence plans

- `scripts/smoke.py` constant block (after `SEARCH_DAYS`, line 21): add `SLOT_SEARCH_START_HOURS = 25` with a one-line comment: online cancel needs the start 24 hours or more away (drlibre-specs.md 5.3); the search starts past that.
- `scripts/smoke.py` `_first_free_start` (lines 91-101): the window starts at now plus `SLOT_SEARCH_START_HOURS`; it still spans `SEARCH_DAYS`, so `to` is `from` plus 14 days.
- `scripts/smoke.py` `_expect_status` (lines 66-68): on a status mismatch, append `_refusal_detail(answer.body)` to the existing message.
- `scripts/smoke.py` new `_refusal_detail(body: str) -> str`, placed above `_expect_status`: returns `""` unless the body is JSON, its top level is an object, `error` is an object and `error.code` is a string. Otherwise returns `": <code>"`, followed by `"; violated rules: a, b"` when `error.details.violated_rules` is a list, and the list's string items are non-empty. Non-string items are dropped. Nothing else of the body is read or printed: no `message`, no `correlation_id`, no other `details` keys.
- `scripts/test_smoke_window_and_detail.py` (new file): the tests below. It imports `FakeStack`, `PROVIDER_ID`, `APPOINTMENT_ID`, `APPOINTMENT_TYPE_ID`, `PROVIDER_ANSWER`, `SLOTS_ANSWER`, `HOLD_ANSWER` from `scripts/test_smoke.py`, and uses `json.dumps` for bodies. No copy of the fake.

## Files, in order

1. `scripts/test_smoke_window_and_detail.py`: new, the tests below. Run before any `smoke.py` change: the three red tests fail for the stated reason, the guard tests pass (see below).
2. `scripts/smoke.py`: the constant, `_first_free_start`, new `_refusal_detail`, `_expect_status`.

Not touched, on purpose:
- `scripts/test_smoke.py`: it is at 500 lines and `make gate` fails above 500 (`scripts/size_cap.py`). Importing from it adds no line to it.
- `README.md`, `Makefile`, `doc/backlog/27c-readme-smoke-test.md`, `doc/handover.md`, `drlibre-specs.md`, any server code, any migration.

## Failing tests to write first

In `scripts/test_smoke_window_and_detail.py`, behaviour names as in CLAUDE.md:

Red on the current code (must fail before the `smoke.py` change):
- `returns_search_window_starting_25_hours_from_now_when_holding`: `before` and `after` are `datetime.now(UTC)` read naive (`.replace(tzinfo=None)`) just before and after the `hold_step` call. The slot search's `from` satisfies `before + 25h - 1s <= from <= after + 25h` (instants are cut to whole seconds). `to` is exactly 14 days after `from`. Fake answers: `PROVIDER_ANSWER`, `SLOTS_ANSWER`, `HOLD_ANSWER`.
- `raises_smoke_failure_naming_code_and_violated_rules_when_cancel_is_refused`: `Journey(fetch=stack, appointment_id=APPOINTMENT_ID)`; cancel answers 422 with body `{"error": {"code": "rule_violation", "details": {"violated_rules": ["cancellation_window_closed"]}}}`. Message is exactly `cancel answered 422, wanted 200: rule_violation; violated rules: cancellation_window_closed`.
- `raises_smoke_failure_naming_code_without_rules_when_refusal_lists_no_rules`: same journey; cancel answers 409 with body `{"error": {"code": "conflict", "details": {}}}`. Message is exactly `cancel answered 409, wanted 200: conflict`.

Guards on the new error path (pass on the current code, because the status check runs first; they fail if `_refusal_detail` stops guarding its parse, which is the proof they can fail):
- `returns_status_only_message_when_refusal_body_is_not_json`: cancel answers 500 with body `<html>Server Error</html>`. Message is exactly `cancel answered 500, wanted 200`. This is the case the architect named: a Django 500 page must not turn into a traceback.
- `returns_status_only_message_when_refusal_error_has_wrong_shape`, parametrized over three bodies, each answered with 500 and expecting exactly `cancel answered 500, wanted 200`: `["error"]` (top level not an object), `{"error": "boom"}` (error not an object), `{"error": {"code": 7}}` (code not a string).

Existing tests in `scripts/test_smoke.py` stay green unchanged. They match with `re.search` on "health answered 503", "code check answered 400", "wanted 'CANCELLED'" and similar, and the suffix does not break them. The existing 14-day window test keeps asserting a 14-day span.

## Invariants and blast radius

- The smoke test only reads and books through the public API on 127.0.0.1. No server code, no authorization, no audit path changes. Audit entries are written by the server exactly as before.
- Blast radius: `make smoke` (Makefile line 48 runs `python3 scripts/smoke.py`) and `make test`, which collects the new test file. The server and the seed do not import `scripts/smoke.py`.
- The slot search window is client-side only. The server's rules (lead time 120 minutes from now, 90-day horizon, 24-hour cancel window) are unchanged; 25 hours clears all three.

## Trust boundaries

- The error body is an answer from the stack under test. It is parsed as JSON, and each field is type-checked before use (object, string, list of strings). A body that fails any check yields the status-only message, never an exception.
- Only the code and the rule names reach stderr. These are the server's fixed vocabulary (`rule_violation`, `cancellation_window_closed`), not personal data. No `message`, booking code, email or name is printed.
- The local stack's answers are not trusted for control flow beyond the status and the existing field checks.

## Domain entities (CLAUDE.md §3 vocabulary)

Visitor (searches, starts a hold), BookingHold (the held slot), Patient (books and cancels), Appointment (the booking; cancel refused as `rule_violation` with `cancellation_window_closed`), AppointmentType (duration, bookable online), Clinician (the provider on the start page), VerificationCode (the code read from the inbox).

## What I will not do

- No change to `SEARCH_DAYS`, to the cancel reason, or to the output of successful steps.
- No shared fixture module, no change to `scripts/test_smoke.py`, no new dependency.
- No README or backlog edits; the orchestrator owns those.
- No status added to content failures (see the open choice).

## Open choice (for the reviewer)

"Its message names the status" is applied to failures that come from an answer's status: the existing `_expect_status` messages, which get the detail suffix. Content failures such as `health reports 'down'` or `no free slot` keep their text. They name the wrong value, and the status there is 200. Adding the status to them would be a separate small change and would move existing test match strings.

## Done check for this run

In the sandbox: `make lint`, `make test`, `make gate` pass. Before the `smoke.py` change, the three red tests fail for the stated reason and the guards pass; after, all pass. The guard proof: with `_refusal_detail`'s JSON parse unguarded, the not-JSON guard fails. `make smoke` against a fresh seeded stack is the orchestrator's check and cannot run here (no Docker in this stage).

## Not in this run

Nothing.

## Risks

- The demo seed must have a free slot from now plus 25 hours through 14 days. Unverified here; the orchestrator's `make smoke` run is the check. The message `no free slot in the next 14 days` now starts 25 hours out, which is still accurate to the window searched.
- Importing from `scripts/test_smoke.py` couples the new file to that module's fixture; if the fixture moves, both files change.

## Revision after architect round 1

Addresses the architect's material point and notes:
- Error path tested: the not-JSON guard and the wrong-shape guard, with the proof described above.
- Cancel tests build the journey with `appointment_id` set.
- Window test reads `before` and `after` around the call, not a fixed clock.
- Duplicate fake replaced with an import, as the nit suggested.
- Open choice on content failures kept, as the architect accepted it.

## Architect review

Round 2. Round 1 asked for the error-path tests; they are in the plan now, and the
body shape they assume is the server's: `error_response` (`scheduling/views/failure_response.py`)
returns `{"error": {"code", "message", "correlation_id", "details"}}`, and the cancel
refusal carries `details.violated_rules` (`scheduling/views/test_appointment_actions.py:85`).
The cancel window is `cancellation_window_closed` in `drlibre-specs.md` 5.3 (24 hours or more);
25 hours clears it and the 120 minute lead time.

Checked against the code:
- The three red tests fail on the current code for the stated reason: the window starts at now,
  and the refusal message has no suffix.
- The two guard tests pass now, as the plan says. They protect the new parse path.
- Existing tests in `scripts/test_smoke.py` match by `re.search` (`cancel answered 409`,
  `wanted 'CANCELLED'`), and the 14-day span test is unaffected by a later start. Green unchanged.
- `scripts/test_smoke.py` is exactly 500 lines; the cap fails above 500, so leaving it untouched
  is required, and the new file is the right place.
- Trust boundary: the body is parsed into `object`, each level type-checked, and nothing but
  `code` and rule names is printed. No sensitive data.

Notes for the implementer (none blocks the run):
1. Line references are stale. `_expect_status` is `scripts/smoke.py` 92-94, not 66-68;
   `_first_free_start` is 141-153, not 91-101.
2. The existing tests import `from scripts.smoke import ...`; the new file should import
   `from scripts.test_smoke import ...` the same way.
3. `json.loads` returns `Any`, which the gate rejects. Annotate `parsed: object`, as `_object_of` does.
4. Scope judgement for the orchestrator, not a revision reason: the brief says "when a step fails,
   its message names the status". The plan adds the status only to status-answer failures.
   Content failures (`health reports 'down'`, `no free slot`) keep their text. Read literally, the brief
   covers those too. Decide before the red stage whether to widen it; the plan's current choice is stated openly.
5. The guard proof (unguarded parse makes the non-JSON guard fail) should be run and recorded in the red stage, not only described.
