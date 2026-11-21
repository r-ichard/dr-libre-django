Task 02: domain model and migrations.

Turn `drlibre-specs.md` section 3 into the Django models and the first migrations. The
owner reads the result before anything is built on it, so the schema must be complete,
strict and easy to read. Schema, constraints and their tests only: no view, serializer,
use case, seed or admin registration.

1. Model every concept of section 3.1 with the exact names of the `CLAUDE.md` vocabulary:
   Hospital, Department, Specialty, User, ClinicianProfile, Room, AppointmentType,
   AvailabilityRule, TimeOff, Appointment, WaitlistEntry, Notification, AuditLogEntry,
   Session, BookingHold, VerificationCode, SignInLink. The API token of section 15 is not
   in this task. The custom User model is in the first migration and uses Django's
   password hashing; a passwordless patient has no usable password and carries the time
   the email was verified.
2. Section 3 preamble: identifiers are opaque and never sequential integers; every
   instant is stored in UTC; every record carries creation time, last update time and,
   where a signed-in user created it, the creator. Choose the identifier type in the plan
   and record why in an ADR; rules elsewhere break ties on "lowest id", so it must sort.
3. Every rule section 3 states about a stored value is enforced by the database, not only
   by Python: uniqueness (codes, lower-case email), ranges (capacity, duration, buffer,
   round robin weight, weekday, slot step, lengths), end after start, the value lists of
   status, source, role, notification kind and waitlist status. Then read sections 4 to
   12 for further invariants on stored data and list in the plan which ones this schema
   encodes now and which wait for their use case, with the reason.
4. Double booking (section 5.2, step 3) gets a last line of defence in the database: two
   active appointments cannot overlap for the same clinician, the same patient or the
   same room. Intervals are half-open, so appointments that touch are legal. An
   appointment that is `CANCELLED` or `NO_SHOW` blocks nothing.
5. Audit log entries are append-only in the database itself: an update or a delete of a
   row is refused whoever asks, the application included.
6. No relation deletes by cascade. Deleting a record that something still refers to
   fails in the database; section 10 "Deleting" later turns that into `has_dependents`.
7. Session, VerificationCode and SignInLink store a hash of their secret and have no
   column that could hold the secret itself. Hashing arrives with the sign-in tasks.
8. Tests, written first: for each constraint one test that the database refuses the
   illegal row and one that its nearest legal neighbour is accepted (touching
   appointments, an overlap with a cancelled appointment, the smallest legal value).
   Name them `returns_X_when_Y` or `rejects_X_when_Y`. Add a check, run by `make test`
   or `make lint`, that fails when a model change has no migration.
9. `doc/data-model.md` for the owner's review: a Mermaid entity-relationship diagram and,
   per model, its fields and every database constraint. Generate it from the models with
   a management command and add a test that fails when the committed file is stale, so
   the document cannot drift from the schema.

Waived for this task only: the rule that a model is unfinished without full create, read,
update, delete and list (§8). Those arrive with the feature that owns each model; the
reviewer does not block on their absence here.

Open points to state in the plan, not to solve: encryption at rest for clinical notes and
visitor details held in a BookingHold; whether `CONFIRMED` stays (section 17).

Done when `make setup && make lint && make test && make gate` pass from a fresh clone,
the migrations apply to an empty PostgreSQL database, and `doc/data-model.md` matches the
models.
