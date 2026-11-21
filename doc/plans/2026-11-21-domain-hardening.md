# Plan: task 06a, domain hardening

Focal point: `scheduling/domain/` becomes importable with no Django, and its slot and ranking
rules get exact, proven behaviour. One unit of behaviour change: clock-change slot ends (item 5).

## Decisions

**1. Domain owns the enumerations.** New `scheduling/domain/vocabulary.py` holds plain
`StrEnum`s `AppointmentStatus`, `AppointmentSource`, `Role`, `SessionKind` (same members, same
string values). `CodePurpose`, `HoldSource` and the other model-only enums stay in models.
Models stop defining those four and import them from the domain; the 23 importers
(use cases, views, seed, tests) change their import line only.
Migration effect: none intended. A `TextChoices` field records
`choices=[(value, label)]`, label = `name.replace("_", " ").title()` ("Round Robin", "No Show").
A model helper `choices_of(enum)` in `models/base.py` returns exactly those pairs, and
`one_of` takes `type[StrEnum]` and reads `[m.value for m in enum]`. Proof: the existing
`test_migrations.returns_no_pending_changes_when_models_match_migrations` stays green
(it runs `makemigrations --check`), plus `git diff --stat scheduling/migrations` empty.
No `.choices`/`.label` use elsewhere except `data_model_document.py:95`, which reads
`field.choices` and so sees the same pairs; its test must stay green unchanged.

**2. Guard.** `scheduling/domain/test_domain_imports.py`: parse every non-test `*.py` in the
domain with `ast`, fail on any `import`/`from` whose module is `django` or starts with
`django.`, `scheduling.models`, `scheduling.use_cases`, `scheduling.views`. Written first and
run against today's code: must fail naming the five modules. Goes green after block 1.

**3. Identifier type.** `ClinicianSchedule` mapping key, `SlotOffer.clinician_ids` and
`Candidate.clinician_id` become `uuid.UUID`; `rank_candidates`/`first_available` return UUIDs.
Ties: lowest `UUID` (ordering by 128-bit value, UUIDv7 = creation order). Tests swap ints for
fixed UUIDs built from ints (`UUID(int=n)`), so the order is explicit.

**4. Exact ranking.** `_rank_key` returns `tuple[int, int, UUID]`; idle score is
`-(idle // timedelta(microseconds=1)) * weight` (integer microseconds). Test: two candidates
whose float products would collide or round differently (idle with microseconds and large
weights) rank by the exact product, equal exact products tie to lowest id.

**5. Clock-change rule (decision, from 5.1).** "Each slot lasts the type's duration" means real
elapsed time. "Availability stays correct across daylight saving" means the rule's wall-clock
window is the boundary. Therefore: a start (wall clock, stepped by slot step from rule start,
nonexistent local times skipped, repeated times use first occurrence as today) is offered only
if `start_utc + duration`, converted back to the hospital's local wall clock, is not after the
rule's wall-clock end. `_rule_starts` loops on `local_start < local_end` and checks the real
end; no naive `local_start + duration` test. Effects:
- spring forward, rule 01:00-02:30, 60 min: slot 01:00 ends 03:00 real, dropped (was offered).
- fall back, rule 00:00-02:00 (repeated 01:00-02:00), 90 min: slot 01:30 first occurrence ends
  02:00 real wall, offered (was dropped by naive 03:00); a slot that ends sooner than its naive
  end stays offered.
Tests, both hemispheres: `America/New_York` (spring 2026-03-08, fall 2026-11-01) and
`Australia/Sydney` (spring forward 2026-10-04, fall back 2026-04-05, i.e. the opposite months).
Existing daylight-saving tests stay and must still pass except any that encoded the old naive end;
those change with the reason stated in the commit.

**6. Property tests.** Add `hypothesis` as a pinned dev dependency (`==` exact, version taken
from the index at implementation time, `uv.lock` updated and `uv sync --locked` verified).
`scheduling/domain/test_free_slots_properties.py`: strategies generate rules (weekday, start,
end, step, validity), time off, appointments (any status), a query window, `now`, zone from
{UTC, New_York, Sydney}, type duration/buffer. Asserted for every offered slot: starts and (real)
ends inside the query range; wall start >= rule start and wall end <= rule end of at least one
rule valid that day; start >= now; no overlap with time off; no overlap with an active
appointment extended by the buffer (cancelled/no-show ignored); list strictly increasing
(sorted, unique). `settings(max_examples=100-ish, deadline=None, derandomize=True)` so
`make mutate` (runs domain tests per mutant) stays quick and stable. Prove it can fail: run once
against a deliberately broken copy (drop the `start < now` check) and record the failure.

**7. Mutation survivors.** Run `make mutate` after blocks 1-5 (names shift with code).
Per survivor: add a test that kills it, else list as equivalent. New
`scripts/mutation_survivors.py` runs/reads `mutmut results`, subtracts names listed in
`mutation-equivalents.txt` (format: `mutant.name: reason`, `#` lines ignored, a missing reason is
an error), prints unlisted survivors and exits 1 if any; it also prints stale list entries
(non-fatal). `make mutate` calls it after `mutmut run` so the exit code carries the result.
`audit_metadata.py` first: tests for each key pattern bound, suffix, bool-as-int, wrong-type,
domain pattern edge, `to_json` shape; every one of the 21 killed by a test, equivalents only
with a stated reason (e.g. regex lengths that cannot be observed). Script gets its own test
(`scripts/test_mutation_survivors.py`) on canned `mutmut results` text. Also close the 8
survivors the review listed in task-06 modules (`_local_days`, `_to_utc_if_it_exists`,
`_rank_key`, `violated_rules`) by test or listing.

## Files, in order
1. `scheduling/domain/test_domain_imports.py` (red on today's code), then
   `scheduling/domain/vocabulary.py`; edit `appointment_status.py`, `booking_rules.py`,
   `free_slots.py`, `session_rules.py`, `sign_in_rules.py` imports.
2. `scheduling/models/{base,booking,people,access}.py` (drop four enums, `choices_of`,
   `one_of`); the 23 importers' import lines.
3. `slot_search.py`, `first_available.py` and their tests (UUID, exact ranking).
4. `free_slots.py` `_rule_starts` plus `test_free_slots_daylight_saving.py`.
5. `pyproject.toml`, `uv.lock` (hypothesis), `test_free_slots_properties.py`.
6. `Makefile`, `scripts/mutation_survivors.py` + test, `mutation-equivalents.txt`,
   `pyproject.toml` (mutmut config if the new vocabulary module needs `do_not_mutate`),
   new killing tests in `test_audit_metadata.py` and neighbours.

Not touched: migrations (must stay byte-identical), `failure.py`, `request_context.py`,
`lockout_rules.py` logic, views, templates, `BusyInterval`/`TimeRange` merge (review "Later"
5, needs a third caller), typed booking attempt (review "Later" 3).

## Invariants and blast radius
- Double booking: `free_slots` still treats active = not cancelled/no-show (`is_active`) and
  half-open intervals; the DB exclusion constraints are untouched. The property test pins this.
- Authorization and audit log: no write path or view changes. `audit_metadata` behaviour
  unchanged, only tested harder; to_json shape pinned.
- Blast radius: every file that imports the four enums (23), `data_model_document.py`,
  model constraint SQL (`one_of` values identical). Wire/stored values unchanged.

## Failing tests first (names; expected values in words)
- `returns_no_forbidden_imports_when_domain_modules_are_parsed`: fails now, lists the five modules.
- `returns_first_candidate_with_lowest_id_when_exact_products_tie` (UUID(int=2) before UUID(int=5)).
- `returns_larger_exact_product_first_when_float_products_would_round_equal`.
- `returns_no_slot_when_spring_forward_real_end_passes_rule_end` (New_York and Sydney).
- `returns_slot_when_fall_back_real_end_is_within_rule_end` (New_York and Sydney).
- `returns_slots_inside_every_rule_window_when_rules_are_generated` and sibling properties
  (range, past, time off, buffered active appointments, sorted and unique).
- audit_metadata survivors: one `rejects_*`/`returns_*` test each, named after the boundary.
Each test is shown failing for the right reason before its code change (red gate).

## Trust boundaries
None crossed: pure functions, no input from clients. Identifier type tightening (UUID) and the
`audit_metadata` guards are what use cases will rely on at their boundaries.

## Vocabulary
Clinician, ClinicianProfile, AvailabilityRule, TimeOff, Appointment, AppointmentType, Hospital
(time zone), AuditLogEntry (metadata), Session, User/Role.

## Will not do
No new abstraction beyond `vocabulary.py` and `choices_of`; no dependency except `hypothesis`
(dev, pinned); no merge of `BusyInterval`/`TimeRange`; no change to migrations; no behaviour
change other than item 5.

## Risks
- `choices_of` label drift would produce a migration: guarded by `makemigrations --check`.
- Hypothesis cost inside `make mutate`: capped examples, derandomized.
- `uv.lock` needs network to pin hypothesis; if the sandbox is offline the stage stops and says so.
- Mutant names change when code changes: equivalents file is written last.

## Architect review

Verdict: approve.

- Ladder: one new module (`vocabulary.py`), one helper (`choices_of`), one dev dependency (`hypothesis`, asked for by item 6). No speculative abstraction. Not-touched list is right.
- Coverage: items 1-7 all mapped to files and named first tests; item 5 rule is stated with worked examples in both hemispheres.
- Migration proof is sound (`makemigrations --check` plus empty `git diff` on migrations). Watch two spots when implementing: `default=SessionKind.PASSWORD` on `Session.opened_by` now takes a plain `StrEnum` (compares equal to the stored string, so no diff expected, but the check must be run), and fields currently pass the enum class to `choices=`; use `choices_of(...)` everywhere, since a plain `StrEnum` has no `.choices`/`.label`.
- Item 3: confirm UUID ordering matches section 5.5 tie-break text; the plan does.
- Item 7: the survivor script must fail on a missing reason and be proven failing once with an unlisted survivor. Plan implies it; do it explicitly in the red-proof stage.
- Hypothesis in `make mutate`: `derandomize=True` plus capped examples is right; also disable the example database so mutant runs stay hermetic.
- Security: no boundary crossed; audit_metadata (personal data out of the audit log) gets stronger tests. Fine.
