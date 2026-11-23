#!/usr/bin/env python3
"""Run SQL against the payments database and print readable tables.

    python3 toolkit/run_sql.py toolkit/sql/03_reconciliation.sql
    python3 toolkit/run_sql.py -q "SELECT status, COUNT(*) FROM payments GROUP BY status"

In a .sql file, the '-- ' comment lines directly above a statement are printed
as its heading. Uses Python's built-in sqlite3, so no client install is needed.
"""
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "payments.db"


def print_table(cur):
    if cur.description is None:
        return
    cols = [d[0] for d in cur.description]
    rows = [["" if v is None else (f"{v:,.2f}" if isinstance(v, float) else str(v)) for v in r] for r in cur.fetchall()]
    widths = [max(len(c), *(len(r[i]) for r in rows)) if rows else len(c) for i, c in enumerate(cols)]
    print("  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(v.ljust(w) for v, w in zip(r, widths)))
    print(f"({len(rows)} row{'s' if len(rows) != 1 else ''})\n")


def statements(text):
    """Yield (heading, sql) pairs from a script."""
    heading, buf = [], ""
    for line in text.splitlines():
        stripped = line.strip()
        if not buf.strip() and not stripped:
            heading = []  # a blank line ends a comment block that isn't a heading
            continue
        if not buf.strip() and stripped.startswith("--"):
            heading.append(stripped.lstrip("-").strip())
            continue
        buf += line + "\n"
        if sqlite3.complete_statement(buf):
            yield " ".join(h for h in heading if h), buf.strip()
            heading, buf = [], ""


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    if not DB.exists():
        raise SystemExit("No database yet - run: python3 app/simulate.py")
    text = sys.argv[2] if sys.argv[1] == "-q" else Path(sys.argv[1]).read_text()
    db = sqlite3.connect(DB)
    for heading, sql in statements(text if text.rstrip().endswith(";") else text + ";"):
        if heading:
            print(f"== {heading}")
        print_table(db.execute(sql))
    db.commit()


if __name__ == "__main__":
    main()
