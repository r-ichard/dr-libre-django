# Plan: HEAD counts as GET on the public schedule pages (task 26b2, review finding)

Slice: items 1 to 3 (one page-view fix, its red tests, the proof for API and FHIR). Nothing else.

## Focal point

`scheduling/views/pages/page_view.py:80` takes the public read hit only when
`request.method == "GET"`. Django's `View.setup` aliases `head` to `get`, and `PageView`
keeps Django's default `http_method_names`, which includes `head`. So a HEAD on the seven
pages with `read_scope = RateLimitScope.SCHEDULE` runs the full schedule computation and
never takes a hit. The limit is bypassed.

## Facts checked in the code (why the other routes are not changed)

- `/api/v1/providers/<id>`, `/hospitals/<id>`, `/specialties/<id>`, `/api/v1/slots`:
  `ApiView.http_method_names` is `["get", "post", "put", "patch", "delete"]` (`api_view.py`).
  DRF's `dispatch` checks that list before looking up the handler, so HEAD answers 405 and
  reaches no `get`, so no schedule is computed and no hit is needed. Holds. Nothing to fix.
- Anonymous `/fhir/...`: `fhir/views.py` `_answer` checks `request.method not in allowed`
  (`_allowed_methods`, built from `METHOD_OF_INTERACTION`, which has no HEAD) before
  `take_read_hit` at line 91. HEAD answers 405 before any read. Holds. Nothing to fix.
- `/search` (`pages/search_page.py`): the hit is taken inside `search_for_visitor`
  (`use_cases/search_limited.py`), which `get` calls for HEAD too. Holds, untested here.
- Spec `drlibre-specs.md` 7.5 says nothing about HEAD. No spec change, no ADR needed.

So one bug exists, in one line.

## Decision for the orchestrator (not made silently)

The brief asks that HEAD on the API twins, `/api/v1/slots` and anonymous `/fhir` answer 429
after 1200 / 600 HEADs. Those routes do not serve HEAD at all; they answer 405 and compute
nothing. Making them answer 429 would mean serving HEAD on the API (adding `head` to
`http_method_names`) and on FHIR (adding HEAD to the method table): larger changes, and a
new public surface. This plan keeps 405 and pins it with a test: HEAD on these routes is
refused before computing and adds no hit, proven by the full GET budget still being there
afterwards. Say if you want HEAD served instead.

## Blocks

1. `scheduling/views/test_read_limits.py`: new tests (below). Red for block 1a only.
2. `scheduling/views/pages/page_view.py`: a module constant `READ_METHODS = frozenset({"GET", "HEAD"})`
   and line 80 becomes `if request.method in READ_METHODS and self.read_scope is not None:`.
   Line 83 (the `http_method_not_allowed` shortcut) stays as it is.

No other production file changes. `api_view.py`, `read_limit.py`, `fhir/views.py`,
`rate_limits.py`, `rate_limit_rules.py`: untouched.

## Files in order

1. `scheduling/views/test_read_limits.py` (add tests; reuse `_paths()`, `ROUTES`, `_fill`,
   `browser_api_client`, `fhir_client`; add a `_head(client, path)` helper that calls
   `client.head`).
2. `scheduling/views/pages/page_view.py`.

Not touched: `scheduling/views/test_public_route_limits.py` (its walker uses GET and POST
only; HEAD is not a route-existence question, so it needs no change), the migrations, the
domain rules, the spec, the README.

## Failing tests to write first (behaviour names, expected values in words)

Block 1a, red before the fix (parametrized over the seven SCHEDULE page routes already in
`ROUTES`: provider, hospital, specialty, book services, book providers, book times,
book details):

- `returns_429_with_retry_after_on_every_schedule_page_when_head_requests_fill_the_counter`:
  1200 HEAD requests from one address answer 200 each; the 1201st HEAD answers 429 with a
  `Retry-After` of at least 1; the next GET answers 429 with `Retry-After`.
  Expected red now: the 1201st HEAD answers 200.

Block 1b, green before the fix (characterization, pins the routes that already hold):

- `returns_405_and_counts_nothing_when_head_reaches_an_api_schedule_read`
  (parametrized over provider, hospital, specialty API and `/api/v1/slots`): 1200 HEADs
  answer 405 each; then 1200 GETs from the same address still answer 200 each. If HEAD had
  been counted, the first GET would answer 429.
- `returns_405_and_counts_nothing_when_head_reaches_an_anonymous_fhir_read`: 600 anonymous
  HEADs on `/fhir/Location` answer 405 each; then 600 anonymous GETs answer 200 each.
  (At red stage check that an anonymous GET of `/fhir/Location` answers 200; if not, use the
  anonymous read the route-limit test accepts and say which.)

Prove the red: run block 1a, see the 1201st HEAD answer 200, then apply block 2 and see green.
Block 1b must pass before the fix as well; if it fails, that is a new finding and goes into
this slice, reported as such.

## Invariants and blast radius

- Double booking, appointments, holds, audit log: no code path touched. Reads write no audit
  entry.
- Authorization: the counter key is still `counter_key(user, address)`, from the session
  user or the network address; the HTTP method adds no input to it. A signed-in caller
  still counts by user id.
- Blast radius: only HEAD requests to seven page routes change. A HEAD on a limited page now
  gets the limited page with 429 and `Retry-After` (body dropped by Django for HEAD). GET is
  unchanged. HEAD requests now draw from the same 1200-per-hour SCHEDULE budget as GET.

## Trust boundaries

- The HTTP method is client input. It is compared as an exact uppercase string against a
  frozen set of two names. It decides only whether a counter is taken; it grants nothing.
- The network address comes from `network_address()` (unchanged).

## Domain entities (CLAUDE.md §3)

- Visitor (anonymous caller, counted by network address), Patient, Clinician, Admin (signed-in,
  counted by User id). RateLimitHit is the stored counter row. No Appointment, Slot, or
  Hold is written.

## What I will not do

- No serving HEAD on the API or FHIR (see decision above).
- No change to `ApiView.http_method_names`, `FHIR` method table, or `take_read_hit`.
- No cleanup of `RateLimitHit` rows (already listed as "Not in this run" in the backlog).
- No new abstraction. The constant is one line; no helper for method sets.
- No test of `/search` HEAD in this slice; no test added for the route-limit walker.

## Not in this run

- Serving HEAD on `/api/v1` and `/fhir` as a counted read (owner decision, see above).
- A test that `/search` counts HEAD (the code path is shared; check in review).
- The review's "Later" items 4 to 5 (validation order, `RateLimitHit` growth).

## Verification at the run's end

`make lint`, `make test`, `make gate`. `make mutate` covers `scheduling/domain` only, so it is
not affected. `make fhir-validate` unaffected (no FHIR output change).

## Architect review

Verdict: approve.

Checked against the code:

- `page_view.py:80` is the only `request.method == "GET"` read-hit guard on the page path. Django's `View.setup` aliases `head` to `get`, and `PageView` keeps the default `http_method_names`, so the bypass is real. The one-line change is the smallest fix in the right layer.
- `ApiView.http_method_names` (`api_view.py:22`) excludes `head`, so HEAD on `/api/v1` reads answers 405 before any handler runs. The plan's "holds, nothing to fix" claim is correct.
- `fhir/views.py:85` checks `request.method not in allowed` before `take_read_hit` at line 91, and `METHOD_OF_INTERACTION` has no HEAD. The 405-before-read claim is correct.
- Budgets match the plan: SCHEDULE 1200 and FHIR 600 per address (`rate_limit_rules.py:38-39`).

Findings:

1. Brief deviation, declared: the orchestrator asked that HEAD on the API twins and anonymous FHIR answer 429. The plan instead pins 405 with an unchanged GET budget and lists serving HEAD as an owner decision. I accept this. The routes hold, and serving HEAD would add public surface. The orchestrator must confirm before merge.
2. Slice wording: the header says "items 1 to 3", but the plan has blocks 1a, 1b and 2 only. Correct the header to match, or leave it: it does not block the run.
3. Red for right reason: block 1a must fail on the 1201st HEAD returning 200, not on a setup error. The plan states this. Keep it in the red proof.
4. Runtime risk: block 1a runs 1200 full schedule renders per parametrized route, seven routes, so about 8400 renders. Expect a slow test. Acceptable for one slice; if it exceeds the suite budget, use a smaller fill only if the limit is read from the rule, not hard-coded.
5. Anonymous FHIR precondition: block 1b assumes an anonymous GET of `/fhir/Location` answers 200. The plan says to check at red; that check must be recorded.
6. `/search` HEAD: the plan says it holds by shared code path and leaves it untested. Acceptable for this slice; a one-line test would settle it if the review asks.

Security: the method is compared as an exact string against a frozen set and only decides whether a counter is taken. No new input reaches the counter key, no audit entry, no write. Holds.
Layer: page view, one line. Holds.
