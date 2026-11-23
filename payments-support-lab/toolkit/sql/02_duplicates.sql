-- Duplicate payments: same client reference posted more than once.
-- client_ref is the client's own ID for a payment, so two POSTED payments with
-- the same client_ref, amount and currency mean the client was debited twice.

-- Duplicate groups, with the gap between the original and the resend
SELECT client_ref,
       client,
       currency,
       amount,
       COUNT(*)                                       AS times_posted,
       GROUP_CONCAT(txn_id, ', ')                     AS txn_ids,
       ROUND((julianday(MAX(received_at)) - julianday(MIN(received_at))) * 86400) AS seconds_apart
FROM payments
WHERE status = 'POSTED'
GROUP BY client_ref, amount, currency
HAVING COUNT(*) > 1
ORDER BY amount DESC;

-- Which copy to reverse: keep the first, reverse the rest (window function)
SELECT txn_id, client_ref, amount, currency, received_at,
       CASE WHEN rn = 1 THEN 'KEEP' ELSE 'REVERSE' END AS action
FROM (
    SELECT p.*,
           ROW_NUMBER() OVER (PARTITION BY client_ref, amount, currency ORDER BY received_at) AS rn,
           COUNT(*)     OVER (PARTITION BY client_ref, amount, currency)                     AS copies
    FROM payments p
    WHERE status = 'POSTED'
)
WHERE copies > 1
ORDER BY client_ref, received_at;

-- Exposure: total value posted twice
SELECT COUNT(*) AS duplicate_postings, ROUND(SUM(amount), 2) AS duplicated_value
FROM (
    SELECT amount,
           ROW_NUMBER() OVER (PARTITION BY client_ref, amount, currency ORDER BY received_at) AS rn
    FROM payments
    WHERE status = 'POSTED'
)
WHERE rn > 1;
