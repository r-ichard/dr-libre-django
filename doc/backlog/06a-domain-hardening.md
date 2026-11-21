Task 06a: domain hardening.

Findings of the orchestrator and of the review of task 06
(`doc/reviews/2026-11-21-scheduling-engine.md`), to close before the booking use cases
build on the engine. No behaviour a user could see changes, except item 5.

1. The domain layer imports the model layer. `free_slots.py`, `booking_rules.py`,
   `appointment_status.py`, `session_rules.py` and `sign_in_rules.py` import their
   enumerations from `scheduling.models`, so the pure layer cannot be imported without
   Django's models (§8). The domain owns its enumerations and the models use them. Say in
   the plan what that does to the migrations and prove no schema change results.
2. Guard it: a test that fails when any module under `scheduling/domain/` imports Django,
   `scheduling.models`, `scheduling.use_cases` or `scheduling.views`. Show it failing on
   today's code first.
3. The engine identifies clinicians by `int` (`slot_search.py`, `first_available.py`).
   Identifiers are UUIDv7 (ADR 0002). Use the real identifier type; ties break on its
   order, as section 5.5 says.
4. Ranking ties in `first_available` depend on floating point. Use exact arithmetic.
5. Clock-change days: a slot is offered when its start plus the duration, counted on the
   wall clock, fits the rule, but the appointment's real end can then pass the rule's
   wall-clock end (spring forward) or fall short of it. Decide the rule from section 5.1
   ("each slot lasts the type's duration", "weekly availability stays correct across
   daylight saving changes"), state it in the plan and test it in both hemispheres.
6. Property-based tests for the slot rules, with a pinned development dependency: for
   generated rules, time off and appointments, every offered slot lies inside a valid
   rule window and inside the query range, never starts before now, never overlaps time
   off or an active appointment extended by the buffer, and the list is sorted and
   unique.
7. Mutation survivors. `make mutate` reports 38 in `scheduling/domain`, 21 of them in
   `audit_metadata.py`, the code that keeps personal data out of the audit log. Kill each
   with a test, or list it as equivalent with its reason in a file `make mutate` reads.
   `make mutate` then exits non-zero when an unlisted survivor remains, so the proof stage
   can rely on it.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
