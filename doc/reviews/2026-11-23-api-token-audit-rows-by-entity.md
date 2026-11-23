# Review: task 26c item 12, the token audit test reads only its own rows

Reviewer: second reader, stage `review`. Diff: `git diff main...HEAD` (3 files, 127 insertions,
2 deletions). Plan: `doc/plans/2026-11-23-api-token-audit-rows-by-entity.md`, verdict `approve`.

## Changed blocks, plan in one sentence each

- `scheduling/use_cases/test_api_tokens.py:105-107`: the audit read is now the same ordered
  queryset filtered by `entity_id=str(issued.client.pk)`. Confirmed at a glance.
- `scheduling/use_cases/test_api_tokens.py:108-113`: unchanged assertions, now run on the
  token's rows only. Confirmed at a glance (diff is four lines; `git show` on the file agrees).
- `doc/backlog/26c-gates-that-hold.md:28`: adds the `scheduling/use_cases/` directory to the
  item 12 path. Confirmed: the file exists at that path.
- `doc/plans/2026-11-23-api-token-audit-rows-by-entity.md`, `doc/reviews/...`: process docs.

Traced (not glanced): the writer. `scheduling/use_cases/api_tokens.py:78-82` (`_audit`) writes
`entity_type="ApiClient"` and `entity_id=str(client.pk)` for issue and revoke. The filter value
and the stored value use the same expression, so the filter selects the token's two rows.
`scheduling/models/audit.py:20` declares `entity_id` as `CharField(max_length=64)`; a UUID
string fits.

## Stage checks

1. Plans: stated above.
2. Correctness and errors: the change is a read filter. No error path is added or swallowed.
   The caplog check (`test_api_tokens.py:111-113`) still runs over the token's metadata and
   the captured log, which is the same scope as before for the token.
3. Authorization and boundaries: test code only. No route, no payload, no log line added.
   The audit log is read through the ORM; the append-only trigger is untouched.
4. Double booking: not in scope.
5. Tests: the test still asserts the two actions, the entity id, the `ids` metadata and the
   absence of the token and the planted service name. The entity-id assertion at line 109 can no
   longer fail, because the queryset filters on that same value. The plan kept it on purpose,
   as the record of what the filter selected. Noted under Later.
6. Names: unchanged test name (`returns_audit_entries_with_ids_only_when_token_issued_and_revoked`).
   No comment added.
7. Proof trace: commits after `plan_gate` are `1e657eb` (plan_gate, no file change), `cf43771`
   (write: test line and backlog line only), `df083fa` (check, no file change) and `cb61aa5`
   (prove, no file change). No product or migration line changed after the green stage, so no
   mutation was left behind. The red proof itself (a foreign row in a scratch copy) is not in the
   repository; see Later.
8. Scope: one test statement and one backlog path. No dependency, no fixture, no helper, no
   `transaction=True` marker. `drlibre-specs.md` is not in the diff. The item 12 path names a
   file that exists.

## Gates

Stage `check` reports `make lint`, `make test` (5263 passed) and `make gate` (comment cap,
escape hatches) passing. This review re-read the diff; it did not re-run the gates.

## Findings

### F1 (Later): filter by `entity_id` alone can read a row of another entity type

- `scheduling/use_cases/test_api_tokens.py:105-107`
- Risk: a row with `entity_type` other than `ApiClient` and the same id string would still be
  read and fail line 108. Needs a UUID collision in practice, so low.
- Smallest fix: add `entity_type="ApiClient"` as a second keyword argument. Plan records this as
  the open point; the orchestrator chose "by entity id".

### F2 (Later): line 109 can no longer fail

- `scheduling/use_cases/test_api_tokens.py:109`
- Risk: an assertion that passes forever after the filter; it documents the filter but tests
  nothing about it. Kept as instructed ("keep every assertion").
- Smallest fix, if the owner wants it gone: delete line 109. Not done here; the orchestrator
  asked for every assertion to stay.

### F3 (Later): root cause is a hypothesis, not observed

- Backlog item 12 says "find the cause". The plan's cause (a foreign row committed by another
  writer in the same worker) is shown by a scratch red proof, not by the original flake. The
  other writer is not identified. This is the orchestrator's open point.
- Smallest next step: search the test suite for committed `AuditLogEntry` writers that do not
  roll back (transactional-test escapes, seeds, `transaction=True` tests), and log the find in
  `doc/retro.md` or a follow-up backlog task.

### F4 (Later): red proof not in the repository

- The plan requires the failure output of the scratch foreign-row run to be recorded in the run
  log. The diff contains no record of it, and the `prove` commit is empty. Not verifiable from
  git. The orchestrator should check the run log before it squash-merges.

### F5 (Later, nit): plan slice label

- `doc/plans/2026-11-23-api-token-audit-rows-by-entity.md`: "Slice: items 1 to 1" should read
  "item 12 only". The plan's architect review already says so. No change needed.

## Left for the orchestrator

- The other writer of the stray `AuditLogEntry` row: not found, not in this run (plan, "Open point").
- `entity_type` gap (F1): one-line follow-up if the orchestrator says so.
- Run log proof of the red step (F4).

## For the owner

None. `drlibre-specs.md` is unchanged, and this run leaves no open specification decision.

## Blocking

None.

## Later

- F1: add `entity_type="ApiClient"` to the filter (`test_api_tokens.py:105-107`).
- F2: line 109 is a tautology after the filter (`test_api_tokens.py:109`); keep or delete per owner.
- F3: root cause of the flake not identified; other writer open (backlog item 12, plan).
- F4: red-proof output must be found in the run log (plan, "Failing test first").
- F5: plan slice label wording (nit).
