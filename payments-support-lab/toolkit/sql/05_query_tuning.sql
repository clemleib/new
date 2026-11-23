-- Query tuning: the ops team's "find payment by client reference" screen is slow.
-- Compare the query plan before and after adding an index.

-- Reset so the demo can be re-run
DROP INDEX IF EXISTS idx_payments_client_ref;

-- BEFORE: full table scan (SCAN payments) - cost grows with every row in the table
EXPLAIN QUERY PLAN
SELECT txn_id, status, amount FROM payments WHERE client_ref = 'NWL-123456';

-- Fix: index the column the screen filters on
CREATE INDEX idx_payments_client_ref ON payments (client_ref);

-- AFTER: index lookup (SEARCH payments USING INDEX ...) - reads only matching rows
EXPLAIN QUERY PLAN
SELECT txn_id, status, amount FROM payments WHERE client_ref = 'NWL-123456';

-- Talking point: indexes speed reads but slow writes and take space, so in production
-- check write volume, test in UAT, and deploy through change management.
