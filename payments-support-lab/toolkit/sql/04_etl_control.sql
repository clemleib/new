-- ETL batch control: did last night's settlement load complete cleanly?

-- Batch status (expected rows come from the file trailer)
SELECT batch_id, file_name, status, expected_rows, loaded_rows, rejected_rows,
       expected_rows - loaded_rows - rejected_rows AS unaccounted_rows,
       started_at, finished_at
FROM batch_control
ORDER BY started_at DESC;

-- Staging vs trailer: loaded count and value per batch
SELECT batch_id, COUNT(*) AS staged_rows, ROUND(SUM(amount), 2) AS staged_value
FROM settlement_staging
GROUP BY batch_id;
