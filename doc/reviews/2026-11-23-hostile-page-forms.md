# Review: hostile input to every page form (task 26c, item 16, page forms)

Diff: `git diff main...HEAD` on `fabro/run/01M83ZVK99DA820BTHSNMQR5Q5`. Two files, both additions:
`scheduling/views/pages/test_hostile_page_forms.py` (+95) and `doc/plans/2026-11-23-hostile-page-forms.md` (+182).
No product code, template, migration, specification, ADR or Makefile change.

Verdict: **approve**. No blocker. Items under Later are real and small; the orchestrator decides which to take.

## Plan in one sentence, and what was traced

- `_page_statuses` (test file :37-51): one client per role, GET the page, POST every walked name with every hostile value, record the status by (action, name, value). Confirmed at a glance.
- Test 2 (:86-95): for each route, collect every 500 across roles, assert the list is empty. Confirmed at a glance.
- Traced (§2.3): `post_forms` and `_FormReader` (`scheduling/views/pages/form_walk_support.py:30-81`) to confirm that the names come from the rendered HTML: hidden inputs, text inputs, textareas and selects are all read, and `submit`, `file`, `disabled` and unchecked boxes are skipped. The walk does include the `csrfmiddlewaretoken` hidden input (see Later 4).
- Traced: `client_for_role` and `browser_client` for the Origin and CSRF setup the plan describes (`page_walk_support.py:71-82`, `browser_support.py:11-18`). Signed-in roles enforce CSRF and send `Origin`; the signed-out client does not, as the plan records.

## Measurements from this review (sandbox, shared machine; the orchestrator re-measures on a quiet machine)

- `pytest -n 0` on the new file: 112 passed in 14.92 s. Slowest: floor test 3.02 s; largest route case 2.19 s (`admin-console/hospitals/<uuid>/edit`); `admin-console/hospitals/new` 1.03 s. Every case is far under the 60 s limit and under the 10 s rule in the plan.
- Requests, counted by a probe over all 110 route cases (probe removed, not committed): 1955 POSTs, 770 GETs (4 per route are the per-role page reads; the rest are GETs made inside the helpers), 183 POSTs in the largest single route case. Every one of the 110 routes sends at least one POST for some role, so no route is vacuous.
- No 500 for any of the five hostile values across those 1955 POSTs, on this branch. Test 2 passes for every route.
- Red proof (probe, removed): a copy of test 1 with `post_forms` filtered to `FIELD_NAMES` (the fixed list) fails at `scheduling/views/pages/test_hostile_page_forms.py:67`: `AssertionError: assert 'clinical_notes' in set()`. The real walk passes the same test. So the test fails on the fixed list and passes on the derived walk. This is the coverage red the plan asked for.
- Forms walked: the floor test asserts at least 126 forms and 325 fields; it passes. Counts over all routes and roles were not separately printed here.
- Commit discipline (§2.7): `286667f` (verify_green) and `92f44cc` (prove) are empty. `0e4993f` (refactor) and `4f055da` (check) change only `scheduling/views/pages/test_hostile_page_forms.py`. No product or migration line changed after green.

## Checks in the order the card asks

1. Plan and trace: done above.
2. Correctness and error handling: the tests catch a status of 500 or more and nothing is swallowed. `_page_statuses` returns `{}` for a non-200 page (:41-42). That is a deliberate skip, covered in Later 2.
3. Authorization: the role comes from the session cookie (`client_for_role`), never from the payload; the test adds no route. Fine. Nothing sensitive is logged; the failure message carries the first 20 characters of a hostile value, which is test data.
4. Double booking: not in this change. Not applicable.
5. Tests: test names state behaviour (§3, §10.1). Test 1 is red on the fixed list (see above). Test 2 is derived from the spec's "every input validated at every boundary" (plan item 6) and the expected result (no 500) is derived from the spec, not from the implementation. The floor test is a tripwire, not an oracle. The plan's assertions 1 and 2 for test 1 are only partly written (Later 3).
6. Names: `_page_statuses`, `names_sent`, `hostile`/`statuses`, `Statuses` and `CLINICIAN_APPOINTMENT_ROUTE` state roles. No `temp`, `data2`, single letters. Comments: the module docstring and the constant comment (:21-22) say why; under 255 characters per block; `make gate` passed in the check stage.
7. Proof trace: see measurements above. Clean.
8. Scope: no dependency added; no contract changed; `FIELD_NAMES`, `test_hostile_input.py` and the walkers are untouched, as the plan says. No `drlibre-specs.md` change in the diff.

## Blocking

None.

## Later

1. **Important (latent)**: `scheduling/views/pages/test_hostile_page_forms.py:50`. The key `(form.action, name, value)` collapses two forms that share an action and a field name on one page; the later status overwrites the earlier, so a 500 from the first can be lost. Probe: no such collision exists on the 110 routes today. Risk: a future page with two forms posting one name to one URL hides a 500. Smallest fix: record the status inside the loop and append to the failure list there, or key by the form's index as well.
2. `scheduling/views/pages/test_hostile_page_forms.py:41-42`. A page or role that answers non-200 sends nothing and passes. The shared world can make this happen: an earlier hostile POST that succeeds (a cancel, a delete) can leave a later role's page at 404 with no POST sent. Only the floor test at :82-83 guards it, in aggregate. Smallest fix: in test 2, assert the GET status is 200 for a role that is expected to see the page, or assert at least one POST was sent per route.
3. `scheduling/views/pages/test_hostile_page_forms.py:62-68`. Test 1 asserts the names sent and no 500. The plan's assertion 1 (page answers 200) and assertion 2 (sent set equals walked set) are not written. The mutant output shows the consequence: the failure reads `'clinical_notes' in set()`, not a status. Smallest fix: `assert client.get(path).status_code == 200` before the walk, in the test body.
4. `scheduling/views/pages/form_walk_support.py:61-68` with the test's loop (:46). The walk includes the `csrfmiddlewaretoken` hidden input and sends each hostile value in its place. For signed-in roles the CSRF check then answers 403 before the form's parser runs, so that name is never exercised. No 500 risk; a coverage gap. Smallest fix: skip `csrfmiddlewaretoken` in the name loop, with a one-line reason. The plan says "every walked name is sent", so this is a plan decision for the owner or the orchestrator.
5. Nit: test name at :71 is `returns_at_least_the_measured_forms_and_fields_when_every_page_is_walked`; the plan names it `..._forms_when_...`. The file's name is the better one; update the plan or leave it.
6. Nit: the floor test (:71-83) repeats the walk loop from `_page_statuses`. Plan item 3 accepted that for a smaller diff; it is fine to leave.
7. Owner question, not a fix: item 16 asks for a wrong type on every field. Page forms carry strings only, so the plan drops wrong types for page forms (plan `## For the owner`). JSON and FHIR runs keep them. Needs the owner's yes.
8. Owner question, not a fix: `FIELD_NAMES` still lacks `clinical_notes`. The plan rejects extending it on purpose. The owner may want to know that the fixed list keeps missing page fields until it is retired.

## For the owner

- Wrong-type values on page forms are dropped (plan `## For the owner`, first bullet). Confirm.
- `FIELD_NAMES` is unchanged and still incomplete for page forms by design (plan `## For the owner`, second bullet). The page-form walk is the coverage for page forms now.

## Left for the orchestrator

- Item 16 for `/api/v1` request schemas and `/fhir` writes: other runs (plan `## Not in this run`).
- Routes answering 404 for the world have no walked forms; a later run gives every record kind its own id in the world (plan `## Not in this run`). Test 2 covers every route that renders a form today; 110 of 110 send POSTs.
- Deduplicating forms by (role, page, action) for the text walker: unchanged (plan `## Not in this run`).
- Measure the page file's durations on a quiet machine (see Later 7 and the measurements above).
