# Post-incident review: INC-20261123, ledger DB timeouts left 25 payments unposted

| | |
|---|---|
| **Severity** | P1 (client payments affected, value over threshold) |
| **Date** | 2026-11-23 (simulated) |
| **Duration** | 14:05 – 14:25 impact window; payments recovered after the fix |
| **Impact** | 25 payments, **120,658.13** total, 8 corporate clients, 4 currencies |
| **Services** | `ledger-posting` (failed); `payment-intake` and `payment-validation` healthy |
| **Format** | Blameless: focus on systems and controls, not people |

## Summary
From 14:05 to 14:25 the ledger database ran out of connections. `ledger-posting` retried each payment three times (30 seconds apart) and then gave up, leaving 25 validated payments unposted. Clients had been told the payments were accepted. The payments were re-posted under ticket INC0012345 once the database recovered, and the day's reconciliation was cleared.

## Timeline
| Time | Event | Source |
|---|---|---|
| 13:55:22 | First `slow response from ledger DB` warning (4,000 ms against a normal ~100 ms). 11 more follow. | `triage.sh` section 4 |
| 14:05 | Connection pool exhausted; retries begin | ledger-posting log |
| 14:06:52 | First posting failure (TXN000392) | `triage.sh` section 5 |
| 14:15 | Error peak: 9 failures in 5 minutes | `triage.sh` section 3 |
| 14:26:28 | Last posting failure (TXN000417); new payments posting normally again | ledger-posting log |
| next day | Stuck payments confirmed by SQL and reconciliation; dry run reviewed; re-post applied under the ticket; health check GREEN for stuck payments | `01_stuck_payments.sql`, `repost_stuck.py` |

## Root cause
The ledger database connection pool was exhausted. *In a real review, the 5 whys would continue here, for example: a long-running report query holding connections, a pool sized for average rather than peak load, or a missing statement timeout.*

## What went well
- Every service logs the same transaction ID, so one command traced any payment end to end.
- Payments failed *safely*: they stayed in `VALIDATED` rather than being lost or half-posted, so recovery was clean.
- The repair was idempotent and tied to a ticket, and a dry run was reviewed before it was applied.

## What went badly
- **Detection was late.** There was a 10-minute warning (slow responses from 13:55) but we only alert on errors.
- **Recovery was manual.** Nothing automatically re-tried the stuck payments once the database came back.
- The same day also had a duplicate-posting issue and an ETL load with rejects, which made the reconciliation harder to read. Several issues landing on one day is normal, so the triage needs to separate them quickly.

## Actions
| # | Action | Type | Owner | Due |
|---|---|---|---|---|
| 1 | Alert on ledger p95 latency above 1,000 ms for 3 minutes (catch the warning signs) | Detect | Support | +1 week |
| 2 | Alert on any payment in `VALIDATED` for more than 5 minutes | Detect | Support | +1 week |
| 3 | Size the connection pool for peak load; add a statement timeout for report queries | Prevent | DBA / development | +1 month |
| 4 | Automatic re-post queue, with a dead-letter queue after N attempts | Recover | Development | Next quarter |
| 5 | Add RB-01 to the on-call training for the junior analysts; run a drill using `simulate.py` | People | Support lead | +2 weeks |
