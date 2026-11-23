# Review: remove `csrf_exempt` from the admin audit page

Date: 2026-11-23. Reviewer: second reader (diff only). Base `main`, head `fabro/run/01M840X4N03QY82RTS12PX46HK`.
Plan: `doc/plans/2026-11-23-admin-audit-csrf-exempt.md`.

Diff: 3 files, +149 / -5. Product: `scheduling/views/pages/admin_audit.py` (-2 lines net of
import and comment). Tests: `scheduling/views/pages/test_admin_audit_page.py`. Plan file only otherwise.

## Verdict

approve. No blocker. Gates were green at `4d6e737` (lint, test, gate, escape hatches), per the stage log.

## Per block: plan in one sentence

- `admin_audit.py:85`: the route is `AuditPage.as_view()` with no wrapper. Confirmed at a glance. The import of `csrf_exempt` is gone and nothing else in the pages package uses it. Checked with grep.
- `test_admin_audit_page.py:146-154` `_browser_request`: visits `/sign-in` with a browser client to get a CSRF cookie, then sends the same token as cookie and `X-CSRFToken` with a site `Origin`. Traced: `browser_client()` enforces CSRF, so the token source is the one the middleware checks.
- `test_admin_audit_page.py:157-164`: parametrized 405 test now uses a valid token and site origin. Traced: the view's `http_method_names = ["get"]` answers 405 after middleware passes. Count assertion kept.
- `test_admin_audit_page.py:180-183`: cross-site POST with a valid token expects 403. Traced: `admin_post` takes its token from a fresh visitor, so only the `Origin` mismatch can cause the 403. Isolates the origin check.
- `test_admin_audit_page.py:186-187`: admin GET expects 200 with enforcement on. Confirmed at a glance.

Traced, not glanced: the 403 test (origin isolation), and the `_browser_request` token source. Confirmed at a glance: the import and the return line.

## Checks in order

1. Plan per block: stated in one sentence above. All four plan blocks are present in the diff. The plan's single combined red test was split into two tests (`:180`, `:186`). Same coverage, fine.
2. Correctness and errors: no swallowed errors, no new error paths. The red run failed for the right reason: `assert 405 == 403` on the cross-site POST (verify_red output). Behaviour change is the one the plan names: a POST without a valid token or from another site now answers 403 from `CsrfViewMiddleware`.
3. Authorization: `PageView` role guard (`allowed_roles = {Role.ADMIN}`) unchanged. No payload-derived auth. No sensitive data in the new tests. No logging change.
4. Double booking: not touched.
5. Tests: the red test is derived from the protected-page rule (cross-site unsafe method answers 403), not from the implementation. Both new assertions have expected values. The parametrized test now sends a token, so it proves the 405 path rather than passing because of the 403 path. Missing edge: a token-less write is not asserted (plan said "not asked"). Fine.
6. Names and comments: `_browser_request` is a role name. The docstring (`:147`) is one line, under the 255 cap. The module docstring of `admin_audit.py` now has a stale claim: see Later 2.
7. Proof trace: commits after `verify_green` (`66adbc4`) are `prove` (`54d750a`, +9 lines, test file only), `refactor` (`cffaaa5`, empty), `check` (`4d6e737`, empty). No product or migration line changed after verify_green. `git diff 66adbc4 HEAD --stat` shows only the test file. No blocker here. But `prove` added an unrelated test; see Later 1.
8. Scope: the diff is the finding and its test changes, plus one unrelated test (Later 1). No dependency added. No spec change (`drlibre-specs.md` not in the diff). No contract change across layers: the route path and methods are the same.

## Findings

### Later

1. **Unrelated test bundled in** — `scheduling/views/pages/test_admin_audit_page.py:105-111`, `returns_staff_but_no_patients_as_actor_choices_when_the_log_is_opened`. Added in the `prove` commit `54d750a`. It tests the actor dropdown, not the CSRF exemption, and the task said "Nothing else". Risk: low, it passes and is test-only. But the orchestrator reviews this diff line by line and it does not belong to the finding. Smallest fix: delete the 7 lines, or move them to their own backlog task.
2. **Stale module docstring** — `scheduling/views/pages/admin_audit.py:2`: "the route answers 405 to every other method". After this change a POST without a valid token, or from another site, answers 403. Risk: a reader trusts a false claim about the refusal code. Smallest fix: reword to "answers 405 to every other method that passes the cross-site check" or drop the clause.
3. **Duplicate token logic in the test** — `test_admin_audit_page.py:146-154` repeats the visitor-GET-for-token steps of `admin_support._form_token()` (`admin_support.py:52-55`). Risk: none today, two copies can drift. Smallest fix: none needed for this task; a later cleanup could make `_form_token` take the method and headers.
4. **Plan naming drift** — the plan named one test `returns_403_to_a_cross_site_post_and_200_to_a_get_when_the_log_is_opened`; the run split it into two tests with names that follow `returns_X_when_Y`. Acceptable. No action.
5. **Commit trailers** — fabro commits carry `Generated with Fabro` and `Fabro-Run`/`Fabro-Execution` trailers (e.g. `54d750a`). Per CLAUDE.md, the squash to `main` must use a hand-written message that discloses tooling and carries no `Co-Authored-By`. Not a blocker here; recorded so the squash does not copy the trailers.

### Blocking

None.

## Left for the orchestrator

- The plan has no `## Not in this run` list. Its slice is the whole finding, and every plan block is done. Nothing unfinished.
- The task names `doc/security-review.md`. It does not exist in the tree. The plan says the finding is recorded at `doc/reviews/2026-11-22-admin-appointments-waitlist-audit-settings.md:17`, which calls the exemption "deliberate and safe". That review is a dated record and was left unedited. Confirm which document the finding should close against.
- Later 1: decide whether to drop the unrelated test before squash.
- Later 2: fix the module docstring, or accept it as a follow-up.

## For the owner

- Open decision: the 2026-11-22 review at `doc/reviews/2026-11-22-admin-appointments-waitlist-audit-settings.md:17` says the exemption was "deliberate and safe". That conclusion is now superseded by this change. Whether the older review gets a note is the owner's call; the run did not edit it.
- `doc/security-review.md`, which the task names, is absent. The owner should say which document the finding belongs to.
