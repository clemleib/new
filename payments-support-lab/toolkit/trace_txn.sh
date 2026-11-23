#!/usr/bin/env bash
# trace_txn.sh - follow one payment across every service, then show its DB record.
# The txn id works like a correlation ID: it is logged by every microservice.
#
#   ./toolkit/trace_txn.sh TXN000405
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TXN="${1:-}"

# Validate input before it goes anywhere near grep or SQL (no injection).
if ! [[ "$TXN" =~ ^TXN[0-9]{6}$ ]]; then
    echo "Usage: $0 TXN000123" >&2
    exit 1
fi

echo "== Log trail for $TXN (all services, in time order)"
if ! grep -h "txn=$TXN " "$ROOT"/logs/*.log | sort; then
    echo "No log lines found for $TXN"
fi

echo
python3 "$ROOT/toolkit/run_sql.py" -q "
-- Payment record
SELECT txn_id, client, client_ref, amount, currency, status, reject_reason, received_at, updated_at
FROM payments WHERE txn_id = '$TXN';
-- Ledger entry
SELECT entry_id, amount, currency, posted_at FROM ledger_entries WHERE txn_id = '$TXN';
-- Settlement file record
SELECT batch_id, amount, currency, value_date FROM settlement_staging WHERE txn_id = '$TXN';"
