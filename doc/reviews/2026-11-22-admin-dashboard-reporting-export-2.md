# Review 2: task 21, admin dashboard, reporting, CSV export (after the address stage)

Diff `main...HEAD`: 48 files. Domain (report range, figures, utilisation, cell escape, audited type
registry), use cases (`admin_report`, `admin_appointment_export`), views, dashboard template, notice
cookie, waitlist query, carried items 14-17. Commits after `verify_green` up to `prove` touch tests
and `mutation-equivalents.txt` only: no product line mutated. `make gate` and escape hatch gate pass.

## Confirmed at a glance
- `admin_report.build_report`: six queries, hospital-local day kept from a one-UTC-day superset
  (`admin_report.py:57-64`). Counted once, whatever the reader's zone.
- `admin_appointment_export.export_appointments`: read, row limit (50,000, refused with a message),
  audit with `row_count` inside one `transaction.atomic` (`:33-44`). POST only, `never_cache`,
  attachment name, every cell through `csv_row`.
- Dashboard: bar is an SVG `rect` width attribute, no style, no script, table beside it.
- `reference_messages` no longer locks (`admin_clinicians.py:173-185`); waitlist busy times left out
  in SQL (`waitlist.py:_without_conflicts`); audit filter reads `AUDITED_ENTITY_TYPES`.

## Findings
### Blocking
- `make test` takes 38 to 40 s here (three runs; the check stage said 41.8 s, verify_green 52 s).
  The task's done-when says under 30 s. Fix: profile with `--durations=20`, trim the
  route-enumerating hostile-input/unique-id/role tests or the new export/notice tests (share fixtures,
  fewer cases per route).

### Important (not blocking)
- `scheduling/use_cases/test_api_tokens.py::returns_audit_entries_with_ids_only_when_token_issued_and_revoked`
  failed in one of four full runs and passed in the others; the file is not in the diff. Flaky, likely
  order or time dependent. Own task.
- `admin_notices.py:18` the notice sentence holds a patient's full name; the cookie is signed, not
  encrypted, so the name is readable in the browser's cookie jar and in a proxy log. Fix: send a code
  plus an id, or encrypt; or accept and document (it is HttpOnly, SameSite=Strict, 60 s).
- Export holds up to 50,000 rows in memory (`admin_appointment_export.py:33`); acceptable at that
  limit, stream if the limit grows.

### Nit
- `dashboard.html:49` password link moved from the home page: unrequested but harmless.
- `admin_dashboard.py` assert with named `# noqa: S101` in `admin_appointment_export.py:23`: allowed.
- Utc-superset test with zones on both sides of UTC still absent (from review 1).
- `make mutate` not run by me; the sandbox run is the proof for the domain modules.

## Blocking
- `make test` over 30 s (38 to 40 s measured).

## Later
- Fix the flaky `test_api_tokens` test.
- Notice cookie: no patient name in a readable cookie.
- Test the report with zones ahead of and behind UTC.
- Why-comment on `_overlap` relying on merged gaps.
