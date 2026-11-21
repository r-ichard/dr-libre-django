# ADR 0002: identifiers and schema guards

Status: accepted, 2026-11-21.

## Decisions

- **UUIDv7 in a native `uuid` column.** Section 3 wants opaque identifiers that are never
  sequential integers, and rules elsewhere break ties on "lowest id", so the identifier must
  sort. UUIDv7 puts a millisecond timestamp first, so it sorts by creation time, needs no
  coordination and is 16 bytes. Rejected: UUIDv4 (does not sort), ULID (text, no native
  type), `BigAutoField` (sequential), PostgreSQL `uuidv7()` (we run 15). Python 3.13 has no
  `uuid.uuid7`, so `scheduling/identifiers.py` lays it out. Ties inside one millisecond
  are random.
- **`django.contrib.postgres` is installed** (ADR 0001 left this open). Django's system
  check refuses `ExclusionConstraint` and `ArrayField` without it. No other contrib app.
- **`btree_gist` extension**, first operation of migration 0001, so the three exclusion
  constraints on `Appointment` can compare a clinician, patient or room with `=` and the
  time range with `&&`. It is a trusted extension; the application role owns the database.
- **Audit log append-only by trigger** (migration 0002): update, delete and truncate raise.
  A superuser can still drop the trigger; beyond that the defence is operational.
- **Every foreign key is `PROTECT`.** No cascade, no `SET_NULL`.
- **Secrets are hash columns only** (`*_hash`, exactly 64 characters).
- **Migrations are generated code** and excluded from ruff, apart from the one hand-inserted
  extension operation and the hand-written 0002.

## Open points

- Encryption at rest for `clinical_notes` and BookingHold `visitor_*` is not decided; both
  are plain text.
- `CONFIRMED` stays in the appointment status list until section 17 is settled.
- Invariants spanning tables (same department, roles of patient and clinician, end equals
  start plus duration) wait for their use cases; see the plan.
