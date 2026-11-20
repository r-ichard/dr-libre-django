#!/bin/sh
# Verdict gate: exit 0 only when the first word of the verdict file is "approve".
# A missing file is a failed review, not a pass: reviewers must write the file (fail closed).
file="$1"
[ -f "$file" ] || { echo "verdict gate: $file missing" >&2; exit 1; }
first=$(head -n 1 "$file" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
echo "verdict gate: $file says '$first'"
[ "$first" = "approve" ]
