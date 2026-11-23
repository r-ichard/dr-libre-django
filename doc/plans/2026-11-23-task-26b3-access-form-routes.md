# Plan: task 26b3 item 3, the five form routes

Slice: item 3 for the five form-only routes in `LEFT_FOR_LATER_RUN` (sign-out, sign-in/email-link, patient/notifications/read-all, admin-console/settings/reminders, admin-console/appointments/export). Nothing else of item 3 is in this run.
Process: `tests-and-docs`. The new tests pass on the product as it stands, so the red gate cannot pass. Red is shown by a sabotage check (see Blocks, step 4), recorded in the run log.

## Focal point

The GET walk (`test_page_access_walk.py`) cannot reach these routes: each answers no GET (405 or a form-only redirect). They get their own walk: one new module that POSTs each form the way a browser does, as each caller, and checks the answer its row gives, or the product's answer where a pair is in `KNOWN_DIFFERENCES`.

## Expected answers (20 pairs: 5 routes x 4 callers)

| Route | visitor | patient | clinician | admin |
|---|---|---|---|---|
| sign-out | 302 /sign-in (row OK) | 302 /sign-in (row OK) | 302 /sign-in (row OK) | 302 /sign-in (row OK) |
| sign-in/email-link | 303 /sign-in/check-email (row OK) | same | same | same |
| patient/notifications/read-all | SIGN_IN (row) | 303 /patient/notifications?page=1 (row OK) | FORBIDDEN (row) | FORBIDDEN (row) |
| admin-console/settings/reminders | SIGN_IN (row) | FORBIDDEN (row) | FORBIDDEN (row) | 303 /admin-console/settings (row OK) |
| admin-console/appointments/export | SIGN_IN (row) | FORBIDDEN (row) | FORBIDDEN (row) | 200 text/csv (row OK) |

Bold reading: a row OK for a POST means "the caller is let in"; a redirect that the product gives instead of the page is a difference, recorded as a pair, as the existing `sign-in` pairs are.

10 of the 20 are product differences (sign-out x4, email-link x4, read-all for patient, reminders for admin). The other 10 match their row.

Home check after sign-out: for patient, clinician and admin, the home (`/patient/`, `/clinician/`, `/admin-console/`) asked with the old session token answers SIGN_IN. The visitor has no home; the check is not made for a visitor. Decision, see "For the orchestrator".

## Blocks and files, in order

1. **`scheduling/views/pages/test_page_access_walk.py`** (the only existing test file edited):
   - Delete `LEFT_FOR_LATER_RUN` (all five routes walked here, so it is empty). Add `FORM_WALKED_ROUTES`: the same five routes, one line, with a comment "walked by test_page_access_form_walk.py: they answer no GET". Reason: removing the five from the old set alone would make `_walked_rows` send GETs to POST-only routes and report them as extra.
   - `_walked_rows`: exclude `FORM_WALKED_ROUTES` instead of `LEFT_FOR_LATER_RUN`.
   - `returns_every_get_route_in_walk_when_resolver_lists_it`: subtract `FORM_WALKED_ROUTES` instead of `LEFT_FOR_LATER_RUN`.
   - `returns_product_answer_when_pair_is_known_difference`: skip routes in `FORM_WALKED_ROUTES` next to the existing record skip, since a GET of a POST route answers 405, not the product's POST answer.
   - `KNOWN_DIFFERENCES`: add 10 pairs. `("sign-out", c): (Answer.OK, "302 /sign-in")` for four callers; `("sign-in/email-link", c): (Answer.OK, "303 /sign-in/check-email")` for four callers; `("patient/notifications/read-all", "patient"): (Answer.OK, "303 /patient/notifications?page=1")`; `("admin-console/settings/reminders", "admin"): (Answer.OK, "303 /admin-console/settings")`. `admin_redirect` sends no query string, so the Location is exact.
   - Replace the comment above the removed set: it says the form-only pages' walk "sends the form"; it now names the new module.

2. **`scheduling/views/pages/test_page_access_form_walk.py`** (new, under 300 lines; no other new file):
   - Docstring: what the tests hold: each walked form route answers each caller's browser POST as its row or pair says; a signed-out session stops the caller's home; the export is a CSV attachment; a cross-site POST is refused. No statement about rate limits.
   - Module-wide `pytest.mark.django_db`. Every client is `browser_client()` (`enforce_csrf_checks=True`, `Origin` set on every POST). Signed-in callers come from `client_for_role` (already browser clients). The visitor uses `browser_client()`.
   - `FORM_PAGES`: the page each form lives on: read-all `/patient/notifications`; reminders `/admin-console/settings`; export `/admin-console/appointments`; email-link `/sign-in`; sign-out: the caller's home, or `/sign-in` for a visitor (no sign-out form shows to a visitor).
   - Per POST, as a browser: GET the form page with `follow=True` (what the browser shows), read the form's named fields from it for the form whose action is the route (`post_forms`, `form_walk_support.py`; empty if the caller cannot see the form), add the typed field, and set `csrfmiddlewaretoken` to the caller's own `csrftoken` cookie (the same way `browser_post` does). Email-link: each caller types a different address, `<caller>@walk.example.test`, so no one email gets more than three requests.
   - Expected answer: the KNOWN pair's product string if the pair exists, else the row's answer. A product string (contains a space) is compared to `f"{status} {location}"` exactly; a row answer is compared through `_answer_of` from the walk module.
   - Clients: one set per test for the four routes that keep sessions. Sign-out ends the session, so sign-out uses its own fresh signed-in clients.
   - Tests (behaviour names):
     - `returns_expected_answer_when_caller_posts_form_route`: loops 5 routes x 4 callers, collects mismatches, one assert.
     - `returns_sign_in_when_home_asked_with_session_token_after_sign_out`: patient, clinician, admin. Save the session token, sign out, GET the home with a new client holding the old token: SIGN_IN.
     - `returns_csv_attachment_when_admin_posts_export`: 200, `text/csv`, `Content-Disposition` names `appointments-<date>.csv`.
     - `returns_403_when_form_posted_from_other_site`: patient on read-all with `Origin: http://other-site.example`: 403, and the audit log or read state unchanged (the notification stays unread).

3. **`doc/handover.md`**: grep it before editing. Update only if it names the five routes or `LEFT_FOR_LATER_RUN`. No other doc changes; `doc/security-review.md` is item 4, not this run.

4. **Sabotage proof (red evidence)**: change one expected answer (for example, the admin reminders pair) in a scratch copy, run the new module, see it fail on that pair, restore. Record the command and output in the run log. Same for the home check with the session token replaced by an empty one.

5. **Gates**: `make lint`, `make test`, `make gate`. `make mutate` is unchanged (domain only). Count check: the walk and the new module together send about 60 requests (20 POSTs, each with a form-page GET that may follow one redirect, plus 6 sign-ins and 3 home checks). Not measured here; the run measures it.

## Invariants and blast radius

- Session authorization: all checks are server-side; the walk only sends what a browser sends, and it never sets a role or user in the payload.
- Sign-out must end the server session, not only clear the cookie: the home check with the old token proves it.
- Audit: the export and reminders POSTs write audit entries; the walk makes them as admin, which is what the product does. Nothing in the walk reads or changes the audit log.
- Email-link: the walk makes a real link request for four addresses that have no account (the answer is the same for any address). No mail is sent for them.
- Blast radius: test files only. No product code. The walk module's existing tests keep their behaviour on every other route.

## Trust boundaries

Each POST crosses the cross-site check (CSRF middleware with `Origin`) and session authorization. Both are exercised as the browser does: the cross-site token from the caller's own page, the session cookie, `Origin: http://testserver`. The `Origin: other-site` test proves the check refuses a POST that lacks the site's origin.

## Domain entities (CLAUDE.md vocabulary)

Visitor, Patient, Clinician, Admin, Session, SignInLink, Notification (read state on read-all), Appointment (the export's rows), AuditLogEntry (written by export and reminders).

## Names of the tests (values from the specification)

- `returns_expected_answer_when_caller_posts_form_route`: each caller gets the table's answer for each form, as the product answers it.
- `returns_sign_in_when_home_asked_with_session_token_after_sign_out`: sign-out ends the session; the home asks for sign-in.
- `returns_csv_attachment_when_admin_posts_export`: an admin gets the appointment list as a CSV file.
- `returns_403_when_form_posted_from_other_site`: a cross-site POST is refused.

## What I will not do

- No change to `form_walk_support.py`, `page_walk_support.py`, `record_walk_support.py`. `client_for_role`, `browser_client`, `post_forms` are used as they are.
- No rename of walk-module helpers. The module imports `_answer_of` (private) as it is now; see the sync point below.
- No coverage check for POST-only routes beyond the five (the table test already checks that every route has a row).
- No rate-limit assertion, no 429 handling.
- No new abstraction for form posting; the walk's loop is the only caller.

## Sync point with the record-pages run

`doc/plans/2026-11-23-task-26b3-access-record-pages.md` also edits `test_page_access_walk.py` and renames `_answer_of` and others to public names. If it merges first, use the public names here (`answer_of`); if this run merges first, the record run rebases onto `FORM_WALKED_ROUTES` and the removed `LEFT_FOR_LATER_RUN`. Keep this run's walk-module diff to the lines named in Block 1.

## For the orchestrator

1. **Visitor home after sign-out.** The check covers the three signed-in homes. A visitor has no home; I did not invent one (`/` answers 200 for everyone). Confirm or give the visitor's expected home.
2. **Sign-out row versus ADR 0012.** The table row says OK for every caller (`test_page_access_rows.py`, NO_SESSION_ROWS). ADR 0012 reading 5 says the table gives a redirect. The rows follow the spec ("Anyone"); the run keeps the row and records the redirect as a pair, as the task says. The ADR text is wrong on this point; the owner decides.
3. **Email-link and read-all are product differences too.** Ten pairs go into "For the owner" with their spec sections (12.2 for sign-out; 7.3 for the link pages; 12.3 for read-all and reminders). The review text is item 4's job; the list goes into the run log.
4. **Removing `LEFT_FOR_LATER_RUN`.** Its only content was these five routes, so it is deleted rather than left empty; `FORM_WALKED_ROUTES` takes its place in the four uses. This is a deliberate reading of "remove each walked route".
5. **Process.** `tests-and-docs`: no red gate; red is shown by the sabotage check in Block 4.

## Not in this run

- Item 3 for the record routes that answer no GET (the other 12 form-only record routes): the record-pages run and a later run.
- Item 4 (the access section of `doc/security-review.md`): a later run.
- Item 5 timing figures beyond the request count: a later run.

## Architect review

Verdict: approve. The slice is coherent, the expected answers match the rows and pairs in
`test_page_access_rows*.py`, and the walk-module changes stay within Block 1. Points the run
must carry through:

1. **`_answer_of` cannot produce the sign-out and email-link pair strings.** It maps every 302
   or 303 whose path starts with `/sign-in` to `SIGN_IN`, so `"302 /sign-in"` and
   `"303 /sign-in/check-email"` never equal its output. `FORM_WALKED_ROUTES` keeps these pairs
   out of `returns_product_answer_when_pair_is_known_difference`, which is the only correct
   behaviour today. The comment on `FORM_WALKED_ROUTES` must say so, and the new module must
   compare raw `f"{status} {location}"` for them, never `_answer_of`.
2. **Blast radius omits audit writes.** `ask_for_link` writes `auth.link_requested` on every
   email-link POST, including addresses with no account (`scheduling/use_cases/sign_in_link.py`).
   The walk therefore adds four audit rows. Name email-link in the Invariants section.
3. **Email-link rate limit.** `RateLimitScope.LINK` allows 10 per address and 3 per email. The
   walk sends four POSTs from the test address, each to a distinct email, so no 429 is expected.
   The plan makes no rate-limit claim, and it should keep it that way.
4. **Visitor sign-out has no form.** The visitor POSTs `/sign-out` with only the cross-site token.
   The plan states this ("empty if the caller cannot see the form"); the test must not assert a
   form field the visitor never sent.
5. **Sabotage proof.** Block 4 changes an expected answer in a scratch copy. That proves the
   test can fail. The run log must record the command and the failing line for each sabotage.
6. **Sign-out row versus ADR 0012 reading 5.** The plan is right to keep the row and record the
   redirect as a pair. The owner decides the ADR text; no change here.

Scope, layers and security: test-only; authorization stays server-side; no product code changes;
no new dependency; no abstraction beyond the existing helpers. Requirements from the brief are
met: five routes, four callers, browser-shaped POSTs, cross-site check enforced, shared helpers
untouched.
