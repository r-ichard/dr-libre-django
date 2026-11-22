# Review finding on 4078bbd: a refusal never quotes a secret

Slice: the whole finding (one review item, about fifteen minutes). Branch `fabro/run/01M82NR25H7XVVD8K5KA6H7KR3`.

## Focal point

`scheduling/domain/text_rules.py` `_message` quotes up to 20 characters before a refused character.
Three request fields carry secrets: the login password (`LoginRequest.password`), the link token
(`LinkVerifyRequest.token`), and the booking hold code (`VerifyRequest.code`). The admin user form
checks its temporary password with the same rule (`admin_user_support._clean_field`). For those four,
the message must name no character and quote no text.

## Blocks, one sentence each

1. `scheduling/domain/text_rules.py`: `check_storable_text` gets a keyword `secret: bool = False`.
   When true, the message is the existing `NOT_STORABLE_MESSAGE` ("Remove the character that cannot
   be saved."), and `_message` is not called.
2. `scheduling/views/schemas.py` `StrictTextRules`: takes a keyword `secret` in `__init__`
   (`self.secret`, default False), passes it to `check_storable_text`, and raises that message.
   DRF stores constructor kwargs for `deepcopy`, so the flag survives copying. The one place that says
   what `secret` means is the docstring of `StrictTextRules`, a single added line.
3. `scheduling/views/auth_schemas.py`: `password = StrictText(..., secret=True)` on `LoginRequest`;
   `token = StrictLine(..., secret=True)` on `LinkVerifyRequest`.
4. `scheduling/views/hold_schemas.py`: `code = StrictCode(..., secret=True)` on `VerifyRequest`.
5. `scheduling/use_cases/admin_user_support.py` `_clean_field`: `check_storable_text(key, text,
   single_line=True, secret=key == "password")`. This is the only declaration the admin form has.
6. `scheduling/views/pages/booking_code.py`: no change. It shows `body.field_messages[0].message`
   from the schema, so the generic message reaches the page. Changed only if the red stage shows a leak.
7. `sign_in.py` and `booking_links.py`/`sign_in_link.py`: no change. The sign-in page passes the raw
   password to `sign_in_with_password` with no rule, and the link page passes the raw token to
   `use_link`. Their tests are guards; they are expected to pass before the change.

## Files to touch, in order

1. `scheduling/domain/test_text_rules.py` (test first)
2. `scheduling/views/test_api_text_fields.py` (API tests)
3. `scheduling/views/pages/test_booking_code_page.py` (change one existing expectation, see below)
4. `scheduling/views/pages/test_sign_in_link_pages.py` (guards)
5. `scheduling/views/pages/test_admin_user_pages.py` (admin temporary password)
6. `scheduling/domain/text_rules.py`
7. `scheduling/views/schemas.py`
8. `scheduling/views/auth_schemas.py`
9. `scheduling/views/hold_schemas.py`
10. `scheduling/use_cases/admin_user_support.py`

Files deliberately not touched: `booking_code.py`, `sign_in.py`, `sign_in_link.py`, `booking_links.py`,
`drlibre-specs.md`, any `doc/` file except this plan, any lock or migration file.

## Failing tests to write first

Expected values are stated in words. The planted secret is `Pl4nted-Secret-9x` for the password and
the token (the token is a `StrictLine`, so it takes no line break); the code is `482913` (six digits).
Each test puts a control character `\x0c` (form feed) after the planted value, so the value is the
text before the refused character.

Domain (`scheduling/domain/test_text_rules.py`):
- `returns_generic_message_without_text_when_field_is_secret`: `check_storable_text("password",
  "Pl4nted-Secret-9x\x0c", single_line=True, secret=True)` gives a Failure whose message equals
  "Remove the character that cannot be saved." and contains no part of the planted text.
- `returns_context_message_when_field_is_not_secret`: the same input without `secret` keeps the
  current message (guards against a mutant that drops the branch).

API (`scheduling/views/test_api_text_fields.py`):
- `returns_400_without_password_when_login_password_holds_control_character`: POST `/api/v1/auth/login`
  with the email of a seeded user and the planted password plus `\x0c`. Expected: 400, and the planted
  text appears nowhere in the response body.
- `returns_400_without_token_when_link_token_holds_control_character`: POST `/api/v1/auth/link/verify`
  with the planted token plus `\x0c`. Expected: 400, planted text absent.
- `returns_400_without_code_when_hold_code_holds_control_character`: POST
  `/api/v1/booking/holds/<id>/verify` with `482913\x0c`. Expected: 400, `482913` absent from the body.
  Hold setup follows the existing hold tests in the same directory.

Pages:
- `returns_422_without_code_when_code_holds_control_character` (`test_booking_code_page.py`): replaces
  `returns_the_rules_message_when_the_code_holds_a_form_feed`. The old test asserts that the page
  shows "Remove the character after "12"." That expectation is the defect, so it changes: the new
  test posts `4829\x0c13` and expects 422, the generic message on the code field, and no "4829" in
  the page. Stated here so the orchestrator sees the one changed expectation.
- `returns_wrong_credentials_without_password_when_password_holds_control_character`
  (`test_sign_in_link_pages.py`, guard): form POST to `/sign-in` with the planted password plus `\x0c`.
  Expected: the sign-in page with the wrong-credentials message, planted text absent.
- `returns_invalid_link_page_without_token_when_token_holds_control_character`
  (`test_sign_in_link_pages.py`, guard): POST to `/sign-in/link` with the planted token plus `\x0c`.
  Expected: 400, the invalid-link page, planted text absent.
- `returns_422_without_temporary_password_when_password_holds_control_character`
  (`test_admin_user_pages.py`): admin creates a user with `Pl4nted-Secret-9x\x0c` as the password.
  Expected: 422 with the generic message, planted text absent from the page. `PLANTED` already exists
  in that file.

Red proof: the API tests for password, token and code, the domain `secret` test, the admin test and
the rewritten code-page test must fail before the change. The sign-in and link guards may pass; the
review records that.

## Trust boundaries

- `/api/v1/auth/login`, `/api/v1/auth/link/verify`, `/api/v1/booking/holds/<id>/verify`: JSON body,
  validated by the schema (`validate_body`) before any use case. The change only alters the refusal text.
- Sign-in form, link form, code form: browser POST, cross-site check and `Origin` set in tests
  (`browser_post`). Authorization is unchanged.
- Admin user form: authorization by session role (admin) already enforced; the change is only the
  refusal text for `password`.

## Invariants and blast radius

- A refusal never quotes a password, token or code. Non-secret fields keep the context message.
- Validation and authorization are unchanged. Accepted values are unchanged.
- Audit log: no write path changes. No new log line.
- Blast radius: every `StrictTextRules` field without `secret` behaves as before. Only four fields change.
- `test_api_text_fields.py` parametrised NUL tests still see a ValidationError for the secret fields.
- `test_text_fields_as_filled.py` skips the password and code fields already; no change there.

## Domain entities (CLAUDE.md §3)

User (password, temporary password set by an Admin), SignInLink (token), BookingHold with
VerificationCode (code), Visitor (signs in or books), ApiClient (uses `/api/v1`).

## What I will not do

- No new message text: the existing `NOT_STORABLE_MESSAGE` is reused.
- No change to sign-in, link or booking page code; the schemas and the rule carry the change.
- No abstraction beyond one keyword on the rule and one on the schema class.
- No change to the wording of other messages, to the reason fields (one-line in pages, free in the
  API, an open decision already in the review), or to `drlibre-specs.md`.
- No ADR: the rule that a secret is never quoted is a small consequence of the existing rule, not a new decision.

## Mutation and gate

- `make mutate` covers `scheduling/domain`: the `secret` branch in `text_rules.py` needs both tests
  (the secret one and the non-secret one) so a mutant that drops the branch survives nowhere.
- `make gate`: the new `__init__` in `schemas.py` must have typed kwargs (`*args: object`,
  `secret: bool = False`, `**kwargs: object`) without `Any` or a bare `# type: ignore`. If the DRF stubs
  reject that override, the fallback is a class attribute on subclasses; this is a known risk.

## Risks

- The `__init__` override on DRF `Field` may need a typing workaround under mypy strict.
- A password that holds a control character gets "Remove the character that cannot be saved." with no
  position; this is accepted (the secret must not be quoted), and the user can still see which field.
- I did not read `drlibre-specs.md` sections on error messages; the decision is taken from the review
  finding and CLAUDE.md §9 ("never leak internals") and §11 ("no sensitive data in logs, URLs").
  If the spec disagrees, the review gets a line under "For the owner".

## Architect review

Verdict: approve. The change is one keyword on the domain rule, one on the schema base, and one
argument at each of four declarations. It sits in the right layers, and the tests come first.

Checked against the code (read, not run):
- `scheduling/domain/text_rules.py`, `scheduling/views/schemas.py`, `auth_schemas.py` (`LoginRequest.password`,
  `LinkVerifyRequest.token`), `hold_schemas.py` (`VerifyRequest.code`), `admin_user_support.py` (`_clean_field`,
  key `"password"`), `booking_code.py` (page message is `field_messages[0].message`), and the route
  `api/v1/booking/holds/<hold_id>/verify` in `drlibre/urls.py` all match the plan's description.
- `test_booking_code_page.py:79` holds the expectation the plan replaces. `PLANTED` exists in `test_admin_user_pages.py:25`.
- Sign-in page (`pages/sign_in.py:93`) passes the raw password to `sign_in_with_password` with no text rule, so its
  guard passes before the change, as the plan says.
- DRF `Field.__new__` keeps constructor kwargs for `deepcopy`, so `secret=True` survives copying.

Reasons, all non-blocking:
1. Owner asked: "say once, where the field is declared, that it is secret." The plan puts the sentence in the
   `StrictTextRules` class docstring. Put it as one comment at the first declaration (`LoginRequest.password`),
   or confirm the class docstring is the intended place.
2. Typing risk named in the plan is real: a `__init__(self, *args: object, secret: bool = False, **kwargs: object)`
   override may trip mypy strict's override check against drf-stubs. Decide the signature in the red stage;
   the class-attribute fallback is the answer if mypy rejects it.
3. API tests must send what the real clients send (CLAUDE.md, API routes): a browser `Origin` and cookie for the
   hold verify route if it is session-based, a bearer token if it is `ApiClient`. The plan does not say which.
4. Out of scope, pre-existing: `pages/sign_in_link.py:66` reads the link token from the query string on POST
   and GET. A token in a URL is a §11 concern ("no sensitive data in URLs"). This change does not quote it, since
   `use_link` has no text rule. Belongs under "For the owner" in the review, not in this diff.
5. Ladder: the plan sets the flag per declaration and does not add subclasses. That is the smaller option.
