# Review: task 26c item 14 (last part), task-numbered test docstrings

Reviewer: second reader, `fabro/run/01M840NRGFQDTBZWJNE0J8S9T4`. Diff: `git diff main...HEAD`, 197 files.
Plan: `doc/plans/2026-11-23-task-26c-item-14-test-docstrings.md`.

## What the diff is

- 194 test and conftest modules under `scheduling/` and `drlibre/`: one hunk each, always at line 1 (`@@ -1 +1 @@`), one line replaced by one line. No code, assertion, import or other comment changed. Checked: 194 of 195 hunks are line-1 hunks; the one other is the new file.
- `drlibre/test_module_docstrings.py` (new, 23 lines): one test, `returns_no_task_numbered_module_docstrings_when_modules_are_parsed`.
- `doc/plans/2026-11-23-module-docstrings-purpose.md`: a two-line banner marking the earlier plan superseded for its section rule.
- The plan file itself.

Plan in one sentence, read without tracing: "rewrite the first docstring line of each task-numbered test module, and add one test that fails on any module docstring that opens with `Task <n>`." Confirmed at a glance from the hunk headers. Traced: the section citations (125 lines gained `Section N`, listed under For the owner) and the test's regex and scan roots.

## Checks run

- `drlibre/test_module_docstrings.py`: `pytest` 1 passed (with the Makefile environment). `ruff check`: clean. `mypy` strict on the file: no issues. `scripts/comment_cap.py`: no violation.
- Remaining offenders on the branch: `grep -rlE '^"""Task [0-9]' scheduling drlibre` returns 0 files.
- Longest changed line: 94 characters (`scheduling/...`, a `Section 12.1` line). Under the 100 cap.
- Proof trace (item 7): commits after the code stage are `8bd3fb9` (check) and `3b5ef87` (prove). Both are empty (`git show --stat` lists no files). The code stage `5bc3b54` (write) is the only commit with the change. No product or migration line moved after it.
- Hard rules: no `Any`, `cast`, bare `# type: ignore` or `# noqa` in the new test. Function far under 100 lines, file under 500. No try/except. No write path, no authorization, no logging touched. `drlibre-specs.md` is not in the diff.

## Findings

1. **Important, not a blocker:** 125 docstrings gained a `Section N` citation where the old first line named none (list under For the owner). The plan made this a judgment per file, "only when a single heading clearly governs". I read the 125 new first lines (listed below) for plausibility; each names a heading that fits its words (for example `scheduling/demo_seed/test_seed_world.py:1`, `Section 16`, for "the seeded world obeys the rules the product enforces"). I did not read each test body against its citation. Risk: a wrong heading sends a reader to the wrong part of the spec. Smallest fix: owner or orchestrator spot-checks the list and drops any wrong citation; the change is one word per line.
2. **Nit:** the red run is not in the diff. The plan says "the red output is recorded in the run", and the prove stage is empty. I could not see that output. The test passes on the current tree (1 passed), which is expected after the rewrite. Its regex `Task \d` matches the 194 original first lines, so it would fail for the right reason. Smallest fix: orchestrator reads the run log for the 194-path failure before merge.
3. **Nit:** `test_module_docstrings.py` uses `ast.get_docstring(tree, clean=False)` and `match`. A module whose docstring starts with a blank line before `Task 1` is missed. Smallest fix: `clean=True`, or `re.match(r"\s*Task \d", ...)`. Not reachable on this tree (`grep` finds 0).
4. **Nit:** `SCANNED_ROOTS` skips missing roots silently (`if not root.is_dir(): continue`). `test_support/` does not exist on this branch, so it is skipped. A misspelled root would also pass silently. Smallest fix: assert each root exists, or drop `test_support` until it exists.
5. **Nit:** the new first lines are not all under the plan's target of 90 characters (the cap is 100; longest is 94). Not a gate failure. Smallest fix: none needed; say so in the PR if the owner cares.
6. **Note:** the goal said the test sits "beside `drlibre/test_product_imports.py`". That file does not exist. The test sits beside the other `drlibre/test_*.py` files, as the plan's decision 1 says. Accepted.
7. **Note, outside line 1 (the owner asked for line 1 only):** `scheduling/views/test_fhir_schedule_writes.py:2` names "task 17"; `scheduling/views/test_search_limits.py:2` and `:3` name "task 12" and "task 26". The gate reads line 1, so these pass. Smallest fix: a later task that rewrites continuation lines.

## Blocking

None.

## Later

- Finding 1 (section citations): owner or orchestrator spot-check of the 125 lines.
- Finding 2 (red run not in diff): orchestrator reads the run log for the 194-path failure.
- Finding 3 (`clean=False` edge case): tighten the scan before a second gate test relies on it.
- Finding 4 (silent skip of missing roots): assert roots exist.
- Finding 5 (lines over the 90-character target): cosmetic.
- Finding 7 (continuation lines naming tasks): a later task.
- Measured, not a blocker: `pytest drlibre/test_module_docstrings.py` took 0.31 s on this machine. The full suite timing is the orchestrator's to measure on a quiet machine.

## For the owner

Decision 5 of the plan: 125 docstrings gained a spec section citation where the old first line named none. Each line is listed below as `file:line`, with the new first line. Line 1 for each. Confirm the citation or tell the orchestrator to remove it.

- `scheduling/demo_seed/test_seed_demo_command.py:1` — Section 16: the seed_demo command, its guards, its accounts and its audit entry.
- `scheduling/demo_seed/test_seed_world.py:1` — Section 16: the seeded world obeys the rules the product enforces.
- `scheduling/demo_seed/test_survives_use.py:1` — Section 16: the seed survives a person using the demo world between two runs.
- `scheduling/demo_seed/test_writer.py:1` — Section 16: what the seeded world contains, and that a rerun changes nothing.
- `scheduling/domain/test_admin_audit_labels.py:1` — Section 10: every audit action an admin record write can produce has plain words.
- `scheduling/domain/test_audit_entity_types.py:1` — Section 4: the audited record types come from one registry.
- `scheduling/domain/test_csv_cells.py:1` — Section 13: a spreadsheet never reads an exported cell as a formula.
- `scheduling/domain/test_fhir_audit_action.py:1` — Section 15.2: `AuditEvent.action` is a code of the R4 value set AuditEventAction.
- `scheduling/domain/test_fhir_audit_event.py:1` — Section 15.2: the product action stays in `type`, `action` is one code, and
- `scheduling/domain/test_fhir_clean.py:1` — Section 15.1: no FHIR resource carries an empty array, object or string, or a null.
- `scheduling/domain/test_fhir_code_identifier.py:1` — Section 15.2: the unique code a client reads and sends back on any record resource.
- `scheduling/domain/test_fhir_coding_code.py:1` — Section 15.2: a concept's first coding code, as the location kind and the department
- `scheduling/domain/test_fhir_communication.py:1` — Section 15.2: `decode_update` refuses a non-date-time `received`, whatever its type.
- `scheduling/domain/test_fhir_practitioner_role.py:1` — Section 15.2: a clinician profile as a PractitionerRole; expected values from FHIR R4
- `scheduling/domain/test_fhir_role_write.py:1` — Section 15.4: a PractitionerRole write body read as profile and time-off changes. The
- `scheduling/domain/test_fhir_search_values.py:1` — Section 15.5: a search value: "either" by comma, closed code lists, NUL characters.
- `scheduling/domain/test_lane_assignment.py:1` — Section 9: blocks that share a column get lanes; touching blocks do not share.
- `scheduling/domain/test_period_days.py:1` — Section 4: a period cut into the part that falls in each local day.
- `scheduling/domain/test_portal_options.py:1` — Section 8: what a patient may do with an appointment, and the plain words when not.
- `scheduling/domain/test_profile_rules.py:1` — Section 7.2: the format rules of the patient profile and of a new password.
- `scheduling/domain/test_record_conflict.py:1` — Section 10: which fields the conflict page lists, and what each row holds. The truth
- `scheduling/domain/test_report_range.py:1` — Section 13: the dates of a report range and what today is.
- `scheduling/domain/test_report_utilisation.py:1` — Section 13: minutes of active appointments over the minutes clinicians could work.
- `scheduling/domain/test_slot_text.py:1` — Section 4: slot text in the hospital's zone.
- `scheduling/domain/test_text_rules.py:1` — Section 4: one text rule for every text a write accepts.
- `scheduling/domain/test_time_zone_shift.py:1` — Section 4: a zone change shifts only the starts whose wall clock differs.
- `scheduling/domain/test_waitlist_window.py:1` — Section 5.8: the waitlist form speaks days, the use case speaks instants.
- `scheduling/domain/test_write_body.py:1` — Section 14: the one rule for "does a write carry a body, and does it say JSON".
- `scheduling/domain/test_written_moment.py:1` — Section 4: one way to write a moment for a person, the zone always named.
- `scheduling/jobs/test_runner.py:1` — Section 4: each job has its own transaction, correlation id and instant, and logs one JSON
- `scheduling/jobs/test_runner_transactions.py:1` — Section 4: the email job runs outside any transaction. Needs real commits, so the test
- `scheduling/models/test_session_kind.py:1` — Section 12.2: how a session was opened is a closed list of kinds.
- `scheduling/use_cases/test_admin_appointment_export.py:1` — Section 13: the export's read and its audit entry are one transaction.
- `scheduling/use_cases/test_admin_last_admin_race.py:1` — Section 10: two admins who deactivate each other at the same moment leave one admin.
- `scheduling/use_cases/test_admin_record_list_queries.py:1` — Section 4: a list page is counted and cut in the database, not in Python.
- `scheduling/use_cases/test_admin_user_delete_atomic.py:1` — Section 4: a refused delete of a user changes nothing, even the clean-up before it.
- `scheduling/use_cases/test_admin_waitlist_search.py:1` — Section 10: the patient search of the admin booking and waitlist pages.
- `scheduling/use_cases/test_audit_action_labels.py:1` — Section 10: every audit action the product writes has plain words in the history.
- `scheduling/use_cases/test_audited_entity_types.py:1` — Section 10: a record type the product audits can always be filtered in the audit log.
- `scheduling/use_cases/test_change_password.py:1` — Section 12.1: change password; a wrong current password is a failed sign-in for lockout.
- `scheduling/use_cases/test_fhir_search_paging.py:1` — Section 15.5: the database counts and cuts the page; no query loads every match.
- `scheduling/use_cases/test_hold_race.py:1` — Section 7.5: the hold counter (five an hour for one email address) and the
- `scheduling/use_cases/test_notification_inbox.py:1` — Section 11: patients read and mark only their own notifications; marking is audited.
- `scheduling/use_cases/test_profile.py:1` — Section 8: a patient edits phone and birth date; the audit names fields, not values.
- `scheduling/use_cases/test_public_details.py:1` — Section 6.6: the three public details answer not found for unlisted results, and the
- `scheduling/use_cases/test_waitlist_busy_times.py:1` — Section 5.8: busy cancelled times are left out in the query, so the first row is the
- `scheduling/use_cases/test_waitlist_offer_fit.py:1` — Section 5.8: an offer needs the clinician, the room and the patient free, at the offer
- `scheduling/views/fhir/test_samples.py:1` — Section 15.1: every sample /fhir answers is free of empty arrays, objects, strings and
- `scheduling/views/pages/test_admin_appointment_export.py:1` — Section 13: the appointment export as a browser sends it. Route:
- `scheduling/views/pages/test_admin_appointment_pages.py:1` — Section 10: the admin appointment list and the appointment page, as a browser
- `scheduling/views/pages/test_admin_audit_page.py:1` — Section 10: the read-only audit list, and its speed on a log of 50 000.
- `scheduling/views/pages/test_admin_booking_pages.py:1` — Section 10: an admin books for a patient and reschedules, as a browser sends it.
- `scheduling/views/pages/test_admin_clinician_weight.py:1` — Section 10: the clinician form refuses a weight beyond its column.
- `scheduling/views/pages/test_admin_conflict_page.py:1` — Section 10: a save over a newer version shows field by field what the admin read, what
- `scheduling/views/pages/test_admin_dashboard_page.py:1` — Sections 10 and 13: the admin dashboard as a browser uses it. Route:
- `scheduling/views/pages/test_admin_form_errors_together.py:1` — Section 4: one submission reports every error, not one round per error.
- `scheduling/views/pages/test_admin_hospital_zone_pages.py:1` — Section 4: saving a hospital with another time zone asks the admin first,
- `scheduling/views/pages/test_admin_notices.py:1` — Section 10: every admin action that changes something answers with a notice that says
- `scheduling/views/pages/test_admin_refusal_words.py:1` — Section 4: every refusal names what is wrong in words, with a status and a way back.
- `scheduling/views/pages/test_admin_settings_page.py:1` — Section 10: the booking policy as the rules read it, and the reminder button.
- `scheduling/views/pages/test_admin_table_component.py:1` — Section 16: every admin table is one component. Wrappers are keyboard-reachable and
- `scheduling/views/pages/test_admin_waitlist_pages.py:1` — Section 10: the admin waitlist as a browser uses it. Routes:
- `scheduling/views/pages/test_booking_code_page.py:1` — Section 7.1: the code page: masked address, wrong code, expiry, resend.
- `scheduling/views/pages/test_booking_confirmation_pages.py:1` — Section 7.1: the confirmation and calendar file, only for the appointment's patient.
- `scheduling/views/pages/test_booking_details_page.py:1` — Section 7.1: the details and review form, the hold, the patient shortcut.
- `scheduling/views/pages/test_booking_hold_cookie.py:1` — Section 7.5: one browser that makes two holds in two tabs completes both. The cookie
- `scheduling/views/pages/test_booking_times_page.py:1` — Section 7.1: a week of free slots in the hospital's zone.
- `scheduling/views/pages/test_clinician_qa_round_two.py:1` — Section 9: the clinician workspace, each defect as a browser meets it.
- `scheduling/views/pages/test_clinician_schedule_pages.py:1` — Section 9: availability, time off, patient and room pages, as a browser sends them.
- `scheduling/views/pages/test_clinician_workspace.py:1` — Section 9: clinician's today, calendar and appointment pages, as a browser sends them.
- `scheduling/views/pages/test_destructive_routes.py:1` — Section 16: a destructive route confirms first. A GET changes nothing; a POST without a
- `scheduling/views/pages/test_details_form_rules.py:1` — Section 7.1: the details form refuses a time that is not offered before it
- `scheduling/views/pages/test_form_focus.py:1` — Section 16: focus moves to the first invalid control of every form, once, in the shared
- `scheduling/views/pages/test_no_iso_dates_in_messages.py:1` — Sections 7.6 and 11: no notification or email a person reads holds an ISO date.
- `scheduling/views/pages/test_page_quality.py:1` — Section 16: every page the product can render, signed out and as each role, meets the
- `scheduling/views/pages/test_page_title_rules.py:1` — Section 16: a page title is plain text, no cross-site token sits outside a form, and
- `scheduling/views/pages/test_pages.py:1` — Sections 12, 16: sign-in, role homes, sign-out, error pages, layout and style page.
- `scheduling/views/pages/test_patient_appointments_page.py:1` — Section 8: appointment lists, cancel step and ownership, as a browser sends them.
- `scheduling/views/pages/test_patient_notifications_page.py:1` — Section 11: notification list, mark as read and unread count, as a browser sends them.
- `scheduling/views/pages/test_patient_portal_fixes.py:1` — Section 8: patient portal pages as the server renders them.
- `scheduling/views/pages/test_patient_portal_guards.py:1` — Section 8: ordering, paging, wording and reschedule steps of the portal, as a browser
- `scheduling/views/pages/test_patient_profile_page.py:1` — Section 8: the profile and change-password pages, as a browser sends them.
- `scheduling/views/pages/test_patient_waitlist_page.py:1` — Sections 5.8, 8: waitlist page as a browser sends it. Each test names its behaviour.
- `scheduling/views/pages/test_patient_waitlist_window.py:1` — Section 5.8: the list shows the last day chosen, not the day after it.
- `scheduling/views/pages/test_portal_notice.py:1` — Section 8: the portal's "Done" notice comes from what the server just did, shown once,
- `scheduling/views/pages/test_safe_redirect.py:1` — Section 12.1: the sign-in `next` parameter may only ever lead to a local path.
- `scheduling/views/pages/test_screens_hardening.py:1` — Sections 12, 16: cookie renewal, favicon, lockout wording, CSRF cookie, table region.
- `scheduling/views/pages/test_search_limited_page.py:1` — Section 6: a limited visitor gets the search page itself with status 429, every
- `scheduling/views/pages/test_search_page.py:1` — Section 6: the root path is the public search, rendered from a plain GET form.
- `scheduling/views/pages/test_status_words.py:1` — Sections 5.6, 16: every status value of the vocabulary has one kind and one word in
- `scheduling/views/pages/test_status_words_and_empty_states.py:1` — Sections 5.6 and 16: every status is a badge with a word wherever it is rendered, and
- `scheduling/views/pages/test_text_as_filled.py:1` — Section 4: text a browser sends from a form, `\\r\\n` line breaks, and the message a
- `scheduling/views/pages/test_text_fields_as_filled.py:1` — Section 16: every post form the product renders, signed out and as each role. A
- `scheduling/views/pages/test_time_grid.py:1` — Section 9: the time grid places items on the 07:00 to 19:00 axis; the rest stay apart.
- `scheduling/views/pages/test_time_grid_blocks.py:1` — Section 9: what a clinician calendar block shows and says, read from the rendered page.
- `scheduling/views/pages/test_time_grid_css.py:1` — Section 16: no browser in the sandbox, so the alignment and containment of the time
- `scheduling/views/pages/test_unique_ids.py:1` — Section 16: an id is unique on every page the product renders. Each page route needs a
- `scheduling/views/pages/test_ux_pass_pages.py:1` — Sections 12, 16: wording and order of sign-in pages, lockout window, favicon, waitlist
- `scheduling/views/test_admin_records_public_follow.py:1` — Sections 6, 10: what public search and booking pages offer follows the admin records
- `scheduling/views/test_api_bodyless_writes.py:1` — Section 14: a write without a body is never refused as unreadable, whatever its type.
- `scheduling/views/test_api_cache_headers.py:1` — Section 14: an answer varying by caller is never stored, and says what it varies on.
- `scheduling/views/test_api_clients_guard.py:1` — Section 14: an API route test gets a client that enforces the cross-site check from
- `scheduling/views/test_api_content_type.py:1` — Section 14: a write to /api/v1 takes JSON only; other media types are refused before the
- `scheduling/views/test_api_live_server.py:1` — Section 14: a test sees the next difference between the test client and the server.
- `scheduling/views/test_api_text_fields.py:1` — Section 14: a text field of `/api/v1` refuses a number, as it refuses a boolean.
- `scheduling/views/test_booking_input_rules.py:1` — Section 7.1: the hold request names the field it was sent under, and a phone is
- `scheduling/views/test_change_notification_text.py:1` — Section 11: the notification of a cancelled or moved appointment says what happened
- `scheduling/views/test_cookie_flags.py:1` — Sections 12.2, 16: with DEBUG off every cookie the product sets is Secure, HttpOnly and
- `scheduling/views/test_fhir_appointment_parity.py:1` — Section 15.6: a booking, a reschedule and a cancellation over FHIR leave what the same
- `scheduling/views/test_fhir_appointment_race.py:1` — Section 15.6: two clients book the same slot over FHIR at once, each in its own
- `scheduling/views/test_fhir_documentation.py:1` — Section 17: every open point of ADR 0005 to 0007 is closed or is a question for the
- `scheduling/views/test_fhir_organisation_writes.py:1` — Section 15.4: admins write Organization, Location and HealthcareService, as clients send
- `scheduling/views/test_fhir_paging.py:1` — Section 15.5: a link the server writes is a request it accepts. Following `next`
- `scheduling/views/test_fhir_practitioner_writes.py:1` — Section 15.4: admins write Practitioner as clients send them (bearer token, no cookie,
- `scheduling/views/test_fhir_role_time_off.py:1` — Section 15.4: a clinician's token updates own PractitionerRole.notAvailable, nothing else
- `scheduling/views/test_fhir_role_writes.py:1` — Section 15.4: admins write PractitionerRole as clients send them (bearer token, no cookie,
- `scheduling/views/test_fhir_sort_by_time.py:1` — Section 15.5: `_sort` on a date parameter orders by that time, in both directions, on
- `scheduling/views/test_fhir_write_declaration.py:1` — Section 15.4: a FHIR write says it is JSON, a reschedule changes only `start`,
- `scheduling/views/test_input_limits.py:1` — Section 4: an unexpected input is refused at the boundary, never a 500.
- `scheduling/views/test_public_route_limits.py:1` — Section 14: every route answering without session or token has a limit or a reason.
- `scheduling/views/test_read_limits.py:1` — Section 6: public reads that compute schedules share one counter per caller
- `scheduling/views/test_request_limit_answers.py:1` — Section 4: a bad Content-Length header is a value in the contract, and a
- `scheduling/views/test_search_limits.py:1` — Section 6: public search is limited per network address (120 an hour, the mechanism of
- `scheduling/views/test_slots_online_only.py:1` — Section 6: a caller with no session, and a patient, see only what public search shows.
- `scheduling/views/test_trusted_proxy.py:1` — Section 16: a forwarded header changes the scheme or the rate-limit address only when a

## Left for the orchestrator

- From the plan's `## Not in this run`: item 14, first part, the test-only probe views move out of the product package (`scheduling/views/probe_views.py`, `scheduling/views/probe_urls.py`). Next run. Not done in this run, and not a blocker.
- Nothing else in the slice is unfinished: 194 files rewritten, the gate test added, the superseded-plan banner in place.
- Finding 2 (red run log) and Finding 1 (citations) need the orchestrator's read before merge.
