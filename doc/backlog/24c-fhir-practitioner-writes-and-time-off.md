Task 24c: FHIR API, Practitioner and PractitionerRole writes, and time off.

`drlibre-specs.md` sections 15.2 and 15.4 for the writes of `Practitioner` and
`PractitionerRole`, on the write rules of ADR 0006 and through the use cases of the admin
console (task 19: users and clinician profiles) and of the clinician workspace (task 17:
time off). A FHIR write does exactly what the screens do. This task adds no rule.

1. `Practitioner` (the clinician user): create, update and delete with an admin's
   token, through `admin_users`. The temporary password of a new user is not a FHIR
   element: say in the ADR how a user created through FHIR gets one, or that they
   cannot be created this way, and keep it out of every answer, log and audit entry.
2. `PractitionerRole` (the clinician profile): create, update and delete with an
   admin's token, through `admin_clinicians`: department, specialty, default room, bio,
   round robin weight, with the console's refusals (a room of another department, a
   move with upcoming appointments).
3. A clinician's token may update the own `PractitionerRole.notAvailable` and nothing
   else (15.4). Adding a period records time off and removing one deletes it, through
   the time off use cases; a period changed in place is refused: time off is recorded
   and removed, not edited. Any other element that differs is refused and named.
   Another clinician's role and an admin's attempt at `notAvailable` follow 15.4: say
   which in the ADR.
4. `PractitionerRole.availableTime` stays read-only: it mirrors the `Schedule`
   resources, and a body that changes it is refused and named.
5. Versions (ADR 0003): a `PractitionerRole` is built from the profile, its rules and
   its time off, a `Practitioner` from the user and the profile. Test that a change of
   a child row moves the parent's `versionId`, and that `If-Match` with the old one is
   then 412.
6. Every write is tested with each role's token and with none, as a FHIR client sends
   it; has its samples in `make fhir-validate`; joins the hostile-input test; and is
   named in the CapabilityStatement.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
