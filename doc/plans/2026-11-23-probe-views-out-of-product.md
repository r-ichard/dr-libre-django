# Probe views out of the product package (task 26c, item 14, second part)

Slice: item 14, second part only. Move `probe_views.py` and `probe_urls.py` out of `scheduling/views/`; no behaviour change.

Focal point: `scheduling/views/probe_urls.py` and `scheduling/views/probe_views.py` are test fixtures that ship inside the product package. They move to a top-level `test_support/` package, which only tests import. Product code (`drlibre/urls.py`, every `scheduling/` module that is not a test) never imports it, and a test enforces that.

Ladder: (1) delete: no, the tests need the routes. (2) existing location: none is test-only outside `scheduling/`; `fhir_test_support.py` sits in the product package, which is what item 14 asks to leave. (3) new top-level `test_support/` package, the name of the existing `fhir_test_support.py` convention. Chosen.

## Blocks, in order

1. **`test_support/__init__.py`**: new, empty, like `scheduling/views/__init__.py`. Makes `test_support` a package for mypy's `explicit_package_bases`.
2. **`scheduling/views/probe_views.py` to `test_support/probe_views.py`**: `git mv`, content unchanged. Filename kept, so `test_json_logging.py:134` (`"probe_views.py" in output`) and `test_failure_response.py:147` (leak check on `probe_views`) keep their meaning.
3. **`scheduling/views/probe_urls.py` to `test_support/probe_urls.py`**: `git mv`. Line 3 becomes `from test_support import probe_views`. Import order after the move: `from scheduling.views.health import HealthView`, then `from test_support import probe_views` (ruff isort, first-party block; `scheduling` sorts before `test_support`). Routes unchanged.
4. **Callers that set `ROOT_URLCONF`**, string `"scheduling.views.probe_urls"` becomes `"test_support.probe_urls"`:
   - `scheduling/views/conftest.py:9` (the `probe_client` fixture)
   - `scheduling/views/test_middleware.py:37`
   - `scheduling/views/test_json_logging.py:93`
   - `scheduling/views/test_process_output.py:17` (string inside `CHILD_PROGRAM`, run by `sys.executable -c` from the repo root, so `test_support` is importable there as `scheduling` is today)
5. **Import of the sentinel**: `scheduling/views/test_failure_response.py:12`, `from scheduling.views.probe_views import SENSITIVE_MESSAGE` becomes `from test_support.probe_views import SENSITIVE_MESSAGE`. It stays last in the first-party block.
6. **`pyproject.toml:58`, `[tool.mutmut] also_copy`**: add `"test_support"`. Without it, mutmut's copy of the tree has no `test_support`, and every views test that uses the probe client fails to import in a mutant run, which corrupts `make mutate` results.
7. **Boundary test, new**: `drlibre/test_product_imports.py`, one function `returns_no_product_module_importing_test_support`. It parses with `ast` every `.py` under `drlibre/` and `scheduling/`, skipping `test_*.py` and `conftest.py`, and collects any `import test_support` / `from test_support...` (module equal to or starting with `test_support.`). Expected: an empty list. Pinned by the task: the product URLconf and code never import the probes.

Not touched: the probe views' code, routes, `SENSITIVE_MESSAGE`, the `probe_client` fixture's location, the test files' assertions, `doc/backlog.md` (orchestrator owns it; its line 126 becomes stale and the orchestrator edits it with the squash), `doc/handover.md` (it names no probe path, grep-checked).

## Failing tests first

- `drlibre/test_product_imports.py::returns_no_product_module_importing_test_support`: expects `[]`. It passes on the tree before the move too, because nothing imports `test_support` yet. Red proof: after block 2 and 3 exist, add a line `import test_support.probe_urls` to `drlibre/urls.py` in the working tree; the test must fail and name `drlibre/urls.py`. Revert it, then the test is green. The proof output goes into the green-stage notes.
- Existing tests carry the behaviour; they must stay green with the same expectations, no edits to assertions:
  - `scheduling/views/test_middleware.py` (routes, correlation id, security headers on `/pages/explode`)
  - `scheduling/views/test_security_headers.py`
  - `scheduling/views/test_json_logging.py` (`probe_views.py` in the traceback; route pattern `api/v1/probe/patients/<str:email>`)
  - `scheduling/views/test_failure_response.py` (500 body has no `Traceback`, `ValueError`, `probe_views`, `SENSITIVE_MESSAGE`; 403 for undeclared view; 201 and 400 for write)
  - `scheduling/views/test_process_output.py` (child process writes only JSON lines)
  - `scheduling/views/test_schemas.py` (nested write: 201 and error lists)
  - the `returns_403_forbidden...` and `returns_..._when_...` cases using `probe_client`

## Trust boundaries and authorization

None crossed or changed. The probe routes are not in `drlibre/urls.py`, so no request reaches them in the product; they run only where a test sets `ROOT_URLCONF`. Authorization is unchanged, server-side as before.

## Domain entities

None. No entity from `CLAUDE.md` section 3 is touched; the probe views are test fixtures.

## Invariants and blast radius

- Behaviour: no product route, response, log line or audit entry changes. Probe routes stay unreachable from `drlibre/urls.py`.
- Double booking, server-side authorization, append-only audit log: not touched.
- `mypy .` and `ruff` cover the new directory already (whole-repo targets); the moved code keeps its strict typing.
- Docker image: `COPY . .` includes `test_support/`; `.dockerignore` excludes nothing relevant. The image still carries the probe code, as it did before the move; that is not a behaviour change.
- Mutation: `also_copy` in block 6.
- Time gate: unchanged; the moved code adds no test.

## Checks to run at green

`make lint`, `make test` (the fixture-using tests above), `make gate` (comment cap, size cap, escape hatches over `test_support/`), and `make mutate` if time allows (it is the slow one; state plainly if skipped). Also `grep -rn "scheduling.views.probe\|scheduling/views/probe" .` must return nothing outside `doc/`.

## What I will not do

- No new abstraction, no fixtures moved, no rename of the probe modules (renaming would break the `probe_views.py` path assertions).
- No rewrite of `probe_views.py` beyond what the move needs (nothing).
- No edit to `drlibre-specs.md`, `doc/backlog.md`, or `doc/handover.md`.
- No other item of task 26c.

## Risks

- Ruff isort order in block 3 and 5: if the import order is wrong, `make lint` fails; fix the order, not the rule.
- A mutant run without block 6 would look like a survivor pattern; block 6 is required, not optional.

## Architect review

Verdict: approve.

- Ladder: a top-level `test_support/` package is the smallest move that takes the probes out of the product package. It follows the existing `fhir_test_support.py` naming. No new abstraction, dependency or refactor.
- Plan knowledge: each block states one purpose. Vocabulary is the tests' own (probe views, probe URLconf, product URLconf), no entity from CLAUDE.md section 3 is involved, correctly stated.
- Scope: every reference found by grep is covered. Checked against the tree: `scheduling/views/conftest.py:9`, `test_middleware.py:37`, `test_json_logging.py:93` and `:134`, `test_process_output.py:17`, `test_failure_response.py:12` and `:147`, and `pyproject.toml` `also_copy` (line 58). No other `probe_urls`/`probe_views` references outside `doc/`. `drlibre/urls.py` and `drlibre/settings.py` do not reference the probes. Block 6 (mutmut `also_copy`) is needed: `scheduling/views` is copied, the probes will no longer be under it.
- Test first: the boundary test passes before the move, so it is not red on its own. The red proof in the plan (a planted `import test_support.probe_urls` in `drlibre/urls.py` must fail and name that file) makes it a real guard. Accepted.
- Test naming: `returns_no_product_module_importing_test_support` matches pytest's `returns_*` pattern (`pyproject.toml` `python_functions`), so it is collected. It lacks the `_when_` form CLAUDE.md asks for. Style only, not a reason to revise.
- Enforcement gap (non-blocking): the boundary test catches `import` statements only. A string reference such as `include("test_support.probe_urls")` or `ROOT_URLCONF = "test_support.probe_urls"` in a product file would pass it. The task's wording ("never import them") is met as written. The plan's sentence "a test enforces that" should say "imports" to stay accurate.
- Security, authorization, audit, transactions: not touched. Probe routes stay out of `drlibre/urls.py`. No trust boundary changes.
- Layers: test-only code moves to test-only location; no product layer touched.
- Checks: `make lint`, `make test`, `make gate`, `make mutate` as planned. `make mutate` is slow; the plan states it may be skipped and says so.
