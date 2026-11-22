Task 26c: the gates hold what they claim.

Third part of the hardening (`doc/backlog/26-security-hardening.md` holds the whole list):
the gates themselves. Each item is a claim the project makes about its own checks that
was found untrue or unchecked. No product behaviour changes.

11. `make test` has no time gate and one test, the hostile-input test, grew to a minute
    once. A single test that takes longer than a stated number of seconds fails the
    suite, with the number in one place; say it in the plan after measuring the ten
    slowest tests. Bring those under it without dropping a case.
11a. `make mutate` passes a mutant no test reaches: of 6221 mutants in
    `scheduling/domain`, 1165 are "no tests", most of them in the FHIR write modules,
    which only tests of the views layer exercise. The card says pure domain logic is
    held by the mutation gate; for a fifth of it that is not true. The gate fails on a
    mutant without a test unless `mutation-equivalents.txt` explains it, and the domain
    modules get tests of their own until it passes. Start with the modules that decide
    access or what a write may change.
12. `test_api_tokens.py::returns_audit_entries_with_ids_only_when_token_issued_and_revoked`
    failed once in four full runs. Find the cause and fix it; a rerun is not a fix.
13. `make audit`: checks the pinned dependencies against known vulnerabilities with a
    pinned tool, and fails on one. Run by the orchestrator at hand-over, not by `make test`.
14. Module docstrings that name a task ("Task 10a: ...") say what the module is for
    instead. The test-only probe views leave the product package.
15. The report has no test with hospital zones on both sides of UTC (review of 21): add
    it for the day an appointment is counted on.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` and `make audit` pass from a fresh clone.
