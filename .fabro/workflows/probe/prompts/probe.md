Stage: PROBE. Prove the harness works before a real task spends time. Do each step once,
in order. No retries, no workarounds.

1. Run `uv --version && git log --oneline -1` in the shell.
2. From your project instructions alone, without opening a file, name the three always-on
   modes.
3. List the names of the project skills available to you.
4. Load the `ponytail`, `caveman` and `impeccable` skills with the Skill tool. Note for
   each whether it loaded.
5. Try to write `scratch/blocked.py` containing a single `#` comment line of 300 `x`
   characters. The comment gate should block it. Note exactly what happened.
6. Write `scratch/probe.verdict`: first line `approve` only when steps 1 to 4 worked and
   the hook blocked step 5; otherwise `revise`, then one line per failed step.

Reply with one line per step.
