Task 02a: finish the domain model and make it ready for FHIR.

Task 02 produced the models, migrations and tests that are on this branch, and its suite
was green. Its run then failed for a process reason (`doc/retro.md`) before refactor and
review. This run adds the FHIR readiness the owner asked for and takes the whole model
through proof, refactor and review. The base of every diff in this run is commit
`314732e` on `main`: use `git diff 314732e...HEAD`.

Read first: `doc/backlog/02-domain-model.md`, which stays binding with its waiver,
`doc/plans/2026-11-21-domain-model.md` and `doc/adr/0002-identifiers-and-schema-guards.md`.

1. Versions (`drlibre-specs.md` section 15.1). Every record a FHIR resource is built
   from carries a version that starts at 1 and grows by one on every change, so
   `meta.versionId`, `If-Match` and the 412 answer can be served later. No code path may
   change such a row without increasing its version, and a stale write must be detectable
   in the statement that writes, not by reading first.
2. One resource, not two (section 15.3). A waitlist entry that is accepted and the
   appointment booked from it are a single FHIR `Appointment`. Decide how the schema
   represents that, record it in an ADR and add what it needs.
3. Mapping check. Go through section 15.2, 15.3 and 15.5 element by element. For each
   FHIR element and search parameter the specification promises, name the column it comes
   from. Add what is missing. List in the plan what is derived or served as an extension
   and needs no column.
4. `doc/data-model.md` states for each model the FHIR resource or resources it maps to,
   or "not exposed" with the reason, generated from the models like the rest of the
   document so it cannot drift. A model that declares neither fails a test.
5. The models keep their `CLAUDE.md` names. FHIR names live in the mapping only: one
   concept maps to two resources and three concepts map to one, so renaming would not
   remove the mapping.
6. Scope of the later stages. Proof, refactor and review cover the whole diff against
   `314732e`, not only what this run adds. In the proof stage break at least one rule of
   each kind in the existing schema (range check, uniqueness, overlap exclusion,
   append-only audit, protected delete) and every rule added here.

Done when `make setup && make lint && make test && make gate` pass from a fresh clone,
the migrations apply to an empty PostgreSQL database, and `doc/data-model.md` matches the
models.
