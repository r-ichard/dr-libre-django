#!/bin/sh
# Red gate (conventions §10): succeed only when the suite really fails. The Makefile
# sentinel "not configured" means the stack is unbound, which is not a red test.
out=$("$@" 2>&1); code=$?
printf '%s\n' "$out"
[ "$code" -ne 0 ] && ! printf '%s' "$out" | grep -q 'not configured'
