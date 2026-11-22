# Review: task 25c slice 1 (admin tables, conflict page, destructive routes)

Diff `main...HEAD`, 20 files. Commits after `verify_green` up to `prove` (`eb90c6a`) touch only
`test_admin_table_component.py` (+1 line) and `test_destructive_routes.py` (+16): no product line
changed during proof. Lint, tests (4027) and gate passed in `check`. `make mutate` was not run in a stage.

## Plan in one sentence, per block
- `domain/record_conflict.py`: pure, lists fields where read-vs-stored or typed-vs-stored differ; `ReadUnknown` is its own type. Confirmed at a glance, matches truth table.
- `admin_records.py` `_conflicts`/`_read_inputs`: 409 branch re-reads the record, formats text, calls the domain. Traced `stored[field]`/`typed[field]`: both dicts cover every shown field (`initial_text`, `kept_text` of the parsed form), no KeyError; password is blanked on both sides.
- Templates and CSS: wrapper `tabindex/role/aria-labelledby`, `data-label` per cell, cards under 40rem. Confirmed.
- `test_destructive_routes.py`: GET changes nothing; POST without token or from another site answers 403 and changes nothing. Matches the architect's wording.

## Findings
1. **Later**, `scheduling/templates/admin/list.html:13`: the plan promised one `components/data_table.html` (and a `/style` entry). None exists; the wrapper, caption and head markup is copied into nine templates (it used the plan's stated fallback). Drift is guarded only by the wrapper-count test. Smallest fix: extract a wrapper/head include.
2. **Later**, `scheduling/templates/admin/list.html:14`: caption id is the same literal `table-caption-list` on every list; fine one table per page, a duplicate id if two share a page. Use a per-table slug as planned.
3. **Later**, `scheduling/views/pages/admin_record_forms.py:222`: the plan said `read_<field>` is length-capped to the field maximum; it is not. Display only, escaped, never written, so no blocker. Cap at the field maximum.
4. **Later**, `static/css/components.css:244`: `.table, .table table, ...` sets `display: block` on `.table` itself; the I1/I2 invariants are only proven by CSS facts. Orchestrator's Chrome check at 375 px and 1440 px is the proof.
5. **Later**, `scheduling/views/pages/admin_records.py:285`: `_conflicts` builds `dict[str, object]`; a small typed row would be clearer. Not a hard-rule break.
6. **Later**: `make mutate` and the time `make test` takes (about 34 s here) are for the orchestrator on a quiet machine.

No hard rule broken: no `Any`/`cast`/bare ignore, no swallowed error, no oversized file or function, authorization unchanged (`allowed_roles = {ADMIN}`), version stays the only conflict test, no write path changed (no audit change needed), no dependency added.

## Blocking
None.

## Left for the orchestrator
- Item 3: status word and icon everywhere, vocabulary-wide test.
- Item 4: empty-state and kept-input audit, empty-database test.
- Destructive routes found without a confirmation page that need a use case change (token revoke is a management command only).
- Chrome check of every admin list and the dashboard at 375 px and 1440 px, two-tab conflict, empty list; `make mutate`.

## Later
Findings 1 to 6 above.
