# Review: task 05b screens hardening

Diff `main...HEAD`: 9 files. Commit order checked: `green`, `verify_green`, `prove`, `refactor`, `check`. Between `verify_green` and `prove` no product or migration line changed (only `prove` commit `1ff193c`, empty of product files per stat). No dependency added. No type escape hatches seen.

## Plan in one sentence per block
- `page_view.py:52-68` PageView keeps the resolved session and re-sets the same token's cookie with the new expiry when it was extended and the view set no session cookie. Confirmed at a glance.
- `settings.py:44` CSRF cookie HttpOnly. `sign_in.py:17` lockout wording. `urls.py:24` favicon.ico redirects to a static SVG. `base.html:7` icon link.
- Tests `test_screens_hardening.py`: derived from the task and plan, assert cookie `expires`, status 403, token change, text, flags. Red proven (5 failed before green).

## Findings

1. **Blocker, correctness/scope.** Item 2 (shared left edges of header, main, footer) is not implemented. `static/css/base.css:59-99` unchanged: header and footer still `padding: var(--space-4)` full width, `.site-footer p` still centred. The plan promised a `--page-gutter` change here. Risk: defect stays at 1440 px. Fix: the plan's `padding-inline: max(var(--page-gutter), (100% - var(--page-width)) / 2 + var(--page-gutter))` on header and footer, drop the footer `p` margin and max-width.
2. **Blocker, correctness/scope.** Item 6 (card space above heading) is not implemented. `static/css/components.css:77-83` has `.card > :last-child` only. Fix: add `.card > :first-child { margin-top: 0; }`.
3. **Later, a11y.** Item 7: the plan said to add a `.table-wrap:focus-visible` outline if `craft-floor.md` requires one. `components.css:86` has none. A focusable region needs a visible focus ring. Check the global `:focus-visible` rule in `base.css`; if absent, add one.
4. **Later, plan drift.** Plan says `RedirectView` and `LOCKOUT_WINDOW` for the minutes. `urls.py:24` uses a lambda with `redirect`, `sign_in.py:17` hard-codes "15". The number can drift from `lockout_rules.py:6`. Smallest fix: build the string from `LOCKOUT_WINDOW`.
5. **Later, test.** `test_screens_hardening.py:127` asserts `"later" not in html` on the whole page; fragile if other copy contains "later". Scope it to the error element.
6. **Later, test.** `test_pages.py:118` lowercases the html but the match string is already lowercase; fine. Cookie renewal on redirect (302) responses has no test.
7. **Later, nit.** `page_view.py:56` reads `request.COOKIES[SESSION_COOKIE]`; safe because `resolved` implies the cookie exists.

## Blocking
- Item 2 not done: header/footer edges in `static/css/base.css`. **fixed** (`--page-edge` in `base.css`; test `returns_shared_edge_rule_when_header_and_footer_are_styled`; pixel check left to Chrome).
- Item 6 not done: `.card > :first-child { margin-top: 0; }` in `static/css/components.css`. **fixed** (test `returns_zero_top_margin_when_card_heading_comes_first`).

## Later
- Focus ring for `.table-wrap` (3).
- Derive lockout minutes from `LOCKOUT_WINDOW` (4).
- Scope lockout test assertion (5).
- Test cookie renewal on a redirect response (6).
