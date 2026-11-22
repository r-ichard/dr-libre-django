# Review: a refusal never quotes a secret

Branch `fabro/run/01M82NR25H7XVVD8K5KA6H7KR3`, base `main`. Plan: `doc/plans/2026-11-22-secret-refusals.md`.
Reviewed: `git diff main...HEAD` (13 files, +447 −20), read from the files. Gates were not re-run in this
stage; the outputs in the stage record (verify_green, check, review_gate) and `mutants/results.txt` were read.

## Verdict

`approve`. No blocker. A refusal for the login password (`LoginRequest`), the link token
(`LinkVerifyRequest`), the hold code (`VerifyRequest`) and the admin temporary password
(`admin_user_support.py:67`) now carries `NOT_STORABLE_MESSAGE` and no text from the field. The
booking-code page and the sign-in and link pages reach the same schemas or refusal paths, as traced below.

## Checks, in the order of the brief

1. Plans per block. `text_rules.py:11-20` `check_storable_text` takes `secret`; a refusal passes it to
   `_message` (confirmed at a glance). `text_rules.py:30-37` `_message`: a secret returns the fixed text
   before reading `before` (confirmed at a glance). `schemas.py:19-30` `StrictTextRules.to_internal_value`
   passes `self.secret` and raises the message (confirmed at a glance). `schemas.py:48-58`: three subclasses
   set `secret = True` (confirmed). Declarations: `auth_schemas.py:21`, `auth_schemas.py:44`,
   `hold_schemas.py:51`, `admin_user_support.py:67` (confirmed at a glance). Traced: `booking_code.py:51-53`
   builds its message from `validate_body(VerifyRequest, ...)`, so the generic text reaches the page with no
   page change.
2. Correctness. A secret with a line break gets the prefix "This field takes one line." and no quoted text
   (`text_rules.py:31-33`); it reveals the kind of character, not the secret. `secret=key == "password"`
   affects only the password key. No swallowed error added.
3. Authorization and boundaries. Only refusal text changes; no route, ownership check or payload authority
   changed. The request log carries route and status (`drlibre.request`), not the body.
4. Double booking. Not touched by this diff.
5. Tests. Domain pair `test_text_rules.py:152-166` covers both branches of `secret`. API tests
   `test_api_text_fields.py:110-146` plant `Pl4nted-Secret-9x\x0c` and `482913\x0c`, assert the generic
   message and that the planted text is absent. Page tests `test_booking_code_page.py:72-83` and
   `test_admin_user_pages.py:82-92` do the same through the page forms, with the `</span>` assertion from the
   prove stage. The sign-in and link page tests (`test_sign_in_link_pages.py:225-244`) pass without this
   change (see Later L2).
6. Names and comments. `secret`, `StrictSecretText`, `StrictSecretLine`, `StrictSecretCode`,
   `NOT_STORABLE_MESSAGE` state roles. `check_storable_text` docstring (`text_rules.py:12-16`) is under the
   255 cap. Secret declared at `auth_schemas.py:19`, `auth_schemas.py:43`, `hold_schemas.py:50`.
7. Proof trace. `git show --stat`: `verify_green` (`ede947d`) and `fb94281` are empty. `prove` (`82aaf51`)
   changed four test files only. `refactor` (`352060e`) changed a docstring in `text_rules.py` and runs after
   `prove`, so it is not a mutation left behind. `address` (`8d089f7`) added the declaration comments and
   `mutation-equivalents.txt` entries.
8. Scope. No dependency, lock, migration, `drlibre-specs.md` or ADR change. The plan file and the review are
   the only `doc/` changes. No unrequested code.

## Findings

| Sev | Where | Summary | Risk | Smallest fix |
|---|---|---|---|---|
| nit | `scheduling/domain/text_rules.py:31-33` | The secret branch with a line break (prefix "This field takes one line.") has no test. Reachable through `StrictSecretLine` (token). | A later edit that drops the prefix on the secret branch passes the suite. | One assertion: `check_storable_text("token", "abc\n", single_line=True, secret=True)` equals the prefixed generic message. |
| nit | `scheduling/views/pages/test_sign_in_link_pages.py:225-244` | Two guard tests pass before the change; the sign-in and link pages never call the text rule (`sign_in.py:79-93`, `sign_in_link.py:66-67`). | None now. They guard against echo, not against the rule. | None needed; see L2. |
| nit | `scheduling/views/auth_schemas.py:19`, `:43`, `scheduling/views/hold_schemas.py:50` | The plan put the "secret" sentence once, in the `StrictTextRules` docstring. The run put it at each of three declarations. | The owner asked "say once"; three copies can drift. | Keep as is, or move the sentence to `schemas.py:14-18` and drop two comments. |
| pre_existing | `scheduling/views/pages/sign_in_link.py:66` | The link page reads the token from the address as well as the body (form has no action). | Token in address bar, history and access logs (§11). Not introduced here. | Own task; see For the owner. |

## Blocking

None.

## Later

- L1 (nit): add the secret line-break test (table row 1, `text_rules.py:31-33`).
- L2 (nit): `test_sign_in_link_pages.py:225-244` passed at the red stage (not in the `verify_red` failure list),
  because `sign_in.py` and `sign_in_link.py` never run the text rule. They pin "no echo", which is the promise.
  Keep; do not count them as red proof of the rule.
- L3 (nit): "say once" (table row 3).
- L4: commits on this branch carry the Fabro byline and `Fabro-Run` trailers (for example `77d38f8`). Squash
  with a hand-written message and disclose the tooling in the body (CLAUDE.md, hand-applied gap 1).
- L5: `make mutate` as run by the address stage: `mutants/results.txt` lists 86 survivors in the whole
  domain; the four in `text_rules.py` are all `x_storable_search` and match the four `mutation-equivalents.txt`
  entries I checked by reading (`storable_search` drops the field name; `single_line=None` is falsy like `False`
  at `text_rules.py:41`). Accepted. The orchestrator re-runs it on a quiet machine.
- Pre-existing `sign_in_link.py:66`: see the table; a task, not this slice.

## Left for the orchestrator

- The plan declares no `## Not in this run` section; the slice is the whole finding. Nothing excluded.
- `final_gates` (`8510cd2`) failed; its output is an unreadable blob. The `address` stage reports `make mutate`
  exit 0 and `make fhir-validate` exit 0. Re-run `sh scripts/final_gates.sh` on the verify clone before squash.
- Gates were not re-run in this stage.

## For the owner

- Should a link token ever appear in the address? The emailed link carries `?token=` by design, and the on-page
  form posts the token back to that address (`sign_in_link.py:66`). Whether the form should post the token in
  its body only, and whether the link should be a one-time redirect, is a decision the spec leaves open as far
  as this review reads. Not decided here.

## Outcomes (earlier address stage, carried over)

| Finding | Outcome | Evidence |
|---|---|---|
| N1 (nit): declarations do not say the field is secret | fixed | One `# Secret: a refusal never quotes it.` line above `password` (`auth_schemas.py:19`), `token` (`auth_schemas.py:43`) and `code` (`hold_schemas.py:50`). |
| Final gate `make mutate`: 4 unlisted survivors in `storable_search` | fixed | Listed in `mutation-equivalents.txt`, as in L5. |
| Final gate `make fhir-validate` | no change needed | Exit 0 per the address stage, warnings only. Not re-checked here. |
