# Review: task 05, password sign-in, sessions and access rules

Diff `main...HEAD`, 35 files. Gates green in the check stage (657 tests, lint, comment cap, escape hatches).

Proof trace: `git diff fc5113f e90c171 --stat` (verify_green to prove) touches only `test_session.py` and `test_sign_in.py`. No product or migration line moved after green. Refactor and check commits not mutations of tests-only scope; no rule broken.

## Plan in one sentence per block (confirmed at a glance)

- `use_cases/session.py`: random 32-byte token, SHA-256 stored, lookup by hash, extension and expiry by request clock.
- `use_cases/sign_in.py`: one hasher call on every path, HMAC-of-email failure rows counted in a 15-minute window, audit in the same transaction.
- `views/api_view.py`: Origin check on writes plus SameSite=Strict cookie.
- `views/access.py`: closed by default, declarations `public`, `signed_in`, `roles`.
- `use_cases/record_access.py`: missing gives `not_found`, other's gives `forbidden`.

Forced a trace: lockout path in `sign_in.py:41-57` (failure is recorded inside `atomic`, failure value returned after commit, so the row is kept; confirmed). Authentication step returning `None` on a bad session (`authentication.py:17-21`) so public endpoints stay public; `NotAuthenticated` then comes from the permission class (confirmed by `test_access_rules.py`).

## Findings

1. **Later**, `scheduling/use_cases/sign_in.py:45-50`: a locked address writes one `auth.lockout` audit entry per attempt. An attacker hammering a locked address floods the append-only audit log. Fix: audit only the attempt that crosses the threshold, or at most once per window.
2. **Later**, `scheduling/use_cases/sign_in.py:36-39`: count then insert is not serialised. Concurrent attempts can pass the threshold by a few. Fix: `select_for_update` on the user row, or accept and document the small overshoot.
3. **Later**, `scheduling/use_cases/sign_in.py:65-66`: stale `SignInFailure` rows are pruned only for the same address. Failures for many distinct addresses accumulate without bound. Fix: a periodic purge by `failed_at` (belongs with a cleanup task).
4. **Later**, `scheduling/use_cases/sign_in.py:23-25`: `hash_email` keys on `SECRET_KEY`; rotating the key resets all counts. Acceptable, note in operations docs.
5. **Later**, `scheduling/views/api_view.py:48-56`: a write with no `Origin` header passes. Justified in the docstring (non-browser client, SameSite=Strict also holds). Re-check if `SameSite` ever relaxes to Lax.
6. **Later**, `scheduling/use_cases/session.py:46-58`: `resolve_session` extension is an unaudited write. Reasonable for a sliding expiry; confirm against section 4 when the audit policy is next read.
7. **Later**, `scheduling/views/access.py:32-34`: `roles()` builds a class on each call. Works; a module-level factory class would read simpler.

Checked, no defect: session token entropy 256 bits; cookie HttpOnly, SameSite=Strict, Secure by `HTTPS_ONLY`; deactivated user fails `resolve_session`; identity only from `request.user`; login password not trimmed and bounded; audit metadata carries domain only; `AuditMetadata` now validates `changed_fields` and `email_domain`; `TransactionRequiredError` rename drops the suppression; no dependency added; migration and `doc/data-model.md` in step; no type escape hatches in the diff (the one `# noqa: S105` on `SessionKind.PASSWORD` names its code).

## Blocking

None.

## Later

Findings 1 to 7 above.
