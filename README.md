# DrLibre

DrLibre is an appointment scheduling product for hospitals. Anyone can search hospitals, clinicians and specialties, see the next free appointment times, and book one without signing in or choosing a password.

## Start it

Needs Docker and git. The stack runs in containers: the application, a PostgreSQL database and a mail inbox.

```sh
git clone https://github.com/r-ichard/dr-libre-django.git drlibre-try && cd drlibre-try
docker compose up --wait                           # migrates; returns when the app answers
docker compose exec web python manage.py seed_demo # demo data; safe to run again
```

Then open:

- the product at `http://127.0.0.1:8000`;
- the mail inbox at `http://127.0.0.1:8025`, which shows every email the product sends.

Compose reads `.env.example` directly, so there is nothing to copy. Health: `curl 127.0.0.1:8000/api/v1/health`.

## Demo accounts

- `admin@example.test`
- `clinician@example.test`
- `patient@example.test`

All three use the password named by `DEMO_PASSWORD` in `.env.example`. Sign in at `http://127.0.0.1:8000/sign-in`.
A visitor needs no account: search, pick a time, type an email address, read the code in the inbox.

## First walk

Walked by hand on commit `6d98501` (2026-11-22); the steps were not re-run for this README. Needs Docker.

1. As `admin@example.test`, in the admin console, create a hospital with its time zone.
2. Add a specialty.
3. Add a department of the hospital.
4. Add a room of the department.
5. Add an appointment type of the department. Type its colour, like `#2f6f6a`, and tick "Bookable online".
6. Add a user with the role Clinician and a temporary password.
7. Under "Clinicians", attach a profile to that user: department, specialty, room.
8. Sign out. Sign in as the clinician. Under "Availability", add one rule per weekday.
9. Sign out. On the start page, the clinician, the hospital and the specialty are found. Pick a time, fill in the details, take the code from the inbox at `http://127.0.0.1:8025`, and confirm.
10. Sign in as the clinician again. The calendar shows the appointment.

## Stop and forget

```sh
docker compose down -v
```

`down` alone stops the containers and keeps the data. `-v` also deletes the database volume, so the demo data and everything made in it are gone. Needs Docker.

## Checks

- `make setup`, once on the host: installs uv if it is missing, syncs the locked dependencies, and makes sure a PostgreSQL answers, starting a local one where it can.
- `make test`: the test suite, on the host, against PostgreSQL.
- `make lint`: ruff and mypy.
- `make gate`: the comment cap, the escape-hatch scan and the size caps.
- `make mutate`: mutation testing of `scheduling/domain`; slow.
- `docker compose exec web make test`: the suite inside the container. Needs Docker.
- `make fhir-validate`: seeds a throwaway database and runs the HL7 validator over `/fhir`. Needs network and Java. When Java is absent it installs `default-jre-headless` with `apt-get`, so it needs root.
- `make audit`: checks the pinned packages in `uv.lock` against a vulnerability service. Needs network. Run it before a hand-over and after any change to `uv.lock`. It is not part of `make test`.

The working rules for changes to this repository are in `CLAUDE.md`.

Run `make smoke` after `docker compose up --wait` and `seed_demo`, before a hand-over or after a deploy, to walk a visitor's hold, code and booking, then a cancel against 127.0.0.1:8000 and 8025 (it is not part of `make test`).

## FHIR API

Every concept is served as FHIR R4 under `/fhir`; the CapabilityStatement is at `/fhir/metadata`.
The commands below ran against the demo seed (`manage.py seed_demo`, `DEBUG` on) on
`127.0.0.1:8000`; answers are shortened and ids differ on your machine.

**Issue a token.** A token is exactly one user's rights. It is printed once; keep it out of
logs and shell history.

```
$ python manage.py api_tokens issue patient@example.test --name my-client
dlk_...
$ export TOKEN=<token>
```

`api_tokens list` and `api_tokens revoke <id>` never print a token.

**One read.**

```
$ curl -s -H "Authorization: Bearer $TOKEN" "127.0.0.1:8000/fhir/Location?_count=1"
{"resourceType": "Bundle", "type": "searchset", "total": 7, ... "name": "Bayside Demo Hospital" ...}
```

**One search.** Free slots of a service in a week (`start` is required, twice, as a range).

```
$ curl -s -H "Authorization: Bearer $TOKEN" \
    "127.0.0.1:8000/fhir/Slot?status=free&service-type=<service id>&start=ge2026-11-23&start=lt2026-11-30&_count=1"
{"resourceType": "Bundle", "type": "searchset", "total": 299, ... "resource": {"resourceType": "Slot", ...}}
```

**One booking.** `<service id>` comes from `/fhir/HealthcareService`, `<slot id>` from the
search above, `<patient id>` is the token owner's `Patient`.

```
$ curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/fhir+json" \
    -d '{"resourceType":"Appointment","status":"proposed",
         "serviceType":[{"coding":[{"code":"<service id>"}]}],
         "slot":[{"reference":"Slot/<slot id>"}],
         "participant":[{"actor":{"reference":"Patient/<patient id>"},"status":"accepted"}]}' \
    127.0.0.1:8000/fhir/Appointment
{"resourceType": "Appointment", "id": "...", "status": "booked", "start": "2026-11-23T08:00:00Z", ...}
```

**One refusal.** The same booking sent again: the slot is taken, answer 409 with the rule that
was broken.

```
$ curl -s -w ' %{http_code}\n' -X POST ... 127.0.0.1:8000/fhir/Appointment
{"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "conflict", ...}]} 409
```

A patient's token reading the audit trail is refused too:

```
$ curl -s -w ' %{http_code}\n' -H "Authorization: Bearer $TOKEN" 127.0.0.1:8000/fhir/AuditEvent
{"resourceType": "OperationOutcome", "issue": [{"code": "forbidden", ...}]} 403
```

**Validate.** `make fhir-validate` seeds a throwaway database, samples every resource type and
interaction `/fhir` answers, and runs the HL7 validator on them. It fetches Java and the pinned
validator jar the first time.

## Running with DEBUG off

With `DEBUG` off, start-up refuses, naming the variable:

- `SECRET_KEY` equal to the published development key from `.env.example`;
- an empty `ALLOWED_HOSTS`;
- `DEMO_PASSWORD` equal to the published demo password;
- a `TRUSTED_PROXY_COUNT` that is negative or not a whole number (refused with `DEBUG` on too).

`.env.example` alone therefore fails. To run this way locally, set a private `SECRET_KEY`, set
`ALLOWED_HOSTS` (for example `localhost,127.0.0.1`) and leave `DEMO_PASSWORD` empty. Cookies are
`Secure` with `DEBUG` off, so a browser on plain http does not keep the session: put the product
behind TLS and set `HTTPS_ONLY=true` with a `HSTS_SECONDS` value. `seed_demo` refuses to run.

`TRUSTED_PROXY_COUNT` is the number of proxies in front of the product that each append the
address they saw to `X-Forwarded-For`. `0` (the default) ignores the header and uses the
connection address, which is right with no proxy. `n` takes the n-th entry from the right as the
caller's address, which the rate limits count, and trusts `X-Forwarded-Proto`. A value larger
than the real number of proxies lets a caller choose its own address.
