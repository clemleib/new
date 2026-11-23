#!/usr/bin/env python3
"""Health check for the payments platform: services, batch and data, rated RED / AMBER / GREEN.

    python3 toolkit/healthcheck.py

Prints a summary, writes reports/dashboard.html, and exits 0 (GREEN), 1 (AMBER)
or 2 (RED), so a scheduler or monitoring tool could call it and raise an alert.
"""
import datetime as dt
import html
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS, DB, REPORT = ROOT / "logs", ROOT / "data" / "payments.db", ROOT / "reports" / "dashboard.html"
LINE_RE = re.compile(r'^(\S+ \S+) (\w+)\s+\[(\S+)\] txn=(\S+) latency_ms=(\d+) msg="(.*)"$')
SERVICES = ["payment-intake", "payment-validation", "ledger-posting"]
RANK = {"GREEN": 0, "AMBER": 1, "RED": 2}

# Thresholds - in a real team these come from the service's agreed SLOs.
ERROR_RATE_RED = 0.01      # 1% of events
P95_LATENCY_AMBER = 1000   # ms


def p95(values):
    if not values:
        return 0
    values = sorted(values)
    return values[int(0.95 * (len(values) - 1))]


def check_services():
    results = []
    for svc in SERVICES:
        path = LOGS / f"{svc}.log"
        if not path.exists():
            results.append({"name": svc, "status": "RED", "detail": "log file missing - service down?"})
            continue
        events = [m.groups() for m in map(LINE_RE.match, path.read_text().splitlines()) if m]
        txns = {e[3] for e in events}
        errors = sum(1 for e in events if e[1] == "ERROR")
        warns = sum(1 for e in events if e[1] == "WARN")
        latency = p95([int(e[4]) for e in events if e[1] == "INFO"] or [0])
        rate = errors / len(txns) if txns else 0
        status = "RED" if rate >= ERROR_RATE_RED else "AMBER" if errors or latency >= P95_LATENCY_AMBER else "GREEN"
        results.append({
            "name": svc, "status": status,
            "detail": f"{len(txns)} payments, {errors} errors ({rate:.1%}), {warns} warnings, p95 {latency} ms",
        })
    return results


def check_data(db):
    one = lambda sql: db.execute(sql).fetchone()  # noqa: E731
    out = []

    batch = one("SELECT status, expected_rows, loaded_rows, rejected_rows, batch_id FROM batch_control "
                "ORDER BY started_at DESC LIMIT 1")
    if batch is None:
        out.append({"name": "Settlement ETL", "status": "RED", "detail": "no batch has run"})
    else:
        st, exp, loaded, rej, bid = batch
        status = {"COMPLETED": "GREEN", "COMPLETED_WITH_ERRORS": "AMBER"}.get(st, "RED")
        out.append({"name": "Settlement ETL", "status": status,
                    "detail": f"{bid} {st}: {loaded}/{exp} rows loaded, {rej} rejected"})

    n, value = one("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments WHERE status = 'VALIDATED'")
    out.append({"name": "Stuck payments", "status": "RED" if n else "GREEN",
                "detail": f"{n} validated but not posted, value {value:,.2f}"})

    n, value = one("""SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM (
                        SELECT amount, ROW_NUMBER() OVER (PARTITION BY client_ref, amount, currency
                                                          ORDER BY received_at) AS rn
                        FROM payments WHERE status = 'POSTED') WHERE rn > 1""")
    out.append({"name": "Duplicate postings", "status": "RED" if n else "GREEN",
                "detail": f"{n} duplicate postings, value {value:,.2f}"})

    breaks = one("""SELECT
        (SELECT COUNT(*) FROM settlement_staging s LEFT JOIN ledger_entries l USING (txn_id) WHERE l.txn_id IS NULL),
        (SELECT COUNT(*) FROM ledger_entries l LEFT JOIN settlement_staging s USING (txn_id) WHERE s.txn_id IS NULL),
        (SELECT COUNT(*) FROM settlement_staging s JOIN ledger_entries l USING (txn_id)
          WHERE ABS(s.amount - l.amount) > 0.005)""")
    total = sum(breaks)
    out.append({"name": "Reconciliation", "status": "RED" if total else "GREEN",
                "detail": f"{total} breaks: {breaks[0]} missing in ledger, {breaks[1]} missing in settlement, "
                          f"{breaks[2]} amount mismatches"})
    return out


def write_dashboard(overall, sections, generated):
    def card(item):
        return (f'<div class="row"><span class="pill {item["status"].lower()}">{item["status"]}</span>'
                f'<div><div class="name">{html.escape(item["name"])}</div>'
                f'<div class="detail">{html.escape(item["detail"])}</div></div></div>')
    body = "".join(f"<h2>{html.escape(title)}</h2>" + "".join(card(i) for i in items) for title, items in sections)
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Payments Health Check</title>
<style>
:root {{ --bg:#f6f7f9; --card:#fff; --text:#1b1f24; --muted:#5b6472; --line:#e3e6ea;
        --red:#c62828; --amber:#b26a00; --green:#2e7d32; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#111418; --card:#1a1f25; --text:#e8eaed; --muted:#9aa3ad;
        --line:#2a3038; --red:#ef6b6b; --amber:#f0b35a; --green:#6cc070; }} }}
body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.5 system-ui, sans-serif; }}
main {{ max-width:760px; margin:0 auto; padding:24px 16px; }}
h1 {{ font-size:22px; margin:0 0 4px; }} h2 {{ font-size:14px; text-transform:uppercase; letter-spacing:.06em;
        color:var(--muted); margin:28px 0 8px; }}
.sub {{ color:var(--muted); font-size:13px; }}
.overall {{ display:inline-block; margin-top:12px; padding:6px 14px; border-radius:6px; font-weight:700;
        color:#fff; background:var(--{overall.lower()}); }}
.row {{ display:flex; gap:12px; align-items:flex-start; background:var(--card); border:1px solid var(--line);
        border-radius:8px; padding:12px; margin-bottom:8px; }}
.pill {{ flex:none; width:58px; text-align:center; font-size:12px; font-weight:700; border-radius:4px; padding:2px 0;
        border:1.5px solid currentColor; }}
.red {{ color:var(--red); }} .amber {{ color:var(--amber); }} .green {{ color:var(--green); }}
.name {{ font-weight:600; }} .detail {{ color:var(--muted); font-size:14px; }}
</style></head><body><main>
<h1>Payments platform health check</h1>
<div class="sub">Generated {generated} by toolkit/healthcheck.py</div>
<div class="overall">OVERALL: {overall}</div>
{body}
</main></body></html>
""")


def main():
    if not DB.exists():
        raise SystemExit("No database yet - run: python3 app/simulate.py")
    db = sqlite3.connect(DB)
    sections = [("Services", check_services()), ("Batch and data", check_data(db))]
    overall = max((i["status"] for _, items in sections for i in items), key=RANK.get)
    generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    colour = {"RED": "\033[31m", "AMBER": "\033[33m", "GREEN": "\033[32m"}
    for title, items in sections:
        print(f"\n{title}")
        for i in items:
            print(f"  {colour[i['status']]}{i['status']:<5}\033[0m  {i['name']:<20} {i['detail']}")
    print(f"\nOVERALL: {colour[overall]}{overall}\033[0m   (dashboard: {REPORT.relative_to(ROOT)})")
    write_dashboard(overall, sections, generated)
    sys.exit(RANK[overall])


if __name__ == "__main__":
    main()
