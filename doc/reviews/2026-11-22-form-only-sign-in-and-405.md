# Review: form-only pages, sign-in leads to the page, 405 is a product page (task 27b item 6, #42)

Reviewed: `git diff main...HEAD` on `fabro/run/01M82M5X750QW4WD7GCC0QFRC8`, 13 files, +333 / -2.
Plan: `doc/plans/2026-11-22-form-only-sign-in-and-405.md`. Scope: item 6 only.
Verdict: **approve**. No blocking item. Gates reported green by the stages (`check`: lint, test 4912 passed, gate clean); not re-run by this review.

## 1. Plan in one sentence per block (§2.5)

- `page_view.py:75-77`: anonymous redirect takes `next` from `form_page` for form-only views. Confirmed at a glance.
- `page_view.py:80-81`: one method check, from `_allowed_methods()`. Confirmed at a glance.
- `page_view.py:84-90`: `is_form_only` says "no page answers GET". Traced: it differs from the plan (see Later 1).
- `page_view.py:92-116`: fills `form_page` from `self.kwargs`; `Allow` and the 405 page from the same hook. Confirmed.
- `errors/405.html`: product page, layout of `404.html`, link back or start page. Confirmed.
- 11 class attributes (table rows 1 to 11): each is the page its button sits on. Checked each against its route and its constant (below).
- Tests: red list in `verify_red` shows the 8 named tests failing before the fix; `verify_green` passes them.

Traced, not glanced: the `form_page` values (every one checked against the route kwarg names and the constants), the authorization order, and the walk test.

## 2. Correctness and error handling

- Authorization order kept: anonymous redirect (`page_view.py:73-77`), then role 403 (`:78-79`), then the method check (`:80-81`). An anonymous visitor never sees a 405 of a role-gated page.
- `form_page.format(**self.kwargs)` (`page_view.py:93`): a missing placeholder raises `KeyError` → 500. That is a broken invariant (a view declared with a placeholder its route does not supply); §9 allows a raise there. The walk test would hit it for every routed form-only address.
- No swallowed error. `log_response` keeps Django's 405 warning; it logs `request.path` only, as Django did before.
- HEAD of a form-only page: `HEAD` removed from `_allowed_methods()` (`page_view.py:98`), so HEAD gets the 405 page. The test `returns_405_not_500_when_signed_in_head_of_mark_all_read` pins it.
- Templated pages: `_allowed_methods()` returns the same set Django accepted, so their accepted methods are unchanged; only the body of their 405 changes (plan, "Blast radius").

## 3. Authorization, boundaries, sensitive data

- `next` is a server constant with the URL's uuid kwargs; it still goes through `sign_in.py`'s `local_path_or_home` (not in the diff, unchanged). No open redirect: the value starts with `/` and has no request input.
- The 405 page renders no record data, only the layout, the correlation id and a server-side link (`405.html:7`).
- No new payload field, no session read, no `next` from the request on this path.
- No serializer, API, FHIR, model or migration changed.

## 4. Double booking

Not touched. No domain, use-case or booking code in the diff. A refused method writes nothing (the 405 path returns before `super().dispatch`).

## 5. Tests

Derived from the item and from the plan's named behaviours (`test_form_only_pages.py:63-141`). Assertions are values, not "does not raise". The walk test (`:98-115`) derives the routes from the resolver (`_routes`, `:53-60`), not from a hand list. Gaps:

- The walk test does not assert that `next` equals the page the form sits on. The plan (line 70) promised "`form_page` filled with the same ids". The test checks only that `next` resolves to a non-form-only view and that the count is at least 14 (`:115`). A wrong but resolvable path (for example `OfferPage` pointing at the list instead of the page with the button) would pass. The eleven rows were checked by hand in this review and are right. See Later 2.
- `returns_405_linking_to_code_page_when_get_of_resend_address` and the rest check the link text and `Allow` for one view each. Adequate for the slice.

## 6. Names and comments

- Names state roles: `is_form_only`, `_form_page_path`, `_allowed_methods`, `next_path`, `answers_get`. Test names are `returns_X_when_Y`.
- Comments: `page_view.py:55` ("The page a form-only address belongs to...") says what the attribute is for; `:86` docstring states the rule. Both under 255 characters; no narration.
- Refactor commit `e80f559` moved the `form_page` line below the docstring in `clinician_today.py:118-121`. Correct: the docstring is the class's first statement again.

## 7. Proof trace (commits)

- `ddba392` red, `ed558be` green, `fb19a07` verify_green (empty), `f068b32` prove: only `test_form_only_pages.py` changed (a test assertion made exact, and a `_TemplatePage` test added). No product line.
- `e80f559` refactor, `05ede16` check: after prove, so product lines allowed. `e80f559` is the docstring move above.
- No product or migration line changed between verify_green and prove. Nothing left behind.

## 8. Scope and dependencies

- Diff is the slice: 11 form-only views, the base class, the template, the test file, the plan.
- `drlibre-specs.md`, `doc/backlog/*`, `doc/handover.md`: not in the diff. The plan's grep of `handover.md` for 405 / sign-in `next` claims found nothing, so no update was needed.
- No dependency added or changed (`pyproject.toml`, `uv.lock` not in the diff).
- Contract sync: the 405 response is a new page on the same `PageView` contract; no API or FHIR contract touched.
- Commit trailers: run commits carry `Fabro-Run` trailers and "Generated with Fabro" lines; the orchestrator squashes with a hand-written message and discloses tooling (CLAUDE.md, hand-applied gap 1).

## Blocking

(none)

## Later

1. **Plan drift in `is_form_only`** (`page_view.py:84-90`). The plan (line 28) defined it as `not template_name and get is PageView.get`. The code adds `"get" in http_method_names`, so a templated page with `http_method_names = ["post"]` counts as form-only. The code is the more correct rule. Fix: none needed; say so in the handover or the plan's history. Risk: none seen; no current view has that shape.
2. **Walk test misses the promised same-ids assertion** (`test_form_only_pages.py:110-113`). Smallest fix: build the expected path from the route's kwargs (`UUID_PLACEHOLDER` values) and assert `next_path == expected`. Risk: a future wrong-but-resolvable `form_page` passes. The current eleven rows are correct.
3. **`# fmt: skip` on the log call** (`page_view.py:112-115`). Style: the call is hand-wrapped with a skip rather than formatted. Smallest fix: let `ruff format` split it and drop the skip. Not a defect.
4. **Private Django hook overridden** (`page_view.py:95`, `_allowed_methods`). Django 6.1.3 is pinned, so a rename breaks the `Allow` tests, not the product silently (plan risk). Watch on the next Django bump.
5. **Layout not measured** (`errors/405.html`). The page reuses the 404 layout and adds no block or CSS. The orchestrator's 375 px and 1440 px walk should check `scrollWidth` equal to `clientWidth` on the 405 page (plan review note).
6. **Stale-link case** (plan "Not in this run"). Old `next=/patient/notifications/read-all` links now reach the 405 product page after sign-in, with a link back to the list. Accepted; not rewritten.
7. **Clinician check-in return** (plan "Not in this run"). The today-list check-in posts `return_to=today`; its GET after sign-in lands on the appointment page, not the list. Accepted limit.

## Left for the orchestrator

- Item 6 slice only. Not done, by design (plan "Not in this run"): `SignOutPage` (`sign_out.py:11`, a plain `View`), API / FHIR / webhook 405s, the rest of `27b-qa-round-3-pages.md` (items 1 to 5, 5a, 7 to 10).
- Squash with a hand-written message; disclose Fabro in the body; no `Co-Authored-By` from the run.
- `make mutate` and `make fhir-validate` are the last scripted gates; `mutate` covers `scheduling/domain` only, so it says nothing about this slice.

## For the owner

- Does a 405 of the sign-out address count as "a page"? `SignOutPage` is a plain `View` and answers an empty 405 today, with `Allow: POST, OPTIONS` already true (plan, "Not in this run").
- The 405 copy is a product wording choice ("This address only takes a form", "Nothing changes when this address is opened. Use the form on the page it belongs to."). Listed here, not an ADR (the item decides the behaviour).
