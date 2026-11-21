#!/bin/sh
# Claude Code PreToolUse hook for Bash, active only in fabro stages (DRLIBRE_PIPELINE=1).
# A stage ends when its agent replies; a process left behind runs on into later stages.
# Exit 2 blocks the call and shows stderr to the agent.

PATTERN='"run_in_background"[[:space:]]*:[[:space:]]*true'
PATTERN="$PATTERN"'|(^|[^[:alnum:]_])(nohup|setsid|disown)([^[:alnum:]_]|$)'
PATTERN="$PATTERN"'|[^&]&([[:space:]]|\\n)*"[[:space:]]*[,}]'
# A subshell that ends in "&)" detaches just as well.
PATTERN="$PATTERN"'|[^&]&[[:space:]]*\)'

starts_background() {
    printf '%s' "$1" | grep -Eq "$PATTERN"
}

if [ "$1" = "--self-test" ]; then
    failures=0
    expect() {
        if starts_background "$2"; then seen=blocked; else seen=allowed; fi
        [ "$seen" = "$1" ] || { echo "self-test: expected $1, got $seen: $2" >&2; failures=1; }
    }
    expect blocked '{"tool_input":{"command":"sleep 5","run_in_background":true}}'
    expect blocked '{"tool_input":{"command":"nohup sleep 5 > /dev/null"}}'
    expect blocked '{"tool_input":{"command":"python run.py &"}}'
    expect blocked '{"tool_input":{"command":"python run.py &\n"},"x":1}'
    expect blocked '{"tool_input":{"command":"(timeout 10 sleep 30 &)"}}'
    expect allowed '{"tool_input":{"command":"make test 2>&1 | tail -5"}}'
    expect allowed '{"tool_input":{"command":"make lint && make test"}}'
    expect allowed '{"tool_input":{"command":"sleep 5","run_in_background":false}}'
    expect allowed '{"tool_input":{"command":"server & pid=$!; curl -s localhost; kill $pid"}}'
    [ "$failures" -eq 0 ] && echo "no_background self-test: ok"
    exit "$failures"
fi

[ "$DRLIBRE_PIPELINE" = "1" ] || exit 0

if starts_background "$(cat)"; then
    echo "Background processes are blocked in pipeline stages: the stage ends and the" >&2
    echo "process keeps changing files and running tests under later stages. Run the" >&2
    echo "command in the foreground with a timeout, split long work into several" >&2
    echo "foreground commands, and stop anything you start inside the same command." >&2
    exit 2
fi
exit 0
