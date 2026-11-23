# Review: security review written (task 26d, items 18 and 19)

Reviewed: `git diff main...HEAD` on `fabro/run/01M83ZJ0ZGQ0V905H6WYP0B6EE`. Two files: `doc/plans/2026-11-23-security-review-written.md` (plan) and `doc/security-review.md` (new). No product code, no test, no migration, no ADR, no `drlibre-specs.md` change in the diff. Hard rules (type escapes, function and file size, swallowed errors, audit, authorization from payload) do not apply to Markdown and nothing in the document asks for a change to them.

## Checks

1. **Plan in one sentence.** Plan: one document, one row per rule of spec sections 4, 11, 12 with enforcing file and function and holding test, then ADR 0004 limits, not-reviewed list, owner question list. Document matches the plan's blocks 1 to 9. Confirmed at a glance; the architect corrections (ADR 0005 has an open-points section, `rate_limited` also drifts, six notification events) are all reflected.
2. **Correctness of claims.** Every cited test name (85 distinct) exists as a `def` in the repository. Every cited source path exists. Spot-checked against code: `record_audit` raises outside `transaction.atomic` (`scheduling/use_cases/audit.py:27-28`); `PAGE_SIZE = 20` in four admin use cases; `LOCKOUT_FAILURES = 10`, `LOCKOUT_WINDOW = 15 min` (`lockout_rules.py:5-6`); `session_lifetime` 12 h admin, 7 d others, 24 h link or code (`session_rules.py:12-15`); cookie `httponly=True`, `samesite=SAME_SITE` (`"Strict"`), `secure=cookie_secure()` (`session_cookie.py:12-28`); `refuse_foreign_origin` returns early when no `Origin` header (`api_view.py:59-60`); `csrf_exempt` at `fhir/views.py:55` and `pages/admin_audit.py:87`; `_notify` saves then `transaction.on_commit` (`notifications.py:65-69`); `_send_in_context` catches and logs (`notifications.py:72-79`); `VISIT_REASON_MAXIMUM = 200`; rate-limit numbers (`rate_limit_rules.py:36-39`); ADR 0004 line 44 says 405, 406, 415 do not occur; ADR 0009 line 55 says refused POST is 405.
3. **Authorization, sensitive data.** Document only. It describes the rules and their enforcement; it adds no route, log or URL.
4. **Double booking.** Not touched.
5. **Tests.** No test in the diff. Document says no test was run and that its rows rest on reading. Two rows are weak evidence (see Later).
6. **Names and comments.** Markdown; no code comments.
7. **Proof trace.** Commits after `verify_green` touch only the document path; no product or migration line changed.
8. **Scope.** Diff is exactly the two files the plan names. Items 16, 17 and the access table are excluded and say so. No dependency added.

## Blocking

None.

## Later

- `doc/security-review.md:226`, owner item 7: says "per signed-in user". True for signed-in reads (`scheduling/use_cases/read_limits.py:9-11`, key `user:<pk>`); anonymous reads share a per-address counter. Fix: "per signed-in user, else per network address". Nit.
- `doc/security-review.md:26`: row says unknown fields are rejected "at every depth" and holds it with a test. ADR 0004's own limit (lines 125-128) says nested `Serializer`s outside `validate_body` are not covered. The row should carry that limit inline. Nit.
- `doc/security-review.md:33`: the "one transaction per logical change" row is held by `test_admin_user_delete_atomic.py`, a delete-dependents test, not a booking or cancel test. Weak evidence for a general rule. Name a booking-flow test or mark the row as read-only. Nit.
- `doc/security-review.md:198`: the "For the owner" intro says the list is the "Owner to confirm" lines plus ADR open points. Items 2, 5, 7, 12, 14, 15 and 16 come from other sources (the review's own drift and limits, ADR 0010 header, backlog review lines). Say so in the intro. Nit.
- `doc/security-review.md:36`: `free_slots.py` admitted not read in full. Stated, so not a defect; the row rests on DST test names only.
- Plan says "Failing tests first: None". Documentation task; CLAUDE.md routes no-behaviour tasks to `tests-and-docs`. Orchestrator to confirm the workflow matches.
- Done-when gates for task 26d (`make mutate`, `make fhir-validate`) were not part of this review and not run here. The check stage ran lint, test and gate only.
- Measured: `make test` 5276 passed in 228.44 s on this shared sandbox; not a budget finding.

## For the owner

Nothing new. The owner list at the end of the document is the question list; ADR 0011 does not exist yet and belongs to the items 16 and 17 run.

## Left for the orchestrator

- Access table (item 10): another run (per task split).
- Items 16 and 17, `doc/adr/0011-security-review.md`: another run.
- Verify on host: `make setup && make lint && make test && make gate && make mutate && make fhir-validate` from a fresh clone, before squash.
