Task 05b: screens hardening.

Defects the orchestrator found in Chrome and in the code of task 05a. No new screen.

1. Sliding sessions do not slide for pages (`drlibre-specs.md` section 12.2). When a page
   request extends a password session, the server moves `expires_at` but the page
   response does not renew the cookie, so the browser drops it at the original expiry:
   an admin is signed out after 12 hours however active. The API renews it
   (`ApiView.finalize_response`); pages must too. Test with the request clock: a page
   request past half the lifetime answers with a cookie that carries the new expiry.
2. At 1440 px the header, the main column and the footer have three different left edges
   (32, 176 and 144 px). Header and footer content share the edges of the main column at
   every width.
3. `/favicon.ico` answers 404 and every page logs a console error. Serve an icon from the
   static files and link it in the layout.
4. The lockout message reads "Too many attempts. Wait 15 minutes, then try again later."
   Say it once: when the user can try again.
5. The cross-site request cookie is readable by scripts. No script needs it: make it
   `HttpOnly`.
6. The card component has more space above its heading than below.
7. A table wider than its wrapper scrolls inside it. Make that region reachable and
   scrollable with the keyboard and name it for assistive technology.

Tests for what the server can prove (items 1, 3, 4, 5, 7). The orchestrator checks items
2 and 6 in Chrome.

Done when `make setup && make lint && make test && make gate` pass from a fresh clone.
