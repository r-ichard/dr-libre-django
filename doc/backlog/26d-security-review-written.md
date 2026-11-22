Task 26d: the security review, written down.

Last part of the hardening (`doc/backlog/26-security-hardening.md` holds the whole list),
after tasks 26a to 26c: decisions and the review document. Prose, and a test only where
an item says so. No product behaviour changes unless the plan shows it is small.

Decided in writing, `doc/adr/0010-security-review.md` and `doc/security-review.md`:

16. Encryption at rest for clinical notes and for a visitor's details in a booking hold:
    what protects them today, what a deployment must add, and the choice left to the
    owner. No code unless the plan shows it is small and needs no new dependency.
17. The server: the container runs Django's development server and file server, also
    with `DEBUG` off. Say what that is safe for and what a deployment would replace.
18. The review document: for each rule of specification sections 4, 11 and 12, where it
    is enforced and which test holds it; the table of item 10; the limits of ADR 0004;
    what was not reviewed.
19. The questions for the owner that the build collected (`doc/backlog.md`, "Owner to
    confirm", and the open points of ADR 0005 to 0009), each with the choice the
    product makes today and what changing it would cost, in one list at the end of
    the review document.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
