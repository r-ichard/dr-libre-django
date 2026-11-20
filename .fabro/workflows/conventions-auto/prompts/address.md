Stage: ADDRESS BLOCKING FINDINGS. Read CLAUDE.md, then the newest file in `doc/reviews/`
and the reasons in `scratch/review.verdict`.

For every blocking finding:
1. Write or sharpen the failing test first, see it red for the right reason, then fix the
   root cause, not the symptom (§1, §10). Smallest change, right place, no refactors.
2. Record the outcome next to the finding in the review document: `fixed` with the test
   name, or `not fixed` with the reason.

Leave the Later list alone. Run `make lint && make test && make gate` until clean.

Reply with the table of findings and outcomes.
