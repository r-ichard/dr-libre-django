# Review: task 24c, FHIR PractitionerRole writes and time off

Diff `main...HEAD`, 23 files. Slice declared in the plan: items 2, 3, 4, 6 and the PractitionerRole half of 5.

## Plan in one sentence per block
- `fhir_role_write.py` (domain): reads a body into console profile fields and time off changes, names the first element that differs from the stored role. Confirmed at a glance.
- `fhir_role_writes.py` (use case): the admin goes through `attach_profile`, `update_profile` and `delete_profile`; the owning clinician goes through `create_time_off` and `delete_time_off` in one locked transaction. Traced `_own_update` (rollback path) and `_admin_update`.
- `fhir_loading.py`, `fhir_practitioner_role.py`: `notAvailable` on the staff build only.
- `admin_clinicians.delete_profile`: gains an optional `expected_version` checked under the lock, the same as `update_profile`.

## Checks
- Proof trace: commits after `verify_green` up to `prove` touch tests and `mutation-equivalents.txt` only (4 files, no product line). Clean.
- Authorization: it comes from the token's user. Refusal runs before the body is read (`fhir_role_writes.py:33`). The own-profile check runs under the lock (`:106`). The use cases re-check the admin.
- Audit and transaction: the writes reuse the console's use cases, which audit in their own transaction. A clinician PUT is one `atomic`, with `set_rollback` on a failure after the first step (`:119`). No reason text is logged.
- Double booking: not touched. Time off leaves booked appointments alone (the console's rule).
- Type escapes: none in product code. The `# noqa: S101` in the test support file names its code.
- Sizes: the largest new file is 277 lines (a test); every function is under 50 lines.
- Dependencies: none added.
- Tests: view tests cover each role's token and no token, a stale `If-Match`, refusals named by element, and the hostile-input case. Domain tests were mutation-proven. Two survivors are explained in `mutation-equivalents.txt`, and both explanations hold.

## Findings
1. **Low**, `fhir_role_writes.py:78-79`. `_admin_update` reads `profile.version` outside the lock and hands it to `RecordEdit`. `update_profile` compares it with the row under the lock, so a concurrent edit yields a conflict, not a lost update. A conflict that is not 412 is possible but harmless. Fix: leave it.
2. **Low**, `fhir_loading.py` (`practitioner_roles_with_all_services`). Every staff token, including another clinician's, sees `notAvailable` reasons, which are free text. 15.4 says "staff see all", so this follows the spec. Fix, if the owner wants it narrower: owner and admin only.
3. **Low**, `fhir_role_writes.py:112`. A clinician who sends `PUT` with an unknown profile id gets 404, while another clinician's profile gets 403. Roles are public, so nothing leaks.
4. **Info**, `fhir_role_write.py` `role_values`. `title` is not writable on create, as the plan says. The profile's model default applies until the Practitioner PUT.

## Blocking
None.

## Left for the orchestrator (plan, `## Not in this run`)
- Task 24c2: `Practitioner` PUT and DELETE, and its version tests (the profile title moves the user's version; the old `If-Match` is 412). Also its samples, hostile-input cases and CapabilityStatement entry. The ADR already fixes the decisions: no `POST /fhir/Practitioner`, with the reason given.
- Full `make mutate` and `make fhir-validate` pass, after both runs.
- Slice not finished: none beyond that list.

## Later
- Findings 1 to 3.
- Timing: `make test` took about 31 to 39 s in the sandbox (4324 tests). The orchestrator measures it on a quiet machine.
- I did not run `make mutate` or `make fhir-validate` myself. I relied on the stage outputs for lint, tests and gate.
