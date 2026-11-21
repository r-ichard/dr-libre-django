Task 03a: fast test suite.

The suite takes 100 seconds for 414 tests in the sandbox and 175 seconds in the web
container, and every pipeline run executes it six times or more. Make it fast without
weakening it. No product behaviour changes.

1. Measure first: run `pytest --durations=25` and put the table in the plan. Fix causes,
   not symptoms, and report the time before and after in your reply.
2. Causes to check: password hashing at production cost inside tests (use a fast hasher
   in tests only, and keep one test proving the product settings still use Django's
   default slow hasher); the demo seed arranged again for every test where one
   arrangement per module would do; anything else the durations table shows.
3. Run the tests in parallel across processors with pytest-xdist (a new development
   dependency: pin it, §11), each worker on its own database. `make test` uses it by
   default. Two suite runs in the same sandbox must no longer be able to collide on the
   `test_drlibre` database: say in the plan how that holds.
4. Keep every guard working under parallel runs: the collection guard still aborts on an
   uncollected test function, the pending-migration test and the data-model-document
   test still run, and a failing test still fails `make test`.
5. Target: under 30 seconds in the sandbox for the current suite.

Done when `make setup && make lint && make test && make gate` pass from a fresh clone.
