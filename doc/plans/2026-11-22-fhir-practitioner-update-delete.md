# Plan: task 24c3, FHIR `Practitioner` update and delete

Slice: items 1 to 6, whole task. It adds no rule: two routes onto the console's user use cases
(task 19) and the profile's `update_profile`. ADR 0009 already fixed the decisions.

## Focal point

One new use-case module, `scheduling/use_cases/fhir_practitioner_writes.py`: `update_practitioner`
and `delete_practitioner` turn a checked body into `update_user`, `update_profile` and
`deactivate_user` (or `delete_user`) inside one transaction and rebuild the answer with the existing
`loading.practitioners_with_contact`.

## Facts found in the code (they shape the plan)

- A `Practitioner` is a user **with a clinician profile** (reads list by profile). A user without
  one is 404 on `PUT` and `DELETE`: it is not a readable resource, so 404 leaks nothing.
- Title is the profile's, and `scheduling_touch_user_on_change` (migration 0004) already moves the
  user's version when the title changes, and the `Practitioner` `versionId` is the user's. Item 5 needs
  no code, only a test through FHIR.
- `resolve_token` (`api_tokens.py:61`) already answers 401 for a token whose user is inactive. Nothing
  is revoked, the token stays stored and works again on reactivation. ADR 0009 says so; test it.
- An admin has no profile (role change refuses a clinician with one), so through FHIR an admin's own
  user, or the last admin, is not reachable as a `Practitioner`: `PUT`/`DELETE` of it is 404. The own-
  account and last-admin rules still sit in the use cases we call; tests reach them by giving the
  admin a profile row directly through the ORM.
- A `DELETE` can only succeed for a user without a profile, which is 404. So in practice `DELETE`
  is 409 `has_dependents` (profile counted) for every real `Practitioner`; the task asks for exactly
  that. ADR 0009 states the consequence: a user is removed by deleting the role first (`DELETE
  PractitionerRole`), then in the console, since the user is no longer a resource.
- `POST /fhir/Practitioner`: 405 with `Allow` follows from `interactions` having no `create`
  (`_methods_of` in `views.py`). Only a test and the ADR reason (exists already, extend) are needed.

## Blocks, one sentence each

1. `scheduling/domain/fhir_practitioner_write.py` (pure, new): `PRACTITIONER_SHAPE` (resourceType,
   id, meta, active, name[text], telecom[system,value], qualification[code.text]); `practitioner_values(body)`
   returns user fields (`full_name`, `email`), `title`, `is_active`, or the element named wrong;
   `practitioner_difference(body, stored)` names the first element that differs where the console
   cannot change it (telecom phone, an extra or missing phone, name beyond `text`), so a read-then-write
   works.
2. `scheduling/use_cases/fhir_practitioner_writes.py` (new, focal): `practitioner_write_refusal(caller)`
   (none 401, non-admin 403, before the body); `update_practitioner(id, body, caller, expected_version)`;
   `delete_practitioner(id, caller, expected_version)`.
   `update_practitioner`: in `transaction.atomic`, lock the user row, 404 unless a profile exists,
   `If-Match` against `user.version` (412), then apply `update_user` (name, email; email change ends sessions and
   links and unverifies, by the use case), `update_profile` (title), then `deactivate_user` when
   `active` goes false; `update_user` carries `is_active=True` to reactivate. The first failure calls
   `set_rollback`, so no earlier step or audit entry stays. Each step's `version` argument is read
   under the lock just before the call (the use cases compare it to the row; `If-Match` is the client's
   check). Failures are renamed to elements (`full_name`→`Practitioner.name`, `email`/`phone`→`Practitioner.telecom`,
   `title`→`Practitioner.qualification`, `is_active`/rule text→`Practitioner.active`) with the existing `named` helper pattern.
   `delete_practitioner`: 404 without profile, `If-Match` check, `delete_user`; its `has_dependents` carries the console's counts.
3. `scheduling/use_cases/fhir_resources.py`: route `Practitioner` in `update` and `delete`;
   `refusal_before_body` gets the `Practitioner` branch.
4. `scheduling/domain/fhir_write_shapes.py`: add `"Practitioner": PRACTITIONER_SHAPE`.
5. `scheduling/domain/fhir_declaration.py:105`: `interactions=(*READ_ONLY, "update", "delete")` for
   `Practitioner`. Allow header, 405 on `POST` and the CapabilityStatement follow.
6. `scheduling/views/fhir/samples_staff.py` or new `samples_practitioner.py` (if over 300 lines),
   registered in `samples.py`: update body, name/email change, deactivate, the delete answer (409
   `has_dependents` outcome), a phone-differs refusal. Run through `make fhir-validate`.
7. `scheduling/views/test_hostile_input.py`: Practitioner `PUT`, `DELETE`, `POST` paths with hostile
   bodies (telecom not a list, huge strings, NUL, `active` as a string, qualification wrong types).
8. `doc/adr/0009-...md`: replace "next run" by what is built: API tokens of a deactivated user (401
   while inactive, stored, work again on reactivation, nothing revoked), why no `POST`, why `DELETE`
   is 409 for every Practitioner, own-account and last-admin reachable only through seeded state.

Not touched: `admin_users.py`, `admin_clinicians.py`, models, migrations, console pages,
`fhir_loading.py`, `fhir_reads.py`, `views.py`, `writes.py` (the method already reaches the refusal),
`doc/backlog.md` (orchestrator).

## Invariants and blast radius

- Authorization from the token's user: admin only for writes; clinician and patient 403, no token 401,
  all before the body is read. Use cases re-check admin under lock.
- One transaction per request; audit entries are the console's (`user.update|deactivate|activate`),
  inside it; names of fields only, no email, phone or password value in audit, logs or answers.
- Audit stays append-only. Double booking unaffected. Appointments untouched by deactivating.
- Blast radius: `Practitioner` leaves read-only; CapabilityStatement and `Allow` for it change;
  existing tests that expect 405 on `PUT /fhir/Practitioner/<id>` must change.
- Trust boundary: JSON body, checked by `exact_elements` against the shape, then pure
  `practitioner_values`/`practitioner_difference`, then the use cases' checks. Size capped by
  `request_limits`.

## Failing tests first (`returns_X_when_Y`), view tests with `fhir_client(token)` (bearer, no cookie, no `Origin`)

New `scheduling/views/test_fhir_practitioner_writes.py` (a second file for race/edge if over 300 lines):
- `returns_200_with_new_etag_when_admin_puts_a_changed_name`; user row has the name, audit
  `user.update` names `full_name` only.
- `returns_200_and_keeps_version_when_put_changes_nothing` (GET then PUT).
- `returns_200_and_unverified_email_and_ended_sessions_and_links_when_email_changes`: the user's
  `email_verified_at` is None, their sessions and sign-in links are gone.
- `returns_200_and_ends_sessions_when_admin_puts_active_false`: sessions gone, tokens not revoked
  (`revoked_at` None), `Practitioner.active` false.
- `returns_401_for_the_deactivated_users_own_token_and_works_again_when_reactivated`.
- `returns_200_and_changed_title_when_put_changes_qualification`; `versionId` moved and old
  `If-Match` answers 412 (item 5); the same for a user-version change.
- `returns_412_when_if_match_is_stale`; `returns_200_when_if_match_is_current`.
- `returns_400_naming_telecom_when_the_phone_differs` and `..._when_a_phone_is_added`;
  `returns_400_naming_name_when_name_is_empty`; `returns_400_naming_telecom_when_email_is_taken`;
  `returns_400_naming_the_element_when_a_server_built_element_differs` (meta aside).
- `returns_400_naming_active_when_an_admin_with_a_profile_deactivates_its_own_user`; same for the
  last active admin (seeded profile on the admin; no other admin).
- `returns_404_when_put_or_delete_names_a_user_without_a_profile` and an unknown id.
- `returns_409_has_dependents_with_profile_count_when_deleting_a_practitioner`;
  with appointments and audit entries the counts are the console's (same words as `user_dependents`);
  nothing is deleted, no audit entry.
- `returns_405_with_allow_get_head_when_posting_a_practitioner` (Allow lists only what answers).
- Role matrix, every write method with admin, own clinician, other clinician, patient, no token:
  `returns_200_for_admin`, `returns_403_for_clinician_and_patient`, `returns_401_without_token`
  (`PUT` and `DELETE`; refusal before body: a garbage body still gets 403/401).
- CapabilityStatement: `Practitioner` lists `read`, `search-type`, `update`, `delete`, not `create`;
  `scheduling/domain/test_fhir_declaration`/capability test updated if it pins the interactions.
- Samples test (`views/fhir/test_samples.py`) covers the new sample names; `make fhir-validate` runs them.
- Pure unit tests `scheduling/domain/test_fhir_practitioner_write.py`: values from a body; difference
  names the phone; round trip of the stored form is no difference. These are the `make mutate` targets.

## Domain entities (§3)

User, ClinicianProfile, ApiClient, Session, SignInLink, AuditLogEntry, Appointment (dependent count).

## Will not do

No password element, no `POST`, no role/phone/clinician-creation path, no new rule, no change to the
console use cases, no new abstraction (the `named` and `admin_of` helpers of `fhir_record_writes` are reused).

## Not in this run

Nothing from the task. Task 24d (closing section 15) is separate.

## Architect review

Verdict: approve.

- Ladder: two routes onto existing use cases, one new use-case module, one pure domain module. No new dependency, no rule change, no console change. Right layers (§8).
- Scope: items 1 to 6 all covered (PUT, DELETE, own-account and last-admin rules, ADR on API tokens, 405 on POST, version test, role matrix, samples, hostile input, CapabilityStatement). Nothing dropped.
- Tests first: named as behaviours, edge and error paths included, role matrix with no token, FHIR client sent as bearer without cookie or `Origin`.
- Security: admin check before body, authorization from the token, no values in audit or logs, one transaction with rollback on first failure.
- Watch in green:
  - The `update_user` and `deactivate_user` calls read the version under the lock; keep `If-Match` as the client's check only.
  - Reactivation (`active` true on an inactive user) must be tested through `update_user`, with the audit entry the console writes.
  - Keep the domain functions under the 100-line function cap, 500-line file cap and 300-line convention. Check the `make mutate` equivalents file for new survivors.
  - A body that changes the email and deactivates in one PUT: test the combined rollback (second step fails, first leaves nothing).
