# ADR 0003: FHIR readiness, versions and waitlist identity

Status: accepted, 2026-11-21.

## Decisions

- **Versions.** Fourteen models (`Versioned`) carry `version`, starting at 1. The trigger
  `scheduling_enforce_version` (migration 0004) refuses an insert that is not 1 and an update
  that is not `OLD.version + 1`, so no path (ORM, `queryset.update`, raw SQL) changes a row
  without growing its version. `Versioned.save()` writes `loaded version + 1`; a stale save is
  refused by the writing statement, with no prior read, and the in-memory version is restored.
  `If-Match` later becomes `filter(pk=..., version=expected).update(version=F("version") + 1)`
  and a row count of 0 is the 412. `Session`, `VerificationCode` and `SignInLink` are
  credentials, not exposed, and carry no version.
- **Parent resources.** Schedule rows (`AvailabilityRule`, `TimeOff`) bump their
  `ClinicianProfile`; a profile insert, delete, title change or owner change bumps its `User`
  (the Practitioner is built from both). A statement changing N rows bumps the parent N times.
  Use cases re-read a profile or user touched in the same transaction before saving it.
- **Specialty list.** `CodeSystem` and `ValueSet` span all rows and rows can be deleted, so a
  one-row table `scheduling_specialty_revision` (`last_value`, advanced by a statement trigger)
  gives the `versionId`. It is a table, not a sequence, so a rolled-back change leaves no gap.
- **One FHIR Appointment for a waitlist entry and its booking.** Two tables stay.
  `Appointment.waitlist_entry` is a nullable one-to-one (`PROTECT`) and
  `Appointment.inherited_version` carries the entry's final version; `versionId` is
  `inherited_version + version` and never falls. The logical id is `waitlist_entry_id` when set.
  A check allows `inherited_version` only with an entry. Rejected: one table (breaks the
  exclusion constraints), the same id in two tables (no link), summing versions in the mapper.
- **`Notification.waitlist_entry`** gives `Communication.about` for `WAITLIST_OFFERED`.
- **Mapping lives on the model**: `fhir_resources` or `fhir_not_exposed`, exactly one, checked
  when `doc/data-model.md` is rendered. No model is renamed.

## Not covered

- Derived elements (`active` of PractitionerRole, Schedule and department Organization, offered
  start, end and practitioner of a waitlist Appointment) follow other rows; a change there does
  not move the served `versionId`.
- `BOOKED` entry implies a linked appointment and a matching `inherited_version`: accept use case.
- `queryset.update` does not set `updated_at`; the use case does.
