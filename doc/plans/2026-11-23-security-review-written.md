# Plan: security review written (task 26d, items 18 and 19)

Slice: items 18 and 19. One new document, `doc/security-review.md`. Items 16 and 17 (encryption at rest, the server) and the access table stay out of this run.

## Focal point

`doc/security-review.md` is a reading review. Each rule of `drlibre-specs.md` sections 4, 11 and 12 gets a row: where it is enforced (file and function), which test holds it (file and test name). The writer opens every cited line and test and greps every name before writing it down, so no row rests on memory. Then ADR 0004's limits, what was not reviewed, and one owner question list. No product code, no tests, no change to `drlibre-specs.md`, no ADR edits.

## Blocks

1. **Header and scope.** Date 2026-11-23, what was read and how (by reading, no test run). A heading `## Access` that says another run writes the access table. Nothing else in that section.
2. **Section 4 rows.** One row per rule: validation at every boundary, identity from session, every write audited, audit metadata, one transaction per change, failure codes, time zone, correlation id, 20 rows per list page. Sources:
   - `scheduling/views/access.py` `signed_in_user`; test `scheduling/views/test_access_rules.py::returns_user_from_cookie_when_body_names_another_user_id`.
   - `scheduling/use_cases/audit.py` `record_audit`; `scheduling/use_cases/test_audit.py::returns_no_audit_entry_when_change_fails`, `returns_unchanged_row_when_audit_write_fails`.
   - `scheduling/domain/audit_metadata.py` `AuditMetadata`; `scheduling/domain/test_audit_metadata.py`.
   - `scheduling/domain/failure.py` (codes); `scheduling/domain/test_failure.py::returns_exactly_the_twelve_specified_codes_when_failure_codes_are_listed`.
   - `scheduling/views/middleware.py` `RequestContextMiddleware`; tests to name at write time.
   - Still to read at write time: `StrictSerializer` location and its test (unknown fields), the list page size, the hospital-zone conversion, the page-address fallback.
3. **Section 11 rows.** The six notification events, in `scheduling/use_cases/notifications.py` (`notify_patient`, `notify_waitlist_patient`, `_notify`); the email goes out in `transaction.on_commit` (`notifications.py:69`); text carries the time only (`scheduling/domain/email_content.py`, test `test_email_content.py`). To read at write time: each caller per event, so the table says which call sends which kind. Reminder and waitlist tests named from `use_cases/test_reminders.py` and `test_waitlist*.py`.
4. **Section 12.1 rows (password sign-in).** `scheduling/use_cases/sign_in.py` `sign_in_with_password`, `_run_hasher_once`, `_record_failure`; `scheduling/domain/lockout_rules.py` (10 failures, 15 minutes); hasher is Django's PBKDF2 (`drlibre/settings.py` default; `drlibre/test_settings.py::returns_default_pbkdf2_hasher_when_product_settings_are_loaded`). Tests from `scheduling/use_cases/test_sign_in.py`: `returns_equal_unauthenticated_when_email_is_unknown_or_password_is_wrong`, the `returns_one_hasher_call_when_*` family, `returns_unauthenticated_when_tenth_failure_is_followed_by_correct_password`, `returns_unauthenticated_when_user_is_inactive_and_password_is_right`, `returns_login_audit_with_actor_and_domain_only_when_password_is_right`. Home per role: `scheduling/domain/sign_in_rules.py` `home_for`. Patients-only link sign-in: `scheduling/use_cases/sign_in_link.py` role check (line 51 and 93), tests in `test_sign_in_link_use.py`.
5. **Section 12.2 rows (sessions).** `scheduling/use_cases/session.py` `open_session`, `resolve_session`, `sign_out`; token stored as SHA-256 (`hash_token`); `scheduling/domain/session_rules.py` `session_lifetime` (12 h admin, 7 d others, 24 h link or code) and `extended_expiry` (only password sessions, under half left). Cookie: `scheduling/views/session_cookie.py` `set_session_cookie` (HttpOnly, SameSite=Strict, Secure outside development). Tests: `scheduling/use_cases/test_session.py` (`returns_hash_of_token_when_session_is_stored`, `returns_unauthenticated_when_user_is_deactivated`, `returns_longer_expiry_when_clock_moves_to_under_half_remaining`); `scheduling/views/test_cookie_flags.py::returns_secure_httponly_samesite_on_every_cookie_when_debug_is_off`.
6. **Section 12.3 rows (access).** `scheduling/views/access.py` (`public`, `signed_in`, `roles`, `DenyUnlessDeclared`); `scheduling/views/api_view.py` `refuse_foreign_origin`; `scheduling/views/pages/page_view.py` `_guarded_dispatch`; `scheduling/use_cases/record_access.py` (not found versus forbidden). Tests: `scheduling/views/test_access_rules.py` (`returns_closed_when_view_declares_no_access`, `returns_403_when_patient_calls_admin_view`), `scheduling/views/pages/test_admin_access.py::returns_sign_in_redirect_to_a_visitor_on_every_console_route`, `scheduling/views/test_auth.py::returns_403_forbidden_when_login_post_has_foreign_origin`, `scheduling/use_cases/test_record_access.py::returns_forbidden_when_record_belongs_to_someone_else`, `returns_not_found_when_record_is_missing`.
7. **ADR 0004 limits.** Its own stated gaps (log text not scrubbed; nested serializers not strict; Django technical page under `DEBUG` for non-API paths). Plus drift found while reading, each stated with its file:
   - `mail_unavailable` is in `failure.py:20` and in `test_failure.py`, but in neither ADR 0004's table nor spec section 4. Spec section 4 lists ten codes; the code has twelve.
   - ADR 0004 says 405, 406 and 415 never occur for API views. ADR 0009 says a refused `POST /fhir/Practitioner` is 405. ADR 0010 proposes 415. The FHIR door is separate; the review says so and does not call either wrong.
   - `ApiView.initial` refuses a cross-origin write only when an `Origin` header is present. A cookie write without one passes; the reliance is on `SameSite=Strict` in current browsers. State as a limit.
   - `csrf_exempt` on `fhir_entry` (`views/fhir/views.py:55`, reads no cookie) and on `AuditPage` (`views/pages/admin_audit.py:87`, GET only; confirm no POST route).
   - Rate limits use `REMOTE_ADDR` unless `TRUSTED_PROXY_COUNT` is set (backlog, review of 12).
   - Lockout key is an HMAC of the address with `SECRET_KEY`; rotating the key resets counts.
   - Tests run the MD5 hasher (`conftest.py:47`), so the timing rows prove call counts, not elapsed time.
8. **Not reviewed.** Encryption at rest (item 16); the server (item 17); dependency pins and `make audit`; templates and escaping for XSS; migrations; deployment (TLS termination, `docker-compose`, the image's dev group); the demo seed; FHIR authorization beyond the rules cited; static files and JavaScript; the notice cookie (backlog, review of 17b). No test was run for this review.
9. **Owner questions (item 19).** One list at the end. Sources:
   - `doc/backlog.md` lines 141 (5.2 step 2 room code), 153 (5.6 status-change time), 166 (patient joins a type not bookable online), 170 (FHIR day search in UTC), 173 (ADR 0010 accept or amend), 175 (reason as free text), 186 (staff rate limits), 188 (405 in section 4).
   - ADR 0006 two points (busy slot by id; patient search by email or phone), which repeat ADR 0007 questions 3 and 4.
   - ADR 0007 questions 1 to 5.
   - ADR 0010 "For the owner" (`_sort` on every date parameter, the 415 code, search-value rules).
   - ADR 0005, 0008, 0009: no open-points section found (checked by grep; state it). ADR 0011 does not exist yet, so the list says so.
   - Each question gets: the choice the product makes today (read from the cited code or ADR), and what changing it would cost (files and tests touched). Written from reading, not decided here.

## Files

Touch, in order:
1. `doc/security-review.md` (new).

Do not touch: `drlibre-specs.md` (never edited), any product code or test, `doc/adr/*` (reviewed, not edited), `doc/backlog.md` (orchestrator), `doc/adr/0011-security-review.md` (other run).

## Invariants and blast radius

Documentation only. Nothing the product does changes, so double booking, server-side authorization and the append-only audit log are untouched. Trust boundaries crossed: none. The review names them only.

## Failing tests first

None. The task says prose, and no item asks for a behaviour change. The one mechanical check is the writer's: every cited path exists, every cited test name exists (grep), and each line number comes from `grep -n` at write time.

## Domain entities (CLAUDE.md §3)

User, Patient, Clinician, Admin, ApiClient (token), Session, SignInFailure, SignInLink, BookingHold, VerificationCode, Notification, AuditLogEntry, Appointment.

## What I will not do

No fixes for the drift in block 7; each one goes to the owner list or a backlog line. No new abstraction, dependency or script. No re-run of the test suite as evidence.

## Not in this run

- Item 16 (encryption at rest) and item 17 (the server): another run, with `doc/adr/0011-security-review.md`.
- The access table (item 10): another run.
- Any change to the drift or the limits listed above.
- The section 15 FHIR rules beyond the ADR questions named in block 9.

## Reading done for this plan

CLAUDE.md; task 26d; spec sections 4, 11, 12, 17; ADR 0004 in full; open points of ADRs 0005 to 0010; `sign_in.py`, `session.py`, `session_rules.py`, `session_cookie.py`, `api_view.py`, `authentication.py`, `audit.py`, `audit_metadata.py`, `views/middleware.py`, `settings.py`, `access.py`, `page_view.py` (method handling), `fhir/views.py` (fhir_entry); test names of the sign-in, session, audit, access, cookie and origin tests. Reading still to do is listed under each block.

## Architect review

Verdict: approve. Slice is coherent: one new document, no product code, no spec or ADR edits, and the access table and items 16 and 17 are excluded as the owner split them. Items 18 and 19 are what one docs-only run can finish.

Checked by reading and grep, not by running tests:
- Every cited source path in blocks 2 to 7 exists. Every cited test name exists in a `.py` file under the named path. Spec sections 4, 11, 12 exist at the expected headings.
- Backlog lines 141, 166, 170, 175 and 188 match the plan's descriptions.
- `Failure.mail_unavailable` (`scheduling/domain/failure.py:20`) is absent from spec section 4 and from ADR 0004. The plan's drift claim holds.

Corrections the writer must make at write time (not reasons to revise):
- Block 7 names only `mail_unavailable` as drift. `rate_limited` (`failure.py:19`) is also absent from spec section 4's table. Name both; the spec table lists ten codes, the enum has twelve.
- Block 9 says ADR 0005 has no open-points section. It does: `doc/adr/0005-fhir-conventions.md:87` "Open points for the owner", which defers to the questions in ADR 0007. Cite it and do not repeat ADR 0007's questions as ADR 0005's.
- Block 2 lists the section 4 rules from memory of the spec. Enumerate them from `drlibre-specs.md` section 4 text itself; the list here is a guide, not the rule set.
- Block 3's "six notification events" is not yet verified against section 11. Count them from the spec text.

Notes for the orchestrator (not blocking):
- "Failing tests first: None" departs from §10 test-first. The task says prose; CLAUDE.md routes no-behaviour tasks to `fabro run tests-and-docs` because the red gate cannot pass. Confirm this run's workflow matches.
- "No re-run of the test suite as evidence" sits against the task's done-when (`make lint`, `make test`, `make gate`, `make mutate`, `make fhir-validate`). A markdown file cannot change those results, but the scripted last gates must still run and be reported as run.
- Block 5 cites `session_cookie.py` for `SameSite=Strict` and `Secure`; the writer should confirm both attributes in the function body, not only the test name.
