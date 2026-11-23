Task 26c: the gates hold what they claim.

Third part of the hardening (`doc/backlog/26-security-hardening.md` holds the whole list):
the gates themselves. Each item is a claim the project makes about its own checks that
was found untrue or unchecked. No product behaviour changes.

11. `make test` has no time gate and one test, the hostile-input test, grew to a minute
    once. A single test that takes longer than a stated number of seconds fails the
    suite, with the number in one place; say it in the plan after measuring the ten
    slowest tests. Bring those under it without dropping a case.
    Measured by the orchestrator after task 26a2 (`pytest --durations=25`, eight
    workers, fresh clone, two other runs on the machine): 4591 tests take 95 seconds;
    alone the suite takes 38 to 45. Under that load the slowest
    entries are not tests but teardowns: 28, 24, 22, 10, 7 and 6 seconds, charged to
    tests that do nothing slow (`scheduling/domain/test_audit_metadata.py`,
    `drlibre/test_parallel_run.py`, `scripts/test_size_cap.py`). Something waits at the
    end of a worker's session, most likely for the live server of
    `test_api_live_server.py` or for database connections a race test left open. Find
    what waits and remove the wait; the gate counts setup and teardown as well as the
    call. Then the hostile-input test: 14 and 11 seconds for its two slowest cases.
11a. `make mutate` passes a mutant no test reaches: of 6221 mutants in
    `scheduling/domain`, 1165 are "no tests", most of them in the FHIR write modules,
    which only tests of the views layer exercise. The card says pure domain logic is
    held by the mutation gate; for a fifth of it that is not true. The gate fails on a
    mutant without a test unless `mutation-equivalents.txt` explains it, and the domain
    modules get tests of their own until it passes. Start with the modules that decide
    access or what a write may change.
12. `scheduling/use_cases/test_api_tokens.py::returns_audit_entries_with_ids_only_when_token_issued_and_revoked`
    failed once in four full runs. Find the cause and fix it; a rerun is not a fix.
13. `make audit`: checks the pinned dependencies against known vulnerabilities with a
    pinned tool, and fails on one. Run by the orchestrator at hand-over, not by `make test`.
14. Module docstrings that name a task ("Task 10a: ...") say what the module is for
    instead. The test-only probe views leave the product package.
15. The report has no test with hospital zones on both sides of UTC (review of 21): add
    it for the day an appointment is counted on.

Carried from tasks 27a and 27a2, tests that claim more than they check:

16. The hostile-input test sends its values to a fixed list of field names, and two
    500s of QA round 3 (#33, #38) passed it. It derives its targets: every field of
    every form the product renders, by its `name` (the walker of
    `form_walk_support.py`); every field of every request schema of `/api/v1`; every
    element a write of the FHIR declaration accepts. Each gets the hostile values (a
    NUL byte, an over-long text, a number beyond 64 bits, a negative number, a wrong
    type, markup) and none answers 500. The plan of 27a2 counted about 7000 requests,
    under a minute: keep it inside the time gate of item 11.
17. One test shows that every form of the product, refused, comes back with what was
    typed, apart from a password and a code.
18. One test compares, for every free-text and every one-line field, what the page,
    `/api/v1` and the FHIR element accept: the three agree, or the difference is
    listed with its reason.

19. `scripts/mutation_survivors.py` prints "stale entry in mutation-equivalents.txt" and
    exits 0. An entry is stale when a test now kills the mutant it called equivalent:
    the claim was wrong, and the line stays. The gate fails on a stale entry. One is
    there now: `scheduling.domain.waitlist_window.x_window_words__mutmut_11`.
20. From task 27b: no two links of an error summary read the same, asserted over every
    form the product renders, submitted empty.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` and `make audit` pass from a fresh clone.
