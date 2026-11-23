#!/usr/bin/env python3
"""Nightly ETL: load the payment network's settlement file into settlement_staging.

File layout (pipe-delimited):
    H|<batch_id>|<value_date>|<sender>
    D|<txn_id>|<amount>|<currency>|<value_date>      (one per settled payment)
    T|<detail_row_count>|<total_amount>

Controls built in (each is a support talking point):
  * header/trailer check   - a missing trailer means a truncated file -> FAILED
  * row-level validation   - bad rows go to data/rejects/<file>.rej with a reason
  * count reconciliation   - loaded + rejected must equal the trailer count
  * idempotent re-run      - the batch's staging rows are deleted before reload
  * batch_control table    - one auditable status row per batch

Usage:
    python3 app/etl_load.py [settlement_file]      # defaults to the newest file in data/inbound
"""
import datetime as dt
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TXN_RE = re.compile(r"^TXN\d{6}$")
AMOUNT_RE = re.compile(r"^\d+\.\d{2}$")
CURRENCIES = {"CAD", "USD", "EUR", "GBP"}
SERVICE = "etl-settlement-load"


def validate(fields):
    """Return a reject reason, or None if the detail row is good."""
    if len(fields) != 5:
        return "WRONG_FIELD_COUNT"
    _, txn, amount, ccy, value_date = fields
    if not TXN_RE.match(txn):
        return "BAD_TXN_ID"
    if not AMOUNT_RE.match(amount):
        return "BAD_AMOUNT_FORMAT"
    if ccy not in CURRENCIES:
        return "BAD_CURRENCY"
    try:
        dt.date.fromisoformat(value_date)
    except ValueError:
        return "BAD_VALUE_DATE"
    return None


def run(db_path, file_path, log_path, run_ts=None):
    file_path = Path(file_path)
    clock = [run_ts or dt.datetime.now()]

    def now():
        return clock[0].strftime("%Y-%m-%d %H:%M:%S.") + f"{clock[0].microsecond // 1000:03d}"

    log_fh = open(log_path, "a")

    def log(level, msg, txn="-"):
        clock[0] += dt.timedelta(milliseconds=7)
        log_fh.write(f'{now()} {level:<5} [{SERVICE}] txn={txn} latency_ms=0 msg="{msg}"\n')

    db = sqlite3.connect(db_path)
    started = now()
    log("INFO", f"Load started file={file_path.name}")

    def finish(batch_id, expected, loaded, rejected, status):
        db.execute("INSERT OR REPLACE INTO batch_control VALUES (?,?,?,?,?,?,?,?)",
                   (batch_id, file_path.name, expected, loaded, rejected, status, started, now()))
        db.commit()
        level = {"COMPLETED": "INFO", "COMPLETED_WITH_ERRORS": "WARN"}.get(status, "ERROR")
        log(level, f"Load finished status={status} expected={expected} loaded={loaded} rejected={rejected}")
        log_fh.close()
        db.close()
        return status

    if not file_path.exists():
        log("ERROR", f"Settlement file not found: {file_path.name}")
        return finish(f"UNKNOWN_{file_path.stem}", None, 0, 0, "FAILED")

    lines = file_path.read_text().splitlines()
    if not lines or not lines[0].startswith("H|"):
        log("ERROR", "Header record missing or invalid")
        return finish(f"UNKNOWN_{file_path.stem}", None, 0, 0, "FAILED")
    batch_id = lines[0].split("|")[1]
    if not lines[-1].startswith("T|"):
        log("ERROR", "Trailer record missing - file is probably truncated")
        return finish(batch_id, None, 0, 0, "FAILED")
    expected = int(lines[-1].split("|")[1])
    details = lines[1:-1]

    # Idempotent: a re-run replaces this batch instead of double-loading it.
    db.execute("DELETE FROM settlement_staging WHERE batch_id = ?", (batch_id,))

    loaded, rejects = 0, []
    for line_no, line in enumerate(details, start=2):
        fields = line.split("|")
        reason = validate(fields)
        if reason:
            rejects.append(f"{line_no}|{reason}|{line}")
            log("ERROR", f"Row {line_no} rejected reason={reason}", txn=fields[1] if len(fields) > 1 else "-")
            continue
        _, txn, amount, ccy, value_date = fields
        db.execute("INSERT INTO settlement_staging VALUES (?,?,?,?,?)", (batch_id, txn, float(amount), ccy, value_date))
        loaded += 1

    if len(details) != expected:
        log("ERROR", f"Detail row count {len(details)} does not match trailer count {expected}")

    reject_file = ROOT / "data" / "rejects" / f"{file_path.stem}.rej"
    reject_file.parent.mkdir(parents=True, exist_ok=True)
    reject_file.write_text("".join(r + "\n" for r in rejects))

    status = "COMPLETED" if not rejects and loaded == expected else "COMPLETED_WITH_ERRORS"
    return finish(batch_id, expected, loaded, len(rejects), status)


def main():
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        files = sorted((ROOT / "data" / "inbound").glob("SETTLEMENT_*.dat"))
        if not files:
            raise SystemExit("No settlement file in data/inbound - run app/simulate.py first")
        path = files[-1]
    status = run(ROOT / "data" / "payments.db", path, ROOT / "logs" / f"{SERVICE}.log")
    print(f"{path.name}: {status}")
    sys.exit(0 if status == "COMPLETED" else 1)


if __name__ == "__main__":
    main()
