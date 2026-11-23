# ADR 0011: encryption at rest for clinical notes and visitor holds, and the development server

Status: proposed, 2026-11-23, for the owner to accept. Task 26d, items 16 and 17.

## Context

Two gaps were recorded as open points before this review: encryption at rest for `clinical_notes`
and for the `visitor_*` fields of a BookingHold (`doc/adr/0002-identifiers-and-schema-guards.md:28`,
`doc/backlog/02-domain-model.md:50`). `doc/handover.md:218` lists them, with the development server
in the container, under "Questions that wait for the owner". This ADR states what the code does
today and what a deployment must add. It makes no code change and picks no option for the owner.

The product runs as a local-only development stack (`compose.yaml`). Nothing here is deployed.

## Decisions

### 16. Encryption at rest: what protects the data today

- **Clinical notes** are a plain `CharField` on ClinicalNote (`scheduling/models/booking.py:110-116`).
  Nothing in the code encrypts a column.
- **Access to notes** is limited to the appointment's clinician, checked server side. Save and read
  both go through `_own_appointment` (`scheduling/use_cases/clinical_notes.py:1-4, 20-52`). Admins
  and patients are refused. The FHIR Appointment loader returns a note only to the owning clinician
  (`scheduling/use_cases/fhir_appointment_loading.py:27-33`).
- **Audit** records the field name only. The audit metadata type cannot carry notes, reasons or
  names (`scheduling/domain/audit_metadata.py:1-3`).
- **Visitor details in a hold** (name, birth date, email, phone, reason) are plain fields on
  BookingHold (`scheduling/models/access.py:109-113`).
- **Short life.** A hold lasts 10 minutes (`drlibre-specs.md`, section 17, item 14). Expired holds are
  deleted by the worker, with their verification codes (`scheduling/use_cases/hold_expiry.py:14-33`).
- **Transport.** `HTTPS_ONLY`, HSTS and secure cookies are switched by settings (`drlibre/settings.py:48-57`).
  The compose file serves plain HTTP on `127.0.0.1:8000` (`compose.yaml:18`).
- **Database.** PostgreSQL 15 keeps its data in the named volume `database` (`compose.yaml:60`). No
  port is published for `db`. No `pgcrypto` is used; the only extension is `btree_gist` (`scheduling/migrations/0001_initial.py:23`), for the booking overlap constraint.

### 16. What a deployment must add

- Encrypted storage under the database volume and under its backups, at host or volume level.
- TLS in front of the product, with `HTTPS_ONLY` set.
- A named owner for key management, and a recorded procedure for key rotation.
- Column-level encryption, if chosen (see below), needs one constraint handled first.
  `visitor_email` has a unique constraint and an exact-match lookup (`scheduling/models/access.py:117-124`,
  `scheduling/use_cases/booking_holds.py:54`). Randomised encryption of that column breaks both. It
  needs a keyed hash column for lookups, the pattern of ADR 0002.

### 16. The choice left to the owner

The product makes no choice here. Three options, with their costs:

- **(a) Volume and backup encryption only.** No code, no dependency. Does not protect the notes
  from a database operator who can read the decrypted data.
- **(b) Application column encryption** for `clinical_notes` and the `visitor_*` fields. Needs a key from
  the environment or a secret store, a pinned library (a new dependency, needs approval), a keyed
  hash column for `visitor_email`, a migration, and key rotation.
- **(c) In-database encryption (`pgcrypto`).** Needs the extension, key handling in SQL, and care
  that queries and logs do not expose plaintext.

Lean, not a decision: (a) now, because holds are short-lived; (b) or (c) for the notes before real
patient notes are kept. The owner decides.

### 17. What the container runs

- `Dockerfile:26` sets the command to `runserver 0.0.0.0:8000`. Django's development server serves
  the pages and the API.
- `compose.yaml:12` runs `migrate` and then `runserver` for the `web` service. The `worker` service
  uses the same image for `run_worker`.
- DEBUG is on: `compose.yaml:2` sets `DEBUG: "true"` in the `environment:` block, which overrides
  `env_file:`. `.env.example` sets no `DEBUG`, so editing it changes nothing.
- `compose.yaml:18` publishes the port as `127.0.0.1:8000`. The source is bind-mounted (`.:/app`).
- Static files: there is no `staticfiles` app and no whitenoise. Django's `serve` view answers
  `/static/` (`drlibre/urls.py:191-192`). Its comment says it is for the local-only product and
  works with DEBUG off.

### 17. What the development server is safe for

- One user, on one machine, reaching the product on `127.0.0.1`.
- Test or demo data only.
- Caveat: inside the container `runserver` listens on all interfaces. Only the host port mapping keeps
  it local. Any other exposure (host networking, a changed port mapping) is outside this allowance.

### 17. What a deployment replaces

- `runserver` with a production WSGI server. A new pinned dependency, needs approval.
- Static files served by a reverse proxy or a `collectstatic`-style step, not by `serve`.
- TLS termination, with `HTTPS_ONLY=true`, `HSTS_SECONDS` and `TRUSTED_PROXY_COUNT` set
  (`drlibre/settings.py:48-57`).
- `DEBUG` off, set in the deployment's own compose file. This file hard-codes it on.
- No bind mount of the source.
- Migrations as a separate job, not in the web start command.
- A production install. `Dockerfile:22` runs `uv sync --locked`, which installs the dev group too.
- A real `SECRET_KEY`. `drlibre/startup_checks.py:13-18` refuses the published development values
  when DEBUG is off. They are not quoted here.

## For the owner

1. The encryption choice in Decision 16: (a), (b) or (c), and when notes must be protected.
2. Accept that the container runs a development server, and that the deployment target is open.
3. Whether `doc/handover.md` drops the two items from "Questions that wait for the owner" once the
   owner decides. This is the orchestrator's edit, not this run's.
