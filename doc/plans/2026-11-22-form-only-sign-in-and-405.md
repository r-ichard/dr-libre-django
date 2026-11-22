# Form-only pages: sign-in leads to the page, a 405 is a product page (task 27b item 6, #42)

Slice: item 6 only (#42). Nothing else of `27b-qa-round-3-pages.md`. Revised after the architect's `revise` verdict (`scratch/plan.verdict`); every reason is answered under "Architect reasons".

## Focal point

`PageView._guarded_dispatch` (`scheduling/views/pages/page_view.py:65-78`). Two wrong answers come from it:

- the anonymous branch (`page_view.py:70-73`) sends a POST-only address to sign-in as `next`, so a GET of it follows the sign-in;
- the GET check (`page_view.py:76-77`) answers Django's empty 405, whose `Allow` comes from `View._allowed_methods` (`django/views/generic/base.py:179`), which lists GET and HEAD because `PageView` defines `get` and `View.setup` sets `head = get` (`base.py:128-129`).

HEAD has a third fault: a HEAD of a POST-only page runs `page()` with an empty template name, so it is not a clean 405 today.

## Ladder

1. Nothing: item 6 stays broken (#42 reproduces with curl).
2. Redirect a GET of a POST-only address to its page: rejected. The item asks for a 405 product page; a 302 hides it and still leaves a redirect into a form address.
3. Use the Referer as the return page: rejected. Client-controlled, absent for `curl`, and only browsers enforce same-origin.
4. Strip the last path segment: rejected. `/patient/notifications/<id>/read` strips to a page that does not exist.
5. **Chosen:** each form-only view declares the page its form sits on, as a path template (`form_page = "/admin-console/appointments/{appointment_id}"`). The base class fills it from the URL's own kwargs (already uuid-converted). The anonymous redirect uses it. Every refused method on any `PageView` renders one product page with `Allow` computed from what the view accepts.

## Blocks, files, lines (in edit order)

1. **Tests first:** new `scheduling/views/pages/test_form_only_pages.py`. Behaviour names in the next section. Beside the code, per §10.

2. **`scheduling/views/pages/page_view.py`** (108 lines now, about +25):
   - class attribute `form_page: str = ""`: the page a form-only address belongs to, a server constant with `{name}` placeholders for URL kwargs.
   - property `is_form_only`: `not self.template_name and type(self).get is PageView.get` (the condition now at line 76).
   - method `_form_page_path(self) -> str`: `return self.form_page.format(**self.kwargs)`. `self.kwargs` is set by `View.setup` before dispatch, so no parameter is threaded through.
   - `_guarded_dispatch`:
     - lines 70-73: `next` = `self._form_page_path()` when `self.is_form_only`, else `request.get_full_path()` as today. An empty `form_page` gives `next=""`, which `sign_in.py` maps to the start page.
     - lines 76-77 replaced by one rule for every page: `if request.method not in self._allowed_methods(): return self.http_method_not_allowed(request)`. For templated pages this is the same set Django already accepts, so their behaviour is unchanged; for form-only pages it refuses GET and HEAD.
   - `_allowed_methods(self) -> list[str]`: `super()` result minus `GET` and `HEAD` when `is_form_only`. One hook feeds the 405 `Allow` and OPTIONS `Allow`.
   - `http_method_not_allowed(self, request, *args, **kwargs) -> HttpResponse`: `render_page(request, "errors/405.html", {"form_page": self._form_page_path()}, status=405, signed_in_user=self.user)`, then `response.headers["Allow"] = ", ".join(self._allowed_methods())`, then Django's `log_response("Method Not Allowed (%s): %s", ...)` call kept (warning log, no sensitive data). Import `log_response` from `django.utils.log`.
   - `_form_page_path` with an empty `form_page` returns `""`; the 405 template handles that (start page link).

3. **`scheduling/templates/errors/405.html`** (new). UI change: before editing, read `PRODUCT.md`, `DESIGN.md`, the `impeccable` skill and `.claude/skills/impeccable/reference/craft-floor.md`. Model: `errors/404.html` (extends `base.html`, one `h1`, one `p`, correlation hint, one link). No new CSS, no new component, not added to `/style`. Copy (for the reviewer): h1 "This address only takes a form"; p "Nothing changes when this address is opened. Use the form on the page it belongs to."; link "Back to the page" to `form_page` when set, else "Go to the start page" to `/`; correlation hint exactly as in `404.html`.

4. **The form-only views** (one class attribute each, in this order). Walked list, from grep and route table, re-checked by the walk test:

   | # | View (file:line) | `form_page` | Why this page |
   |---|---|---|---|
   | 1 | `MarkReadPage` (`patient_notifications.py:56`) | `PATH` (line 23) | the notification list has the button |
   | 2 | `MarkAllReadPage` (`patient_notifications.py:69`) | `PATH` | same list |
   | 3 | `AcceptOfferPage` (`patient_waitlist.py:84`) | `WAITLIST_PATH` (imported line 24) | the accept button is `patient_waitlist_rows.py:32` |
   | 4 | `RemindersPage` (`admin_settings.py:38`) | `SETTINGS_PATH` (line 12) | the reminders form sits on settings |
   | 5 | `AppointmentExportPage` (`admin_appointment_export.py:21`) | `LIST_PATH` of `admin_appointments.py:39` | the export button is `export_action` on the list (`admin_appointments.py:116`) |
   | 6 | `StatusActionPage` (`admin_appointments.py:182`) and its subclasses `CheckInPage` (:201), `CompletePage` (:206), `NoShowPage` (:211) | `"/admin-console/appointments/{appointment_id}"` | the status buttons sit on the appointment page; route `one` (`admin_appointments.py:258`) names `appointment_id` |
   | 7 | `OfferPage` (`admin_waitlist.py:181`) | `"/admin-console/waitlist"` (`LIST_PATH`, line 39) | the offer button is `offer_action` on the list (`admin_waitlist.py:83`) |
   | 8 | `AcceptPage` (`admin_waitlist.py:194`) | same | `accept_action` on the list (line 84) |
   | 9 | `NotesPage` (`clinician_appointment.py:130`) | `"/clinician/appointments/{appointment_id}"` (`APPOINTMENT_PATH` line 17 of `clinician_support.py`) | the notes form is on the appointment page |
   | 10 | `StatusActionPage` (`clinician_today.py:118`) and subclasses `CheckInPage` (:143), `CompletePage` (:147), `NoShowPage` (:151) | `"/clinician/appointments/{appointment_id}"` | the default return of `_return_path` (`clinician_today.py:136-140`) |
   | 11 | `ResendPage` (`booking_code.py:99`, no `allowed_roles`) | `"/book/holds/{hold_id}/code"` (= `code_href`, `booking_links.py:42`) | the code page has the resend button; no sign-in involved, the 405 link is what matters |

   Subclasses inherit `form_page` and `allowed_roles`; no change in them. Admin and clinician routes share class names: the walk test fills each route with its own kwargs, so a wrong path cannot pass.

5. **Doc:** `doc/handover.md`: grep for claims about the 405 or sign-in `next`; update only if one exists (CLAUDE: state in the commit that changes it). `drlibre-specs.md`, the backlog file: not touched.

**Not touched:** `sign_in.py` (its `local_path_or_home` at `sign_in.py:99` still guards `next`), `safe_redirect.py`, `sign_out.py` (a plain `View`, see "Not in this run"), every API and FHIR view, the audit writer, the domain.

## Failing tests first (behaviour names; expected values in words from the item)

Written before the change; each must fail for the stated reason today.

- `returns_sign_in_next_of_notifications_list_when_anonymous_mark_all_read_is_posted`: anonymous POST to `/patient/notifications/read-all` gives a redirect to sign-in whose `next` is `/patient/notifications`. Today: the full path.
- `returns_405_with_allow_post_and_options_when_signed_in_get_of_mark_all_read`: status 405, `Allow` is exactly `POST, OPTIONS`. Today: `GET, POST, HEAD, OPTIONS`.
- `returns_405_product_page_linking_to_list_when_signed_in_get_of_mark_all_read`: body has the layout heading, a correlation reference and a link to `/patient/notifications`. Today: empty body.
- `returns_405_not_500_when_signed_in_head_of_mark_all_read`: status 405, no `HEAD` in `Allow`. Today: the HEAD runs `page()` with no template (red proof for the HEAD fault; if today it is a clean 405, drop the HEAD branch and say so).
- `returns_options_allow_without_get_when_asked_for_mark_all_read`: `Allow` is `POST, OPTIONS`.
- `returns_sign_in_next_that_answers_get_for_every_form_only_route`: **walk test.** Walks `get_resolver().url_patterns`. For each route whose `view_class` is a `PageView` with `allowed_roles` and `is_form_only` (instantiated to read the property), fills each `<uuid:name>` with a fresh uuid, GETs it anonymously, expects a redirect to `/sign-in?next=` plus `form_page` filled with the same ids, and expects that `next` to resolve to a view that is not form-only. It must cover at least the fourteen routed addresses of table rows 1 to 10 (the subclasses with no route, such as an unrouted `NoShowPage`, are covered by the class checks in the same test). A missing `form_page` fails it, so a future form-only view cannot land on the start page unnoticed. Today: fails on the full-path `next`.
- `returns_405_linking_to_code_page_when_get_of_resend_address`: `ResendPage` GET (anonymous): 405, `Allow` is `POST`, link `/book/holds/<id>/code`. Today: empty body.
- `returns_405_linking_to_start_page_when_form_page_is_not_declared`: a probe `PageView` in the test module with `http_method_names = ["post"]` and no `form_page`: 405 product page, link `/`. Today: empty body.
- Existing, must stay green: `returns_405_when_the_offer_route_is_opened_with_get` (`test_admin_waitlist_pages.py:121`), `returns_405_when_sign_out_is_a_get` (`test_pages.py:208`), and the sign-in `next` tests in `test_pages.py` and `test_patient_waitlist_page.py:238`.

Red proof: `make test` with the new file before block 2 must show these failing; then `make lint`, `make test`, `make gate`.

## Invariants and trust boundaries

- **`next` is never request input on this path.** `form_page` is a server constant; its placeholders take the URL's uuid kwargs (the converter already validated them). The result starts with `/`, has no `//` and no `\`, and still goes through `local_path_or_home` in `sign_in.py`. No open redirect.
- **Authorization order unchanged:** anonymous redirect, then role check (403), then the method check (405). An anonymous visitor never sees a 405 of a role-gated page. The 405 page renders no record data, only the layout and the correlation id.
- **No write on any changed path.** No audit, booking or double-booking code is touched. A refused method writes nothing.
- **Clock:** none used. **Logging:** Django's 405 warning kept via `log_response`; no new sensitive field.
- Pages not form-only (templated) keep the same `Allow` and the same accepted methods; their 405 body changes to the product page.

## Domain entities (CLAUDE.md §3)

Patient (notifications, waitlist accept), Admin (settings reminders, appointment export and status, waitlist offer and accept), Clinician (appointment status, notes), Notification, WaitlistEntry, Appointment, BookingHold and VerificationCode (the code page, via `ResendPage`), Visitor (the anonymous redirect). Session: resolved, unchanged.

## Blast radius

- `PageView` is the base of every server-rendered page. `_guarded_dispatch` now refuses by `_allowed_methods()`: same accepted set for templated pages, so their status codes and `Allow` headers are unchanged. The 405 body of every page becomes the product page.
- Sign-in `next` changes for the allowed-role form-only views of table rows 1 to 10 (fourteen routed addresses in the walk; `ResendPage` has no sign-in).
- Test impact: the walk test and the named tests above; existing sign-in `next` tests are checked by running them, not assumed.

## Not in this run

- `SignOutPage` (`sign_out.py:11`, a plain `View`): a GET answers an empty 405 whose `Allow` is already true (`POST, OPTIONS`). Not a `PageView`, so not changed here. Question for the owner: does a 405 of the sign-out address count as "a page"?
- The clinician check-in button on the today list posts `return_to=today`. Its GET after sign-in lands on the appointment page, not the list, because the GET carries no form data. Accepted limit; the appointment page is a page the action was on.
- Old links already in circulation with `next=/patient/notifications/read-all`: after sign-in they reach the new 405 product page with its link back to the list. Not rewritten.
- The 405 copy is a product wording choice: listed for the owner in the review, not an ADR (the item decides the behaviour).
- API, FHIR and webhook 405s (`/api/v1`, `/fhir`): not pages, unchanged (owner question for task 26d, the wrong-method 404 finding).

## Risks

- `_allowed_methods` is a private Django hook (Django 6.1.3, pinned). If django-stubs types it differently, mypy strict fails at the override: fix the annotation, do not add `# type: ignore`. A rename breaks the `Allow` tests, not the product silently.
- HEAD handling rests on the HEAD test; if HEAD proves a clean 405 today, drop the HEAD branch.
- Hand-written `form_page` values (table rows) duplicate route strings; the walk test is the guard. A new path under a renamed route fails the walk.
- The 405 template is new UI: impeccable reads listed in block 3; reviewer checks the copy.
- Layout: the 405 page reuses the 404 layout and adds no block, so no new measurement is claimed. The sandbox has no browser; the orchestrator walks it at 375 px and 1440 px.

## Architect reasons (`scratch/plan.verdict`) and how this plan answers them

1. **Scope gap (material):** done. Table of eleven rows (sixteen allowed-role classes and `ResendPage`) with file:line, including the four named (`admin_appointments.py:182`, `admin_waitlist.py:181` and `:194`, `clinician_today.py:118`, `clinician_appointment.py:130`) and their subclasses. Each has its `form_page`, so no fallback to the start page for them. The walk test finds the routes from the resolver, not from grep.
2. **Blast radius and tests:** done. Fourteen routed form-only addresses and `ResendPage` in the walk and named tests; admin and clinician views covered by the walk, not only notifications, waitlist, reminders and export.
3. **Line numbers:** done. Anonymous branch `page_view.py:70-73`; GET check `page_view.py:76-77`; `get` at `page_view.py:80`.
4. **Checked and sound** (kept): `local_path_or_home` at `sign_in.py:99`; role check before the 405, so an anonymous visitor never sees it; HEAD reaches `page()` via `View.setup` (`head = get`), the HEAD test is a valid red proof; `Allow` through `_allowed_methods` covers the 405 and OPTIONS.
5. **Not a reason to revise** (kept): the 405 copy and the private hook are acknowledged risks above.

## Architect review

Second review, of the revised plan. Checked against `scheduling/views/pages/page_view.py`, the twelve classes in the table, Django's `View` (`_allowed_methods` at `base.py:179`, `head = get` at `base.py:129`), and `sign_in.py` / `safe_redirect.py`.

1. **Ladder:** approved. The base-class change plus one class attribute per form-only view is the smallest change that gives every address a true page. Rejected rungs (redirect, Referer, path strip) are correctly rejected.
2. **Plan knowledge:** each block states its purpose in one sentence. Vocabulary matches §3 (Patient, Admin, Clinician, Notification, WaitlistEntry, Appointment, BookingHold).
3. **Test-first:** named behaviours cover the anonymous redirect, the `Allow` value, the 405 body, HEAD, OPTIONS, the undeclared-`form_page` fallback and a walk over every routed form-only address. Each names its present-day failure. Red proof required before block 2.
4. **Security:** `next` is a server constant with uuid kwargs, still passed through `local_path_or_home`, which returns home for `""`. Authorization order (anonymous, 403, 405) is kept. The 405 renders no record data. No write on the changed path.
5. **Architecture:** change stays in the view base and a thin template; no domain, use-case or audit change. Expected refusal is a value (405 response), not an exception.
6. **Scope:** the eleven-row table covers every allowed-role form-only class the reviewer found (including the admin and clinician status and notes views the first review named), plus `ResendPage`. Slice is coherent and not "Not in this run" for item 6 itself.

Non-material notes (do not block):
- Layout: the 405 page reuses the 404 layout. CLAUDE asks for an invariant and a measurement on any layout change; the plan defers to the orchestrator's 375 px and 1440 px walk. Acceptable, but state the check (for example `scrollWidth` equal to `clientWidth` at 375 px) in the review.
- The walk test's "at least fourteen routed addresses" is a count the test must derive from the resolver, not a hand-written list. The plan already says so.
- `drlibre-specs.md` and the backlog file are untouched, as the task requires.
