# ADR 0005: FHIR conventions, tokens and the public resources

Status: accepted, 2026-11-22. Builds on ADR 0003 (ids, versions) and ADR 0004 (failures, limits).

## Decisions

- **One door, same rules.** `/fhir` is FHIR R4 (4.0.1) JSON, `Content-Type: application/fhir+json`.
  It reads through the use cases and the visibility rule the application API uses
  (`bookable_types`, `listable_profiles` in `search_catalog.py`), never a second copy.
- **`Accept`.** Served: no header, `*/*`, `application/*`, `application/json`,
  `application/fhir+json` (parameters such as `q` or `charset` ignored). Anything else, for
  example `text/html`, is 406 with an `OperationOutcome`. The answer is always FHIR JSON.
- **Failures are `OperationOutcome`s** with the status of ADR 0004: unknown resource type or id,
  a method other than GET (404, the application API's choice: one status for "no such route"),
  a refused parameter (400, named in `issue.expression`), input limits (400), a bad token (401),
  a full attempt counter (429), an unexpected error (500: fixed text and the correlation id).
  The text is fixed, never built from input. Every response carries `X-Correlation-Id`.
- **Ids and versions** as ADR 0003: the product's id, `meta.versionId` the row version,
  `meta.lastUpdated` the update time, a read answers `ETag: W/"<versionId>"`. A hospital is an
  `Organization` and a `Location` with the same id; a department is an `Organization`, a room a
  `Location`.
- **Canonical URLs.** Base `https://drlibre.example/fhir`: a name, not a host this service
  answers on. Code system `<base>/CodeSystem/specialty`, value set `<base>/ValueSet/specialty`,
  extensions `<base>/StructureDefinition/<name>` (`room-floor`, `room-capacity`,
  `room-equipment`, `service-duration-minutes`, `service-buffer-minutes`, `service-colour`,
  `service-needs-room`, `service-bookable-online`, `role-round-robin-weight`, `role-bio`,
  `hospital-time-zone`). They live in `scheduling/domain/fhir_common.py`, the one place a mapper reads
  them. The code system and value set each have the single id `specialty`.
- **Search.** Parameters of 15.5 per type, declared once in `fhir_declaration.py`; routing, the
  parser and `GET /fhir/metadata` read that declaration, so the CapabilityStatement cannot name
  what is not served. `_count` 1 to 100 (default 20), `_offset` pages, `_sort` accepts `name`,
  `address-city` and `active` where the type has them (a prefix `-` reverses), `_include` only
  `PractitionerRole:practitioner` and `PractitionerRole:organization`. A parameter the type does
  not have, a repeated one, or a value that cannot be read is 400. Search is bounded in queries
  per page, not per row.
- **Tokens (`ApiClient`).** A name, the one user whose rights it gives, the SHA-256 of the token
  (as for sessions), created, last used (at most once a minute) and revoked. The token is
  `dlk_` plus 32 random bytes, shown once by `manage.py api_tokens issue <email> --name <name>`.
  `list` and `revoke <id>` never print a token or a hash. Issue and revoke are audited in their
  transaction (`api_client.issue`, `api_client.revoke`; entity `ApiClient`; metadata holds
  `user_id` only, no name, because a name may be a person). The actor is empty: a shell is not a
  user.
- **Authentication.** Only `Authorization: Bearer <token>`. No header: public. A token that is
  unknown, revoked, malformed (any other scheme, extra spaces) or of an inactive user is 401 and
  never the public answer. A token is never read from the address (`access_token` is a refused
  parameter) and the session cookie is never read under `/fhir`.
- **Failed attempts.** Scope `token` of the existing `RateLimitHit` table: 5 failed attempts an
  hour per presented token (keyed hash) and 20 an hour per network address (`REMOTE_ADDR` only).
  Only a failure counts, so a working client is never throttled. A full counter answers 429
  before the token is looked up.
- **Rights (15.4).** A clinician's or an admin's token: every record, inactive ones too, and a
  clinician's email and phone as `Practitioner.telecom`. Birth date is never served. No token or
  a patient's token: active records, name and title of a clinician only.
- **No admin page for tokens.** The specification has none; the command is the whole interface.

## Open points for the owner

- **Which clinicians are public.** Section 15.4 says "active clinicians"; section 6.1 hides a
  clinician with no appointment type patients may book online, and the application API hides such
  a type from a caller without a session. We took the stricter reading: what the public search
  and `GET /api/v1/slots` hide, `/fhir` hides from a public caller. Staff tokens see them.
- **Inactive references.** A staff `PractitionerRole` lists only online-bookable types as
  `healthcareService`, though a staff `HealthcareService` read shows inactive types.
- **Caching.** The same URL answers differently by viewer. `Vary: Authorization` and
  `Cache-Control: private` are not set yet.
- **Token expiry and scopes** are not built: a token is exactly its user's rights until revoked.
- **Validation of the JSON against the R4 definitions** is not part of this change.
