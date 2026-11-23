# RB-04 Reconciliation breaks: settlement vs ledger

**Run daily** after the settlement load. Breaks must be explained and closed, or aged and escalated.

```bash
python3 toolkit/run_sql.py toolkit/sql/03_reconciliation.sql
```

| Break type | Meaning | Usual root cause | Owner and fix |
|---|---|---|---|
| `MISSING_IN_LEDGER` | Network settled it, we never posted it | Posting failure (see RB-01) | Support: re-post after the fix |
| `MISSING_IN_SETTLEMENT` | We posted it, it's not in the loaded file | ETL reject (see RB-03), or the network didn't settle it | Support with the sender: corrected file / investigate |
| `AMOUNT_MISMATCH` | Both sides have it, amounts differ | Posting logic defect (here: EUR cents truncated) | Development: code fix; operations: adjusting entries |

## Reading the result
- **Count and value both matter.** 3 amount mismatches worth 1.53 total look trivial, but a *systematic* rounding defect affects every EUR payment from now on. Raise a problem ticket for the root cause, not just an adjustment for today.
- **Pattern before fix.** Group by break type, currency, client and time window. A cluster in one window means an incident; a steady trickle means a defect.

## Escalation
Any break still open after one business day goes on the aged-breaks report to operations and the control function, with an owner and a target date.
