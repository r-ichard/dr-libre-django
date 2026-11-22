Area: the FHIR API.

Specification: `drlibre-specs.md` section 15, with sections 4, 5 and 12.3 for the rules
it must share with the rest of the product. Decisions: `doc/adr/0003-*`, `0005-*`,
`0006-*`. Only the resources and interactions `GET /fhir/metadata` lists exist; one the
specification names and the statement does not is not built yet and not a finding.

Tokens: `uv run --env-file .env.example python manage.py api_tokens issue <email> --name
<name>` prints a token once. Issue one for an admin, two clinicians of different
departments and two patients. No browser is needed; use `curl`.

Try at least:
- The statement against the door: every resource, interaction, search parameter and
  `_include` it names answers; nothing it does not name answers anything but an
  `OperationOutcome`. Every answer under `/fhir`, for every method, header and body you
  can think of, is FHIR JSON with a correlation id: never HTML, never the body of
  `/api/v1`, never a 500.
- Paging: for every searchable type, follow `next` from the first page to the last with
  `_count=1` and `_count=100`; count the entries against `total`; no entry twice; `self`
  reads back the same page.
- Who sees what, with no token and with each token: inactive records; the clinician the
  public search hides; a clinician's email and phone; `Patient` (the own record, a
  clinician's patients, everyone for an admin); `Slot` statuses other than free; an
  `_include` or a Bundle that carries a resource the caller could not read directly; a
  search whose `total`, links or error tell that a record exists.
- Tokens: revoked, of a deactivated user, malformed, in the address, in a cookie; many
  bad tokens and whether a good one still works; whether a token or its hash appears in
  any answer, log line or audit row; the session cookie of a signed-in admin sent to
  `/fhir` without a token.
- Writes: every write the statement lists, as each role and with no token. A body with
  an unknown element, a wrong type, another resource's id, an id on create, elements the
  server owns. `If-Match` stale, current, missing and malformed. The same create sent
  twice at once.
- One door, same rules (15.1): for each FHIR write, the same request through the pages
  or `/api/v1`, and compare the refusal, the audit entry, the notification and the email.
  Look for anything FHIR allows that the application refuses: booking for another
  patient, a slot outside availability, a lead time, a fourth open booking, a status
  change the table of 5.6 does not allow, a schedule that overlaps, a time off edit.
- Slots: the same type, clinician and range through `/fhir/Slot` and `/api/v1/slots`
  must agree; slot ids read back; an id altered by one character; ranges of 31 and 32
  days, across a daylight saving change, in the past.
- Validity: `make fhir-validate` passes; then save answers it does not sample (an empty
  search, a search with every parameter, every refusal you provoked) and check them for
  empty arrays, nulls and elements that are not FHIR R4.
- Personal data: `Cache-Control` and `Vary` on answers that depend on the token; a
  patient's name, email, phone or birth date in `scratch/qa/server.log` after reads,
  searches by email and phone, and refused updates.
