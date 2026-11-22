Task 24c3: FHIR API, Practitioner update and delete.

The last write of `drlibre-specs.md` section 15.4, left twice under "Not in this run"
(tasks 24c and 24c2). ADR 0009 already fixed the decisions: build them, and nothing
else. A FHIR write does exactly what the admin console does for a user (task 19).

1. `PUT /fhir/Practitioner/<id>` with an admin's token, through `update_user`,
   `deactivate_user` and `update_profile`: name, title, email, active. An element the
   console cannot change through this resource, a phone that differs, is 400 and named.
2. `DELETE /fhir/Practitioner/<id>` with an admin's token, through `delete_user`: 409
   with `has_dependents` and the console's counts while the user has a profile,
   appointments or audit entries.
3. The user's own rules hold through FHIR as on the screens: an admin's token cannot
   deactivate, demote or delete its own user; the last active admin stays; a changed
   email is unverified again and ends sessions and sign-in links; deactivating ends the
   user's sessions and revokes nothing else silently. Say in ADR 0009 what happens to
   the API tokens of a deactivated user, and test it.
4. No `POST /fhir/Practitioner`: 405 with `Allow`, the reason in ADR 0009.
5. Versions (ADR 0003): a change of the profile's title moves the Practitioner's
   `versionId`, and the old `If-Match` is then 412. Test it.
6. Every write is tested with each role's token and with none, as a FHIR client sends
   it; has its samples in `make fhir-validate`; joins the hostile-input test; and the
   CapabilityStatement names `update` and `delete` for `Practitioner` and nothing that
   does not answer.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
