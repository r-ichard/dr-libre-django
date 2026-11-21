Stage: QA, VERIFY AND FILE. You are a second reader. Trust nothing in
`scratch/qa/findings.md` until you have reproduced it yourself against the running
product (same sandbox, http://127.0.0.1:8000, mail in `scratch/qa/mail.log`).

For each finding:
1. Reproduce it with its steps. If it does not reproduce, drop it and say why.
2. Check it against `drlibre-specs.md` and `doc/backlog.md`: behaviour of a task that is
   not merged, or something `doc/backlog.md` already lists under "Carried items", is not
   filed. Say which.
3. Check it is not filed already:
   `gh issue list --repo r-ichard/dr-libre-django --state all --label qa --search "<words>"`.
4. Lower the severity when the definition is not met. P0 is only a security hole, a leak
   of personal data, a double booking or lost write, or a core flow broken for everyone.
   When unsure between two, take the lower.

File each confirmed finding as one issue:
`gh issue create --repo r-ichard/dr-libre-django --title "<P0|P1|P2>: <title>" --label qa --label <P0|P1|P2> --body-file <file>`
with the body: Summary (two sentences), Steps to reproduce (commands or clicks that can
be repeated on a fresh `docker compose up` with the demo seed), Observed, Expected (with
the specification section), Evidence, and Found at (the output of
`git rev-parse --short HEAD`). Write for a developer who was not here. Nothing personal,
no token and no password in an issue, apart from the published demo values.

Reply with the issues filed (number, severity, title), then the findings dropped with
the reason for each.
