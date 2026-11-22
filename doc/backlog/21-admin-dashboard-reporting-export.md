Task 21: admin console, dashboard, reporting and the CSV export.

`drlibre-specs.md` section 10 (dashboard) and section 13 (reporting, CSV export), for
signed-in admins, on top of tasks 18 to 20. Impeccable mode is on: read `PRODUCT.md`,
`DESIGN.md` and the `impeccable` skill, reuse the existing components, no inline script
or style, every step works without JavaScript.

Figures:

1. Each figure of the table in section 13 is a pure function in the domain layer, under
   the mutation gate, with the table's definition as its tests: appointments,
   cancellations, utilisation, no-show rate, online share, waitlist size. A ratio whose
   denominator is zero is "n/a", never 0 %.
2. Utilisation divides the minutes of active appointments inside the range by the
   available minutes: the availability rule hours of active clinicians in the range
   minus their time off. Test a range that crosses a daylight saving change, a rule that
   starts or ends inside the range, and time off that covers part of a day.
3. The hospitals sit in several time zones and the specification says "ending today".
   Say in the plan which day an appointment is counted on and what "today" is, and write
   the rule on the page. An appointment is counted once, whatever the zone of the reader.

Dashboard:

4. A range of today, 7 days (the default) or 30 days, ending today, chosen in the
   address; an unusable value falls back to 7 days.
5. The tiles of section 13, a bar chart of appointments per day, and the 5 busiest
   clinicians of the range.
6. The chart is drawn by the server with no script and no inline style, and the same
   numbers are in a table a screen reader and a 375 px screen can use. Colour is never
   the only signal. Say in the plan how a bar gets its height under the content security
   policy.
7. The dashboard loads with a bounded number of queries whatever the number of
   appointments: say the number in the plan and assert it in a test.

Export:

8. The appointment list of task 20 exports its whole filtered set as CSV with the
   columns of section 13, instants in ISO 8601 UTC, ids only: no name, no email address,
   no reason, no free text.
9. A cell that starts with `=`, `+`, `-` or `@` is prefixed with an apostrophe. The
   escaping is a pure function under the mutation gate, applied to every cell.
10. The export is audited with the row count, in the same transaction as the read it
    reports. It is asked for with a form, not a link, so another site cannot make an
    admin's browser write audit entries. The answer is never cached and names its file.
11. A large set is streamed or refused with a message: say the limit in the plan.

Everywhere:

12. A patient, a clinician and a visitor reach none of these pages. Every new route
    joins the role test and the hostile-input test of the earlier tasks. Every audit
    action has its plain words; no page holds the same element id twice.
13. Empty states: a range with no appointment shows zeros and "n/a", not an error.
    Accessibility to WCAG 2.2 level AA and 375 px to 1440 px. Every form is tested as a
    browser sends it.

The sandbox has no browser. The orchestrator opens the dashboard as the demo admin in
Chrome at 375 px and 1440 px, checks two figures against the database by hand, and
opens the export in a spreadsheet reader.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone, and `make test` stays under 30 seconds in the sandbox.
