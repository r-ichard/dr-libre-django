Task 18: admin console, hospitals, specialties, departments, rooms, appointment types.

`drlibre-specs.md` section 10 (hospitals, specialties, departments, rooms, appointment
types, deleting) with the fields of section 3.1 and the rules of section 4, for signed-in
admins. An admin manages every hospital. Users and clinicians are task 19; appointments,
waitlist, audit log and settings are task 20; the dashboard is task 21. Impeccable mode
is on: read `PRODUCT.md`, `DESIGN.md` and the `impeccable` skill, reuse the existing
components, no inline script or style, every step works without JavaScript.

1. The console has one navigation that names its sections (dashboard, hospitals,
   specialties, departments, rooms, appointment types, and the sections tasks 19 to 21
   will add) and shows which one is current, usable with the keyboard and at 375 px.
2. For each of the five records: a list with a search by name or code, 20 rows per page
   with the total count (section 4), a page that shows one record, create, edit, and
   delete. The five lists, forms and delete steps are the same flow: build it once and
   say in the plan what is shared and what each record adds.
3. Fields are those of section 3.1, with the checks the model already holds plus what a
   column cannot say: a hospital's time zone is a zone the platform knows, latitude and
   longitude come together, a department names its hospital, a room and an appointment
   type name their department, a colour is `#rrggbb`. A taken code answers on the form,
   beside the code field, whatever the letter case and also when two admins save at the
   same moment. Every refusal keeps what the admin typed.
4. A room cannot move to another department while clinicians of the old one use it as
   their default room: the refusal names how many.
5. Delete asks for confirmation on its own page, then deletes, or is refused with
   `has_dependents` and the reasons of the table in section 10, each with its count. The
   decision is a pure function in the domain layer, under the mutation gate. A dependent
   that appears between the check and the delete is still a refusal, never a 500.
6. Every write is a use case that takes the admin from the session, writes its audit
   entry in the same transaction and raises the record's version (ADR 0003). Audit
   metadata holds ids and the names of changed fields, nothing else. An edit that changes
   nothing writes nothing.
7. Two admins who edit the same record: the second save does not silently undo the
   first. Say in the plan how the form carries the version it read and what the second
   admin sees.
8. What the public search and the booking pages offer follows these records at once and
   through the same loading: test that an inactive hospital, specialty, room and
   appointment type stop being offered, and that a new appointment type of a department
   with available clinicians is offered.
9. Changing a hospital's time zone moves nothing that is stored, but its availability is
   read in the new zone from then on. The edit form says so when the hospital has
   upcoming appointments, with their count.
10. A new specialty has no vendored icon and shows the fallback one; the page that shows
    a specialty says which icon it uses.
11. A patient, a clinician and a visitor reach none of these pages: forbidden page or
    sign-in, by the rules of section 12.3. Test each role on each route, and derive the
    routes from the URL configuration so a new one is covered.
12. Every new route joins the hostile-input test of task 17a. Accessibility to WCAG 2.2
    level AA and 375 px to 1440 px. Test what the server can prove in the rendered HTML.
    Every form is tested as a browser sends it.

The sandbox has no browser. The orchestrator creates a hospital with a department, a
room and an appointment type as the demo admin in Chrome, watches the public search
follow, and tries each refused delete.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
