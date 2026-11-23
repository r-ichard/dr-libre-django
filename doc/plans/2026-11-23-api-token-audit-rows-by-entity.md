# Task 26c item 12: the token audit test reads only its own token's rows

Slice: items 1 to 1 (one test assertion scope, plus the backlog path correction).

## Focal point

`scheduling/use_cases/test_api_tokens.py:105` reads every `AuditLogEntry` row in the worker's
database, then asserts on all of them. A row committed by any other writer in the same worker
(a transactional test, a seed, another run) breaks the equality at line 106 now and then. The
test's claim is about the two rows written for the token it issued and revoked, so it must read
only those rows.

## Blocks

- `test_api_tokens.py:105`: replace `AuditLogEntry.objects.order_by("created_at", "id")` with the
  same queryset filtered by `entity_id=str(issued.client.pk)`. Ordering stays. One line changes.
- `test_api_tokens.py:106-111`: no change. Every assertion stays, and each now runs on the
  token's rows only. The `entity_id` assertion at 107 becomes a tautology for the filtered set;
  it is kept as the claim that the filter selected the right rows, not removed.
- `doc/backlog/26c-gates-that-hold.md:28`: the item 12 line names
  `test_api_tokens.py::...`. Correct it to `scheduling/use_cases/test_api_tokens.py::...`
  (the orchestrator's decision). No other backlog text changes.

## Files to touch, in order

1. `scheduling/use_cases/test_api_tokens.py` (line 105 only).
2. `doc/backlog/26c-gates-that-hold.md` (line 28 only).

## Files deliberately not touched

- `scheduling/use_cases/api_tokens.py`: the writer is correct; it writes `entity_type="ApiClient"`
  and `entity_id=str(client.pk)` (line 78).
- `scheduling/models/audit.py`, the append-only trigger (migration 0002): no change.
- Any other test: the other writer is an open point for the orchestrator, not this run.
- `drlibre-specs.md`: no change.

## Invariants and blast radius

- Append-only audit log: untouched. The test only reads.
- Authorization: not involved (test code).
- Blast radius: one test function in one file, plus one backlog line. No product code.
- Test set semantics: the test still asserts exactly the two actions `api_client.issue` and
  `api_client.revoke`, the entity id, the `ids` metadata, and the absence of the token and the
  planted service name from metadata and logs. Only the population the assertions run on shrinks
  to the token's own rows.

## Failing test first (§7 proof)

The change is a filter, so the red proof is a scratch check, not a new test, to keep the diff
small:

- Before the edit, with a foreign row inserted in the same test (an `AuditLogEntry` with
  `action="api_client.issue"`, another `entity_id`, committed or not), the test fails at line 106.
  Record that failure output in the run log.
- After the edit, the same foreign row is ignored and the test passes.

The foreign-row insertion lives in a throwaway copy under `scratch/` and is not committed. The
existing test names stay as they are: `returns_audit_entries_with_ids_only_when_token_issued_and_revoked`.

## Trust boundaries

None crossed. The test reads its own database through the ORM. No input from a client.

## Domain entities (CLAUDE.md §3)

ApiClient (the token), AuditLogEntry (append-only), User (the owner of the token).

## What I will not do

- No new fixture, helper, or transaction marker (`transaction=True`) in the test module.
- No `entity_type` filter. The orchestrator decided "by entity id". See the open point below.
- No change to assertions, no removal of the caplog check, no `sorted` or `order_by` change.
- No deleting or truncating audit rows in the test to clean up: the log is append-only (trigger).
- No fix for the other writer.

## Open point for the orchestrator (not fixed in this run)

Filtering by `entity_id` alone matches any `AuditLogEntry` whose `entity_id` string equals
`str(client.pk)` regardless of `entity_type`. A row of another entity type with the same numeric
id would still be read. Adding `entity_type="ApiClient"` closes that gap with one more keyword
argument and changes no assertion. Not done here because the decision said "by entity id"; say
the word and it is a one-line follow-up.

## Verification for the test stage

- `make test` for the module, several repeated runs (`pytest -k returns_audit_entries_with_ids_only`).
- `make lint`, `make gate` (the diff must stay within the 255-char comment cap and no new escape
  hatches).
- The red proof above, recorded.

## Architect review

Verdict: approve.

Checked against the repo, not only the plan text:

- Backlog line 28 is item 12 and names `test_api_tokens.py::...` without the directory; the
  path correction is right.
- `AuditLogEntry.entity_id` is a `CharField(max_length=64)`. `api_tokens.py:78-82` writes
  `entity_type="ApiClient"` and `entity_id=str(client.pk)` for both issue and revoke, so the
  filter `entity_id=str(issued.client.pk)` selects the token's two rows.
- Ladder: one keyword argument on one line, no helper, fixture or transaction marker. Smallest
  change that addresses the stated cause.
- Assertions at 106 to 111 are kept unchanged; the caplog and token-absence checks still run.
- Audit log stays append-only; the test only reads. No trust boundary, no new dependency.

Reasons the verdict is not `revise`:

- Red proof is a scratch check with a foreign row, not a new test. Acceptable for a
  one-line filter; the plan records the failure output to be captured in the run log.
- The root cause ("another writer's row breaks line 106") is a hypothesis the plan asserts.
  The scratch red proof demonstrates the mechanism, not the original flake. The orchestrator
  has the other writer as an open point, so this is recorded, not hidden.
- The `entity_id`-only filter can still read a row of another entity type with the same id
  string. The plan names this as an open point with a one-line follow-up (`entity_type`).
  Not a blocker for this slice.

Nits (no change required):

- "Slice: items 1 to 1" is a mislabel; the work is item 12 of task 26c. Read it as "item 12
  only".
- The plan writes the cap as "255-char comment cap"; the rule is 255 characters per block.
  Same meaning, wording only.
