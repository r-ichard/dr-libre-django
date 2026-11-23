# Hostile input to every page form, derived from the rendered pages (task 26c, item 16, page forms only)

Slice: item 16, page forms only. `/api/v1` request schemas and `/fhir` writes are other runs (see `## Not in this run`).

## Focal point

`scheduling/views/test_hostile_input.py` sends its values to the fixed `FIELD_NAMES` list (38 names).
Field `clinical_notes` (textarea on the clinician appointment page, `scheduling/templates/clinician/appointment.html:38`,
POSTed to `{base}/notes`, `scheduling/views/pages/clinician_appointment.py:75`) is rendered and
is not in that list. The fixed list is the gap behind QA round 3 (#33, #38). The new test takes its
targets from the walk instead: every `name` of every post form the page renders, for each page route,
signed out and as each role.

## Ladder

1. Existing: reuse the walker. `form_walk_support.post_forms` (parses forms), `page_walk_support`
   (`page_routes`, `make_world`, `client_for_role`, `path_of`, `ROLES`). No new parser, no new fixture.
2. Rejected: add names to `FIELD_NAMES`. That is the fixed list the item asks to stop using.
3. Rejected: move `_walked` out of `test_text_fields_as_filled.py`. It walks the whole site per call; the
   new test walks one page per case. Its ten lines are repeated in the new file, which is smaller than a
   shared-module change for a reviewer to read.
4. Chosen: one new test file beside the walker, parametrized by page route (one case per route).

## Blocks and files, in order

1. `scheduling/views/pages/test_hostile_page_forms.py` (new, about 90 lines; under 300).
   - `HOSTILE_VALUES`: a named tuple or tuple constant of five strings: NUL (`"a\x00b"`), over-long
     text (`"x" * 20_000`), beyond 64 bits (`str(2**64)`), negative (`"-1"`), markup
     (`"<script>alert(1)</script>"`). Form bodies are strings, so no wrong-type values (see `## For the owner`).
   - `_page_statuses(role, world, path) -> dict[tuple[str, str, str], int]`: keyed by (action, name,
     value). Builds one client for the role, sets `client.raise_request_exception = False` (the walk's
     clients raise on 500 by default, so a 500 would error instead of being counted). GETs the page; if not
     200 returns `{}`. For each `PageForm` from `post_forms(html, path)`, each name in `form.values`, each
     value: `client.post(form.action, {**form.values, name: value}, headers={"Origin": SITE_ORIGIN})`,
     and records the status. The form's values carry the page's own `csrfmiddlewaretoken`, as a browser
     sends it. `browser_post` is not used: it overwrites that token with a fresh one.
   - `returns_clinical_notes_sent_and_no_500_when_the_clinician_appointment_page_is_walked()`: test 1 (red).
   - `returns_no_500_when_every_page_form_field_gets_hostile_value_as_each_role(route)`, parametrized by
     `page_routes()`. `world = make_world()` once per case. For each role in `ROLES`, collect
     `f"{role} {path} {action} {name} {value[:20]!r} -> {status}"` where status >= 500. Assert the list is
     empty, with the list as the assertion message.
   - `returns_at_least_the_measured_forms_when_every_page_is_walked`: over all routes and roles, the count
     of forms and of fields is at least the numbers the green stage measures (floor, not a target). A
     tripwire: if the walk goes blind, the per-route test passes with no cases.

2. No other file changes. `FIELD_NAMES` and `test_hostile_input.py` stay as they are.

## Files deliberately not touched

- `scheduling/views/test_hostile_input.py`: its query, JSON and form kinds keep `FIELD_NAMES`.
  Widening it would not reach the page forms by name and would widen the diff.
- `page_walk_support.py`, `form_walk_support.py`, `test_text_fields_as_filled.py`: unchanged.
- Product code, templates, migrations, specs, ADRs, `doc/backlog/26c-*.md`, `doc/backlog.md`,
  `doc/retro.md`, `doc/handover.md`: unchanged in this run.
- `mutation-equivalents.txt`, `Makefile`, `pyproject.toml`: unchanged.

## Requests: count and time

- Per route case: 4 GETs (one per role) plus, for each role and each walked form, `fields x 5` POSTs.
- Earlier figures (2065 requests, 325 fields, 1625 POSTs) are superseded: they multiplied the count of
  distinct names by 5, not the count of fields per form per role, so they undercount. The exact count is
  printed by the green stage (the walk counted once per case) and written into the review; no figure
  in this plan is measured.
- Time: the earlier 2.25 s was measured on GETs only. POST cost is unmeasured. The largest case is the
  admin hospital edit, about 26 fields, so about 130 POSTs. Not measured: the claim "far under 60 s" is
  not made. At green, `--durations=5` for the page file is reported, and any case over 10 s stops the run.
- Split: one case per page route, so no case holds more than one page's posts.

## Failing tests first (behaviour names, expected values in words from the specification)

1. `returns_clinical_notes_sent_and_no_500_when_the_clinician_appointment_page_is_walked` (coverage red,
   not a 500 red).
   - Assertion 1: the page answers 200 for the clinician and the walk finds a form with name
     `clinical_notes`. If the page does not render the notes form for the world's appointment, the world
     needs a status that shows it; that is found at red and recorded.
   - Assertion 2: the set of names the test sends to that page equals the set of names the walk found, and
     `clinical_notes` is in it. The walked names come from `post_forms`, not from `FIELD_NAMES`.
   - Assertion 3: no status >= 500 (the same list as test 2).
   - Why it is red on the right thing: the fixed list `FIELD_NAMES` lacks `clinical_notes`. The red proof
     is a mutant: `_page_statuses` filtered to `FIELD_NAMES` (the old behaviour). That mutant fails
     assertion 2 with `clinical_notes` in the difference. The probe output goes into the review.
   - No 500 red is known. #38 (NUL in `clinical_notes`) is fixed in `4078bbd`; `text_rules` refuses NUL. A
     500 red can come only from test 2 on `main`, which is not yet known.
2. `returns_no_500_when_every_page_form_field_gets_hostile_value_as_each_role`, for every route. Expected:
   a 4xx or a 303 for each hostile value, never 500. Red on first run if any page form answers 500.
3. `returns_at_least_the_measured_forms_when_every_page_is_walked`: the floor, set from the green count.
   Red only if the walk breaks.

## Trust boundaries crossed

- Browser form POST: every field and value is client input. Each goes through the page's own rules on
  the server. Unchanged; the test checks that no value answers 500.
- Authorization: the role comes from the session cookie (`client_for_role`), never the payload. A hostile
  `user_id` or `role` field cannot change who the request acts as. Same actors as the existing walkers.
- Cross-site check: `Origin` is set to `SITE_ORIGIN`, as the browser sends it. The signed-out role uses a
  plain `Client()` from `client_for_role`, which does not enforce the cross-site token check, so the
  form's parser is reached. The signed-in roles use `browser_client()`, which enforces it. Recorded here,
  not a change.

## Domain entities (CLAUDE.md section 3)

Visitor (signed out), Patient, Clinician, Admin. Forms reached: Hospital, Department, Room,
AppointmentType, Clinician (ClinicianProfile), Appointment (clinical note, cancel reason), WaitlistEntry,
TimeOff, AvailabilityRule, Notification, User (sign-in, profile, password), Specialty.

## Invariants and blast radius

- No product behaviour changes. No route, model, migration, template or message changes.
- A hostile POST may save a value. It goes through the existing use case, so the transaction, the
  authorization and the audit entry are unchanged. The `django_db` transaction rolls back at the end of
  each test.
- Within one case the same world serves all roles and all POSTs, so an earlier save or delete can change
  what a later POST finds. Each route case has its own world, so this stays inside one page.
- A form that sends email (sign-in link) writes to the test mail backend, not to smtp4dev.
- `make test` gains one case per page route (110 cases) and the floor test.

## What I will not do

- No extension of `FIELD_NAMES`, no per-name list, no skip list. Every walked name is sent.
- No wrong-type values in forms (strings only), no `/api/v1` schemas, no `/fhir` writes.
- No fix of any 500 found here. A product defect is a new task (CLAUDE.md, host defect = new task). The
  run goes red and stops at the review.
- No new abstraction, no dependency, no change to the existing walkers or their tests.
- No comments that narrate; each test name states its behaviour.

## Not in this run

- Item 16 for `/api/v1` request schemas and `/fhir` writes: other runs (second and third sentences of
  item 16).
- Routes that answer 404 for the world (no walked forms). A gap for a later run that gives every record
  kind its own id in the world. The floor test stops the gap growing silently.
- Deduplicating forms by (role, page, action) for the text walker: unchanged.

## Not known yet (checked at red and green, not guessed here)

- Whether the clinician appointment page renders the notes form for the world's appointment status.
- Whether any page form answers 500 for any of the five values on `main`.
- Whether `read_*` names (hidden inputs on `scheduling/templates/admin/form.html:13`) take a hostile value
  without a 500.

## Checks at green

- `make test` on the new file first, then all; `make lint`; `make gate`.
- Red proven: test 1 fails under the `FIELD_NAMES` filter mutant and passes on the real code.
- Counts reported from the run: routes walked, forms, fields and requests. The floor in test 3 is set from
  them.
- `--durations=5` for the new file; no case over 10 s.

## For the owner (for the review, under "For the owner")

- Item 16 asks for a wrong type on every field. For page forms the plan drops it: a browser sends
  strings, so a wrong type cannot reach a page form. JSON and FHIR keep it in their own runs.
- The test covers `clinical_notes` by name through the walk; `FIELD_NAMES` still lacks it. Extending
  `FIELD_NAMES` was rejected on purpose.

## Architect review

Verdict: revise. Scope, ladder, layer and security were sound; the red test and client setup were not.
Each point is answered in place:

1. Red test now names its assertion (test 1, assertions 1 to 3) and says it is a coverage red, proven by
   a mutant that filters names to `FIELD_NAMES`, not by a missing helper.
2. The walk clients are set to `raise_request_exception = False` in `_page_statuses`, so a 500 is counted
   and not raised.
3. Timing: the GET-only 2.25 s is labelled as such; the POST cost is unmeasured; "far under 60 s" is
   removed. The durations are reported at green.
4. Field location: `clinical_notes` is on the clinician appointment page
   (`clinician/appointment.html:38`); `/notes` is the POST target.
5. The narrowed item (no wrong types for forms) is recorded under `## For the owner`.
6. Tests 2 and 3 name their values from the spec (section 4: every input validated at every boundary)
   and keep the per-value status in the message.

## Architect review (second pass)

Verdict: approve. The first pass's five points are answered and checked against the code:
`FIELD_NAMES` has 38 names; `clinical_notes` is absent from it; the textarea is at
`clinician/appointment.html:38` and `notes_action` at `clinician_appointment.py:75`; `signed_in_patient`
uses `browser_client()` (CSRF enforced, Origin sent); `SITE_ORIGIN` exists in `browser_support.py`;
`#38` is fixed in `4078bbd`; `test_destructive_routes.py` does not clash, since it tests GETs and bad tokens.

Remaining nit, not a reason to revise: `## Blast radius` says "110 cases", but `## Requests` says no
figure is measured. Count it at green or write "one case per route".
