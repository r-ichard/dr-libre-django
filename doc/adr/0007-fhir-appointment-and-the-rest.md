# ADR 0007: FHIR Appointment, AppointmentResponse, Communication, AuditEvent

Status: accepted, 2026-11-22. Builds on ADR 0003 (ids, versions), ADR 0004 (failures), ADR 0005
(conventions) and ADR 0006 (writes, failure table).

## Decisions

- **Sort order.** A FHIR search sorts by the database collation (PostgreSQL's, for text), then by id
  as tie-break. A client must not assume byte or locale-independent order.
- **Appointment** is one type for three origins. A booked appointment maps to `booked` (booked,
  confirmed), `checked-in`, `fulfilled`, `cancelled`, `noshow`. A waitlist entry maps to `waitlist`
  (waiting), `proposed` (offered, with the offered `start`/`end`) and `cancelled` (expired). A booking
  hold is `pending`. Its logical id is the waitlist entry id once an offer became an appointment
  (ADR 0003).
- **Extensions** (`StructureDefinition/<name>`): `appointment-source` (`valueCode`: where the
  booking came from, on bookings and holds) and `appointment-status` (`valueCode`: the product's
  status, only when the FHIR status is `booked`, because `booked` and `confirmed` look the same in
  FHIR). A refused write carries on its `OperationOutcome` issue `violated-rule` (one per rule the
  booking broke, the product's rule name) and `conflicting-resource` (a reference to what the slot
  collides with). Both are read by clients that want to explain a refusal; none is ever sent on a
  write.
- **What an Appointment body may change.** Create: `proposed` (book) or `waitlist` (join), nothing
  else. Update: move `start` (the end follows the stored duration; a client `end` that disagrees is
  refused) or change `status` to `cancelled`, `checked-in`, `fulfilled`, `noshow` if the status table
  of the product allows it, with `cancelationReason`. Moving and changing status in one body is
  refused. Every other element that differs from the stored resource is 400 and named. The end is
  never taken from the client. Every write calls the use case the screens call.
- **AppointmentResponse** exists only to accept a waitlist offer: participant status `accepted`.
  Declining is not in the specification of this product, so no other status is shown or accepted.
  Only the offered patient may accept; authorization is checked before the actor is compared.
  A clinician searching `AppointmentResponse` gets an empty search (200, total 0), as a clinician
  asking for a slot status the clinician may not see does, because a clinician has no offers.
- **Communication** is a notification. A recipient may change one thing: set `received` once, which
  is "mark as read". Every other difference, or a second `received`, is 400 and named. `category`
  is the notification kind, its display in words (the same words as the pages).
- **AuditEvent** is read only and admin only. `AuditEvent.action` is the R4 code of the value set
  AuditEventAction: `C`, `R`, `U`, `D`, `E`. A pure domain function maps each product action: a
  known table, then the suffix `.create`, `.update`, `.delete`, else `E`. Creations, expiry and
  purges are `C` and `D`; state changes (`appointment.cancel`, `user.activate`,
  `user.deactivate`, `waitlist.offer`) are `U`; exports and reads are `R`; sign-ins, mail and any
  unknown action are `E`, so a new action stays valid FHIR before it has a row. A test fails when an
  action in `audit_labels` has no explicit or suffix mapping.
- **Search by `action`** reads the product's action name, which is `AuditEvent.type.code`, not the
  element `action` (a single letter would find too much). `type` and `action` are both served.
- **`entity.detail`** holds the metadata of the audit entry key by key, only the keys of
  `AuditMetadata`, by name, so a key added later is not served until it is allowed here. Metadata is
  ids, counts, status values, field names and an email domain; never a name, address, phone, birth
  date, reason or note (spec section 4). A test asserts this over every event of the demo seed.
- **Validation.** `make fhir-validate` samples every type of the declaration and every interaction:
  each status or kind served, search Bundles with every `_include`, the body of each write, and one
  refusal. A test fails when a type or an interaction has no sample.

## Open points for the owner

Collected as "Questions for the owner" below.

## Questions for the owner

1. Which clinicians are public over FHIR? Section 15.4 says "active clinicians"; section 6.1 hides a
   clinician with no appointment type patients may book online. Today the product: hides from a
   public caller what the public search and `GET /api/v1/slots` hide; staff tokens see them (ADR 0005).
2. Should a token expire or carry scopes? Today the product: a token is exactly its user's rights
   until revoked, with no expiry and no scope (ADR 0005).
3. Should a busy slot be readable by its id? Today the product: only a free slot is (ADR 0006).
4. Is a `Patient` search by email, phone and birth date in the query string acceptable? Today the product: serves it; the server logs no query string, but a client or proxy may (ADR 0006).
5. Should a patient be able to decline a waitlist offer over FHIR? Today the product: accepts only
   `accepted` in an `AppointmentResponse`; declining needs a status the specification does not give.
