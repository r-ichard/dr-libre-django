# Review: task 26b3 item 3, the five form-only routes

Reviewed: `git diff main...HEAD` on `fabro/run/01M84BBEBDCDDNPY8VCT51JAZM`. Three files: the plan
(`doc/plans/2026-11-23-task-26b3-access-form-routes.md`, already reviewed at plan stage), the
walk module `scheduling/views/pages/test_page_access_walk.py` (edited), and the new module
`scheduling/views/pages/test_page_access_form_walk.py`. No product code, no migration, no
dependency, no shared helper (`form_walk_support.py`, `page_walk_support.py`,
`record_walk_support.py`, `browser_support.py`) changed. `drlibre-specs.md` not in the diff.

Verdict: approve. No blocker found.

## Checks

1. **Plan per block, one sentence each.**
   - Walk module: swaps the `LEFT_FOR_LATER_RUN` set for `FORM_WALKED_ROUTES` in three filters,
     adds ten `KNOWN_DIFFERENCES` pairs, skips form routes in the known-difference test.
     Confirmed at a glance; the diff is small.
   - Form module: posts each form as a browser does and compares to the row or pair. Confirmed
     at a glance for the set-up and the loop; traced `_post_form` and `_form_values` (below)
     because the form's action is not used.
2. **Correctness, errors.** No swallowed error, no `except`. `_answer_as_sent` compares raw
   `"status Location"` when the expected value contains a space and `_answer_of` otherwise; table
   answers (`ok`, `sign-in`, `forbidden`, `not-found`) contain no space, so the split is safe.
   `_form_values` returns `{}` silently when no form matches (`test_page_access_form_walk.py:78-82`);
   see Later 1.
3. **Authorization, boundaries, sensitive data.** The module makes requests only; it sets no role
   or user in the payload. Cross-site check enforced (`browser_client()`, `browser_support.py`),
   `Origin` set on every POST (`test_page_access_form_walk.py:85-95`). The 403 test
   (`:144-150`) asserts that the notification stays unread after the refused POST. No logging, no
   secrets in URLs.
4. **Double booking.** Not touched by this diff.
5. **Tests.** Derived from the table and the plan's expected answers, not from the code path.
   The four tests can fail: each compares against a string or a status. The sign-out home check
   (`:124-133`) asserts the token opens the home before sign-out, so the later SIGN_IN is caused by
   sign-out. The export test (`:136-141`) asserts 200, content type and an attachment name pattern.
   Gaps against the plan are listed under Later.
6. **Names and comments.** Names state roles (`FORM_WALKED_ROUTES`, `stale`, `shared`,
   `typed_fields`). Comments name why (the redirect comparison, the form page for signed-in
   callers). Two comments are inaccurate; see Later 2. The gate passed the 255-character cap.
7. **Proof left no trace.** `git show --stat` per commit:
   - `84d011f` plan_review: the plan document only.
   - `114e469` plan_gate, `ad585bd` check, `4f14a29` prove: no file changed (empty).
   - `88ac22b` write: the walk module and the new module, both tests.
   No product or migration line changed after the write stage. Confirmed.
8. **Scope and contract.** Renaming `LEFT_FOR_LATER_RUN` to `FORM_WALKED_ROUTES` is a reading of
   "remove each walked route", recorded in the plan (item 4 of "For the orchestrator"); see
   Left for the orchestrator. No dependency added. The walk module imports `_answer_of`,
   `_wanted`, `_all_rows` (private names) from siblings; the plan accepted this.

## Run

- `make gate`: exit 0, escape hatches clean, comment and size caps pass.
- `uv run --env-file .env.example pytest` on the two walk modules, with the `make test`
  environment (`SECRET_KEY` and `DB_NAME` set as the Makefile does): 10 passed, 1.49 s. The
  full suite was not re-run here; the check stage reports 5432 passed.
- Sabotage proof (plan Block 4) is not in the diff and I did not run it: it needs a scratch copy
  and edits. See Left for the orchestrator.

## Findings

### Blocking

None.

### Later

1. **Important, not a blocker: the form module posts to a hard-coded path and accepts a missing
   form.** `test_page_access_form_walk.py:78-82` (`_form_values`) returns `{}` when no form on the
   page has the route as its action, and `:85-95` (`_post_form`) posts to `f"/{route}"`, not to the
   form's `action`. Failure scenario: the reminders form in `scheduling/templates/admin/settings.html:19`
   loses its `{% csrf_token %}`, or its action changes from `{{ action }}`, or the page stops
   rendering it for admin. The test still posts to `/admin-console/settings/reminders` with the
   cross-site token, gets 303, and passes. Same for the read-all form (`patient/notifications.html:9`)
   and the export form (`admin/appointments.html:36`). That is the bug class this module exists to
   catch (task 13a, task 22). Smallest fix: in `_post_form`, find the form for the route, assert
   it was found for every caller whose expected answer is not a sign-in redirect, and post to
   `urlsplit(form.action)` (path and query).
2. **Comment wrong for email-link.** `test_page_access_form_walk.py:45-46` says "one page serves
   every caller". The email-link form exists only in `scheduling/templates/sign_in.html:7`. A
   signed-in caller who opens `/sign-in` is redirected home, which does not hold that form. For
   patient, clinician and admin the POST is therefore built from no fields plus the typed address,
   not from a form they could see. The product answer (303) is still the right check. Smallest fix:
   say so in that comment, and in the module docstring if it claims a browser POST.
3. **Export query string not sent.** `scheduling/views/pages/admin_appointments.py:116` builds
   `export_action` with `address_with(EXPORT_PATH, asked)`, so the real form may post with a
   filter query. The test posts to the bare path (`test_page_access_form_walk.py:95`). Fix with
   item 1 (post to the form's action).
4. **Sign-out page differs from plan text.** The plan said sign-out uses the caller's home for
   signed-in callers and `/sign-in` for a visitor. `FORM_PAGES` (`:47-52`) uses `/sign-in` for all,
   which redirects a signed-in caller to home, so the form is found the same way. Behaviour is
   equal; the plan text is not. Nit.
5. **Private names imported across test modules.** `test_page_access_form_walk.py:24-40` imports
   `_answer_of`, `_wanted`, `_all_rows`. The plan's sync point says the record-pages run renames
   them to public names. Nit, recorded for that rebase.
6. **The 403 test checks only that some notification stays unread.**
   `test_page_access_form_walk.py:144-150`. The plan allowed "audit log or read state". Adding
   "no audit entry" would make it stronger. Nit.
7. **The read-all success path is not asserted as a state change.** The module checks only the
   303 for the patient (`:106-121`); it does not check that the notification is now read. Not
   in the plan's promises. Nit.
8. **Makefile budget and timing.** Not measured as a blocker. Measured here: the two walk modules,
   10 tests, 1.49 s on a shared sandbox; the orchestrator measures on a quiet machine.

## Left for the orchestrator

From the plan's "Not in this run":
- Item 3 for the other 12 form-only record routes: the record-pages run and a later run.
- Item 4, the access section of `doc/security-review.md`: a later run.
- Item 5 timing figures beyond the request count: a later run.

Slice items the run did not show:
- Plan Block 4, sabotage proof: the command and the failing line for each sabotage must be in the
  run log (`doc/retro.md`). Not in the diff. Confirm before squash-merge.
- `FORM_WALKED_ROUTES` replaces `LEFT_FOR_LATER_RUN` instead of the set being emptied. Plan
  item 4 records it as deliberate. Confirm you accept that reading of "remove each walked route".
- `doc/handover.md` names neither the five routes nor `LEFT_FOR_LATER_RUN` (grepped); no edit needed.

## For the owner

`KNOWN_DIFFERENCES` (`test_page_access_walk.py:45-57`) gains ten pairs. Each is a product answer
that is not the table's word for the caller. The module comment calls each one a question.

| Route | Callers | Table | Product |
|---|---|---|---|
| sign-out | visitor, patient, clinician, admin | OK | 302 /sign-in |
| sign-in/email-link | visitor, patient, clinician, admin | OK | 303 /sign-in/check-email |
| patient/notifications/read-all | patient | OK | 303 /patient/notifications?page=1 |
| admin-console/settings/reminders | admin | OK | 303 /admin-console/settings |

1. **Is a POST redirect an OK answer?** For the four form routes that let a caller in, the product
   answers a post-redirect-get 303 or a 302 to a sign-in page. The table has no "redirect" word, so
   a table OK for a POST means "accepted". Decide whether these are differences at all, or whether
   the table should gain a redirect answer. The plan's cited spec sections (12.2 sign-out, 7.3
   sign-in link, 12.3 access rules) were checked by heading only.
2. **Sign-out for everyone.** `drlibre-specs.md:606` says "Sign-out deletes the session" and does
   not name where to redirect. ADR `doc/adr/0012` reading 5 says the table gives a redirect; the
   table row (`test_page_access_rows.py`, NO_SESSION_ROWS) says OK for every caller. The plan keeps
   the row and records the redirect as the pair. The owner decides the ADR text.
3. **Email-link for signed-in callers.** The product answers 303 to a signed-in caller who posts
   the link form, though the form is shown only to visitors (see Later 2). Confirm that is intended.
