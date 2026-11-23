# RB-03 Settlement ETL completed with errors, failed, or file missing

**Severity guide:** P2 by default; P1 if the file is missing near the reconciliation cut-off.

## Symptoms
- Health check: **Settlement ETL AMBER** (`COMPLETED_WITH_ERRORS`) or **RED** (`FAILED` / no batch).
- `etl-settlement-load.log` shows `Row N rejected reason=...`.
- Reconciliation shows `MISSING_IN_SETTLEMENT` breaks, one for each rejected row.

## Triage
```bash
./toolkit/check_batch.sh                                   # arrival, header/trailer, load status, rejects
python3 toolkit/run_sql.py toolkit/sql/04_etl_control.sql  # expected vs loaded vs rejected
```

| Finding | Likely cause | Action |
|---|---|---|
| No file | Upstream late, or the file transfer job failed | Check the transfer job and scheduler; chase the payment network |
| Trailer missing | File truncated in transfer | Request a resend; **don't** load a partial file |
| Count ≠ trailer | Truncated, or rows dropped | Same as above |
| Row rejects (format) | Upstream data quality | Ask the sender for a corrected file, or repair under a ticket with approval |

## Resolution
1. Get a corrected file (preferred), or repair the specific rows with documented approval.
2. Re-run: `python3 app/etl_load.py data/inbound/<file>`. The load is **idempotent**: it deletes and reloads that batch, so a re-run never double-counts.
3. Confirm `COMPLETED`, and that the `MISSING_IN_SETTLEMENT` breaks have cleared.

## Prevent
- Agree a file specification and data-quality SLA with the sender; report reject rates to them weekly.
- Alert on `COMPLETED_WITH_ERRORS`, not just `FAILED`. A "green" job that dropped rows is the dangerous one.
