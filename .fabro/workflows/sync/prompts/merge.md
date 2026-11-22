You join a finished task branch to `main`. The task on this branch passed its own plan,
tests and review; `main` moved while it ran, because a second task merged first. Your
job is the meeting of the two and nothing else: no new feature, no refactor, no clean-up.

Goal of this run: {{ goal }}

Read `CLAUDE.md` first. Foreground commands only.

1. Get `main` and merge it into this branch:
   `git fetch https://github.com/r-ichard/dr-libre-django main && git merge FETCH_HEAD`.
   Merge, not rebase: the branch is squashed when it reaches `main`.
2. Each conflict has two finished, reviewed sides. Keep the behaviour of both. Never drop
   a line of either side to make the merge easy, and change nothing outside the conflict
   to make it fit. If the two sides cannot both hold, stop: say which lines and why in
   your reply, and leave the conflict unresolved. Do not choose a winner.
3. Process documents are the orchestrator's: for `doc/backlog.md`, `doc/retro.md`,
   `doc/backlog/**`, `doc/qa/**`, `CLAUDE.md`, `.fabro/**`, `.claude/**` and `scripts/**`
   take the version of `main`, always.
4. Generated files are generated again, not merged by hand: `doc/data-model.md` with its
   management command. If both sides added a migration with the same number, renumber
   the branch's migration and its dependency; never touch a migration that is on `main`.
5. Run `make lint && make test && make gate`. A failure that comes from the meeting of
   the two sides (a rule `main` gained that this branch's code does not keep yet, or the
   reverse) is yours: fix it in the smallest way, in the code that breaks the rule, and
   keep the test that found it unchanged. A failure that has nothing to do with the
   merge: stop and report it, do not fix it.
6. Commit the merge.

If this is not your first visit, the gate after you failed: read its output in the
context above and fix only what it names.

Reply with: each conflict (file, what each side had, how both were kept); each failure
that came from the meeting and its fix; every line of either side that you dropped,
which must be none; and what you did not run.
