# Review 3: task 21, admin dashboard, reporting, CSV export (after the second address stage)

Diff `main...HEAD`, 51 files. Commits after `verify_green` up to `prove` change tests and
`mutation-equivalents.txt` only (checked with `git diff 4e48961 7681b36`): no product line mutated.
Re-run here: `make lint` clean, `make gate` clean, `make test` 3618 passed.

## Confirmed at a glance
- Export: POST only, `never_cache`, attachment name, ids only, every cell through `csv_row`
  (`admin_appointment_export.py` view `:23-34`, use case `:33-44`); read, 50,000 row limit and audit
  with `row_count` share one `transaction.atomic`. Over the limit refuses with a message.
- `escape_cell` covers `= + - @` plus tab and carriage return (`csv_cells.py:3-8`).
- Notice cookie is signed, HttpOnly, SameSite=Strict, 60 s; unsigned or stale value is no notice.
- Carried items 14 to 17 present, each with a test.

## Findings
### Blocking
- `make test` over 30 s. Measured here on 18 cores, load 7: 31.9 s, 37.9 s, 36.9 s. The review-2
  fix (20,000 character value, 8 workers) moved it from 40 s to about 32 to 38 s; done-when says
  under 30 s. Cost is concentrated: `scheduling/views/test_hostile_input.py` holds the top call times
  (5.8 s, 5.5 s, 3.6 s, 2.4 s) and `scripts/test_size_cap.py` and
  `drlibre/test_deployment_checks.py` teardowns take 10.5 s and 6.7 s (database teardown on a worker).
  Smallest fix: split the hostile-input parametrisation so no one case exceeds about 2 s (one case per
  role and hostile kind, not per role), and find why those two teardowns wait 7 to 10 s (a worker drop
  of its test database while another holds a connection).

### Important (not blocking)
- `admin_notices.py:18` the notice sentence holds a patient's name in a signed, not encrypted,
  cookie. Fix: code plus id, or accept and document.
- `test_api_tokens.py::returns_audit_entries_with_ids_only_when_token_issued_and_revoked` flaked once
  in review 2 (file not in diff). Own task.
- Export holds 50,000 rows in memory; stream if the limit grows.

### Nit
- Dashboard shows the password link moved from the home page (`dashboard.html`): unrequested.
- Test with hospital zones both ahead of and behind UTC for the report day superset still absent.
- `make mutate` not run in this stage.

## Blocking
- `make test` takes 32 to 38 s, done-when says under 30 s.

## Later
- Notice cookie without a patient name.
- Flaky `test_api_tokens` test.
- Report test with zones on both sides of UTC.
- Stream the export.
