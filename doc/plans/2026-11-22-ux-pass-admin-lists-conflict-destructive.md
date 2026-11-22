# Task 25c, slice 1: admin tables at 375 px, the conflict page, destructive routes confirm

Slice: items 1, 2, 5 and 6 (the pages those change). Items 3 and 4 are the next run.

Three earlier plans were refused. The architect's last three reasons are requirements here and
each has its own section below.

## Focal point

One table component, `components/data_table.html` plus one rule block in `static/css/components.css`,
used by every admin list and the dashboard table. Everything else in item 1 is "use it".

## Item 1: one table component

**Decision: the DOM stays a real `<table>`.** Under 40rem the CSS turns rows into cards
(`display: block` on `tr`, `td::before { content: attr(data-label) }`). A screen reader keeps the
table, its headers and row headers. The one risk is that `display: block` on table parts makes some
screen readers drop table semantics; the fix is `role="table"`, `role="row"`, `role="rowheader"`,
`role="cell"`, `role="columnheader"` written on the elements, so the semantics do not depend on
`display`. A list would need a second markup for the same data; one markup is cheaper.

Component contract (`{% include "components/data_table.html" with caption=... columns=... rows=... %}`):
- Wrapper: `<div class="table-wrap" tabindex="0" role="region" aria-labelledby="<caption id>">`
  on **every** wrapper, at every width (reason 1 of the architect). Label comes from the caption,
  not a second string. Caption id: `table-caption-<slug of caption>`; the duplicate-id check of
  the page quality test guards it when two tables share a page.
- Every `td` carries `data-label="<column header text>"`; the row header cell is labelled by the
  same column. Cards under 40rem show the label from `data-label`; the `thead` is
  visually hidden there (`.visually-hidden` clip, not `display: none`, so headers stay announced).
- From 40rem: ordinary table, `white-space: nowrap` as today, wrapper scrolls inside its frame.
  Between 40rem and about 800 px the table is wider than its frame; the wrapper stays focusable so
  a keyboard user can scroll it. That is why `tabindex="0"` is not conditional.
- Templates moved onto it: `admin/list.html`, `admin/dashboard.html` (per-day table; its `Bar`
  column keeps `aria-hidden` svg), `admin/waitlist.html`, `admin/audit.html`,
  `admin/appointments.html`. Clinician tables (`time_off`, `availability`, `patients`) also lack
  `tabindex/role/label` on their wrapper; they move onto the component too because "one component"
  and the wrapper rule says every wrapper. Cell content (badges, links, forms) is passed through
  by the row loop in each template, so the component is the wrapper, caption, head and `data-label`
  attribute only. If a block include cannot carry a row loop in Django templates, the component
  is the CSS plus a `{% include %}` of `components/table_head.html` and a wrapper tag copied by
  two lines per template; the test counts wrappers so a copy cannot drift.
- Small fix on the way: `admin/list.html` empty search text has literal `{{ ... }}` inside a
  `with` string and is never interpolated; use a `with` variable.

**Layout invariants and measurement** (`CLAUDE.md`, "Layout"; the sandbox has no browser):
- I1 (page): at 375 px `document.scrollingElement.scrollWidth <= clientWidth` on each list and
  the dashboard.
- I2 (frame): at 375 px `frame.scrollWidth <= frame.clientWidth` for each `.table-wrap`.
- I3 (card): under 40rem each `td` is `display: block`; its box is within the frame content edge.
- Numbers I can derive: frame 341 px = 375 - 2 x 17 px page padding; under 40rem the widest card
  child is a block with `white-space: normal; overflow-wrap: anywhere`, so width = frame - 2 x
  `--space-4`, independent of content. That is the argument that I1 and I2 hold for any content.
  The test asserts the CSS facts that make the argument true: inside `@media (max-width: 39.99rem)`
  the rules `display: block` for table/thead-hidden/tbody/tr/th/td and `white-space: normal` exist
  (parse `components.css`), and no `min-width` or `width` in px larger than 341 in that block.
- Not derivable without a browser: real text wrapping of a very long unbroken value (a UUID in a
  code column). `overflow-wrap: anywhere` is the guard; the orchestrator's Chrome check at 375 px
  is the proof, as the task states.

## Item 2: the conflict page shows three values per field

Type of "what the admin read" (reason 3): a dedicated union in the domain, not an empty string.

```
@dataclass(frozen=True) class ReadKnown: text: str
@dataclass(frozen=True) class ReadUnknown: pass
ReadValue = ReadKnown | ReadUnknown
@dataclass(frozen=True) class FieldConflict: field: str; label: str; read: ReadValue; stored: str; typed: str
```

Source of the read value: the edit form gets one hidden input `read_<field>` per shown field,
holding the text the form was rendered with (same `initial_text` the inputs use; never the
password, which an edit does not show). The view parses the post: a present key is
`ReadKnown(text)`; an absent key (older tab, hand-made post) is `ReadUnknown()`. Trust: display
only, rendered escaped, never written, never authorization input; the version number stays the
only conflict test (`row.version != edit.version`). Size: <= 6 short fields per record, fine.
After the 409 page the hidden `read_` inputs are refreshed to the stored text, as `version` already
is, so a second save round compares against what the admin has now seen.

Stored value: the 409 branch re-reads the record through `admin_record_reads.find_record` (a use
case read, inside `record_or_404`); the view formats it with `initial_text` and passes text, no
query in the view. Pure function `domain/record_conflict.py::conflicting_fields(labels,
read, stored, typed)` decides which rows appear.

Truth table (field appears when `Y`):

| read | read vs stored | typed vs stored | appears | what the row says |
|---|---|---|---|---|
| Known | equal | equal | N | nothing changed by anyone |
| Known | equal | differ | Y | admin's edit; stored is unchanged by others, saving changes it |
| Known | differ | equal | Y | other admin changed it, admin typed the same; nothing lost |
| Known | differ | differ | Y | true conflict: all three values differ or typed differs from both |
| Unknown | n/a | equal | N | nothing to replace |
| Unknown | n/a | differ | Y | read cell says "Not known: this form did not keep it" |

If no row qualifies (everything equal) the page still shows the stale notice and a line "No field
differs; saving again changes nothing." Page: a `<table>`-free `<dl>` per field inside a fieldset
legend "What differs" (three labelled lines: "You read", "Now stored", "You typed"), under the
stale notice, above the form, reusing `notice` and the field styles. Wording replaces "Saving
again replaces theirs." with a sentence that names the choice: "Save again to replace the stored
values with yours, or open the record again to start over." Both controls exist: the form button
and the existing back link.

## Item 5: destructive routes confirm first

Found (HTML routes that delete, cancel, deactivate or revoke), each with a confirmation page
(GET shows, POST does):
- record delete x5 kinds: `admin-console/<kind>/<id>/delete` (`admin/delete.html`)
- user deactivate: `admin-console/users/<id>/deactivate` (`admin/deactivate.html`)
- admin appointment cancel: `admin-console/appointments/<id>/cancel`
- clinician appointment cancel: `clinician/appointments/<id>/cancel`
- patient appointment cancel (`patient/cancel.html`)
- clinician availability rule delete, time off delete (`rule_delete.html`, `time_off_delete.html`)
- token revoke: **no page**; only the `api_tokens revoke` management command (shell, deliberate
  act). Named here, out of scope: not a route.
- Found without a clear route by grep: patient waitlist leave, admin waitlist remove, sign-out.
  The new test enumerates the URL configuration and reports them; any route that destroys and
  has none is fixed in this run only if the missing page is a template and a view (no use case
  change); otherwise it goes under "Not in this run".

Test (reason 2 of the architect; says two things only), in
`scheduling/views/pages/test_destructive_routes.py`, routes derived from `page_routes()` by the
last path segment in `{delete, cancel, deactivate, revoke, remove, leave}` so a new one is
covered:
1. `returns_the_same_rows_and_status_when_a_destructive_route_is_got`: GET as the right role
   changes nothing: row count of every table touched and the record's status equal before and after.
2. `returns_403_and_changes_nothing_when_a_destructive_route_is_posted_without_token_or_origin`:
   POST with no CSRF token, and POST with token but no `Origin`, answer 403; counts and status equal.
The POST with both is the confirmation and is already covered by each page's own test; it is not
repeated. Mutation proof: remove the `csrf_protect` of one route, the test goes red.

## Item 6

`test_page_quality.py` already walks every route as every role; it runs unchanged. Added: the new
table is exercised with rows (waitlist, audit, appointments and the admin lists have none in
`make_world`), so the walk seeds one row of each in `make_world` or a local fixture.
Findings checked: table without header cells, duplicate ids, label of the region.

## Files, in order

1. `scheduling/domain/record_conflict.py` + `test_record_conflict.py` (domain, mutate-covered; add
   to the mutate set automatically; every truth-table row is a test).
2. `scheduling/views/pages/admin_record_forms.py` (read_ parsing, hidden inputs), `admin_records.py`
   (409 branch builds the context), `templates/admin/form.html`, new
   `templates/components/conflict_fields.html`.
3. `templates/components/data_table.html` (+ `table_head.html` if needed), `static/css/components.css`,
   the eight templates above, `templates/style.html` (documents the component).
4. `scheduling/views/pages/test_destructive_routes.py`; fixes for any missing confirmation found.

Not touched: use cases for writes, models, `update_record` conflict test (version only), the audit
log, FHIR, clinician time grid, patient and public pages.

## Failing tests first (names, expected values in words)

- `returns_every_labelled_wrapper_when_any_table_page_is_rendered`: every `.table-wrap` has
  `tabindex="0"`, `role="region"`, `aria-labelledby` pointing at its caption id.
- `returns_a_data_label_on_every_cell_when_a_list_is_rendered`: each `td` has `data-label` equal to
  the header text of its column.
- `returns_card_rules_under_40rem_when_the_stylesheet_is_read`: the facts of I3 above.
- `returns_one_component_when_every_admin_list_is_rendered`: the lists share the class and attribute set.
- `returns_the_changed_field_with_three_values_when_the_save_is_stale`: HTTP 409, page holds
  "You read", "Now stored", "You typed" with Before / First admin / Second admin.
- `returns_not_known_for_the_read_value_when_the_form_posts_no_read_field`.
- `returns_no_row_for_a_field_that_nobody_changed`.
- Domain: one test per truth-table row, plus `returns_unknown_for_an_absent_key`.
- The two destructive-route tests.
- `returns_the_typed_value_kept_when_the_save_is_stale` stays green.

## Invariants and blast radius

Server-side authorization unchanged (all pages `allowed_roles = {ADMIN}`); optimistic lock by
`version` unchanged; audit log untouched; no double booking path touched. `read_` values are
escaped by Django autoescape and are never logged. Blast radius: templates of eight list pages and
`components.css` table rules (a regression shows as layout, caught by the CSS-facts test and the
Chrome check). No inline script or style; no JavaScript needed: cards and wrappers are CSS.

## Trust boundaries

Browser to `RecordFormPage.post`: `version` validated as ASCII digits (exists); `read_<field>` is
untrusted display text, length-capped to the field's maximum, only keys for shown fields read.
Domain entities: Admin, Hospital, Department, Specialty, User, Clinician, Room, AppointmentType,
Appointment, WaitlistEntry, AuditLogEntry (read only).

## Not in this run

- Item 3: status word and icon everywhere (admin appointments list prints bare text; user
  Active/Inactive has no icon; no page renders an API token status, the command only) and the
  vocabulary-wide test.
- Item 4: empty-state and kept-input audit of every list and form, and the empty-database test.
- Destructive routes found without a confirmation page that need a use case change.

## Architect review

Verdict: approve.

- Ladder: one component, one CSS block, one pure domain function; no new dependency. The `role=` attributes on a real table are justified by the `display: block` risk. Right layers: conflicting-field decision in the domain, stored read in a use case, view formats only.
- The three earlier requirements are met: the wrapper rule (`tabindex`, `role="region"`, caption label, at every width), the destructive-route test (GET changes nothing, POST without token or `Origin` answers 403), and the typed `ReadKnown | ReadUnknown` with its source and a truth-table row for "unknown".
- Slice (items 1, 2, 5, 6; items 3 and 4 next) is coherent and leaves the product whole. Items 3 and 4 do not depend on these changes.
- Security: `read_<field>` is named as untrusted display text, escaped, length-capped, never written and never an authorization input. The version number stays the only conflict test.

Things to watch in red and green, not reasons to revise:
1. The "POST with a token but no `Origin` answers 403" case holds only if the project enforces `Origin` itself, because Django alone accepts a valid token over http without `Origin`. Check the real enforcement before writing the test. Do not assume it.
2. The destructive-route enumeration of waitlist leave, admin waitlist remove and sign-out is still open in the plan. The run must write down what the test finds, and anything left unfixed goes under "Not in this run" with its route name.
3. The CSS-facts test is a weak proxy for I1 and I2. The orchestrator's Chrome check is the real proof, so keep that stated in the hand-off.
4. Seed rows for waitlist, audit and appointments in the quality walk, so the new component is exercised with content.
