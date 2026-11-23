# DrLibre

Appointment scheduling for several hospitals. Setup and the working rules are in `CLAUDE.md`.

Run `make audit` before a hand-over and after any change to `uv.lock`. It queries a vulnerability service over the network, so it is not part of `make test`.

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
