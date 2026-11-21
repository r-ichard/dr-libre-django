# Review: task 14, patient portal home and appointments

Scope read: views `patient_appointments.py`, `patient_reschedule.py`, `patient_refusal.py`,
`patient_rows.py`, `booking_steps.py`; use cases `patient_appointments.py`, `booking_page_data.py`;
domain `portal_options.py`; templates; `urls.py`; tests. Diff stat and `git log` checked.

## Confirmed at a glance
- Authorization from session (`allowed_roles = {PATIENT}`, `self.user`); record rule via `guard_record`
  (404 missing, 403 other patient's), `patient_appointments.py:own_appointment`.
- Writes go through `cancel_appointment` / `reschedule_appointment` (transaction, audit, conflict checks live there; not re-implemented).
- Proof trace: commits `verify_green`..`prove` touch only `test_portal_options.py` and `test_patient_portal_guards.py`. Clean.
- No new dependency, no escape hatches, gate and lint passed in `check`.
- No-store headers via `add_never_cache_headers` in `page_view.py:44`.

## Findings

### Important
1. `scheduling/templates/homes/patient.html:4`, `scheduling/views/pages/homes.py:16`: home is unchanged.
   Still "Hello, name / Patient portal". Task item 1 (and plan step 6, plan line 98) require the next upcoming
   appointment, unread notification count and a "Book an appointment" action. No test covers it.
   Risk: requested behaviour missing; a patient landing after sign-in sees no appointment and no way to book.
   Fix: in `PatientPortal.get`, add `upcoming_appointments(user, now)[:1]` row, unread count (Notification
   model, own user only), link to `/book`; render with `appointment_card.html`; add tests incl. empty state.

### Minor
2. `patient_refusal.py:38`: the 24-hour rule is shown from `appointment_options`, while the use case decides
   with its own `_cancellation_violations`. Both use `CANCELLATION_WINDOW`, so they agree today; a second source of truth if rules change.
3. `patient_reschedule.py:49`: `week_of_slots` failure becomes a bare 404 with no way forward (item 6).
4. `patient_appointments.py:56`: `assert` guards (noqa with code and reason) repeated in every handler; acceptable, noisy.
5. `appointment_card.html:3`: heading ids use `forloop.parentloop`; breaks if the include is used outside a nested loop (duplicate ids).

## Blocking
- Home page (task item 1) not implemented: greeting only, no next appointment, unread count or "Book an appointment" (`homes/patient.html`, `homes.py`).
  Outcome: fixed. Tests `returns_home_with_next_appointment_unread_count_and_book_action`,
  `returns_home_empty_state_when_patient_has_no_upcoming_appointment` in
  `test_patient_appointments_page.py`.

## Later
- Single source for cancel/reschedule rules (finding 2).
- Way forward on week-load failure (finding 3).
- Robust heading ids in `appointment_card.html` (finding 5).

## Second pass (after `address`)
Re-read `homes.py`, `homes/patient.html`, the two new home tests and `git diff --stat 909bff3 HEAD`.
- Home now shows greeting, next upcoming appointment (own rows only via `upcoming_appointments`), unread
  count filtered to `recipient=self.user`, and the "Book an appointment" link. Empty state covered.
  Tests assert another user's unread notification is not counted. Blocker closed.
- `address` touched only home view, template, tests and docs. `refactor` touched only `patient_refusal.py`.
- No new blocker. Later list unchanged.
- Minor: `homes/patient.html` empty-state text has no action inside the card; the "Book an appointment" button
  below serves it. Acceptable.
