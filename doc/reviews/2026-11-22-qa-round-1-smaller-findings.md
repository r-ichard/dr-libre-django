# Review: task 17b, QA round 1, the smaller findings

Base `88f8fe4`, head `35903a1`. No local `main` in the sandbox. 64 files, mostly tests.
`make lint`, `make test` (2449 passed, 21.7 s) and `make gate` passed in the `check` stage.
`make mutate` was not run by me.

## Stage trace (checklist 7)
`prove` (52b763b) touches tests only (six `test_*.py` files). `refactor` (d48a104) touches
`use_cases/placement.py` only, which is allowed after `prove`. No mutation left behind.

## Plan in one sentence, per block (checklist 1)
- Online-only visibility: `online_only_for(user)` picks the filter, `active_appointment_type` and
  `department_clinicians` apply it. Seen at a glance. Traced: `placement._select` keeps the type
  visible (`online_only=False`) and filters only the clinician pool by actor, so a staff booking
  keeps non-online types and a patient gets the typed `rule_violation`.
- Record rule: `OwnAppointmentPage.appointment_or_refusal` gives forbidden, cancelled gives 404.
- Notice: server sets a 60 s `HttpOnly`, `SameSite=Strict` cookie, next page takes it and deletes it.
- Room: `choose_room` and `_select` drop the room when the type needs none.
- Details form: shared domain rules (`valid_birth_date`, `phone_failure`) run in `read_details`.
- `slot_is_offered` gates the details GET.
- Password: all problems collected in one answer, empty is "enter".
- Focus: one selector, `[data-autofocus], [aria-invalid="true"]`.
- Limits: pure functions in `domain/request_limits.py`, `declared_length` returns `None` for junk,
  `handler400` plus `process_exception` for pages.

## Findings
1. Low, `doc/adr/0004-failure-contract-and-request-context.md` (amendment table, "Page number"):
   says "patient portal list: at most 6 digits" while the API maximum is 1,000,000 (7 digits). The
   two limits differ and the table does not say so. Fix: state 999,999 for the portal.
2. Low, `scheduling/views/pages/portal_forms.py:redirect_with_notice`: cookie has no `secure=True`.
   Harmless today (local only, notice key not sensitive), wrong once served over TLS. Fix: set
   `secure=not settings.DEBUG`.
3. Low, `scheduling/views/middleware.py:5,20`: middleware imports from `views.pages`, an API/page
   layering cross. Fix: move `bad_request_page` to a shared module when a second caller appears.
4. Low, `scheduling/views/pages/errors.py:bad_request_page`: `exception` argument unused. Django
   handler signature requires it, so keep.
5. Low, `scheduling/views/test_hostile_input.py:_requests_for`: a guard-refused actor only gets the
   size and field kinds, and a GET never carries a JSON or form body. Plan states this, and the
   suite is under 30 s. Risk: a route that reads the body before its guard would be missed. Fix:
   none now; revisit if a route reads before the guard.
6. Low, `mutation-equivalents.txt`: the new `json_depth__mutmut_3` entry has a sound reason, but
   mutant numbering shifts with edits to that function. Re-run `make mutate` after any edit.

## Checked, no defect
- No `Any`, `cast`, bare `type: ignore` or `noqa` found in the diff; one `type: ignore[call-overload]`
  names its code. No file or function near the caps.
- Writes: change_password and cancel/reschedule keep their audit entries inside the transaction;
  notifications are created in the same transaction.
- Authorization comes from the session (`self.user`, `request.user`), never the payload.
- Double booking: placement still locks clinicians, rooms and patient in the transaction; the room
  rule only removes a room when none is needed.
- No dependency added.

## Blocking
None.

## Later
Findings 1 to 3, 5 and 6 above.
