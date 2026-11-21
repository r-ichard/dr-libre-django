Task 06: scheduling engine, pure.

The rules of `drlibre-specs.md` section 5 as pure domain functions: no I/O, no clock, no
ORM (§8). Inputs and outputs are plain values; `now` and the hospital time zone are
arguments. The use cases that load rows, lock and write are task 07. This is the code
where a mistake books a patient into a slot that does not exist, so it is also where
mutation testing starts.

1. Free slots (5.1), for one clinician, one appointment type and a time range, exactly
   the four steps of the specification. Details that are easy to get wrong:
   - Weekdays are 0 Sunday to 6 Saturday in the specification and in the stored rule.
   - A rule is valid on a local day between its valid-from and valid-to dates.
   - A slot is offered while its start plus the type's duration is not after the rule's
     end; each slot lasts the duration.
   - Each existing active appointment is extended at its end by the buffer of the type
     being booked, not by its own type's buffer.
   - Intervals are half-open: a slot may start when time off or an appointment ends.
   - Weekly availability is local wall-clock time of the hospital and stays correct
     across daylight saving changes (section 4). State in the plan what happens to a
     slot whose local start does not exist or exists twice, and test both changes in a
     northern and a southern time zone.
2. With no clinician named: the union of the free slots of the given clinicians, one
   entry per start, each entry knowing which clinicians are free then (round robin needs
   it). A query covers at most 31 days.
3. Booking rules (5.3) as one function returning every violated rule by its name from
   the table, for who is acting and for booking, rescheduling or cancelling. The three
   numbers are named policy constants in one place.
4. Appointment status (5.6): the transition table, who may make each change, and which
   statuses can be rescheduled. An `active` appointment is defined once.
5. First available (5.5): the ranking of candidates, never assigned first, then the
   largest time since last assignment times weight, ties to the lowest id.
6. Bind `make mutate` to a mutation testing tool, scoped to `scheduling/domain/` (a new
   development dependency: pin it, §11, and say in the plan why this tool). Reach the 80
   percent target of the proof stage on the modules of this task and record the score
   in your reply. It must run in the foreground within a stage: say how long it takes.
7. Property-based tests are welcome for the slot rules (a slot never overlaps time off or
   an active appointment, never starts in the past, the list is sorted and unique); a
   pinned development dependency for them is allowed.

Read the rules the model plan left to use cases
(`doc/plans/2026-11-21-domain-model.md`, "Waits for its use case"): the pure ones among
them belong here.

Done when `make setup && make lint && make test && make gate` pass from a fresh clone
and `make mutate` runs and reports.
