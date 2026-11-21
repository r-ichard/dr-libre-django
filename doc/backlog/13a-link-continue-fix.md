Task 13a: the sign-in link does not work in a browser.

Found by the orchestrator in Chrome after task 13. Small fix, wide lesson.

1. Pressing "Continue" on `/sign-in/link` answers 403, "CSRF verification failed. Origin
   checking failed - null does not match any trusted origins". The page sets
   `Referrer-Policy: no-referrer`; a browser then sends `Origin: null` with the form's
   POST, and Django's cross-site request check refuses it. Reproduced with curl: the same
   POST passes the check with the site's own origin and with no `Origin` header, which is
   what the test client sends, so every test passed. Make the button work in a browser
   while the token still cannot reach another site through a referrer, and say in the
   plan why the policy you choose does both.
2. Tests that would have caught it. Page forms are tested as a browser sends them: with
   the cross-site request check enforced and the `Origin` header a browser sets. Add that
   for this form, and for the sign-in, sign-out and link request forms, in a helper the
   next page tasks reuse. A POST with `Origin: null` or another site's origin must still
   be refused.
3. The refusal page. A failed cross-site request check shows Django's own page, with
   help text about `DEBUG` and template tags. Show the product's 403 page with the
   correlation id, whatever `DEBUG` says.
4. `background_mail._send` catches `OSError` only; any other exception stays in the
   future and is never logged (review of task 13). Log it, without the address or the
   body.

The orchestrator follows a link from the smtp4dev inbox in Chrome again.

Done when `make setup && make lint && make test && make gate && make mutate` pass from a
fresh clone.
