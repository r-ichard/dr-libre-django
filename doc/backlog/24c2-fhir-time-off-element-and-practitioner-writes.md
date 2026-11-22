Task 24c2: FHIR API, time off under its R4 name, and Practitioner writes.

This branch holds what the run of task 24c
(`doc/backlog/24c-fhir-practitioner-writes-and-time-off.md`, ADR 0009) finished: the
writes of `PractitionerRole` and time off through `notAvailable`. Its review is in
`doc/reviews/`. It is not merged, because two gates fail on it, and neither its run nor
its reviewer ran them. They are now the last stage of every run
(`scripts/final_gates.sh`). Reproduce each finding with a failing test before the fix.

1. `make fhir-validate` fails: 3 of 112 samples. `PractitionerRole.notAvailable` is
   served and accepted with an element `period`. FHIR R4 names it `during`
   (`PractitionerRole.notAvailable.during`, a Period). The orchestrator's standard
   request, `{"description": "Dentist", "during": {"start": "...", "end": "..."}}`, was
   refused with 400 naming `PractitionerRole.notAvailable.during`. Serve and accept
   `during`; `period` is refused like any unknown element. Check every other element
   name task 24c introduced against the R4 definition of `PractitionerRole`, and say in
   ADR 0009 which were checked.
2. `make mutate` fails: `unlisted survivor:
   scheduling.domain.fhir_record_write.x__coding_code__mutmut_9` and `..._mutmut_11`.
   Kill both with tests; a line in `mutation-equivalents.txt` only for a mutant that
   cannot change behaviour, with the reason.
3. With the element right, prove time off end to end through FHIR with the clinician's
   own token, in one test: add a period, read it back with its `id`, see the slots of
   that period gone from `GET /api/v1/slots` and present as `busy-unavailable` in
   `/fhir/Slot`, remove the period, see the slots return. And the refusals: a period
   changed in place, an identical period twice, an end before its start, another
   clinician's role, an admin's attempt (ADR 0009 says which answer).
4. What task 24c left under "Not in this run", with the decisions ADR 0009 already
   fixed: `Practitioner` update and delete with an admin's token through the use cases
   of the admin console for users (task 19); no `POST /fhir/Practitioner`, with the
   reason in the ADR. The user's own rules hold through FHIR: an admin cannot
   deactivate or delete their own account, the last active admin stays, a user with
   appointments or audit entries is not deleted. Versions as ADR 0003: a change of the
   profile's title moves the Practitioner's `versionId`, and the old `If-Match` is 412.
5. Every write is tested with each role's token and with none, as a FHIR client sends
   it; has its samples in `make fhir-validate`; joins the hostile-input test; and is
   named in the CapabilityStatement, which names nothing that does not answer.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
