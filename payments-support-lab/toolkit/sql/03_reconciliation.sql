-- Reconciliation: payment network settlement file vs our ledger.
-- Three kinds of break:
--   MISSING_IN_LEDGER      network settled it, we never posted it  (stuck payments)
--   MISSING_IN_SETTLEMENT  we posted it, it isn't in the loaded file (ETL rejects)
--   AMOUNT_MISMATCH        both have it, amounts differ             (posting bug)

-- Break summary
WITH breaks AS (
    SELECT s.txn_id, 'MISSING_IN_LEDGER' AS break_type, s.amount AS settlement_amount, NULL AS ledger_amount
    FROM settlement_staging s
    LEFT JOIN ledger_entries l ON l.txn_id = s.txn_id
    WHERE l.txn_id IS NULL
    UNION ALL
    SELECT l.txn_id, 'MISSING_IN_SETTLEMENT', NULL, l.amount
    FROM ledger_entries l
    LEFT JOIN settlement_staging s ON s.txn_id = l.txn_id
    WHERE s.txn_id IS NULL
    UNION ALL
    SELECT s.txn_id, 'AMOUNT_MISMATCH', s.amount, l.amount
    FROM settlement_staging s
    JOIN ledger_entries l ON l.txn_id = s.txn_id
    WHERE ABS(s.amount - l.amount) > 0.005
)
SELECT break_type,
       COUNT(*) AS breaks,
       ROUND(SUM(ABS(COALESCE(settlement_amount, 0) - COALESCE(ledger_amount, 0))), 2) AS value_at_risk
FROM breaks
GROUP BY break_type
ORDER BY value_at_risk DESC;

-- Break detail (what goes into the break report for operations)
WITH breaks AS (
    SELECT s.txn_id, 'MISSING_IN_LEDGER' AS break_type, s.amount AS settlement_amount, NULL AS ledger_amount
    FROM settlement_staging s
    LEFT JOIN ledger_entries l ON l.txn_id = s.txn_id
    WHERE l.txn_id IS NULL
    UNION ALL
    SELECT l.txn_id, 'MISSING_IN_SETTLEMENT', NULL, l.amount
    FROM ledger_entries l
    LEFT JOIN settlement_staging s ON s.txn_id = l.txn_id
    WHERE s.txn_id IS NULL
    UNION ALL
    SELECT s.txn_id, 'AMOUNT_MISMATCH', s.amount, l.amount
    FROM settlement_staging s
    JOIN ledger_entries l ON l.txn_id = s.txn_id
    WHERE ABS(s.amount - l.amount) > 0.005
)
SELECT b.break_type, b.txn_id, p.client, p.currency,
       b.settlement_amount, b.ledger_amount, p.status AS payment_status
FROM breaks b
JOIN payments p ON p.txn_id = b.txn_id
ORDER BY b.break_type, b.txn_id;
