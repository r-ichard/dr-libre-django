Task 17d: the demo seed books through the use cases.

`seed_demo` (task 03, `scheduling/demo_seed/`) writes appointments, waitlist entries and
notifications straight through the models. The demo world therefore breaks rules the
product enforces, and a person who tries the product meets them first. This task changes
the seed and nothing else of the product.

Findings to close, each reproduced with a failing test before the fix:

1. #32 (`doc/qa/2026-11-21-round-2-clinician.md`): `WEEKDAYS_WORKED = (0, 1, 2, 3, 4)`
   opens the clinics Sunday to Thursday, because the product counts 0 as Sunday
   (`drlibre-specs.md` section 3.1). Demo clinicians work Monday to Friday.
2. Seeded appointments fall outside their clinician's availability (after 17:00, on
   weekends) and outside the 07:00 to 19:00 calendar grid. Every seeded appointment sits
   on a slot `free_slots` offers at the moment it is booked.
3. Seeded time off starts and ends at 01:00 local time, a midnight in UTC. Time off
   reads as a person would record it: whole local days or working hours.
4. Seeded notifications carry titles that are not those of section 11.

How:

5. Appointments, their status changes (checked in, completed, no-show, cancelled),
   waitlist entries and offers are made by calling the use cases of tasks 08 and 09 as
   the demo users, so each has its audit entry and its notification with the product's
   own text. A past appointment is booked with the request context's clock set before
   it; say in the plan how the seed moves that clock and that nothing else can.
6. The seed sends no email and leaves none pending for the worker to send later. Say in
   the plan how.
7. The seed stays repeatable: a second run changes no row and adds no audit entry, and a
   run on a later day moves the demo world forward without duplicating it. Seeded
   records are recognised by a marker, not by guessing from patient, clinician and type.
   Say in the plan what the marker is and why it leaks nothing through any API or page.
8. It still refuses to run with `DEBUG` off and still needs `DEMO_PASSWORD`.
9. The demo world keeps what the earlier tasks relied on: the accounts of
   `.env.example` and the README, three hospitals in three time zones, a patient with a
   password and one without, a clinician with appointments today in every status, a
   waiting and an offered waitlist entry, unread notifications. List in the plan what a
   visitor, a patient, a clinician and an admin each find on first sign-in.
10. A test runs the seed on an empty database and asserts, for every seeded appointment,
    that it lies inside an availability rule of its clinician, outside their time off,
    and breaks no constraint; and that a second run is a no-op.

No page, API route, model or use case changes. If a use case cannot do what the seed
needs, stop and say so in the reply instead of changing it.

Write the commit so that merging it closes the issue: the reply of the last stage lists
"Closes #32".

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone, and `make test` is not slower than before by more than 5 seconds.
