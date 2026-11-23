#!/usr/bin/env bash
# triage.sh - the first five minutes of an incident.
# Where are the errors, what are they, and when did they start?
#
#   ./toolkit/triage.sh [log_dir]
set -uo pipefail

LOG_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)/logs}"
[ -d "$LOG_DIR" ] || { echo "No log directory at $LOG_DIR - run: python3 app/simulate.py" >&2; exit 1; }

bold() { printf '\n\033[1m%s\033[0m\n' "$1"; }

bold "1. Errors and warnings by service"
printf '%-24s %8s %7s %7s\n' SERVICE LINES WARN ERROR
for f in "$LOG_DIR"/*.log; do
    svc=$(basename "$f" .log)
    total=$(wc -l < "$f" | tr -d ' ')
    warn=$(grep -c ' WARN ' "$f")
    err=$(grep -c ' ERROR ' "$f")
    printf '%-24s %8s %7s %7s\n' "$svc" "$total" "$warn" "$err"
done

bold "2. Top error messages (numbers masked so similar errors group together)"
grep -h ' ERROR ' "$LOG_DIR"/*.log \
    | sed -E 's/.*\[([^]]+)\].*msg="([^"]*)".*/\1: \2/' \
    | sed -E 's/[0-9]+/N/g' \
    | sort | uniq -c | sort -rn | head -10

bold "3. Errors per 5-minute window (look for the spike)"
grep -h ' ERROR ' "$LOG_DIR"/*.log \
    | awk '{ split($2, t, ":"); printf "%s %s:%02d\n", $1, t[1], int(t[2] / 5) * 5 }' \
    | sort | uniq -c \
    | awk '{ bar = ""; for (i = 0; i < $1; i++) bar = bar "#"; printf "%s %s  %3d %s\n", $2, $3, $1, bar }'

bold "4. Leading indicators: warnings in the 30 minutes before the first error"
first_err=$(grep -h ' ERROR ' "$LOG_DIR"/*.log | sort | head -1 | awk '{print $1" "$2}')
if [ -n "$first_err" ]; then
    echo "First error at: $first_err"
    grep -h ' WARN ' "$LOG_DIR"/*.log | sort \
        | awk -v fe="$first_err" '
            function mins(t) { split(t, p, ":"); return p[1] * 60 + p[2] }
            BEGIN { split(fe, f, " "); fday = f[1]; fmin = mins(f[2]) }
            $1 == fday && ($1" "$2) < fe && mins($2) >= fmin - 30' \
        | sed -E 's/.*\[([^]]+)\].*msg="([^"]*)".*/\1: \2/' | sed -E 's/[0-9]+/N/g' \
        | sort | uniq -c | sort -rn | head -5
    echo "(Slow responses before an outage usually mean resource exhaustion: connection pool, disk, memory.)"
else
    echo "No errors found."
fi

bold "5. First and last error"
grep -h ' ERROR ' "$LOG_DIR"/*.log | sort | sed -n '1p;$p'

echo
echo "Next: trace an example with ./toolkit/trace_txn.sh <TXN_ID>, check the batch with ./toolkit/check_batch.sh"
