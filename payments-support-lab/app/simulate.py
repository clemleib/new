#!/usr/bin/env python3
"""Simulate one business day on a small payments platform.

Payments flow through three microservices, each writing its own log:

    payment-intake  ->  payment-validation  ->  ledger-posting

At end of day the payment network sends a settlement file. The nightly ETL
job (etl_load.py) loads it, and the support team reconciles it against the
ledger.

Faults are injected on purpose so there is something to support:
  ledger_timeout   ledger DB connection pool exhausted 14:05-14:25 -> stuck payments
  duplicates       idempotency cache down -> client resends are posted twice
  bad_file         malformed rows in the settlement file -> ETL rejects
  amount_mismatch  rounding bug in ledger posting for EUR -> recon breaks

Usage:
    python3 app/simulate.py                  # all faults (default)
    python3 app/simulate.py --faults none    # a clean day, everything GREEN
    python3 app/simulate.py --faults ledger_timeout,bad_file
"""
import argparse
import datetime as dt
import random
import shutil
import sqlite3
from pathlib import Path

import etl_load

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOGS = ROOT / "logs"
DB_PATH = DATA / "payments.db"
ALL_FAULTS = ["ledger_timeout", "duplicates", "bad_file", "amount_mismatch"]

SCHEMA = """
CREATE TABLE payments (
    payment_id    INTEGER PRIMARY KEY,
    txn_id        TEXT NOT NULL UNIQUE,
    client_ref    TEXT NOT NULL,        -- client's own reference; should be unique per payment
    client        TEXT NOT NULL,
    amount        REAL NOT NULL,
    currency      TEXT NOT NULL,
    status        TEXT NOT NULL,        -- VALIDATED, REJECTED, POSTED
    reject_reason TEXT,
    received_at   TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE TABLE ledger_entries (
    entry_id  INTEGER PRIMARY KEY,
    txn_id    TEXT NOT NULL,
    amount    REAL NOT NULL,
    currency  TEXT NOT NULL,
    posted_at TEXT NOT NULL
);
CREATE TABLE settlement_staging (
    batch_id   TEXT NOT NULL,
    txn_id     TEXT NOT NULL,
    amount     REAL NOT NULL,
    currency   TEXT NOT NULL,
    value_date TEXT NOT NULL
);
CREATE TABLE batch_control (
    batch_id      TEXT PRIMARY KEY,
    file_name     TEXT NOT NULL,
    expected_rows INTEGER,
    loaded_rows   INTEGER,
    rejected_rows INTEGER,
    status        TEXT NOT NULL,        -- COMPLETED, COMPLETED_WITH_ERRORS, FAILED
    started_at    TEXT NOT NULL,
    finished_at   TEXT
);
"""

CLIENTS = {
    "NWL": "Northwind Logistics", "MPG": "Maple Grocers", "LSE": "Lakeshore Energy",
    "HBF": "Harbour Freight", "BWP": "Bluewater Pharma", "GRC": "Granite Construction",
    "AUR": "Aurora Retail", "SMT": "Summit Telecom",
}
CURRENCIES = ["CAD"] * 5 + ["USD"] * 3 + ["EUR", "GBP"]
REJECT_REASONS = ["INVALID_ACCOUNT", "SANCTIONS_SCREEN_HIT", "DAILY_LIMIT_EXCEEDED"]


def fmt(ts):
    return ts.strftime("%Y-%m-%d %H:%M:%S.") + f"{ts.microsecond // 1000:03d}"


def ms(n):
    return dt.timedelta(milliseconds=n)


def parse_faults(value):
    if value == "all":
        return set(ALL_FAULTS)
    if value == "none":
        return set()
    faults = {f.strip() for f in value.split(",") if f.strip()}
    unknown = faults - set(ALL_FAULTS)
    if unknown:
        raise SystemExit(f"Unknown fault(s): {', '.join(sorted(unknown))}. Choose from {ALL_FAULTS}")
    return faults


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="business date (YYYY-MM-DD)")
    ap.add_argument("--payments", type=int, default=600)
    ap.add_argument("--faults", default="all", help=f"'all', 'none' or a comma list of {ALL_FAULTS}")
    ap.add_argument("--seed", type=int, default=42, help="same seed = same day, so demos are repeatable")
    args = ap.parse_args()

    faults = parse_faults(args.faults)
    rng = random.Random(args.seed)
    day = dt.date.fromisoformat(args.date)
    at = lambda h, m: dt.datetime.combine(day, dt.time(h, m))  # noqa: E731

    # Fresh environment every run.
    for d in (DATA, LOGS):
        shutil.rmtree(d, ignore_errors=True)
    for d in (DATA / "inbound", DATA / "rejects", LOGS):
        d.mkdir(parents=True)
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)

    # 1. Build the day's payment requests.
    requests = []
    for _ in range(args.payments):
        code = rng.choice(list(CLIENTS))
        requests.append({
            "t": at(9, 0) + dt.timedelta(seconds=rng.uniform(0, 8 * 3600)),
            "client_ref": f"{code}-{rng.randint(100000, 999999)}",
            "client": CLIENTS[code],
            "amount": round(min(rng.lognormvariate(8, 1.2), 2_000_000), 2),
            "ccy": rng.choice(CURRENCIES),
            "force_valid": False,
            "duplicate": False,
        })
    if "duplicates" in faults:
        morning = [r for r in requests if 10 <= r["t"].hour < 12]
        for orig in rng.sample(morning, 5):
            orig["force_valid"] = True
            dup = dict(orig, t=orig["t"] + dt.timedelta(seconds=rng.randint(90, 240)), duplicate=True)
            requests.append(dup)
    requests.sort(key=lambda r: r["t"])

    # 2. Push each payment through the three services.
    events = []      # (ts, service, level, txn_id, latency_ms, message)
    settled = []     # rows the payment network will confirm in the settlement file
    mismatches_left = 3 if "amount_mismatch" in faults else 0
    slow_start, outage_start, outage_end = at(13, 55), at(14, 5), at(14, 25)

    for i, r in enumerate(requests, start=1):
        txn = f"TXN{i:06d}"
        t0, amt, ccy = r["t"], r["amount"], r["ccy"]

        # payment-intake
        lat = rng.randint(5, 40)
        if r["duplicate"]:
            events.append((t0, "payment-intake", "WARN", txn, lat,
                           "Duplicate check skipped: idempotency cache unavailable"))
        events.append((t0, "payment-intake", "INFO", txn, lat,
                       f"Payment received client_ref={r['client_ref']} amount={amt:.2f} {ccy}"))

        # payment-validation
        t1 = t0 + ms(lat + rng.randint(1, 20))
        lat = rng.randint(10, 80)
        if not r["force_valid"] and rng.random() < 0.03:
            reason = rng.choice(REJECT_REASONS)
            events.append((t1, "payment-validation", "WARN", txn, lat, f"Payment rejected reason={reason}"))
            status, reason_col, updated = "REJECTED", reason, t1
        else:
            events.append((t1, "payment-validation", "INFO", txn, lat, "Payment validated"))
            status, reason_col, updated = "VALIDATED", None, t1
            settled.append((txn, amt, ccy))

            # ledger-posting
            t2 = t1 + ms(lat + rng.randint(1, 20))
            if "ledger_timeout" in faults and outage_start <= t2 < outage_end:
                for attempt in (1, 2, 3):
                    events.append((t2, "ledger-posting", "WARN", txn, 30000,
                                   f"DB connection pool exhausted, retry attempt={attempt}/3"))
                    t2 += dt.timedelta(seconds=30)
                events.append((t2, "ledger-posting", "ERROR", txn, 30000,
                               "Posting failed: DB connection timeout after 3 retries, payment left in VALIDATED"))
            else:
                if "ledger_timeout" in faults and slow_start <= t2 < outage_start:
                    lat, level, msg = rng.randint(1500, 4000), "WARN", "Payment posted (slow response from ledger DB)"
                else:
                    lat, level, msg = rng.randint(20, 120), "INFO", "Payment posted"
                posted_amt = amt
                if mismatches_left and ccy == "EUR" and amt != int(amt):
                    posted_amt = float(int(amt))  # the rounding bug: cents truncated
                    mismatches_left -= 1
                events.append((t2, "ledger-posting", level, txn, lat, f"{msg} entry_amount={posted_amt:.2f} {ccy}"))
                db.execute("INSERT INTO ledger_entries (txn_id, amount, currency, posted_at) VALUES (?,?,?,?)",
                           (txn, posted_amt, ccy, fmt(t2 + ms(lat))))
                status, updated = "POSTED", t2 + ms(lat)

        db.execute(
            "INSERT INTO payments (txn_id, client_ref, client, amount, currency, status, reject_reason,"
            " received_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (txn, r["client_ref"], r["client"], amt, ccy, status, reason_col, fmt(t0), fmt(updated)))
    db.commit()

    # 3. Write one log file per service.
    events.sort(key=lambda e: e[0])
    handles = {}
    for ts, svc, level, txn, lat, msg in events:
        fh = handles.get(svc) or handles.setdefault(svc, open(LOGS / f"{svc}.log", "w"))
        fh.write(f'{fmt(ts)} {level:<5} [{svc}] txn={txn} latency_ms={lat} msg="{msg}"\n')
    for fh in handles.values():
        fh.close()

    # 4. Payment network's end-of-day settlement file (header / detail / trailer).
    vd = day.isoformat()
    rows = [f"D|{txn}|{amt:.2f}|{ccy}|{vd}" for txn, amt, ccy in settled]
    if "bad_file" in faults:
        corrupt = rng.sample(range(len(rows)), 4)
        txn, amt, ccy = settled[corrupt[0]]
        rows[corrupt[0]] = f"D|{txn}|{amt + 10000:,.2f}|{ccy}|{vd}"      # thousands separator
        txn, amt, ccy = settled[corrupt[1]]
        rows[corrupt[1]] = f"D|{txn}|{amt:.2f}||{vd}"                    # missing currency
        txn, amt, ccy = settled[corrupt[2]]
        rows[corrupt[2]] = f"D|{txn}|{amt:.2f}|{ccy}|{day:%d/%m/%Y}"     # wrong date format
        txn, amt, ccy = settled[corrupt[3]]
        rows[corrupt[3]] = f"D|{txn}|{amt:.2f}|{ccy}"                    # truncated row
    total = sum(a for _, a, _ in settled)
    settle_file = DATA / "inbound" / f"SETTLEMENT_{day:%Y%m%d}.dat"
    settle_file.write_text("\n".join(
        [f"H|BATCH{day:%Y%m%d}|{vd}|PAYNET"] + rows + [f"T|{len(rows)}|{total:.2f}"]) + "\n")
    db.close()

    print(f"Simulated {len(requests)} payments for {day} with faults: {', '.join(sorted(faults)) or 'none'}")
    print(f"  logs        -> {LOGS.relative_to(ROOT)}/")
    print(f"  database    -> {DB_PATH.relative_to(ROOT)}")
    print(f"  settlement  -> {settle_file.relative_to(ROOT)}")

    # 5. Overnight batch: run the ETL load at 01:30 the next morning.
    run_ts = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(1, 30))
    status = etl_load.run(DB_PATH, settle_file, LOGS / "etl-settlement-load.log", run_ts)
    print(f"  nightly ETL -> {status}")
    print("\nNext: ./toolkit/triage.sh   then   python3 toolkit/healthcheck.py")


if __name__ == "__main__":
    main()
