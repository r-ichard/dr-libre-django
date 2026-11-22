# Review: task 24c3, FHIR Practitioner update and delete

Base `cdc50b3`, head `5a5cecd`. Gates reported green in the run (lint, 4390 tests, gate). I did not re-run them.

## Plan in one sentence per block
- `domain/fhir_practitioner.py`: pure parse of a body into the console's values, plus refusal of a differing phone. Confirmed at a glance.
- `use_cases/fhir_practitioner_writes.py:60-118`: admin check, one transaction, `update_user`, then `update_profile` for the title, then `deactivate_user`. Forced a trace: nested transactions, rollback via `set_rollback`, and the version passed between steps.
- `fhir_resources.py`, `views/fhir/*`: routing, `Allow` on the collection, samples. Confirmed at a glance.
- `admin_users.py:166`: `delete_user` gains an optional `If-Match` check inside the lock. Console callers are unchanged.

## Trace results
- Authorization: the admin comes from the token (`admin_of`), checked before the body is read. A missing profile gives 404 before the body. A role other than admin gets 403 and no token gets 401.
- Atomicity: each step returns a `Failure`, the outer block rolls back, and every console audit entry sits in the same transaction.
- Own-user and last-admin rules come from `deactivate_user` and `update_user`, so they are not duplicated.
- Phase order: no product or migration line changed between `verify_green` and `prove`. `prove` touched only tests and `mutation-equivalents.txt`. After `prove`, `refactor` touched one use-case file (13 lines). The reviewer sees it in this diff and it has the required stage name.
- No dependency added. No `Any`, `cast` or bare ignore seen in the diff.

## Findings
1. Nit, `fhir_practitioner_writes.py:89-92`: `expected_version` is compared with the user's version, while a title change moves the same `versionId` only because `update_profile` also touches the user. The tests cover it (412 after a title change). Risk: a later change to `update_profile` would silently break item 5. Smallest fix: a comment naming the coupling.
2. Nit, `fhir_practitioner.py:78`: `active` that is not a bool is read as false, which deactivates. The shape check should reject it earlier through `PRACTITIONER_SHAPE`; confirm a test sends `"active": "yes"`.
3. Nit, `views/fhir/views.py:103`: `lists_instance_methods` is a flag used by one resource. That is fine until a second caller exists.

## Blocking
None.

## Later
- Findings 1 to 3.
- Timing: `make test` took 33 to 47 s here on a shared machine. The orchestrator measures it on a quiet one.
- `make mutate` and `make fhir-validate` run as the last scripted gate, not here.

## Left for the orchestrator
The plan's "Not in this run" says: nothing from the task. Task 24d (closing section 15) is separate. No item of the slice was left unfinished.
