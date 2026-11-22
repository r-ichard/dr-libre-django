Task 19: admin console, users and clinicians.

`drlibre-specs.md` section 10 (users, clinicians, deleting) with the fields of section
3.1 and the rules of sections 4 and 12, for signed-in admins, on top of task 18: reuse
its list, form and delete flow and its navigation. Impeccable mode is on: read
`PRODUCT.md`, `DESIGN.md` and the `impeccable` skill, reuse the existing components, no
inline script or style, every step works without JavaScript.

Users:

1. List with a search by name or email, 20 rows per page with the total count. Create
   with name, email, role and a temporary password. Edit name, email, role and the
   active flag. An email is unique whatever its letter case and stored in lower case.
2. A password is 10 to 72 characters, is stored only as its hash, and appears in no page
   after the form is sent, no audit entry and no log line. Prove each with a planted
   value. Say in the plan how the person replaces a temporary password: a patient has the
   page of task 15; a clinician and an admin need one too.
3. An admin cannot deactivate their own account or change their own role. The last
   active admin cannot be deactivated or given another role, also when two admins act at
   the same moment.
4. Deactivating a user ends their sessions at once (section 12.2) and their unused
   sign-in links. The confirmation says how many upcoming appointments a clinician or a
   patient still has; they stay booked.
5. A changed email address is a new address nobody has proven: say in the plan what
   happens to the time the email was verified, to open sessions and to unused sign-in
   links, so that a link sent to the old address cannot open the account.
6. A role change never leaves a record that contradicts the role: a clinician with a
   profile, a patient with appointments. Refuse it with the reasons.
7. Delete follows the table of section 10: refused for the admin's own account, a user
   with appointments as patient or clinician, or a user who is the actor of audit
   entries, with the reasons and the advice to deactivate instead.

Clinicians:

8. Attach a profile to an active Clinician user who has none: department, specialty
   (active), title, optional bio, optional default room (an active room of that
   department), round robin weight (an integer of at least 1, default 1). Edit the same
   fields. A clinician with upcoming appointments, availability rules or a default room
   cannot move to another department: refused with the reasons (section 3.2).
9. The list shows each clinician with department, specialty, active flag and a summary
   of weekly availability, with the search and the paging of the other lists.
10. Each clinician has a read-only week calendar: the time grid of the clinician
    workspace, with previous and next week, no action, and never a clinical note.
11. Deleting a profile is refused while it has appointments (section 10).

Everywhere:

12. Every write is a use case that takes the admin from the session, writes its audit
    entry in the same transaction and raises the record's version. Audit metadata holds
    ids and the names of changed fields: never a name, an email address, a phone number
    or anything of a password. An edit that changes nothing writes nothing. Two admins
    who edit the same record: the second save does not silently undo the first.
13. Each rule above that needs no stored data is a pure function in the domain layer,
    under the mutation gate.
14. A patient, a clinician and a visitor reach none of these pages. Every new route
    joins the role test and the hostile-input test of the earlier tasks. Every audit
    action has its plain words; no page holds the same element id twice.
15. What the public search offers follows at once: a deactivated clinician and a
    clinician whose profile was just attached. Test both through the search use case.
16. Accessibility to WCAG 2.2 level AA and 375 px to 1440 px. Test what the server can
    prove in the rendered HTML. Every form is tested as a browser sends it.

The sandbox has no browser. The orchestrator creates a clinician user, attaches a
profile, signs in as that clinician, deactivates the account from the admin console and
watches the clinician's session end.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone, and `make test` stays under 30 seconds in the sandbox.
