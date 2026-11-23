#!/usr/bin/env python3
"""Re-post payments stuck in VALIDATED once the ledger is healthy again.

    python3 toolkit/repost_stuck.py                 # dry run: show what would change
    python3 toolkit/repost_stuck.py --apply --ticket INC0012345

Production-support safety rules built in:
  * dry run by default - nothing changes without --apply
  * a change/incident ticket is required to apply
  * idempotent - a payment that already has a ledger entry is skipped, so a
    second run can never double-post
  * one transaction - all or nothing
  * every action is written to the ledger-posting log for audit
"""
import argparse
import datetime as dt
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "payments.db"
LOG = ROOT / "logs" / "ledger-posting.log"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually re-post (default is a dry run)")
    ap.add_argument("--ticket", help="incident or change ticket, required with --apply")
    args = ap.parse_args()
    if args.apply and not args.ticket:
        ap.error("--apply needs --ticket (no production data fix without a ticket)")

    db = sqlite3.connect(DB)
    stuck = db.execute("""
        SELECT p.txn_id, p.amount, p.currency, p.client
        FROM payments p
        LEFT JOIN ledger_entries l ON l.txn_id = p.txn_id
        WHERE p.status = 'VALIDATED' AND l.txn_id IS NULL
        ORDER BY p.txn_id""").fetchall()

    total = sum(r[1] for r in stuck)
    print(f"{len(stuck)} stuck payment(s), total value {total:,.2f}")
    for txn, amount, ccy, client in stuck:
        print(f"  {txn}  {amount:>12,.2f} {ccy}  {client}")
    if not stuck:
        return
    if not args.apply:
        print("\nDRY RUN - nothing changed. Re-run with --apply --ticket <ID> once the ledger DB is healthy.")
        return

    now = dt.datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M:%S.") + f"{now.microsecond // 1000:03d}"
    with db:  # one transaction: commits on success, rolls back on any error
        for txn, amount, ccy, _ in stuck:
            db.execute("INSERT INTO ledger_entries (txn_id, amount, currency, posted_at) VALUES (?,?,?,?)",
                       (txn, amount, ccy, stamp))
            db.execute("UPDATE payments SET status = 'POSTED', updated_at = ? WHERE txn_id = ?", (stamp, txn))
    with open(LOG, "a") as fh:
        for txn, amount, ccy, _ in stuck:
            fh.write(f'{stamp} INFO  [ledger-posting] txn={txn} latency_ms=0 '
                     f'msg="Manual re-post ticket={args.ticket} entry_amount={amount:.2f} {ccy}"\n')
    print(f"\nRe-posted {len(stuck)} payment(s) under {args.ticket}. Re-run healthcheck.py to confirm.")


if __name__ == "__main__":
    main()
