Area: the public surface, privacy and abuse limits.

Specification: `drlibre-specs.md` sections 6, 7.1, 7.2, 7.5, 7.6, 7.7 and the public rows
of section 14. Everything here is reachable with no session.

Try at least:
- Search (6.1 to 6.5): text matching, each filter alone and combined, each sort and its
  tie order, paging and page sizes, a page past the end, junk in every parameter, what is
  listed and what must not be (inactive hospital, clinician or specialty, a type not
  bookable online). The slots a result shows must be bookable.
- Detail pages and their API (6.6): the same, plus ids of inactive or unbookable records.
- Nothing private in any public answer or page: a clinician's email, phone or birth
  date, anything about a patient, an internal field. Compare the answers with the
  database rows.
- Booking without signing in (7.1, 7.2): the hold, its 10 minutes, one hold per address,
  the code (6 digits, 10 minutes, 5 attempts, resend), a correct code, replay, a staff
  address, an existing patient, a taken slot, an expired hold. Guess the code within the
  limits and work out the odds.
- Enumeration: can any answer, status, timing or email tell whether an address has an
  account? Compare a new address, a patient and a staff address on every public route.
- Rate limits (7.5): per address and per network address, on holds, codes and sign-in
  links. Find a public route that sends email or costs the server work without a limit.
- Emails (7.6) in `scratch/qa/mail.log`: what each contains, that none holds the reason
  for the visit or a note, and that only the sign-in link email signs its reader in.
- Logs and audit rows after all of the above: no address, name, phone, birth date,
  reason, code or token in `scratch/qa/server.log`, `scratch/qa/worker.log` or the audit
  table.
- Robustness: malformed requests, very long values, wrong content types. No 500.
