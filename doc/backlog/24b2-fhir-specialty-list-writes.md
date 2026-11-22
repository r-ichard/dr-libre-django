Task 24b2: FHIR API, the specialty list through CodeSystem and ValueSet.

What the run of task 24b (`doc/backlog/24b-fhir-admin-writes-organisation.md`, ADR 0008)
left under "Not in this run": `drlibre-specs.md` section 15.4, "Create, update, delete:
Admin", for `CodeSystem` and `ValueSet`. The specialty list is one `CodeSystem` and one
`ValueSet` with the single id `specialty` (ADR 0003, 0005); its version is the revision
row of ADR 0003. Writes go through the use cases of the admin console for specialties
(task 18). This task adds no rule. The design the last plan sketched is a starting
point, not a decision: judge it.

1. With an admin's token a client adds, renames, deactivates and removes one specialty.
   Say in ADR 0008 how: which resource a client writes, what the body carries (the
   whole list or one concept), how a concept is matched to a specialty, how "inactive"
   is said in FHIR R4, and what the other resource answers to a write.
2. Removing a specialty a clinician has answers 409 with `has_dependents` and the
   console's counts; nothing of the request is applied.
3. One request is one transaction: a body that adds one specialty and renames another
   does both or neither, with one audit entry per changed specialty, as the console
   would have written them.
4. `versionId` and `If-Match`: a write that changes something moves the version, a
   write that changes nothing does not; a stale `If-Match` is 412. Two admins who write
   at the same moment: one applies, the other answers 412 or 409, and the list holds
   what one of them sent, not a mix.
5. Any other token is 403 and no token 401, tested as a FHIR client sends it. What the
   public search offers follows at once: a new specialty with its fallback icon, a
   renamed one, a deactivated one gone.
6. Samples in `make fhir-validate` for each write body and each answer; the hostile-input
   test; the CapabilityStatement names the interactions and nothing else answers.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
