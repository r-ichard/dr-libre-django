# Review: access walk over the routes that name no record

Diff: `git diff main...HEAD`, six files, all test code and one plan. No product file, migration,
dependency, or `drlibre-specs.md` changed. Commits after `write`: `check` (no file changes) and
`prove` (`scheduling/views/test_api_access_world.py`, a test helper: adds a session-cookie
assertion). Both allowed.

Verdict: **approve**. Re-ran `test_api_access_walk.py`, `test_api_access_table.py` and
`test_api_access_rows.py` with the test environment from the Makefile: 3 passed.

## Block by block (one-sentence plan, then what forced a trace)

- `test_api_access_rows.py`: `Caller` enum, `AccessRow.answer_for`, `KnownDifference`, and an
  empty `KNOWN_DIFFERENCES`. Confirmed at a glance. Cells unchanged (diff shows additions only).
- `test_api_access_table.py`: docstring only. Confirmed.
- `test_api_access_world.py`: builds one clinic, three signed-in accounts and their logout
  clients through the product's login, and a passwordless patient; `_new_link` writes a
  `SignInLink` at send time. Traced: `_sign_in` posts through `browser_api_client()` (enforced
  CSRF, `Origin`), `_build_world` asserts the session cookie per client, and `_new_link` is
  created inside the verify sender because `ask_for_link` cancels open links for the same
  address (`sign_in_link.py:47-51`, per the plan; not re-read).
- `test_api_access_requests.py`: one sender per walked `(method, route)`, 14 keys. Traced each
  body against the serializers' field names. Visitor gets a fresh client per request.
- `test_api_access_walk.py`: `WALKED_ROWS` (no `<`, not `booking/holds`) gives 14 rows, the
  sender loop sends 14 x 4 = 56 requests, compares to `_expected_status`, and asserts
  `problems == []`. Traced the filter by hand: health, login, logout, link, verify, slots,
  three search, GET and POST appointments, waitlist, reminders, catch-all = 14. Traced
  `_expected_status` and `_difference_problems`: with an empty tuple the second is a no-op.

Request count, from the code: 56 walk requests, 6 sign-ins in `_build_world` (3 shared, 3
logout), so 62 HTTP requests. Verify-link rows are direct writes. Matches the plan.

## Checks

1. Plans: stated in one sentence for every block above.
2. Correctness and errors: no `except`, no swallowed error. Failing status is a mismatch; a
   product exception surfaces because the client keeps `raise_request_exception=True`.
3. Authorization: test code only. Each request carries the browser's cookie and `Origin`; the
   walk asserts status codes only. Bodies are fixtures, not input.
4. Double booking: product not changed. The walk books three distinct slots (A at `STARTS_AT`
   for patient, B at `+1h` for clinician, C at `+2h` for admin); the visitor's booking is
   refused before any slot is taken.
5. Tests: derived from the access rows (specification-based), not from the code. The walk
   asserts answers, not bodies; the plan says the per-route modules own bodies.
6. Names: `returns_the_row_answer_for_each_caller_when_the_walk_sends_each_request` follows the
   rule. Module docstrings name what each module holds, no task number (grep for `26b3` and
   `item` in the walk files: no hits). No `Any`, `cast`, bare `# type: ignore`, or bare `# noqa`
   in the new files. Line counts: 127, 217, 51, 93, 97; no function over 50 lines.
7. Proof trace: see Later item 2.
8. Scope: nothing beyond the slice. No dependency. No contract change across layers.

## For the owner

Nothing. `KNOWN_DIFFERENCES` is empty: the product's answers match the access rows for all 56
walked pairs. No row was changed to make the walk pass.

## Findings

### Later

1. **nit**, `scheduling/views/test_api_access_requests.py:14`, `:66`, `:68`, and
   `scheduling/views/test_api_access_world.py:88`. The sender module imports `_new_link`, a
   private name, from the world module. Risk: low; a reader takes the underscore as "not for
   this module". Smallest fix: rename to `new_link` in `world.py:88` and the three uses.
2. **important, not blocking**, `scheduling/views/test_api_access_walk.py:43-82`. `_difference_problems`
   and the both-ways check (`row_answer` equals the cell, `product_answer` differs from it) run
   only when `KNOWN_DIFFERENCES` is non-empty (`test_api_access_rows.py:49` is empty). The walk
   passes today without ever executing that branch. Risk: a flipped comparison passes until the
   first real divergence. Smallest fix: the build records one listed pair run both ways. The
   run's commits do not show that, and the plan's revert proof (waitlist clinician cell 403 to
   201 yields exactly one mismatch) is not in the trace. I did not edit sources, so I could not
   reproduce it. The orchestrator should check the build's log for both proofs.
3. **nit**, `scheduling/views/test_api_access_world.py:51`. The plan named `sign_in(email,
   password) -> Client`; the code has `_sign_in(user: User)`. Harmless; the plan's signature was
   not kept.
4. **nit**, `scheduling/views/test_api_access_walk.py:29`. Nothing asserts `len(WALKED_ROWS) ==
   14`. A filter change that drops rows shrinks the walk without a failure. Smallest fix: a
   named constant `WALKED_ROW_COUNT = 14` and an assertion in the walk test.
5. **measured, not a finding**: the three access modules ran in 1.52 s on this sandbox. The
   `check` stage's full `make test` took 123.38 s (5392 passed) on a shared machine. The
   orchestrator measures the budget on a quiet machine.

## Blocking

None.

## Left for the orchestrator

From the plan's `## Not in this run` (out of this slice, not blockers):

- The record-naming rows (`hospitals/{id}`, `providers/{id}`, `specialties/{id}`,
  `appointments/{id}/...`, `waitlist/{id}/...`) and the hold routes (`booking/holds...`): next run.
- The `/fhir` rows: the owner scoped this run to `/api/v1`.
- Item 4 of task 26b3: the access section of `doc/security-review.md`, the generator command,
  and the drift test.
- Method mismatches (for example `GET /api/v1/auth/login`): not rows, not walked.
- Any product fix: none needed in this slice.
- Documentation: `doc/handover.md` unchanged, since no product state changed.

Not finished from the slice itself:

- The build-stage proofs in the plan (walk fails on a changed cell; `KNOWN_DIFFERENCES` checked
  both ways). Not in the run's commits. See Later 2.
