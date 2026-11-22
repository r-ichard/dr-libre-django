# ADR 0009: FHIR `PractitionerRole` writes and time off

Status: accepted, 2026-11-22. Builds on ADR 0006 (write rules) and ADR 0008. Task 24c built
the `PractitionerRole` half; task 24c3 the `Practitioner` half below.

## Decisions

- **Who writes what.** An admin creates, updates and deletes a `PractitionerRole` through
  `attach_profile`, `update_profile` and `delete_profile` of `admin_clinicians`: department,
  specialty, default room, bio and round robin weight, with the console's refusals (a room of
  another department, an inactive specialty, a move with upcoming appointments, rules or a kept
  room, a delete with dependents). A clinician's token may `PUT` the own role and change only
  `notAvailable`. No token is 401, a patient token 403. A clinician `POST` or `DELETE`, or a `PUT`
  of another clinician's role, is 403: roles are public, so 403 leaks nothing. The refusal comes
  before the body is read.
- **`notAvailable` is the clinician's.** An entry without `id` records time off
  (`create_time_off`); a stored period the body leaves out is removed (`delete_time_off`); an entry
  with a stored `id` whose during or description differs is 400 naming `notAvailable[i]`: time off is
  recorded and removed, not edited. An unknown `id` is 400 the same way. No use case records time
  off for someone else, and 15.4 gives it to the clinician, so an **admin** whose body differs in
  `notAvailable` is 400 naming `PractitionerRole.notAvailable`; one that repeats it as stored
  (compared by content, order aside) is fine, so read-then-write works.
- **Read.** Staff see `notAvailable` (one entry per `TimeOff`: `id`, `during`, `description` = the
  reason, "Time off" when empty); the public never does. Time off reasons stay out of audit entries
  (ids only), as in the screens.
- **R4 names checked.** Against the R4 `PractitionerRole` definition: `active`, `practitioner`,
  `organization`, `specialty`, `location`, `healthcareService`, `availableTime`
  (`daysOfWeek`, `availableStartTime`, `availableEndTime`) and `notAvailable` (`description`,
  `during`, a Period) are R4 elements. `period` is not a `notAvailable` element; it is refused as
  unknown. `id` on a `notAvailable` entry is the standard element `id`; `role-bio` and
  `role-round-robin-weight` are extensions.
- **Mapping on a write.** `practitioner` (required on create, equal to the stored one on update),
  `organization` (department), `specialty` (code of the managed list), `location` (default room),
  extensions `role-bio` and `role-round-robin-weight`. `active`, `healthcareService`, `availableTime`
  and `notAvailable` are server-built: a body may repeat them, never change them, else 400 naming
  the element. `availableTime` mirrors the `Schedule` resources: change those.
- **Atomic.** A clinician `PUT` locks the profile, compares `If-Match`, applies removals then
  additions in one transaction; the first refusal rolls all of it back, so no time off and no audit
  entry of an earlier step stays. `delete_profile` gained an optional `expected_version`, checked
  under the lock like `update_profile`'s.
- **Versions (ADR 0003).** A `PractitionerRole` is built from the profile, its rules and its time
  off: a child row moves the profile's version (database triggers), so an old `If-Match` is 412. A
  profile with a rule is therefore never at version 1 after the rule is added.
- **`Practitioner` (next run).** `POST /fhir/Practitioner` is not offered: the console's create needs
  a temporary password, which is not a FHIR element, and a user without a profile is not a readable
  `Practitioner`. A user is created in the console, which hands out the temporary password; its id is
  then the `practitioner` of a role `POST`. `PUT` (name, email, `active`; title through the profile)
  and `DELETE` (409 while the profile exists) go through `update_user`, `deactivate_user`,
  `update_profile` and `delete_user`. A phone that differs is 400: the console cannot edit it. The
  password appears in no FHIR element, answer, log or audit entry.
- **API tokens of a deactivated user (task 24c3).** Deactivating ends the user's sessions and
  revokes no `ApiClient` row; the token stays stored but is answered 401 while the user is inactive
  and works again when the user is reactivated. Silent revocation would make reactivation lose
  integrations the owner never asked to lose; revoking is its own explicit action.
- **Collection `Allow`.** A refused `POST /fhir/Practitioner` is 405 and its `Allow` also names
  `PUT` and `DELETE`, so a client learns that Practitioners are written one by one.
