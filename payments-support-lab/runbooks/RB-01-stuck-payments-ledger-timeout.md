# RB-01 Stuck payments: ledger-posting timeouts

**Severity guide:** P1 if payments are stuck and the count is still rising; P2 if the outage is over and only recovery is left.

## Symptoms
- `ledger-posting` log shows `DB connection pool exhausted` warnings, then `Posting failed: DB connection timeout`.
- Health check: **Stuck payments RED**. Reconciliation shows `MISSING_IN_LEDGER` breaks.
- Clients or operations report payments that were "accepted" but don't appear on statements.

## Business impact
Clients have been told a payment went through, but our books don't show it. Balances are wrong, and if this runs into the end-of-day cut-off, the payments miss their value date. Funding and liquidity reporting are wrong until it's fixed.

## Triage (first 10 minutes)
```bash
./toolkit/triage.sh                                    # confirm: which service, when it started, is it still happening?
python3 toolkit/run_sql.py toolkit/sql/01_stuck_payments.sql   # how many, how much, which clients
./toolkit/trace_txn.sh <TXN_ID>                        # confirm one example end to end
```
Questions to answer:
1. **Is it still happening?** Compare the last error time with now.
2. **What is the blast radius?** Count, value, clients and currencies.
3. **What changed?** Recent deployments, DB maintenance, traffic spikes. Slow responses *before* the errors point to resource exhaustion, not a code bug.

## Resolution
1. **Stop the bleeding.** Work with the DBA or platform team to restore the ledger DB (kill blocking sessions, restart or resize the connection pool). If it can't be restored quickly, pause intake so payments aren't accepted and left stuck.
2. **Confirm recovery.** New payments post normally and `triage.sh` shows no new errors.
3. **Recover stuck payments:**
   ```bash
   python3 toolkit/repost_stuck.py                              # dry run, review the list
   python3 toolkit/repost_stuck.py --apply --ticket INC0012345  # needs business approval for a P1
   ```
4. **Verify.** Run `python3 toolkit/healthcheck.py`: stuck payments GREEN, no `MISSING_IN_LEDGER` breaks.

## Escalation
- 15 minutes with no fix → escalate to the ledger DB / platform L3 team and open a bridge call.
- Value over the agreed threshold, or the end-of-day cut-off at risk → tell the business and payments operations heads.

## Comms template
> **[P1] Payments not posting to ledger: UPDATE hh:mm**
> **Impact:** N payments (value X) accepted between 14:05 and 14:25 are not posted. Clients affected: …
> **Status:** Root cause is ledger DB connection exhaustion. DB restored at hh:mm; new payments are posting normally.
> **Next:** Re-posting the stuck payments under INC…, ETA hh:mm. Next update in 30 minutes.
