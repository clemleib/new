-- Stuck payments: validated but never posted to the ledger.
-- A payment should move VALIDATED -> POSTED within seconds; anything still
-- VALIDATED is money the client thinks has gone but our books don't show.

-- Summary: how many, how much, which currencies
SELECT currency,
       COUNT(*)              AS stuck_count,
       ROUND(SUM(amount), 2) AS stuck_value,
       MIN(received_at)      AS first_received,
       MAX(received_at)      AS last_received
FROM payments
WHERE status = 'VALIDATED'
GROUP BY currency
ORDER BY stuck_value DESC;

-- When it happened: stuck payments per 5-minute window (finds the outage window)
SELECT substr(received_at, 1, 15) || CAST(CAST(substr(received_at, 16, 1) AS INTEGER) / 5 * 5 AS TEXT) AS window_start,
       COUNT(*) AS stuck_count
FROM payments
WHERE status = 'VALIDATED'
GROUP BY window_start
ORDER BY window_start;

-- Which clients are affected (for the business update / client comms)
SELECT client,
       COUNT(*)              AS stuck_count,
       ROUND(SUM(amount), 2) AS stuck_value
FROM payments
WHERE status = 'VALIDATED'
GROUP BY client
ORDER BY stuck_value DESC;
