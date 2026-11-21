Task 12a: booking pages.

The screens of `drlibre-specs.md` section 7.1 on top of the use cases of tasks 07 and 12:
from a chosen appointment type and provider to a booked appointment, for a visitor and
for a signed-in patient. The search and public pages that lead here are tasks 10a and 11;
this task defines the addresses they will link to. Impeccable mode is on: read
`PRODUCT.md`, `DESIGN.md` and the `impeccable` skill, reuse the components of task 05a,
no inline script or style, every step works without JavaScript.

1. Times. A page for one appointment type and one provider, or "first available" in the
   type's department, showing a week of free slots, Monday to Sunday, with previous and
   next week, in the hospital's time zone, which the page names. It names the type, its
   duration, the provider and the hospital with its address. Each slot leads to the next
   step. Build the week strip as a component: the provider page, the patient's reschedule
   and the booking wizard will reuse it.
2. Details, for a visitor: full name, date of birth, email, optional phone, optional
   reason, acceptance of the terms and privacy notice. The chosen appointment stays
   visible. Errors are tied to their fields and the first invalid one is focused.
   Submitting creates the hold.
3. Code. The page says where the code was sent, without repeating more of the address
   than the visitor needs to recognise it, that it is valid for 10 minutes, and offers
   to send a new one. A wrong code, a used-up code and an expired hold each say what to
   do next.
4. Confirmation, after the code: the appointment with whom (provider, title, specialty),
   when (date, start and end, time zone named) and where (hospital, address, department,
   room when assigned), that a confirmation email was sent, a calendar file to download
   and a link to the patient's appointments.
5. A signed-in patient skips details and code: one review page with the optional reason
   and a confirm button.
6. Calendar file. Each appointment downloads as an iCalendar event for its patient: start
   and end in UTC, the provider and type as the summary, the hospital address as the
   location, never the reason or notes. Only the appointment's patient may download it.
7. Every refusal has its message and a way forward: the slot was taken meanwhile (with a
   link back to the refreshed times), a booking rule (each rule in plain words), the rate
   limit, the mail server being down, a hold that expired.
8. No personal detail travels in an address: the details go by POST and the pages after
   it are addressed by the hold. Pages that show personal data are never cached.
9. Accessibility to WCAG 2.2 level AA and 375 px to 1440 px, as in task 05a. Test what
   the server can prove in the rendered HTML.

Every form is tested as a browser sends it, with the helper of task 13a
(`scheduling/views/pages/browser_support.py`).

The sandbox has no browser. The orchestrator books in Chrome as a visitor and as a
patient, at 375 and 1440 px, with the keyboard only, and runs an accessibility audit.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
