# RB-02 Duplicate payments posted

**Severity guide:** P1. Client money has moved twice. Treat it as a financial loss event and involve operations and risk early.

## Symptoms
- `payment-intake` log shows `Duplicate check skipped: idempotency cache unavailable`.
- Health check: **Duplicate postings RED**.
- A client calls about being debited twice.

## Triage
```bash
python3 toolkit/run_sql.py toolkit/sql/02_duplicates.sql   # groups, the copy to reverse, total exposure
grep -h "Duplicate check skipped" logs/*.log | head        # when the cache failed and how long for
```
Duplicates are found by **client_ref + amount + currency**. client_ref is the client's own unique reference. The query keeps the first copy and marks later copies to **REVERSE**.

## Resolution
1. **Contain.** Restore the idempotency cache. Until it is back, consider holding intake or switching to the database-backed duplicate check.
2. **Confirm with the business.** Some "duplicates" are genuine repeat payments (payroll, for example). Operations confirms the list before anything is reversed. Support never reverses client money on its own.
3. **Reverse** through the approved operations process, under a ticket, using the `REVERSE` list from the query.
4. **Recall if needed.** If the duplicate already left the bank, operations raises a recall with the receiving bank. This is time-sensitive.
5. **Notify** the affected clients through their relationship managers.

## Prevent
- Treat the duplicate check as a **control**. If it can't run, the service should *fail closed* (reject or queue) rather than skip it.
- Back it with a unique constraint on (client, client_ref) so a cache outage can't create duplicates.
- Alert on the `Duplicate check skipped` warning, not just on errors.
