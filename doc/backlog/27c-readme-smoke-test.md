Task 27c: a README a person can start from, and a smoke test of the running stack.

The last task of milestone M9 (GitHub issue #9). The hand-over document
(`doc/handover.md`) is the orchestrator's and is not part of this task. Two runs, one per
item.

1. README. A person who has Docker and nothing else reads `README.md` from the top and
   gets, in this order: what DrLibre is (two sentences from `drlibre-specs.md` section 1);
   how to start it (`docker compose up --wait`, `seed_demo`, the two addresses: product on
   8000, mail inbox on 8025); the demo accounts and where the password is; a first walk
   from an empty hospital to a booking, as `doc/handover.md` "Run it" describes it; how to
   stop and forget (`docker compose down -v`); the commands for checks (`make test`,
   `make lint`, `make gate`, `make mutate`, `make fhir-validate`, `make audit`); what
   `DEBUG` off refuses at start-up. The FHIR section stays. Every command in the README
   is one the run has executed in its sandbox, or one it marks as needing Docker.
   No new file beside the README.

2. Smoke test. `make smoke` runs against a stack already started with
   `docker compose up --wait` and seeded, and fails with a message that names the step
   when one step fails: the health check answers; the start page answers and finds a
   demo provider; a visitor holds a free slot through `/api/v1`, reads the code from the
   mail inbox's API (smtp4dev, port 8025), confirms it, and the appointment is listed for
   the new patient; the patient cancels it. It uses only the standard library of Python
   and talks to 127.0.0.1 only. It is not part of `make test`. The README says when to
   run it.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone, and, for item 2, when the orchestrator
has run `make smoke` against a fresh stack.
