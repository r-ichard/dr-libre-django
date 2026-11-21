# Review: task 15, patient portal, waitlist, notifications, profile

Diff `main...HEAD`, 47 files: domain rules, use cases, seven page routes, templates, the three carried fixes, one migration. Second pass after the `address` stage. The first pass blocked on missing pages, ownership tests and the bare 404; the pages, routes and tests are now in the diff. I re-read them rather than trusting the earlier "Fixed" notes.

## Confirmed

- **Plan in one sentence, at a glance:** `patient_notifications.py`, `patient_waitlist.py`, `patient_profile.py` and `portal_forms.py` each read as a thin view that parses form input, calls one use case and renders or redirects with 303. Tracing was needed only for `change_password` (`scheduling/use_cases/profile.py:50-75`) and `_join_errors` (`scheduling/views/pages/patient_waitlist.py:98`).
- **Authorization:** every view sets `allowed_roles = {PATIENT}`. The patient is `self.user` from the session. Ids in the address go through `guard_record` (`notification_inbox.py:35`, `waitlist_inbox.py:19`), which gives 404 for a missing row and 403 for another patient's. `mark_all_read` filters on `recipient=actor`. The password page raises 404 for a passwordless patient on GET and POST (`patient_profile.py:84`) and `change_password` itself returns forbidden (`profile.py:52`).
- **Audit:** `update_profile`, `change_password`, `mark_read` and `mark_all_read` record the audit entry inside the same `transaction.atomic()`. Metadata holds field names, counts and ids, never the phone, birth date or a password. Joining and accepting go through the task 09 use cases unchanged.
- **Password rules:** a wrong current password calls `record_wrong_password` (`profile.py:57-59`), which counts toward the task 05 lockout. A locked address answers the same message. The other sessions end and the current one is kept (`profile.py:63-66`).
- **Hard rules:** `make gate` is clean (no `Any`, `cast`, bare ignore or bare noqa, no swallowed error, sizes within cap). The `noqa` lines name their code.
- **Proof left no trace:** `c612072..4180e87` (`verify_green` to `prove`) changes only three test files. The later `profile.py` change falls in the `refactor` stage, which may change product code.
- **Carried fixes:** `.card-list` uses `var(--space-4)` (`static/css/components.css:77`). Past completed or missed appointments show no "Call the hospital" hint (`appointment_card.html:10`, `portal_options.py:62`). The unloadable week strip answers the refusal page with a way back (`patient_reschedule.py:46`).
- **UI:** one `portal_nav` on all five sections with `aria-current="page"`, 44 px targets and wrapping at 375 px. Unread state is a word, not colour alone. No inline script or style. Forms are plain POST and work without JavaScript. Empty states exist for waitlist, notifications and appointments.

## Findings

1. **Nit, `scheduling/use_cases/notification_inbox.py:52-56`.** `mark_all_read` saves row by row, so a patient with many unread rows runs one UPDATE each. Smallest fix: one `QuerySet.update(read_at=now)` inside the same transaction, keeping the count for the audit entry. Correct today.
2. **Nit, `scheduling/use_cases/profile.py:57-61`.** The recorded wrong-password failure survives only because the function returns instead of raising inside `atomic()`. A later raise there would silently lose the lockout count. Add a test that pins the record, or a comment saying why it must not raise.
3. **Nit, `scheduling/use_cases/profile.py:54-55`.** A locked address gets "The current password is not right", with no hint about the lockout. This gives no oracle, but it could confuse a patient. A product decision.
4. **Nit, `scheduling/templates/components/notification_card.html:5`.** Times are shown as UTC, not in the hospital's zone. The rest of the portal uses the hospital zone. Notifications carry no hospital, so this needs a decision (the patient's zone, or the linked appointment's hospital).
5. **Nit, `scheduling/models/booking.py:147`, migration `0010`.** The plan said no migration. The change is a default on `created_at` with no data rewrite, and `test_migrations.py` is updated. It is harmless but missing from the plan. Name it in the plan or retro.
6. **Nit, `scheduling/views/pages/patient_waitlist.py:121-130`.** Any non-invalid-input failure on join is mapped to "Choose a service" or "That provider does not offer this service". A real forbidden or conflict failure would show a misleading message. Narrow the mapping by failure code.

## Blocking

None.

## Later

- Bulk update in `mark_all_read` (finding 1).
- Pin or comment the failure-record-in-transaction behaviour (finding 2).
- Lockout hint on change password (finding 3).
- Notification time zone (finding 4).
- Name migration `0010` in the plan (finding 5).
- Narrow the join failure mapping (finding 6).
