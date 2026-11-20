# DrLibre: functional specification

This document describes what the product does, not how it is built. It is meant to be
enough to rebuild the product from scratch in any language and stack.

Sections marked **[existing]** describe behaviour the current apt-clinic application
already has. Sections marked **[new]** describe additions: several hospitals, a public
search engine, booking without an account, and a FHIR API. Where a new feature changes an
existing rule, the change is stated in the new section.

## 1. Purpose

DrLibre is an appointment scheduling product for hospitals. Anyone can search hospitals,
clinicians and specialties, see the next free appointment times, and book one without
signing in or choosing a password. Booking with an email address makes that person a
patient with an account: they sign in through a link sent to that address and see all
their appointments in a portal.
Clinicians run their day, calendar and availability. Administrators manage the
organisation, the waitlist and the audit log, and watch utilisation. Every write is
recorded in an append-only audit log. Every concept is also available through a FHIR API.

## 2. Actors

| Actor | Signed in | What they do |
| --- | --- | --- |
| Visitor **[new]** | No | Searches, views public profiles and free slots, starts a booking and proves control of an email address to finish it |
| Patient | Yes: by a sign-in link sent by email (passwordless, 24 hour session) **[new]**, or by password | Sees all own appointments, books, reschedules, cancels, joins the waitlist, reads notifications, edits profile |
| Clinician | Yes | Works own agenda, updates appointment status, writes notes, manages own availability and time off |
| Admin | Yes | Manages hospitals, departments, rooms, specialties, appointment types, users and clinicians; books for patients; manages waitlist; reads audit log and dashboard |
| API client **[new]** | Token | Reads and writes through the FHIR API with the rights of the user the token belongs to |

There is no separate guest **[new]**. A visitor who books becomes a patient the moment
their email address is verified (section 7). A *passwordless patient* is a patient with no
password. They have the same rights as any other patient and sign in through a link sent
to their email address.

The public word for Clinician is "provider". The domain name stays Clinician.

## 3. Domain model

Identifiers are opaque strings. All instants are stored in UTC. Every record carries
creation time, last update time and, where a signed-in user created it, the creator.

### 3.1 Concepts

**Hospital [new].** Name, unique code, description, street address, postal code, city,
country, phone, time zone, optional latitude and longitude, active flag. Owns departments.

**Department.** Name, unique code, optional description. Belongs to one hospital
**[new]**. Owns clinicians, rooms and appointment types.

**Specialty [new].** Name, unique code, active flag. Replaces the free-text specialty the
current application stores on the clinician.

**User.** Email (unique, stored lower case), password hash, full name, role (Admin,
Clinician, Patient), active flag, optional phone, optional date of birth, last login time.
**[new]** A patient may have no password (a passwordless patient) and carries the time
their email was verified.

**Clinician profile.** One per Clinician user. Department, specialty, title, optional bio,
optional default room, round robin weight (integer, at least 1, default 1), time of last
round robin assignment.

**Room.** Name, unique code, floor, capacity (at least 1), equipment list, active flag,
department.

**Appointment type.** Name, unique code, duration in minutes (at least 1), department,
whether it needs a room, buffer minutes after the visit (0 or more), display colour,
active flag, whether patients may book it online.

**Availability rule.** A weekly recurring window for one clinician: weekday (0 Sunday to
6 Saturday), start and end time of day (HH:MM, end after start), slot step in minutes (5
to 240), optional room, valid-from date, optional valid-to date.

**Time off.** A period during which one clinician is unavailable: start, end (after
start), optional reason (up to 200 characters).

**Appointment.** Patient, clinician, appointment type, optional room, start, end, status,
source, optional reason given by the patient, optional clinical notes (up to 5000
characters), cancellation time and cancellation reason.

- Status: `BOOKED`, `CONFIRMED`, `CHECKED_IN`, `COMPLETED`, `CANCELLED`, `NO_SHOW`.
- Source: `ONLINE` (the patient booked a named clinician), `ROUND_ROBIN` (the patient
  booked "first available"), `STAFF` (a clinician or admin booked for the patient).
- An appointment is *active* unless it is `CANCELLED` or `NO_SHOW`.

**Waitlist entry.** Patient, appointment type, optional preferred clinician, earliest and
latest acceptable time (latest after earliest), status (`WAITING`, `OFFERED`, `BOOKED`,
`EXPIRED`), and the freed appointment whose slot is currently offered.

**Notification.** Recipient user, kind (appointment reminder, appointment cancelled,
schedule changed, waitlist offered, waitlist booked), title, body, optional appointment,
read time.

**Audit log entry.** Actor (may be empty for failed logins and for steps taken before an
email address is verified), action name,
entity type, entity id, metadata, time, correlation id. Entries are never changed or
deleted.

**Session.** A signed-in browser session: user, expiry, user agent. Only a hash of the
session token is stored.

**Booking hold [new].** A temporary reservation of one slot for a visitor who is verifying
their email: clinician, appointment type, start, end, the details the visitor typed,
expiry.

**Verification code [new].** A one-time code sent to an email address: hashed code,
email, purpose, expiry, attempts used.

**Sign-in link [new].** A one-time link sent to a patient's email address: hashed token,
patient, expiry, time used.

### 3.2 Relationships

- Hospital 1 to many Department. Department 1 to many Clinician profile, Room,
  Appointment type.
- A clinician works in exactly one department, so in exactly one hospital.
- An appointment's clinician and type belong to the same department.
- A room used by an appointment is active when the booking is made.

## 4. Rules that apply everywhere **[existing]**

- **Validation at every boundary.** Every input is validated. Unknown fields are
  rejected on writes. Unusable values in a page address (page number, filter, date) fall
  back to the default instead of failing the page.
- **Identity comes from the session or token, never from the request body.** A patient
  cannot name another patient. A clinician cannot name another clinician.
- **Every write is audited** in the same transaction as the write. If the audit entry
  cannot be written, the write does not happen. Audit metadata holds ids, counts, status
  values and the names of changed fields. It never holds names, emails (only the email
  domain for login events), phone numbers, birth dates, reasons or clinical notes.
- **One transaction per logical change**, including its audit entry and notifications.
- **Expected failures are results, not crashes**, with these codes:

| Code | Meaning | HTTP status |
| --- | --- | --- |
| `invalid_input` | Validation failed; carries a list of field messages | 400 |
| `unauthenticated` | No valid session or token | 401 |
| `forbidden` | Signed in, not allowed | 403 |
| `not_found` | No such record, or it is inactive | 404 |
| `conflict` | Overlap; lists the resources in conflict (clinician, patient, room) | 409 |
| `no_room_available` | The type needs a room and none is free | 409 |
| `no_clinician_available` | Round robin found nobody free | 409 |
| `invalid_transition` | The status change is not allowed; carries the current status | 409 |
| `has_dependents` | Delete refused; lists what still uses the record | 409 |
| `rule_violation` | A booking rule failed; lists the violated rules | 422 |

- **Time.** Times are shown in the time zone of the hospital the appointment is in
  **[new]** (the current application has one clinic time zone, Europe/Paris by default).
  The page states the time zone. Weekly availability is defined in local wall-clock time
  and stays correct across daylight saving changes.
- **Correlation id.** Each request has a correlation id, taken from the
  `x-correlation-id` request header or generated. It is returned on the response and
  stored on audit entries and logs.
- **Lists** in the admin console show 20 rows per page with a total count.

## 5. Scheduling engine **[existing]**

### 5.1 Free slots

For a clinician, an appointment type and a time range:

1. For each local day in the range, take the clinician's availability rules for that
   weekday that are valid on that day.
2. For each rule, propose starts from the rule's start time, stepping by the rule's slot
   step, while start plus the type's duration is not after the rule's end time. Each slot
   lasts the type's duration.
3. Drop a slot that starts before the range, ends after the range, starts in the past,
   overlaps time off, or overlaps an active appointment of that clinician. For this
   check each existing appointment is extended at its end by the buffer minutes of the
   type being booked.
4. Remove duplicate starts and sort ascending.

A slot query covers at most 31 days. With no clinician named, the result is the union of
the free slots of every active clinician in the type's department, one entry per start
time.

### 5.2 Placing an appointment

All booking paths (patient, staff, round robin, waitlist acceptance) run the same
steps in this order and stop at the first failure:

1. The type is active, the clinician's user is active, and both are in the same
   department. Otherwise `not_found`.
2. A room named in the request (staff only) must be active.
3. **Conflicts.** No active appointment may overlap the new one for the same clinician,
   the same patient, or the same named room. Otherwise `conflict`.
4. **Booking rules** (5.3). Otherwise `rule_violation`.
5. **Room.** If the type needs a room and none was named: the clinician's default room if
   free, otherwise the first free active room of the department in code order. None free
   gives `no_room_available`. Types that need no room get none.
6. Create the appointment with status `BOOKED`, end equal to start plus the type's
   duration, write the audit entry, notify the patient.

The end time is never accepted from the caller.

### 5.3 Booking rules

| Rule | Applies to | Violation |
| --- | --- | --- |
| Start is at least 120 minutes from now | Patients, on book and reschedule | `lead_time_too_short` |
| The appointment starts 24 hours or more from now | Patients, on cancel and reschedule | `cancellation_window_closed` |
| The patient holds fewer than 3 open online bookings (future, active, source `ONLINE` or `ROUND_ROBIN`) | Patients, on book | `too_many_open_bookings` |
| The type allows online booking | Patients, on book and reschedule | `type_not_bookable_online` |
| The slot is exactly one of the free slots (5.1) | Everyone, on book and reschedule | `outside_availability` |

Staff are bound only by availability and conflicts. The three numbers are policy
constants shown read-only in the admin settings page.

### 5.4 Who may book for whom

- A patient books for themself only and cannot choose a room.
- A clinician books only into their own calendar and must name an active patient.
- An admin books for any active patient with any clinician. Admin booking always names a
  clinician; "first available" is not offered to staff.

### 5.5 First available (weighted round robin)

When a patient books a type at a start time without naming a clinician:

1. Candidates are the active clinicians of the type's department with weight above 0 and
   a free slot at that start.
2. Rank them: a clinician never assigned before comes first; then the largest value of
   (time since last assignment × weight); ties go to the lowest id.
3. Book with the first candidate (5.2), source `ROUND_ROBIN`, and set that clinician's
   last assignment time to now.
4. No candidate gives `no_clinician_available`.

### 5.6 Appointment status

Allowed changes:

| From | To |
| --- | --- |
| `BOOKED` | `CONFIRMED`, `CHECKED_IN`, `CANCELLED`, `NO_SHOW` |
| `CONFIRMED` | `CHECKED_IN`, `CANCELLED`, `NO_SHOW` |
| `CHECKED_IN` | `COMPLETED`, `CANCELLED` |
| `COMPLETED`, `CANCELLED`, `NO_SHOW` | none |

- **Check in, complete, mark no-show:** staff only. A clinician acts on own appointments,
  an admin on any. No notification.
- **Cancel:** the patient (own appointment, 24 hour rule), the appointment's clinician, or
  an admin. A reason is required. Records cancellation time and reason, notifies the
  patient, then runs waitlist matching (5.8).
- **Reschedule:** only `BOOKED` or `CONFIRMED`. Same clinician and type, new start. Runs
  conflicts and booking rules with the appointment itself ignored, reassigns the room
  preferring the current one, notifies the patient.
- No action sets `CONFIRMED` in the current application (see section 16).

### 5.7 Reminders

A reminder job creates one reminder notification for each appointment that starts within
the next 24 hours, has status `BOOKED` or `CONFIRMED`, and has no reminder yet. Running it
twice reminds nobody twice. An admin can run it from the settings page or the API; it
should also run on a schedule. It writes one audit entry with the count when it created
any.

### 5.8 Waitlist

- **Join.** A patient joins for themself; an admin may add a patient; clinicians cannot.
  The type must be active and a preferred clinician, if named, must be active.
- **Automatic offer.** When an appointment is cancelled, take the `WAITING` entries for
  the same type whose preferred clinician is empty or is the freed clinician and whose
  window contains the freed slot. The oldest entry wins (ties: lowest id). It becomes
  `OFFERED`, linked to the freed appointment, and the patient is notified.
- **Manual offer.** An admin can offer a `WAITING` entry the first future cancelled slot
  of the same type inside its window, provided that clinician is still free then and no
  other entry holds that offer.
- **Accept.** The patient (own entry) or an admin accepts an `OFFERED` entry. A new
  appointment is placed (5.2) for the offered clinician, type and start, so conflicts and
  booking rules still apply. The entry becomes `BOOKED` and the patient is notified.
- An offer does not reserve the slot. If someone else books it first, accepting fails
  with `conflict`.
- **Expiry.** A `WAITING` entry whose latest time has passed becomes `EXPIRED`.

## 6. Public search **[new]**

Open to everyone, no sign-in. The landing page of the product is the search.

### 6.1 What can be searched

One search box and a set of filters. The text matches, case-insensitively and on partial
words: hospital name, city, clinician name, specialty name, department name and
appointment type name. Results come in three lists the visitor switches between:

- **Providers** (clinicians)
- **Hospitals**
- **Specialties**

Only public, bookable data appears: active hospitals, active clinicians, active
specialties, and active appointment types that allow online booking. A clinician with no
online-bookable type in their department is not listed.

### 6.2 What each result shows

| Result | Shown | Next availabilities |
| --- | --- | --- |
| Provider | Full name, title, specialty, hospital, department, city | The next 3 free slot starts, each one bookable in one click, and a link to all times |
| Hospital | Name, address, city, specialties offered, number of bookable providers | The earliest free slot in the hospital and the number of providers with a free slot in the horizon |
| Specialty | Name, number of providers, number of hospitals | The earliest free slot across all its providers |

Never shown publicly: clinician email, phone, date of birth, anything about patients.

**Which appointment type the times are for.** If the visitor filtered on an appointment
type, slots are computed for that type. Otherwise they are computed for the shortest
active online-bookable type of the clinician's department, and the result names that
type.

**Horizon.** Next availabilities are looked for from now plus the 120 minute lead time up
to 90 days ahead. A result with nothing free in the horizon is still listed, after the
results that have a free slot, with the text "No availability in the next 90 days".

Slots shown are exactly the slots booking would accept at the moment the list was built.
Booking checks again, so a slot taken in the meantime fails cleanly with a message and a
refreshed list.

### 6.3 Filters

All filters combine with AND. Each is optional.

- Specialty
- Hospital
- City
- Appointment type
- Earliest date ("available on or after")
- Availability window: any, today, within 3 days, within 7 days
- Time of day: morning (before 12:00), afternoon (12:00 to 17:00), evening (after 17:00),
  in the hospital's time zone

A time filter changes both which results are listed and which slots are shown on them.

### 6.4 Sorting

- Soonest availability (default)
- Name, A to Z
- Name, Z to A
- Distance, nearest first, only when the visitor gave a location and hospitals have
  coordinates

Sorting is over the whole result set, not within a page. Ties break on name, then id, so
the order is stable.

### 6.5 Pagination

20 results per page by default; the visitor may choose 10, 20 or 50. The page shows the
total count, the current page and the page count. Search text, filters, sort, list and
page all live in the page address, so a search can be shared and the back button works.
An out-of-range page shows the last page.

### 6.6 Public detail pages

- **Provider page:** name, title, specialty, bio, hospital and department, the
  online-bookable appointment types, and a week-by-week strip of free slots for the
  chosen type (Monday to Sunday, previous and next week).
- **Hospital page:** name, address, phone, description, departments, specialties,
  providers, and for each provider the next free slots. Offers "first available" per
  appointment type.
- **Specialty page:** the provider list filtered on that specialty.

## 7. Booking without signing in: passwordless patients **[new]**

A visitor who picks a slot from search or a public page can book it without signing in
and without ever choosing a password. There is no guest status: verifying an email
address makes the visitor a patient with an account. A patient without a password is a
*passwordless patient* and signs in through a link sent to their email address.

### 7.1 Booking flow

1. **Choose.** Appointment type, then a named provider or "first available" in a
   department, then a slot.
2. **Details.** Full name, date of birth, email, optional phone, optional reason for the
   visit, and acceptance of the terms and privacy notice.
3. **Hold.** Submitting the details creates a booking hold on the slot for 10 minutes. A
   held slot is not offered to anyone else and counts as a conflict. An expired hold
   frees the slot. One open hold per email address at a time.
4. **Verify.** A 6 digit code is sent to the email address. It is valid for 10 minutes
   and allows 5 attempts. A new code can be requested at most 3 times per hour per email.
5. **Book.** With a correct code the appointment is placed (5.2) for the patient
   identified by that email (7.2), with source `ONLINE` or `ROUND_ROBIN`. The hold is
   removed.
6. **Signed in.** The correct code also signs the patient in with a 24 hour session
   (7.3). The confirmation page shows the appointment and a calendar file, and links to
   the patient's appointments. A confirmation email is sent.

If the code is never entered, nothing is booked, no account is created and the hold
expires. A patient who is already signed in skips steps 2 to 4.

### 7.2 The patient account

- If no user has that email, a Patient user is created with the given name, birth date
  and phone, no password, and the email marked verified. This is a passwordless patient.
- If an active Patient user has that email, with or without a password, the booking is
  made for that patient. The details typed in the form do not change the existing
  profile.
- If the email belongs to an Admin, a Clinician or an inactive user, the booking is
  refused with a generic message that does not reveal why.

A passwordless patient is a Patient in every respect: same portal (section 8), same
booking rules (5.3), same access rules. The only difference is how they sign in.

### 7.3 Signing in with an email link

1. On the sign-in page the patient enters their email address and asks for a sign-in
   link.
2. If the address belongs to an active Patient user, a link is sent to it. In every
   other case nothing is sent. The page shows the same message either way, so it never
   reveals whether an address has an account.
3. The link is valid for 15 minutes and works once. Asking for a new link cancels the
   earlier ones. At most 3 links per hour per email address.
4. Opening the link shows a "Continue" button. The link is used only when the button is
   pressed, so mail scanners that open links do not use it up. The patient then lands on
   a clean address that no longer contains the link's token.
5. The patient is signed in with a session that lasts 24 hours and is not extended.
   After that they ask for a new link.

Rules:

- Sign-in by link is for the Patient role only. Admins and clinicians sign in with a
  password.
- A patient who has a password may use either way. A session opened by link lasts 24
  hours whichever kind of patient opened it.
- Only a hash of the link's token is stored. The token never appears in logs.
- An account exists once an email address has been verified in a booking (7.1). Asking
  for a sign-in link with an address that has never booked creates nothing.

### 7.4 What the session shows

The patient lands on their appointments (section 8): every appointment booked with that
email address, upcoming and past, each with

- **whom:** the provider's name, title and specialty,
- **when:** date, start and end time, in the hospital's time zone, which is named,
- **where:** hospital name and address, department, and room when one is assigned,

plus the appointment type and status. From there the patient has the whole patient
portal: book again without retyping details or verifying, reschedule, cancel, download
the calendar file, join the waitlist, read notifications and edit their profile. A
passwordless patient has no password to change.

### 7.5 Rules and limits

The booking rules of 5.3 apply from the first booking: 120 minute lead time,
online-bookable types only, at most 3 open online bookings per patient (so per verified
email address), 24 hour window for cancelling and rescheduling.

Additional limits, because these endpoints are public:

- Holds, code requests and sign-in link requests are rate limited per email address and
  per network address.
- Responses never reveal whether an email address already has an account.
- Before the code is verified, nothing about the patient or their other appointments is
  returned.

### 7.6 Email

A passwordless patient may not be signed in when something happens, so every patient
notification is also sent by email: booking confirmation, reschedule, cancellation,
reminder, waitlist offer. The verification code and the sign-in link are sent by email
only. Emails about an appointment carry the time, the hospital and the provider name.
They never carry the reason for the visit or clinical notes. Apart from the sign-in link
email itself, emails link to the sign-in page and never contain a link that signs the
reader in.

### 7.7 Audit

Hold created, hold expired, code verification failed, patient account created, booking
made, sign-in link requested, sign-in link used and sign-in link refused are all audited,
with the email domain only. Before verification the actor is empty; after it, the actor
is the patient.

## 8. Patient portal **[existing]**

For signed-in patients, whether they signed in by email link or by password.

- **Home.** Greeting, the next upcoming appointment, count of unread notifications, a
  "Book an appointment" action.
- **Book.** A four step wizard: service (appointment type, grouped by department),
  clinician (a named one or "first available"), time (week strip of free slots), review
  and confirm with an optional reason. **[new]** The wizard starts from the same search
  and public pages that visitors use; a signed-in patient skips the details and
  verification steps.
- **Appointments.** Two lists. Upcoming: status `BOOKED`, `CONFIRMED` or `CHECKED_IN` and
  not yet started, soonest first. Past: everything else, latest first. Each row shows
  whom (clinician and specialty), when (time, with the time zone named), where (hospital
  name and address **[new]**, department, room), type, status and reason, and offers
  cancel and reschedule when the rules allow them.
- **Reschedule.** Week strip of free slots for the same clinician and type.
- **Cancel.** Confirmation dialog with a required reason.
- **Calendar file.** Each appointment downloads as an iCalendar (`.ics`) event.
- **Waitlist.** Form to join (type, optional preferred clinician, date window) and the
  list of own entries with status. An offered entry shows the offered time and an accept
  button.
- **Notifications.** In-app list, newest first, with mark as read.
- **Profile.** Name and email shown. Phone (7 to 20 characters of digits, spaces,
  `+ ( ) -`) and date of birth (a real date, not in the future) are editable; empty input
  clears them. Change password needs the current password and a different new one of 10
  to 72 characters; passwordless patients do not see it **[new]**.

## 9. Clinician workspace **[existing]**

For signed-in clinicians. A clinician sees and changes only their own calendar.

- **Today.** The agenda for one day, with previous, next and today navigation. Tiles:
  appointments (cancelled ones counted separately), completed, no-shows, next free slot.
  Appointments are grouped by hour, each with patient, type, room, status and the status
  actions currently allowed.
- **Calendar.** A week grid from 07:00 to 19:00 in 30 minute rows showing active
  appointments in the colour of their type, and time off blocks.
- **Appointment.** Patient name, phone and age, time, type, room, reason, status. Actions:
  check in, complete, no-show, cancel. Clinical notes (saved separately, visible to this
  clinician only). Reschedule for the patient from a week strip. History: the audit
  entries of this appointment in time order. Opening another clinician's appointment
  shows "Not your appointment".
- **Availability.** List, create, edit and delete own availability rules. A rule's room
  must be an active room of the clinician's department. Two rules of the same clinician
  on the same weekday may touch but not overlap. A new rule is valid from today with no
  end date. List, create and delete own time off; an identical period cannot be recorded
  twice. Time off does not cancel appointments already booked in it.
- **Patients.** Patients who have at least one appointment with this clinician, with
  phone, last visit and next visit, and a search by name.
- **Rooms.** A day timeline, 07:00 to 19:00, of the active rooms of the clinician's
  department. Own appointments show the patient name; others show only "Occupied".

## 10. Admin console **[existing, extended]**

For signed-in admins.

- **Dashboard.** Range: today, 7 days (default) or 30 days, ending today. KPI tiles as
  defined in section 13, a bar chart of appointments per day, and the 5 busiest
  clinicians.
- **Hospitals [new].** Create, read, update, delete, list with search.
- **Specialties [new].** Create, read, update, delete, list with search.
- **Departments, rooms, appointment types.** Create, read, update, delete, list with
  search. Codes are unique. A room cannot move to another department while clinicians of
  the old one use it as default room.
- **Users.** List with search by name or email. Create with name, email, role and a
  temporary password. Edit name, email, role and active flag. An admin cannot deactivate
  their own account or change their own role.
- **Clinicians.** Attach a profile to an active Clinician user who has none: department,
  specialty, title, bio, default room (an active room of that department), round robin
  weight. The list shows a summary of weekly availability. Each clinician has a read-only
  week calendar.
- **Deleting.** Delete always asks for confirmation and is refused with the reasons when
  something depends on the record:

| Record | Cannot be deleted while |
| --- | --- |
| Hospital **[new]** | It has departments |
| Department | It has clinicians, rooms or appointment types |
| Specialty **[new]** | A clinician has it |
| Room | It has appointments, availability rules, or is a clinician's default room |
| Appointment type | It has appointments or waitlist entries |
| Clinician profile | It has appointments |
| User | It is the admin's own account, has appointments as patient or clinician, or is the actor of audit entries. Deactivate instead. |

- **Appointments.** List filtered by date range, department, clinician, status and
  source, newest first. Export the whole filtered set as CSV (section 13). Book for a
  patient: pick the patient by name or email, then the same wizard without "first
  available" and including types that are not bookable online. Reschedule any
  appointment.
- **Waitlist.** List filtered by status, oldest first. Manual offer on a waiting entry.
- **Audit log.** Read-only list, newest first, filtered by actor, entity type and date
  range. Shows time, actor, action, entity and correlation id.
- **Settings.** The booking policy constants, read-only, and a button that runs the
  reminder job.

## 11. Notifications **[existing]**

Created in the same transaction as the event, for the patient:

| Event | Kind | Title |
| --- | --- | --- |
| Appointment booked | Schedule changed | Appointment booked |
| Appointment rescheduled | Schedule changed | Appointment rescheduled |
| Appointment cancelled | Appointment cancelled | Appointment cancelled |
| Waitlist slot offered | Waitlist offered | Waitlist slot offered |
| Waitlist offer accepted | Waitlist booked | Waitlist slot booked |
| Reminder job | Appointment reminder | Appointment reminder |

In-app notification text carries the time only: no names, reasons or emails.
**[new]** Each notification is also sent to the patient by email (7.6).

## 12. Sign-in, sessions and access

### 12.1 Sign-in with a password **[existing]**

- Email and password. Passwords are stored with a slow salted hash.
- A wrong email and a wrong password give the same message and take the same time.
- An inactive user cannot sign in.
- After 10 failures in 15 minutes for one email address, sign-in for that address is
  refused until the window passes. A success clears the count.
- Success, failure and lockout are audited with the email domain only.
- After sign-in the user lands on their role's home: patient portal, clinician workspace
  or admin console.
- **[new]** Patients may instead sign in with a link sent by email and no password
  (7.3). Admins and clinicians cannot.

### 12.2 Sessions **[existing]**

- A random token in a cookie that scripts cannot read, sent only to the same site, and
  only over HTTPS in production. The server stores a hash of the token.
- After a password sign-in: lifetime 12 hours for admins and 7 days for everyone else,
  extended to a full lifetime whenever less than half remains.
- **[new]** After a sign-in by email link or by booking verification code: 24 hours,
  never extended.
- Sign-out deletes the session. A deactivated user's sessions stop working at once.

### 12.3 Access rules

- Search, public pages, the booking steps up to email verification, and asking for a
  sign-in link need no session **[new]**.
- Every other page needs a session; without one the user is sent to sign-in.
- A signed-in user who opens another role's area gets a "forbidden" page.
- All access checks run on the server for every read and write.
- A missing record gives `not_found`; a record that exists but belongs to someone else
  gives `forbidden`.
- State-changing requests from another origin are refused.

## 13. Reporting **[existing]**

All figures are for appointments that start in the chosen range.

| Figure | Definition |
| --- | --- |
| Appointments | Appointments that are not cancelled |
| Cancellations | Cancelled appointments |
| Utilisation | Minutes of active appointments inside the range ÷ available minutes. Available minutes are the availability rule hours of active clinicians in the range minus their time off |
| No-show rate | No-shows ÷ appointments that are not cancelled |
| Online share | Appointments with source `ONLINE` or `ROUND_ROBIN` ÷ appointments that are not cancelled |
| Waitlist size | Entries currently `WAITING` or `OFFERED`, regardless of range |

A ratio with a zero denominator shows "n/a", not 0 %.

**CSV export.** Columns: appointment id, start, end, status, source, patient id, clinician
id, department id, appointment type id, room id. Instants in ISO 8601 UTC. Ids only, no
names or free text. A cell that starts with `=`, `+`, `-` or `@` is prefixed with an
apostrophe. The export is audited with the row count.

## 14. Application API

A JSON API under `/api/v1` backs the screens. Errors use the codes and statuses of
section 4. Every response carries the correlation id.

**[existing]**

| Method and path | Purpose | Who |
| --- | --- | --- |
| `POST /auth/login`, `POST /auth/logout` | Start and end a session | Anyone |
| `GET /health` | Liveness | Anyone |
| `GET /slots` | Free slots for a type, optional clinician, range up to 31 days | Signed in; public **[new]** |
| `GET /appointments` | List, filtered by patient, clinician, status, range, limited to what the caller may see | Signed in |
| `POST /appointments` | Book; without a clinician it uses round robin | Signed in |
| `POST /appointments/{id}/cancel` | Cancel with reason | Patient, clinician, admin |
| `POST /appointments/{id}/reschedule` | Move to a new start | Patient, clinician, admin |
| `POST /appointments/{id}/check-in`, `/complete`, `/no-show` | Status change | Clinician, admin |
| `POST /waitlist` | Join | Patient, admin |
| `POST /waitlist/{id}/accept` | Accept an offer | Patient, admin |
| `POST /jobs/reminders` | Run the reminder job | Admin |

**[new]**

| Method and path | Purpose | Who |
| --- | --- | --- |
| `GET /search/providers`, `/search/hospitals`, `/search/specialties` | Search with text, filters, sort, page and page size; each result includes its next availabilities | Anyone |
| `GET /hospitals/{id}`, `GET /providers/{id}`, `GET /specialties/{id}` | Public detail | Anyone |
| `POST /booking/holds` | Create a hold with the visitor's details; sends the code | Anyone |
| `POST /booking/holds/{id}/verify` | Submit the code; books and opens a 24 hour session | Anyone |
| `POST /booking/holds/{id}/resend` | Send a new code | Anyone |
| `POST /auth/link` | Ask for a sign-in link for an email address; the answer is always the same | Anyone |
| `POST /auth/link/verify` | Exchange the link's token for a 24 hour session | Link holder |

## 15. FHIR API **[new]**

### 15.1 Conventions

- FHIR R4 (4.0.1), JSON (`application/fhir+json`), base path `/fhir`.
- `GET /fhir/metadata` returns a CapabilityStatement listing every resource, interaction
  and search parameter below.
- The FHIR API is another door to the same product. A FHIR write runs the same
  validation, booking rules, access rules, audit and notifications as the screens. No
  FHIR write can do what the application API would refuse.
- Errors are `OperationOutcome` resources with the HTTP statuses of section 4.
- Searches return a `searchset` Bundle with `total` and `self`, `next` and `previous`
  links. `_count` sets the page size (default 20, at most 100). `_sort` is supported on
  the parameters listed.
- Resources carry `meta.versionId` and `meta.lastUpdated`. Updates accept `If-Match` and
  fail with 412 on a stale version.
- Each resource keeps the product's id as its logical id.

### 15.2 Concept mapping

| Concept | FHIR resource | Notes |
| --- | --- | --- |
| Hospital | `Organization` (type `prov`) and `Location` (the site) | Address, phone, position and time zone on the Location |
| Department | `Organization` (type `dept`, `partOf` the hospital) | |
| Specialty | `CodeSystem` and `ValueSet` | Used in `PractitionerRole.specialty` and `HealthcareService.specialty` |
| Room | `Location` (physical type room, `partOf` the hospital site) | Floor, capacity and equipment as extensions; managing organization is the department |
| Clinician user | `Practitioner` | Name and title public; email and phone only to staff |
| Clinician profile | `PractitionerRole` | Department, specialty, default room, bio, round robin weight (extension) |
| Admin user | `Practitioner` with a `PractitionerRole` coded as administrator | Admin only |
| Patient user | `Patient` | Name, birth date, email, phone, active |
| Appointment type | `HealthcareService` | Provided by the department; duration, buffer, colour, needs-room and online-bookable as extensions |
| Availability rule | `Schedule`, one per rule | Actors: practitioner and room. Planning horizon: valid-from to valid-to. Weekday, times and slot step as an extension. Also mirrored read-only in `PractitionerRole.availableTime` |
| Time off | `PractitionerRole.notAvailable` | FHIR R4 has no stand-alone resource for it; created and removed by updating the PractitionerRole |
| Free slot | `Slot` | Computed, read-only. Status `free`, or `busy`, `busy-tentative` (held), `busy-unavailable` (time off) when asked for |
| Appointment | `Appointment` | Participants: patient, practitioner, room. `serviceType` is the appointment type. Source as an extension |
| Booking hold | `Appointment` with status `pending` | Staff only |
| Waitlist entry | `Appointment` with status `waitlist` | `requestedPeriod` is the window; optional practitioner participant is the preferred clinician |
| Waitlist acceptance | `AppointmentResponse` | Participant status `accepted` |
| Notification | `Communication` | Recipient, category (kind), payload text, `sent`, `received` (read time), `about` the appointment |
| Audit log entry | `AuditEvent` | Read-only. Action, time, agent, entity, metadata as entity details, correlation id |
| Session | not exposed | Sign-in sessions are credentials. Sign-in events are visible as `AuditEvent` |

### 15.3 Status mapping

| Appointment status | FHIR `Appointment.status` |
| --- | --- |
| `BOOKED`, `CONFIRMED` | `booked` (the internal value is kept in an extension) |
| `CHECKED_IN` | `checked-in` |
| `COMPLETED` | `fulfilled` |
| `CANCELLED` | `cancelled`, with `cancelationReason` text |
| `NO_SHOW` | `noshow` |

| Waitlist status | FHIR `Appointment.status` |
| --- | --- |
| `WAITING` | `waitlist` |
| `OFFERED` | `proposed`, with the offered start, end and practitioner |
| `BOOKED` | `booked`: from acceptance on, this resource is the booked appointment, one resource and not two |
| `EXPIRED` | `cancelled` |

Clinical notes map to `Appointment.comment` and are returned only to the appointment's
clinician. The patient's reason maps to `Appointment.reasonCode.text`.

### 15.4 Interactions and access

| Resource | Read and search | Create, update, delete |
| --- | --- | --- |
| `Organization`, `Location`, `HealthcareService`, `CodeSystem`, `ValueSet` | Anyone, active records only | Admin |
| `Practitioner`, `PractitionerRole` | Anyone, public fields of active clinicians only; staff see all | Admin; a clinician may update own `notAvailable` |
| `Schedule` | Anyone | The owning clinician |
| `Slot` | Anyone, free slots only; staff may ask for other statuses | none, computed |
| `Patient` | The patient (own record), clinicians (own patients), admin | The patient (own phone and birth date), admin |
| `Appointment` | The patient (own), the clinician (own calendar), admin | Same rules as sections 5.4 and 5.6 |
| `AppointmentResponse` | The patient (own), admin | The patient (own offer), admin |
| `Communication` | The recipient | The recipient may set `received`; no create or delete |
| `AuditEvent` | Admin | none |

Unauthenticated FHIR access is read-only. Booking without signing in is not offered through
FHIR.
Authenticated calls use a bearer token that belongs to one user; the token gives exactly
that user's rights.

### 15.5 Search parameters

| Resource | Parameters |
| --- | --- |
| `Organization` | `name`, `type`, `partof`, `address-city`, `active` |
| `Location` | `name`, `address-city`, `organization`, `partof`, `type`, `near` |
| `HealthcareService` | `name`, `organization`, `specialty`, `active` |
| `Practitioner` | `name`, `active` |
| `PractitionerRole` | `practitioner`, `organization`, `specialty`, `location`, `service`, `active` |
| `Schedule` | `actor`, `date`, `active` |
| `Slot` | `schedule`, `schedule.actor`, `service-type`, `start`, `status`; a start range of at most 31 days is required |
| `Patient` | `name`, `email`, `phone`, `birthdate` |
| `Appointment` | `patient`, `practitioner`, `location`, `status`, `date`, `service-type` |
| `Communication` | `recipient`, `category`, `sent` |
| `AuditEvent` | `agent`, `entity`, `entity-type`, `action`, `date` |

`_include` is supported for the references a client needs to draw a result:
`PractitionerRole:practitioner`, `PractitionerRole:organization`, `Slot:schedule`,
`Appointment:patient`, `Appointment:practitioner`, `Appointment:location`.

### 15.6 Booking through FHIR

- **Find:** search `Slot` with `service-type`, `start` and optionally `schedule.actor`.
  Slot ids are stable for the same schedule, type and start, so a client can refer to
  one.
- **Book:** create an `Appointment` with status `proposed`, the patient, the
  `serviceType`, and either a `slot` reference or a start plus a practitioner. Leaving
  out the practitioner asks for "first available". The server answers with status
  `booked`, the assigned practitioner and room, or an `OperationOutcome`.
- **Reschedule:** update the appointment's start. **Cancel:** update status to
  `cancelled` with a `cancelationReason`. **Check in, complete, no-show:** update status.
  Any other status change is refused with 409.
- **Waitlist:** create an `Appointment` with status `waitlist` and a `requestedPeriod`.
  Accept an offer by creating an `AppointmentResponse` with status `accepted`.

## 16. Product qualities

- Usable from 375 px to 1440 px wide, on a phone as well as a desktop.
- Accessible to WCAG 2.2 level AA: keyboard operable, visible focus, labelled fields,
  errors tied to their field with focus moved to the first invalid one, status never
  shown by colour alone.
- Plain, warm, precise wording in sentence case. No marketing text inside the product.
- Loading states, empty states and error states on every list and form. Destructive
  actions confirm first.
- Standard security response headers, including a content security policy that forbids
  framing by other sites.
- Logs are structured, carry the correlation id, and never contain sensitive data.
- Demo data: a seed that can be run again without duplicating rows, with several
  hospitals, departments, rooms, types, clinicians with availability, patients and
  appointments in every status, and one demo sign-in per role.

## 17. Decisions taken and open points

Decisions made while writing this specification. Each can be changed before the rebuild.

1. **Several hospitals.** The current application models one clinic. Search by hospital
   needs a Hospital concept above Department, with its own time zone.
2. **Admins are global.** One admin manages every hospital. Hospital-scoped admins are
   not specified.
3. **One department per clinician.** A clinician working at two hospitals is not
   specified.
4. **Specialty is a managed list**, not free text, so it can be searched and filtered.
5. **There is no guest.** Whoever books is a patient. A first booking creates a
   passwordless patient account once the email address is verified.
6. **An email address is verified before the booking exists.** This is what stops
   anonymous slot hoarding and what the 3 open bookings rule is counted on. It makes
   email delivery a requirement; the current application has in-app notifications only.
   Text messages are not specified.
7. **A code while booking, a link for signing in later.** The code keeps the visitor on
   the page that holds the slot, also when they read email on another device. Both open
   the same 24 hour session.
8. **Sign-in by link is for patients only**, and its 24 hour session is never extended.
   Staff keep passwords.
9. **Emails never contain a link that signs the reader in**, except the sign-in link
   email itself. A forwarded confirmation or reminder gives no access.
10. **A passwordless patient cannot set a password.** Not specified. Patients with a
    password are those an admin created.
11. **Bookings made without signing in keep the source `ONLINE` or `ROUND_ROBIN`**, so the
    online share figure includes them.
12. **The waitlist needs a signed-in patient**, passwordless or not.
13. **FHIR version R4.** The token scheme (for example SMART on FHIR scopes) is open; the
    requirement is only that a token carries one user's rights.
14. **Search horizon 90 days, 3 slots per provider result, 10 minute hold, 15 minute
    sign-in link.** These are proposed values.

Behaviour of the current application that this specification changes or leaves open:

- `CONFIRMED` exists as a status and in the transition table, but no action sets it. The
  rebuild should either remove it or define who confirms (for example the patient, from
  the reminder).
- Waitlist expiry (5.8) is defined in the current application but never run. This
  specification requires it.
- The reminder job runs only when an admin triggers it. This specification asks for a
  schedule as well.
- The booking policy numbers are fixed in code. Making them editable is not specified.
- There is no patient self-registration today. Section 7 creates a patient account at the
  first verified booking; a stand-alone sign-up page is not specified.
