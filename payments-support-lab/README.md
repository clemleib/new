# Payments Support Lab

A production-support toolkit for a simulated payments platform. It covers what an application support lead does every day: **find incidents early, diagnose them with SQL, shell and Python, fix them safely, and explain the business impact.**

The platform has three Python microservices (intake → validation → ledger), a SQL database and a nightly ETL job that loads the payment network's settlement file. Faults are injected on purpose (database timeouts, duplicate postings, a bad batch file, a rounding bug) so there are real problems to support.

No installs: Python 3.8+ (standard library only) and bash. It runs on macOS or Linux.

## Five-minute demo

```bash
python3 app/simulate.py                       # 1. run a business day, with faults
python3 toolkit/healthcheck.py                # 2. what is broken? (RED / AMBER / GREEN; also writes reports/dashboard.html)
./toolkit/triage.sh                           # 3. which service, when, what error, any warning signs?
./toolkit/trace_txn.sh TXN000405              # 4. follow one payment across every service and table
python3 toolkit/run_sql.py toolkit/sql/01_stuck_payments.sql   # 5. blast radius: count, value, clients
python3 toolkit/repost_stuck.py               # 6. dry-run fix ...
python3 toolkit/repost_stuck.py --apply --ticket INC0012345    #    ... then apply it under a ticket
python3 toolkit/healthcheck.py                # 7. prove the fix
```

`python3 app/simulate.py --faults none` gives a clean day (all GREEN). You can also pick faults: `--faults ledger_timeout,bad_file`.

## What's in it

| Path | What it does | Skill it shows |
|---|---|---|
| `app/simulate.py` | Runs a business day through 3 services; writes logs, DB and the settlement file | Microservices, structured logging, correlation IDs |
| `app/etl_load.py` | Nightly load: header/trailer checks, row validation, rejects file, batch control table, safe to re-run | ETL controls |
| `toolkit/triage.sh` | Errors by service, top errors, 5-minute error histogram, warning signs before the first error | Unix: grep, sed, awk, sort, uniq |
| `toolkit/trace_txn.sh` | One payment's full trail across logs and tables (input validated) | Troubleshooting |
| `toolkit/check_batch.sh` | File arrival, integrity, load status, rejects | Batch support |
| `toolkit/sql/` | Stuck payments, duplicates (window functions), 3-way reconciliation, ETL control, index tuning | SQL |
| `toolkit/healthcheck.py` | RAG health of services and data, HTML dashboard, exit codes for monitoring | Python, monitoring |
| `toolkit/repost_stuck.py` | Repair script: dry run by default, needs a ticket, safe to run twice, single transaction, audit log | Safe production changes |
| `runbooks/` | Runbooks for each failure: symptoms, impact, triage, fix, escalation, comms | Mentoring, operational maturity |
| `postmortem/` | Blameless post-incident review with timeline and actions | Incident leadership |

## The injected faults

| Fault | What happens | How it's caught | Runbook |
|---|---|---|---|
| `ledger_timeout` | Ledger DB connection pool exhausted 14:05–14:25; 25 payments stuck | triage, health check, SQL 01, recon | RB-01 |
| `duplicates` | Idempotency cache down; 5 client resends posted twice | WARN in intake log, SQL 02 | RB-02 |
| `bad_file` | 4 malformed rows in the settlement file | check_batch, SQL 04, recon | RB-03 |
| `amount_mismatch` | EUR cents truncated on posting | recon (SQL 03) | RB-04 |
