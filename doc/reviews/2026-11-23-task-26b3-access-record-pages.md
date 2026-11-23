# Review: task 26b3 item 3, record pages walk

Reviewer: second reader (§12, §13.3). Diff: `git diff main...HEAD` on `fabro/run/01M846NHZY55065WPP76KBERRD`.
Changed: `scheduling/views/pages/page_walk_support.py` (+7), `record_walk_support.py` (new, 213 lines),
`test_page_access_records.py` (new, 113 lines), `test_page_access_walk.py` (+24, -3), and the plan.
No product code, no row file, no `drlibre-specs.md`, no migration, no dependency change.

Verdict: **approve**. No blocker. Findings below go to Later.

## Read order and what was confirmed

1. Block plans, stated in one sentence each:
   - `fill_route`: substitute `<uuid:name>` from a mapping. Confirmed at a glance; `path_of` now delegates to it unchanged (`page_walk_support.py:104`, `:108-112`).
   - `records_of`: build the other records and one hold per caller. Confirmed at a glance (`record_walk_support.py:49-72`).
   - `_hold_carried_to` / `_hold_made_by`: a visitor browser makes the hold, its `drlibre_hold` cookie is copied to the caller. Traced: `made_this_hold` reads only that cookie (plan, "Deviations"); the 303 is asserted before the Location is parsed (`:84-88`).
   - `ids_for` / `_id_of` / `_admin_record_id`: a placeholder maps to a record per leg. Traced; each `match` arm was checked against the plan's record table. Unknown names raise (`:148`, `:171`), so a new placeholder fails loudly, not silently.
   - `accepted_answers`: own = row answer; other = refusal (or row answer when refused); missing = 404 when admitted. Traced against plan; see Later 2 for the admission source.
   - `leaks` / `other_marks`: text search of the body. Confirmed; see Later 1 for its reach.
   - `test_page_access_records.py`: four tests, each `_mismatches(leg)` plus a coverage test. Confirmed.
2. Correctness and errors: no swallowed error. Every `assert` in the support module names its code (`# noqa: S101`) and guards a setup invariant, not an expected answer. The hold POST's 303 assert is a broken-setup guard, which is the right use (§8.2 invariant).
3. Authorization: nothing product-side changed. The walk sends GETs with the cookie a browser would send; setup POSTs go through `browser_post` (CSRF and Origin). Nothing sensitive written to logs or URLs.
4. Double booking: not in scope of this diff (test-only, creates other appointments with distinct clinicians and default times). The fixture comment in the plan notes a first try hit the no-overlap constraint; the final choice avoids it.
5. Tests: derived from the specification (12.3) and the table, not from the product's output. Two checks on whether they can fail:
   - Coverage test: compares resolver record routes that answer GET with walked rows (`test_page_access_records.py:104-113`). Adding a record route without a row fails it; removing a route fails it (extra).
   - Leg B and leg C each check an answer, so a product that answers 200 on another's record fails leg B.
   - Mutation results are recorded in the plan (three reds, each reverted). I did not re-run them: the reviewer edits no source. Trace is clean: `git diff 6bf4803 2b787ed -- scheduling/` is empty, so `prove` left no residue.
6. Names and comments: names state roles (`records`, `holds`, `other_marks`, `accepted_answers`). One shortened word (`_pk`) and one loose type (`Model`), both Later. Comments explain why (the slot query, the owner-less exemption, hold cookie); none narrate.
7. Proof trace: commits after `verify_green` (`6bf4803` write, `ca048ae` check, `2b787ed` prove) touch no product line. `2b787ed` is empty against `6bf4803` for `scheduling/`.
8. Scope: one slice. No dependency added. The `KNOWN_DIFFERENCES` additions are the five pairs in the plan (`test_page_access_walk.py:51-64`); each is a product answer the table does not give, see `## For the owner`.

## Findings

### Later

1. **Leak check reach** — `record_walk_support.py:186-207`, `test_page_access_records.py:60-73`. Severity: nit for this slice. The check matches only ids and the two owners' emails. A refused page that printed the other patient's or clinician's name would pass. Risk: a name leak in a 403/404 body goes undetected. Smallest fix: add each other owner's display name (`get_full_name()` or the clinician's display name) to `other_marks`, and add a leg B case that fails when it appears.

2. **Leg C admission reads the product answer** — `record_walk_support.py:174-183` calls `_wanted`, which returns the `KNOWN_DIFFERENCES` answer. For the five pairs whose table answer is OK but whose product answer is not (`book/<appointment_type_id>/details` for clinician and admin; admin `appointments/new/<appointment_type_id>/provider`, `/times`, `/review`), a missing type is accepted as 403 or 302, not the 404 that spec 12.3 gives a missing record. Risk: the missing-record rule is unverified for those five pairs. Smallest fix: decide admission from `_expected_answer(row, caller)`, and let leg C accept 404 only; the five pairs then need owner resolution (see `## For the owner`) or a leg C pair in `KNOWN_DIFFERENCES`.

3. **Stale no-GET list is not checked** — `test_page_access_records.py:35-51`, `:104-113`. The coverage test compares resolver routes with walked rows but never checks that each `NO_GET_RECORD_ROUTES` entry still exists. A removed route stays in the list silently. Smallest fix: assert `NO_GET_RECORD_ROUTES <= {all record route strings from _all_rows() and the resolver}` in the coverage test.

4. **Naming and types** — `record_walk_support.py:40-41` (`time_off: Model`, `other_time_off: Model`): type as `TimeOff` (the walk's `make("TimeOff", …)` returns the model). `:210-213` `_pk`: a shortened word; rename `_uuid_of` (CLAUDE.md §3, no shortened words). `:127` `other = leg == "other"`: acceptable; `is_other_leg` would state the role.

5. **Private names imported across test modules** — `record_walk_support.py:23` (`Caller`, `_wanted`), `test_page_access_records.py:22-29` (`_answer_of`, `_answers_get`, `_clients`, `_page_callbacks`). The plan records the `conftest.py` reason and the later move. Smallest fix in a later run: move these helpers into `page_walk_support.py` so the record module imports from a support module.

6. **Measured cost, not a blocker** (§ budget rule). On this shared sandbox: `test_page_access_records.py` alone runs 4 tests in 2.27 s (the walk's largest test, leg A, 0.61 s call); full suite `make test` 141.9 s at `-n auto` (the plan's `Left` section reported 172 s for an earlier run). The orchestrator measures on a quiet machine.

7. **Mutation proof not re-run here.** The three reds recorded in the plan's `Deviations` (patient cancel row flipped; other appointment owned by the world's patient; time-off delete dropped) are the only evidence of red. The orchestrator judges "red for the right reason" from them (process note 2).

8. **Plan citation slip** — the plan's `Left` section cites spec "7.2" for public booking. Section 7.2 is the patient account. The booking flow is 7.1 (`drlibre-specs.md:367`). Doc only; the owner question below cites 7.1.

## For the owner

Each is a product answer that differs from the table; each is kept as a `KNOWN_DIFFERENCES` pair with both answers.

a. **`book/<uuid:appointment_type_id>/details`, clinician and admin**: table OK, product 403 (`scheduling/views/pages/booking_details.py:70-72`, `_refuse_staff`). Spec 7.1 (`drlibre-specs.md:367`) describes the booking flow for a visitor who becomes a patient; spec roles table (`drlibre-specs.md:26-29`) says staff book "for patients" through the admin flow. The product's 403 fits the spec; the table's OK for clinician and admin looks wrong. Owner decides: keep the product's 403 (table fixed) or open the public details page to staff.

b. **`admin-console/appointments/new/<uuid:appointment_type_id>/provider`, `/times`, `/review`, admin**: table OK, product 302 to `/admin-console/appointments/new` with no wizard state. Same pattern as the existing `new/service` pair. The spec section for the admin appointment wizard was not located in `drlibre-specs.md` during this review; the owner names it or accepts the redirect.

c. **Admin is not walked on leg B for admin-console user-owned routes** (`record_walk_support.py:97-103`). The backlog text says another user's record "must answer 403 or 404" for every caller. Spec roles table (`drlibre-specs.md:29`) says admin manages users and clinicians, and 12.3 says a record "belongs to someone else gives forbidden" for signed-in users of another role's area. The exemption is the spec's reading; the orchestrator confirms it narrows the backlog text, as the plan asks.

## Blocking

None.

## Left for the orchestrator

From the plan's `## Not in this run`:
- Sign-out (`sign-out`), sign-in form pages (`sign-in/email-link`), `patient/notifications/read-all`, `admin-console/appointments/export`, `admin-console/settings/reminders`: form-only or non-GET; another run.
- The 12 record routes that answer no GET (`NO_GET_RECORD_ROUTES`): form-only; another run.
- Backlog item 4 (access section in `doc/security-review.md`, generated by a Makefile command and checked by a test): another run.

Not in the plan's slice, unfinished: nothing. The item 3 record-page slice is complete as the plan states it.

Orchestrator confirmations the plan asks for (not blockers, not reviewer's call): (a) visitor on a sign-in row gets the sign-in redirect on own, other and missing record; (b) admin exemption on leg B (see For the owner c); (c) `tests-and-docs` with mutation proof as red evidence; (d) a signed-in caller's hold POST creates a hold — verified indirectly: the walk's hold tests pass on the current product (leg A, `book/holds/<hold_id>/code` for each caller).
