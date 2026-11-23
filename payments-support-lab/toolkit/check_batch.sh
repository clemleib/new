#!/usr/bin/env bash
# check_batch.sh - morning check on the overnight settlement ETL load.
# Did the file arrive, is it complete, did the load succeed, what was rejected?
#
#   ./toolkit/check_batch.sh
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INBOUND="$ROOT/data/inbound"

echo "== 1. File arrival"
FILE=$(ls -1 "$INBOUND"/SETTLEMENT_*.dat 2>/dev/null | sort | tail -1)
if [ -z "$FILE" ]; then
    echo "MISSING: no settlement file in $INBOUND - chase the payment network, check the file transfer job"
    exit 2
fi
echo "Latest file: $(basename "$FILE")  ($(wc -c < "$FILE" | tr -d ' ') bytes)"

echo
echo "== 2. File integrity (header / trailer / row count / total)"
awk -F'|' '
    $1 == "H" { header = $2 }
    $1 == "D" { rows++; total += $3 }
    $1 == "T" { trailer_rows = $2; trailer_total = $3 }
    END {
        printf "Header batch   : %s\n", (header ? header : "MISSING")
        printf "Trailer rows   : %s   detail rows counted: %d\n", (trailer_rows != "" ? trailer_rows : "MISSING"), rows
        printf "Trailer total  : %s\n", (trailer_total != "" ? trailer_total : "MISSING")
        if (trailer_rows == "") print "RESULT: FAIL - no trailer, file is probably truncated"
        else if (rows != trailer_rows) print "RESULT: FAIL - row count does not match trailer"
        else print "RESULT: OK - file is complete (row-level problems are checked by the load)"
    }' "$FILE"

echo
echo "== 3. Load result (batch_control)"
python3 "$ROOT/toolkit/run_sql.py" -q "
SELECT batch_id, status, expected_rows, loaded_rows, rejected_rows, finished_at
FROM batch_control ORDER BY started_at DESC LIMIT 1;"

echo "== 4. Rejected rows"
REJ="$ROOT/data/rejects/$(basename "$FILE" .dat).rej"
if [ -s "$REJ" ]; then
    echo "line|reason|original row"
    cat "$REJ"
    echo
    echo "Reasons:"
    cut -d'|' -f2 "$REJ" | sort | uniq -c
    echo "Action: raise with the payment network for a corrected file, or repair and re-run the load"
    echo "        (the load is idempotent - re-running replaces the batch, it does not double-load)."
else
    echo "None."
fi

echo
echo "== 5. ETL job log"
cat "$ROOT/logs/etl-settlement-load.log"
